"""PDB file management: download, validation, and preprocessing."""

import httpx
import asyncio
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from src.utils.logger import get_logger
from src.utils.cache_manager import CacheManager

logger = get_logger()

# Only alnum/underscore/hyphen - blocks path traversal ("..", "/", "\\") if
# session_id is ever concatenated into a filesystem path. FastAPI's own
# endpoints already validate session_id (see api.py's _safe_segment())
# before it reaches here, via every current call path - this is a second,
# independent check so PDBManager doesn't quietly depend on every future
# caller remembering to pre-validate a value that's attacker-controlled at
# the API layer (it's a query parameter).
_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _write_bytes(path: Path, content: bytes) -> None:
    """Plain synchronous write - only ever called via asyncio.to_thread()
    from async code, never awaited directly."""
    with open(path, "wb") as f:
        f.write(content)


# Common non-standard residues clean_pdb() maps to their standard equivalent.
_RESIDUE_NAME_MAPPING = {
    "HYP": "PRO",
    "MSE": "MET",
    "CSD": "ALA",
    "CAS": "CYS",
    "KCX": "LYS",
    "LLP": "LYS",
    "CME": "CYS",
    "MLY": "LYS",
}


class _CleanSelect:
    """clean_pdb()'s residue/atom filtering, as a real class taking its
    parameters via __init__ instead of a nested class closing over the
    method's locals - lets it (and clean_pdb() itself) be reasoned about
    independently. Duck-types Bio.PDB.Select's accept_model/accept_chain/
    accept_residue/accept_atom contract (PDBIO.save() just calls these,
    with no isinstance check) rather than subclassing it, so this module
    doesn't need a top-level Bio.PDB import."""

    def __init__(
        self,
        is_plddt_model: bool,
        plddt_scale: float,
        remove_water: bool,
        remove_heteroatoms: bool,
    ):
        self.is_plddt_model = is_plddt_model
        self.plddt_scale = plddt_scale
        self.remove_water = remove_water
        self.remove_heteroatoms = remove_heteroatoms

    @staticmethod
    def accept_model(model) -> int:
        return 1

    @staticmethod
    def accept_chain(chain) -> int:
        return 1

    def _below_plddt_threshold(self, residue) -> bool:
        try:
            # Bio.PDB residues don't have a single B-factor, we check the first atom (usually N or CA)
            atoms = list(residue.get_atoms())
            return bool(atoms) and (atoms[0].bfactor * self.plddt_scale) < 50
        except (AttributeError, IndexError):
            return False

    def accept_residue(self, residue) -> int:
        # Remove water
        if self.remove_water and (residue.id[0] == "W" or residue.resname == "HOH"):
            return 0

        # pLDDT Pruning (Strip disordered regions < 50 if it's a predicted model)
        if self.is_plddt_model and self._below_plddt_threshold(residue):
            return 0

        # Keep standard residues
        if residue.id[0] == " ":
            return 1

        # For non-standard residues (HETATM), keep them if they have a CA atom
        if residue.has_id("CA"):
            return 1

        return 0 if self.remove_heteroatoms else 1

    @staticmethod
    def accept_atom(atom) -> int:
        # Exclude hydrogens (mustang often crashes on them)
        if atom.element == "H" or atom.name.startswith("H"):
            return 0
        return 1


class PDBManager:
    """Manages PDB file downloads, validation, and preprocessing."""

    def __init__(
        self,
        config: Dict[str, Any],
        cache_manager: Optional[CacheManager] = None,
        session_id: Optional[str] = None,
    ):
        """
        Initialize PDB Manager.

        Args:
            config: Configuration dictionary
            cache_manager: Optional CacheManager instance
            session_id: Optional session ID for per-user file isolation

        Raises:
            ValueError: if session_id is provided but isn't a safe path
                segment (see _SAFE_SESSION_ID above).
        """
        if session_id is not None and not _SAFE_SESSION_ID.match(session_id):
            raise ValueError(f"Invalid session_id: {session_id!r}")

        self.config = config
        self.cache_manager = cache_manager
        self.session_id = session_id
        self.pdb_source = config.get("pdb", {}).get(
            "source_url", "https://files.rcsb.org/download/"
        )
        self.timeout = config.get("pdb", {}).get("timeout", 60)
        self.max_size_mb = config.get("pdb", {}).get("max_file_size_mb", 500)

        # Namespace directories by session ID if provided
        if session_id:
            self.raw_dir = Path("data/raw") / session_id
            self.cleaned_dir = Path("data/cleaned") / session_id
        else:
            self.raw_dir = Path("data/raw")
            self.cleaned_dir = Path("data/cleaned")

        # Create directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def detect_source(pdb_id: str) -> str:
        """
        Identify which structure database an ID belongs to, based on its
        prefix: "AF-" -> AlphaFold, "SM-" -> SWISS-MODEL, "ESM-" -> ESM
        Metagenomic Atlas, otherwise a standard RCSB PDB ID.
        """
        upper = pdb_id.strip().upper()
        if upper.startswith("AF-"):
            return "alphafold"
        if upper.startswith("SM-"):
            return "swissmodel"
        if upper.startswith("ESM-"):
            return "esmfold"
        return "pdb"

    @staticmethod
    def validate_pdb_id(pdb_id: str) -> bool:
        """
        Validate PDB ID format.
        Supports standard 4-char PDB IDs, AlphaFold IDs (AF-UniProt-F1),
        SWISS-MODEL IDs (SM-UniProt), and ESM Atlas IDs (ESM-MGYPxxxx).
        """
        pdb_id = pdb_id.strip().upper()
        # Standard PDB ID
        if re.match(r"^\d[A-Z0-9]{3}$", pdb_id):
            return True
        # AlphaFold ID (Supports AF-UniProt-F[Fragment] and optional -v[Version])
        if re.match(r"^AF-[A-Z0-9]+-F\d+(-V\d+)?$", pdb_id):
            return True
        # SWISS-MODEL ID (SM-UniProt)
        if re.match(r"^SM-[A-Z0-9]+$", pdb_id):
            return True
        # ESM Metagenomic Atlas ID (ESM-MGYPxxxxxxxxxx)
        if re.match(r"^ESM-MGYP\d+$", pdb_id):
            return True
        return False

    def save_uploaded_file(
        self, uploaded_file: Any
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Save an uploaded file to the raw directory.

        Args:
            uploaded_file: Streamlit UploadedFile object

        Returns:
            Tuple of (success, message, file_path)
        """
        try:
            # Clean filename
            name = Path(uploaded_file.name).stem
            # Replace spaces with underscores
            name = re.sub(r"\s+", "_", name)

            output_file = self.raw_dir / f"{name}.pdb"

            with open(output_file, "wb") as f:
                f.write(uploaded_file.getbuffer())

            logger.info(f"Saved uploaded file: {output_file}")
            return True, "Saved uploaded file", output_file
        except Exception as e:
            logger.exception("Failed to save upload")
            return False, str(e), None

    def save_uploaded_bytes(
        self, original_filename: str, content: bytes, structure_id: str
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Save and validate an SPA-uploaded structure (see POST /api/upload).

        Unlike save_uploaded_file() (Streamlit's UploadedFile-shaped input),
        this takes plain bytes and a pre-generated synthetic ID
        ("UPLOAD-{random}"), and actually validates the content parses as a
        real structure with at least one chain - a .pdb-named text file that
        isn't a structure should fail clearly here, not reach Mustang later
        and produce a confusing downstream error.

        The saved filename's extension is picked from original_filename (not
        forced to .pdb) so mmCIF uploads still get parsed with MMCIFParser -
        see _get_structure(). download_pdb()'s cache-hit check knows to look
        for either extension for IDs it doesn't recognize a source for.
        """
        size_mb = len(content) / (1024 * 1024)
        if size_mb > self.max_size_mb:
            return (
                False,
                f"File too large ({size_mb:.1f} MB, limit is {self.max_size_mb} MB)",
                None,
            )

        ext = ".cif" if original_filename.lower().endswith(".cif") else ".pdb"
        output_file = self.raw_dir / f"{structure_id.lower()}{ext}"

        try:
            _write_bytes(output_file, content)
        except OSError as e:
            return False, f"Failed to save upload: {e}", None

        try:
            structure = self._get_structure(output_file)
            chain_count = sum(1 for model in structure for _chain in model)
            if chain_count == 0:
                raise ValueError("no chains found")
        except Exception as e:
            output_file.unlink(missing_ok=True)
            return (
                False,
                f"Couldn't parse '{original_filename}' as a structure: {e}",
                None,
            )

        logger.info(f"Saved and validated uploaded structure: {output_file}")
        return True, "ok", output_file

    async def _fetch_alphafold_response(
        self, pdb_id: str, client: httpx.AsyncClient, manage_client: bool
    ) -> Tuple[bool, str, Optional[httpx.Response]]:
        # AlphaFold DB URL support
        parts = pdb_id.upper().split("-")
        uniprot_id = parts[1]
        fragment = parts[2] if len(parts) > 2 else "F1"

        # Use v6 as new default standard, but allow explicit versioning
        version_hint = "6"
        has_explicit_version = False
        if len(parts) > 3 and parts[3].startswith("V"):
            version_hint = parts[3].replace("V", "")
            has_explicit_version = True

        # Versions to attempt if not found
        versions_to_try = (
            [version_hint] if has_explicit_version else ["6", "4", "5", "3", "2", "1"]
        )

        try:
            success = False
            last_response = None

            for v in versions_to_try:
                url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-{fragment}-model_v{v}.cif"
                logger.info(f"Attempting AlphaFold download (v{v}): {url}")
                response = await client.get(url, follow_redirects=True)

                if response.status_code == 200:
                    success = True
                    last_response = response
                    break
                else:
                    logger.debug(
                        f"AlphaFold v{v} not found (Status {response.status_code})"
                    )

            if not success:
                logger.error(f"All AlphaFold download attempts for {pdb_id} failed.")
                if manage_client:
                    await client.aclose()
                return (
                    False,
                    f"Not found in AlphaFold DB (Tried versions {', '.join(versions_to_try)})",
                    None,
                )

            return True, "ok", last_response

        except httpx.TimeoutException:
            logger.error(f"Timeout while downloading {pdb_id}")
            return False, "Download failed: Connection timeout", None
        except Exception as e:
            logger.exception("AlphaFold download crash")
            return False, f"Error: {str(e)}", None

    async def _fetch_swissmodel_response(
        self, pdb_id: str, client: httpx.AsyncClient, manage_client: bool
    ) -> Tuple[bool, str, Optional[httpx.Response]]:
        # SWISS-MODEL Repository (homology models, keyed by UniProt ID)
        uniprot_id = pdb_id.upper().split("-", 1)[1]
        url = f"https://swissmodel.expasy.org/repository/uniprot/{uniprot_id}.pdb"
        try:
            logger.info(f"Attempting SWISS-MODEL download: {url}")
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                logger.error(
                    f"SWISS-MODEL download for {pdb_id} failed with status {response.status_code}"
                )
                if manage_client:
                    await client.aclose()
                return (
                    False,
                    f"Not found in SWISS-MODEL Repository (Status {response.status_code})",
                    None,
                )
            return True, "ok", response
        except Exception as e:
            return False, f"SWISS-MODEL download failed: {e}", None

    async def _fetch_esmfold_response(
        self, pdb_id: str, client: httpx.AsyncClient, manage_client: bool
    ) -> Tuple[bool, str, Optional[httpx.Response]]:
        # ESM Metagenomic Atlas (predictions for MGnify metagenomic sequences)
        mgyp_id = pdb_id.upper().split("-", 1)[1]
        url = f"https://api.esmatlas.com/fetchPredictedStructure/{mgyp_id}"
        try:
            logger.info(f"Attempting ESM Atlas download: {url}")
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                logger.error(
                    f"ESM Atlas download for {pdb_id} failed with status {response.status_code}"
                )
                if manage_client:
                    await client.aclose()
                return (
                    False,
                    f"Not found in ESM Metagenomic Atlas (Status {response.status_code})",
                    None,
                )
            return True, "ok", response
        except Exception as e:
            return False, f"ESM Atlas download failed: {e}", None

    async def _fetch_pdb_response(
        self, pdb_id: str, client: httpx.AsyncClient, manage_client: bool
    ) -> Tuple[bool, str, Optional[httpx.Response]]:
        """`pdb_id` is expected already-uppercased by the caller - matches
        the original branch's own `pdb_id = pdb_id.upper()`, which also
        affected the outer function's later cache-registration/log-message
        pdb_id, so that reassignment stays at the call site."""
        url = f"{self.pdb_source}{pdb_id}.pdb"
        try:
            logger.info(f"Attempting PDB download from: {url}")
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                logger.error(
                    f"Download for {pdb_id} failed with status code {response.status_code}"
                )
                if manage_client:
                    await client.aclose()
                return False, f"Download failed (Status {response.status_code})", None
            return True, "ok", response
        except Exception as e:
            return False, f"PDB Download failed: {e}", None

    async def download_pdb(
        self,
        pdb_id: str,
        force: bool = False,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Download a structural file from RCSB PDB, AlphaFold DB, SWISS-MODEL
        Repository, or the ESM Metagenomic Atlas (Asynchronous), based on the
        ID's prefix (see detect_source()).
        """
        pdb_id = pdb_id.strip()
        source = self.detect_source(pdb_id)
        ext = ".cif" if source == "alphafold" else ".pdb"

        # Use lower-case filenames internally to avoid WSL case-sensitivity issues
        safe_id = pdb_id.lower()
        output_file = self.raw_dir / f"{safe_id}{ext}"

        if not output_file.exists():
            # detect_source() doesn't recognize an uploaded ID's "UPLOAD-"
            # prefix, so ext defaults to .pdb above - but save_uploaded_bytes()
            # saves with whichever extension actually matches the upload's
            # real format. Check for that before assuming this ID needs to
            # be fetched from a remote source it was never downloaded from.
            alt_ext = ".pdb" if ext == ".cif" else ".cif"
            alt_file = self.raw_dir / f"{safe_id}{alt_ext}"
            if alt_file.exists():
                output_file = alt_file

        if output_file.exists() and not force:
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            if self.cache_manager:
                self.cache_manager.update_access(pdb_id)
            return True, f"Using local file ({file_size_mb:.2f} MB)", output_file

        if not self.validate_pdb_id(pdb_id):
            return False, f"Invalid ID format: {pdb_id}", None

        manage_client = client is None
        if manage_client:
            client = httpx.AsyncClient(timeout=self.timeout)

        if source == "alphafold":
            success, msg, response = await self._fetch_alphafold_response(
                pdb_id, client, manage_client
            )
        elif source == "swissmodel":
            success, msg, response = await self._fetch_swissmodel_response(
                pdb_id, client, manage_client
            )
        elif source == "esmfold":
            success, msg, response = await self._fetch_esmfold_response(
                pdb_id, client, manage_client
            )
        else:
            # Standard PDB
            pdb_id = pdb_id.upper()
            success, msg, response = await self._fetch_pdb_response(
                pdb_id, client, manage_client
            )

        if not success:
            return False, msg, None

        # 3. SAVE FILE (Unified for PDB/AF)
        try:
            # Check file size
            file_size = len(response.content)
            file_size_mb = file_size / (1024 * 1024)

            # Synchronous file I/O blocks the whole event loop for its
            # duration - to_thread offloads it to a worker thread, same
            # pattern already used for other blocking work in this
            # codebase (e.g. api.py's Mustang/Foldseek pipeline calls).
            await asyncio.to_thread(_write_bytes, output_file, response.content)

            if manage_client:
                await client.aclose()

            if self.cache_manager:
                self.cache_manager.register_item(pdb_id, output_file)

            logger.info(f"Downloaded {pdb_id} successfully ({file_size_mb:.2f} MB)")
            return True, f"Downloaded ({file_size_mb:.2f} MB)", output_file

        except Exception as e:
            logger.exception(f"Failed to save {pdb_id}")
            return False, f"Save failed: {str(e)}", None

    async def batch_download(
        self, pdb_ids: List[str]
    ) -> Dict[str, Tuple[bool, str, Optional[Path]]]:
        """
        Download multiple PDB files in parallel using AsyncIO.
        """
        results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [self.download_pdb(pdb_id, client=client) for pdb_id in pdb_ids]
            download_responses = await asyncio.gather(*tasks)

            for pdb_id, res in zip(pdb_ids, download_responses):
                results[pdb_id] = res

        return results

    def _get_structure(self, file_path: Path) -> Any:
        """Hybrid parser for PDB and mmCIF formats."""
        from Bio.PDB import MMCIFParser, PDBParser

        if file_path.suffix.lower() == ".cif":
            parser = MMCIFParser(QUIET=True)
        else:
            parser = PDBParser(QUIET=True)
        return parser.get_structure("protein", str(file_path))

    def analyze_structure(self, pdb_file: Path) -> Dict:
        """
        Analyze structural file and return information.
        """
        structure = self._get_structure(pdb_file)

        chains = []
        total_residues = 0

        for model in structure:
            for chain in model:
                chain_id = chain.id
                residues = list(chain.get_residues())
                chains.append({"id": chain_id, "residue_count": len(residues)})
                total_residues += len(residues)

        file_size_mb = pdb_file.stat().st_size / (1024 * 1024)

        return {
            "file_size_mb": file_size_mb,
            "chains": chains,
            "total_residues": total_residues,
            "num_models": len(structure),
        }

    @staticmethod
    def _detect_plddt_scale(structure, is_plddt_model: bool) -> float:
        """AlphaFold writes pLDDT on a 0-100 scale, but ESM Atlas structures
        write it as a 0-1 fraction instead. Detect which convention this
        file actually uses (rather than assuming AlphaFold's) so the same
        "< 50" threshold means the same thing either way - without this,
        every residue of a 0-1-scale structure gets stripped (0.96 < 50 is
        always true), leaving zero CA atoms and silently failing the whole
        structure."""
        if not is_plddt_model:
            return 1.0
        try:
            max_bfactor = max(
                (atom.bfactor for atom in structure.get_atoms()), default=0.0
            )
            return 100.0 if max_bfactor <= 1.5 else 1.0
        except Exception:
            return 1.0

    @staticmethod
    def _find_target_chain(model, chain: Optional[str]):
        for ch in model:
            if chain is None or ch.id == chain:
                return ch
        return None

    @staticmethod
    def _build_clean_residue(residue, clean_select: "_CleanSelect", res_count: int):
        """A new sanitized Bio.PDB Residue (renumbered, standard ATOM
        record, non-hydrogen atoms only, common non-standard residue names
        mapped to their standard equivalent), or None if `clean_select`
        rejected the residue entirely or every one of its atoms was a
        hydrogen `accept_atom` stripped."""
        from Bio import PDB

        if not clean_select.accept_residue(residue):
            return None

        res_name = residue.resname.strip()
        std_res_name = _RESIDUE_NAME_MAPPING.get(res_name, res_name)
        new_res = PDB.Residue.Residue((" ", res_count, " "), std_res_name, " ")

        atoms_added = 0
        for atom in residue:
            if not clean_select.accept_atom(atom):
                continue
            new_res.add(
                PDB.Atom.Atom(
                    atom.name,
                    atom.coord,
                    atom.occupancy,
                    atom.bfactor,
                    atom.altloc,
                    atom.get_fullname(),  # Fix: fullname must be string
                    atom.serial_number,
                    element=atom.element,
                )
            )
            atoms_added += 1

        return new_res if atoms_added > 0 else None

    def clean_pdb(
        self,
        pdb_file: Path,
        chain: Optional[str] = None,
        remove_heteroatoms: bool = True,
        remove_water: bool = True,
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Clean structural file (PDB/CIF) and sanitize into standard PDB.
        """
        try:
            from Bio import PDB
            from Bio.PDB import PDBIO

            structure = self._get_structure(pdb_file)

            # AlphaFold and ESMFold both encode per-residue pLDDT confidence
            # in the B-factor column; SWISS-MODEL homology models don't, so
            # they're excluded from this pruning heuristic.
            is_plddt_model = pdb_file.name.lower().startswith(("af-", "esm-"))
            plddt_scale = self._detect_plddt_scale(structure, is_plddt_model)
            clean_select = _CleanSelect(
                is_plddt_model, plddt_scale, remove_water, remove_heteroatoms
            )

            # Extract model 0
            model = structure[0]

            # Create a New sanitized structure
            new_structure = PDB.Structure.Structure(structure.id)
            new_model = PDB.Model.Model(0)
            new_structure.add(new_model)

            target_chain_obj = self._find_target_chain(model, chain)
            if not target_chain_obj:
                return False, f"Chain {chain} not found", None

            new_chain = PDB.Chain.Chain(target_chain_obj.id)
            new_model.add(new_chain)

            res_count = 1
            for residue in target_chain_obj:
                new_res = self._build_clean_residue(residue, clean_select, res_count)
                if new_res is not None:
                    new_chain.add(new_res)
                    res_count += 1

            # Check if there are any Alpha Carbons (required by Mustang)
            ca_atoms = sum(1 for atom in new_chain.get_atoms() if atom.name == "CA")
            if ca_atoms == 0:
                chain_desc = (
                    f"Chain {target_chain_obj.id}" if chain else "The selected chain"
                )
                return (
                    False,
                    f"{chain_desc} contains 0 Alpha Carbon (CA) atoms. Mustang only aligns protein structures (DNA, RNA, and small molecules are unsupported).",
                    None,
                )

            # Save cleaned structure with LF line endings
            # Force .pdb extension for Mustang compatibility and normalize to lowercase
            clean_name = pdb_file.stem.lower()
            output_file = self.cleaned_dir / f"{clean_name}.pdb"
            with open(str(output_file), "w", newline="\n") as f:
                io = PDBIO()
                io.set_structure(new_structure)
                io.save(f)

            # Get size reduction
            original_size = pdb_file.stat().st_size / (1024 * 1024)
            cleaned_size = output_file.stat().st_size / (1024 * 1024)

            logger.info(
                f"Cleaned {pdb_file.name}: {original_size:.2f}MB -> {cleaned_size:.2f}MB (lowercase: {clean_name}.pdb)"
            )

            return True, "Cleaning and sanitization successful", output_file

        except Exception as e:
            logger.exception(f"Failed to clean {pdb_file.name}")
            return False, f"Cleaning failed: {str(e)}", None

    def build_residue_renumber_map(
        self,
        pdb_file: Path,
        chain: Optional[str] = None,
        remove_heteroatoms: bool = True,
        remove_water: bool = True,
    ) -> Dict[int, int]:
        """
        Map original residue numbers to the 1-based sequential numbers
        clean_pdb() assigns, without writing a file.

        Ligand/interaction analysis runs against the raw downloaded PDB
        (original numbering), but the 3D viewer displays Mustang's aligned
        output, which is built from a cleaned copy with every chain
        renumbered from 1 (and ligands typically stripped). This lets
        callers translate a raw residue number into the number the aligned
        structure actually uses. Reuses `_CleanSelect.accept_residue` - the
        exact same predicate clean_pdb() uses to decide what survives -
        instead of a second, hand-duplicated copy that could drift out of
        sync with it.
        """
        try:
            structure = self._get_structure(pdb_file)
        except Exception:
            logger.exception(f"Failed to parse {pdb_file.name} for renumbering")
            return {}

        is_plddt_model = pdb_file.name.lower().startswith(("af-", "esm-"))
        plddt_scale = self._detect_plddt_scale(structure, is_plddt_model)
        clean_select = _CleanSelect(
            is_plddt_model, plddt_scale, remove_water, remove_heteroatoms
        )

        target_chain_obj = self._find_target_chain(structure[0], chain)
        if not target_chain_obj:
            return {}

        mapping: Dict[int, int] = {}
        res_count = 1
        for residue in target_chain_obj:
            if not clean_select.accept_residue(residue):
                continue
            mapping[residue.id[1]] = res_count
            res_count += 1

        return mapping

    def batch_clean(
        self, pdb_files: List[Path], max_workers: int = 4
    ) -> Dict[str, Tuple[bool, str, Optional[Path]]]:
        """
        Clean multiple PDB files in parallel.

        Args:
            pdb_files: List of PDB file paths
            max_workers: Number of parallel workers

        Returns:
            Dictionary mapping PDB filename to (success, message, path)
        """
        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(self.clean_pdb, p): p for p in pdb_files}

            with tqdm(total=len(pdb_files), desc="Cleaning PDB files") as pbar:
                for future in as_completed(list(future_to_file.keys())):
                    pdb_file = future_to_file[future]
                    try:
                        results[pdb_file.name] = future.result()
                    except Exception as e:
                        logger.exception(f"Error cleaning {pdb_file.name}")
                        results[pdb_file.name] = (False, f"Error: {str(e)}", None)
                    pbar.update(1)

        return results

    @staticmethod
    def _empty_metadata() -> Dict[str, str]:
        return {"title": "N/A", "method": "N/A", "resolution": "N/A", "organism": "N/A"}

    @staticmethod
    def _classify_pdb_ids(
        pdb_ids: List[str],
    ) -> Tuple[Dict[str, str], List[str], List[str], List[str], List[str]]:
        """Splits a mixed batch of PDB/AlphaFold/SWISS-MODEL/ESM Atlas IDs
        into their per-source id lists, deduplicated, plus a mapping from
        each original (as-passed) id to the base id its metadata is keyed
        under - multiple original IDs can share one base id (e.g. two chain
        variants of the same PDB entry)."""
        original_to_base: Dict[str, str] = {}
        unique_base_ids, af_ids, sm_ids, esm_ids = [], [], [], []

        for pid in pdb_ids:
            # Preserve original casing in mapping keys
            clean_id = pid.strip().upper()
            if clean_id.startswith("AF-"):
                af_ids.append(clean_id)
                original_to_base[pid] = clean_id
            elif clean_id.startswith("SM-"):
                sm_ids.append(clean_id)
                original_to_base[pid] = clean_id
            elif clean_id.startswith("ESM-"):
                esm_ids.append(clean_id)
                original_to_base[pid] = clean_id
            else:
                base_id = clean_id[:4]
                unique_base_ids.append(base_id)
                original_to_base[pid] = base_id

        return (
            original_to_base,
            list(set(unique_base_ids)),
            list(set(af_ids)),
            list(set(sm_ids)),
            list(set(esm_ids)),
        )

    @staticmethod
    async def _fetch_uniprot_name_organism(
        client: httpx.AsyncClient, uniprot_id: str, fallback_name: str
    ) -> Tuple[str, str]:
        """Best-effort UniProt lookup for a protein's name and organism,
        shared by the AlphaFold and SWISS-MODEL metadata fetchers below
        (both are keyed by UniProt accession)."""
        try:
            up_url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
            up_resp = await client.get(up_url, timeout=10)
            if up_resp.status_code != 200:
                logger.warning(
                    f"UniProt API returned {up_resp.status_code} for {uniprot_id}"
                )
                return fallback_name, "N/A"

            up_data = up_resp.json()
            desc = up_data.get("proteinDescription", {})

            name = None
            name_sources = [
                desc.get("recommendedName"),
                desc.get("submissionNames", [{}])[0],
                desc.get("alternativeNames", [{}])[0],
            ]
            for source in name_sources:
                if source and isinstance(source, dict):
                    name = source.get("fullName", {}).get("value")
                    if name:
                        break

            if not name:
                genes = up_data.get("genes", [{}])
                name = genes[0].get("geneName", {}).get("value", fallback_name)

            organism = up_data.get("organism", {}).get("scientificName", "N/A")
            return name, organism
        except Exception as e:
            logger.warning(
                f"Failed to fetch UniProt meta for {uniprot_id}: ({type(e).__name__}) {e}"
            )
            return fallback_name, "N/A"

    @staticmethod
    async def _fetch_rcsb_metadata(
        client: httpx.AsyncClient, unique_base_ids: List[str]
    ) -> Dict[str, Dict[str, str]]:
        if not unique_base_ids:
            return {}

        query = """
        query($ids: [String!]!) {
          entries(entry_ids: $ids) {
            rcsb_id
            struct { title }
            exptl { method }
            rcsb_entry_info { resolution_combined }
            polymer_entities {
              rcsb_entity_source_organism { scientific_name }
            }
          }
        }
        """
        url = "https://data.rcsb.org/graphql"
        payload = {"query": query, "variables": {"ids": unique_base_ids}}
        logger.info(f"Fetching metadata for {len(unique_base_ids)} PDB entries")
        response = await client.post(url, json=payload)
        if response.status_code != 200:
            return {}

        data = response.json()
        entries = (data.get("data") or {}).get("entries") or []
        results = {}
        for entry in entries:
            bid = entry.get("rcsb_id")
            if not bid:
                continue
            results[bid] = PDBManager._parse_rcsb_entry(entry)
        return results

    @staticmethod
    def _parse_rcsb_entry(entry: Dict[str, Any]) -> Dict[str, str]:
        struct = entry.get("struct") or {}
        exptl_list = entry.get("exptl") or []
        res_list = (entry.get("rcsb_entry_info") or {}).get("resolution_combined") or []

        organism = "N/A"
        for entity in entry.get("polymer_entities") or []:
            sources = entity.get("rcsb_entity_source_organism") or []
            if sources:
                organism = sources[0].get("scientific_name", "N/A")
                break

        return {
            "title": struct.get("title", "N/A"),
            "method": exptl_list[0].get("method", "N/A") if exptl_list else "N/A",
            "resolution": f"{res_list[0]:.2f} \u00c5" if res_list else "N/A",
            "organism": organism,
        }

    async def _fetch_alphafold_metadata(
        self, client: httpx.AsyncClient, af_ids: List[str]
    ) -> Dict[str, Dict[str, str]]:
        results = {}
        for af_id in af_ids:
            # Extract UniProt ID (AF-P12345-F1 -> P12345)
            parts = af_id.split("-")
            if len(parts) < 2:
                continue
            name, organism = await self._fetch_uniprot_name_organism(
                client, parts[1], "AF Model"
            )
            results[af_id] = {
                "title": f"[AlphaFold] {name}",
                "method": "Predicted (AF2)",
                "resolution": "pLDDT Scored",
                "organism": organism,
            }
        return results

    @staticmethod
    async def _fetch_swissmodel_repository_info(
        client: httpx.AsyncClient, up_id: str, sm_id: str
    ) -> Tuple[str, str]:
        """(method, resolution) from SWISS-MODEL's own repository API -
        it aggregates both true homology models and experimental PDB
        structures already covering that UniProt entry, so "method"
        reflects which one this actually is."""
        method, resolution = "Homology model", "N/A"
        try:
            sm_url = f"https://swissmodel.expasy.org/repository/uniprot/{up_id}.json"
            sm_resp = await client.get(sm_url, timeout=10)
            if sm_resp.status_code == 200:
                sm_data = sm_resp.json()
                models = (sm_data.get("result") or {}).get("structures") or []
                if models:
                    model = models[0]
                    method = model.get("method") or method
                    template = model.get("template")
                    coverage = model.get("coverage")
                    if template:
                        resolution = f"Template {template}" + (
                            f" ({coverage * 100:.0f}% cov.)"
                            if isinstance(coverage, (int, float))
                            else ""
                        )
        except Exception as e:
            logger.warning(
                f"Failed to fetch SWISS-MODEL meta for {sm_id}: ({type(e).__name__}) {e}"
            )
        return method, resolution

    async def _fetch_swissmodel_metadata(
        self, client: httpx.AsyncClient, sm_ids: List[str]
    ) -> Dict[str, Dict[str, str]]:
        results = {}
        for sm_id in sm_ids:
            up_id = sm_id.split("-", 1)[1]
            name, organism = await self._fetch_uniprot_name_organism(
                client, up_id, "SWISS-MODEL"
            )
            method, resolution = await self._fetch_swissmodel_repository_info(
                client, up_id, sm_id
            )
            results[sm_id] = {
                "title": f"[SWISS-MODEL] {name}",
                "method": method,
                "resolution": resolution,
                "organism": organism,
            }
        return results

    @staticmethod
    def _esm_metadata(esm_ids: List[str]) -> Dict[str, Dict[str, str]]:
        # No per-structure metadata API exists for these anonymous
        # metagenomic predictions - fields are fixed.
        return {
            esm_id: {
                "title": f"[ESMFold] {esm_id.split('-', 1)[1]}",
                "method": "Predicted (ESMFold)",
                "resolution": "pLDDT Scored",
                "organism": "Metagenomic (unclassified)",
            }
            for esm_id in esm_ids
        }

    def _remap_metadata_to_original_ids(
        self, original_to_base: Dict[str, str], base_results: Dict[str, Dict[str, str]]
    ) -> Dict[str, Dict[str, str]]:
        final_results = {}
        for orig_id, b_id in original_to_base.items():
            # Try uppercase match first, then exact
            meta = base_results.get(b_id) or base_results.get(b_id.upper())
            final_results[orig_id] = meta or self._empty_metadata()
        return final_results

    async def fetch_metadata(
        self, pdb_ids: List[str], client: Optional[httpx.AsyncClient] = None
    ) -> Dict[str, Dict]:
        """
        Fetch metadata for multiple PDB IDs from RCSB GraphQL API (Asynchronous).
        """
        if not pdb_ids:
            return {}

        original_to_base, unique_base_ids, af_ids, sm_ids, esm_ids = (
            self._classify_pdb_ids(pdb_ids)
        )
        base_results = {
            bid: self._empty_metadata()
            for bid in (unique_base_ids + af_ids + sm_ids + esm_ids)
        }

        try:
            manage_client = client is None
            if manage_client:
                client = httpx.AsyncClient(timeout=15)

            base_results.update(
                await self._fetch_rcsb_metadata(client, unique_base_ids)
            )
            base_results.update(await self._fetch_alphafold_metadata(client, af_ids))
            base_results.update(await self._fetch_swissmodel_metadata(client, sm_ids))
            base_results.update(self._esm_metadata(esm_ids))

            if manage_client:
                await client.aclose()

            return self._remap_metadata_to_original_ids(original_to_base, base_results)

        except Exception:
            logger.exception("Metadata fetch critical failure")
            # Fallback for all IDs to prevent UI crash
            return {pid: self._empty_metadata() for pid in pdb_ids}
