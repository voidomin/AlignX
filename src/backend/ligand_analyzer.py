import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import numpy as np
import pandas as pd

from src.backend.interaction_geometry import classify_contact
from src.backend.pdb_manager import parse_structure_file
from src.utils.logger import sanitize_for_log

logger = logging.getLogger(__name__)

RCSB_CHEMCOMP_BASE_URL = "https://data.rcsb.org/rest/v1/core/chemcomp"

# Ligand/HETATM codes are always alnum (occasionally with a trailing digit
# for numbered variants) - this allowlist keeps the RCSB request path safe
# regardless of caller, same defense-in-depth pattern validation_service.py
# uses for pdb_id.
_SAFE_LIGAND_CODE = re.compile(r"^[A-Za-z0-9]+$")


class LigandAnalyzer:
    """
    Analyzes ligand-protein interactions in PDB structures.
    Identifies ligands (HETATM) and finds interacting residues.
    """

    def __init__(self, config: Dict[str, Any] = None, cache_db: Optional[Any] = None):
        """
        Initialize the LigandAnalyzer.

        Args:
            config: Optional configuration dictionary
            cache_db: Optional HistoryDatabase-like object (duck-typed via
                get_annotation_cache/set_annotation_cache, same pattern
                AnnotationAggregator already uses) for caching ligand
                chemistry lookups - static data, so worth persisting
                across requests/users the same way GO-term names are.
        """
        self.config = config or {}
        self.cache_db = cache_db
        self.cache_ttl_days = (
            (config or {}).get("annotation", {}).get("cache_ttl_days", 30)
        )
        # Water, crystallization buffer/cryoprotectant components, and
        # non-catalytic monatomic ions - none of these are ever biologically
        # meaningful ligands, so they're excluded outright. Catalytic/
        # structural metal cofactors (MG, CA, ZN, MN, FE, CU, NI, CO, CD, MO)
        # are deliberately NOT in this set (v3.87.0 fix) - a zinc-finger's
        # Zn, a kinase's Mg, or a heme's Fe is exactly the kind of ligand a
        # structural biologist would want interaction analysis for, so they
        # now pass through as real ligands instead of being silently dropped
        # alongside solvent noise. classify_contact() (interaction_geometry.py)
        # gives them their own "Metal Coordination" contact type.
        self.ignored_residues = {
            "HOH",
            "WAT",
            "TIP",
            "SOL",  # Water
            "NA",
            "CL",
            "K",  # Non-catalytic monatomic ions
            "SO4",
            "PO4",
            "ACT",
            "EDO",
            "GOL",
            "DMS",  # Common crystallization additives
        }

    def get_ligands(self, pdb_file: Path) -> List[Dict[str, Any]]:
        """
        Identify potential ligands in a PDB file.

        Args:
            pdb_file: Path to the PDB file

        Returns:
            List of dictionaries containing ligand info (name, id, location)
        """
        pdb_file = Path(pdb_file)
        if not pdb_file.exists():
            logger.error(f"PDB file not found: {pdb_file}")
            return []

        try:
            structure = parse_structure_file(pdb_file)
        except Exception:
            logger.exception(f"Failed to parse {pdb_file}")
            return []

        # Model 0 only - a multi-model (NMR ensemble) file would otherwise
        # return the same ligand once per model (duplicated N times), which
        # doesn't match calculate_sasa()/_pocket_sasa() below, both of which
        # already only ever look at structure[0]. See PDBManager.analyze_
        # structure()'s is_nmr flag for surfacing that an ensemble exists.
        ligands = [
            ligand_info
            for chain in structure[0]
            for ligand_info in (
                self._ligand_info_from_residue(residue, chain) for residue in chain
            )
            if ligand_info is not None
        ]

        logger.info(f"Found {len(ligands)} ligands in {pdb_file.name}")
        return ligands

    def _ligand_info_from_residue(self, residue, chain) -> Optional[Dict[str, Any]]:
        """Builds a ligand-info dict for one residue if it's a HETATM that
        isn't water/a common ion/crystallization additive, else None.
        BioPython uses keys like ('H_NAG', 123, ' ') for HETATMs - standard
        residues have an empty first element in the tuple id."""
        hetfield, resseq, _ = residue.get_id()
        if hetfield == " ":
            return None

        resname = residue.get_resname().strip()
        if resname in self.ignored_residues:
            return None

        coords = [atom.get_coord() for atom in residue]
        center = np.mean(coords, axis=0).tolist() if coords else [0, 0, 0]

        return {
            "name": resname,
            "id": f"{resname}_{chain.get_id()}_{resseq}",
            "chain": chain.get_id(),
            "resi": resseq,
            "full_id": residue.get_full_id(),
            "center": center,
            "atom_count": len(residue),
        }

    def calculate_interactions(
        self, pdb_file: Path, ligand_id: str, cutoff: float = 5.0
    ) -> Dict[str, Any]:
        """
        Find residues interacting with a specific ligand.

        Args:
            pdb_file: Path to PDB file
            ligand_id: Unique ID of the ligand (Name_Chain_Resi)
            cutoff: Distance cutoff in Angstroms (default 5.0)

        Returns:
            Dictionary with interaction details
        """
        from Bio.PDB import NeighborSearch

        try:
            structure = parse_structure_file(Path(pdb_file))
        except Exception as e:
            return {"error": str(e)}

        # Find the specific ligand residue
        target_ligand = None
        target_atoms = []

        # Parse ligand_id to find it (Format: RESNAME_CHAIN_RESI)
        # Verify format matches get_ligands output
        try:
            parts = ligand_id.split("_")
            # Handle cases where resname might have underscores (rare but possible)
            # Assuming standard 3 parts: Name, Chain, Resi
            l_chain = parts[-2]
            l_resi = int(parts[-1])
            l_name = "_".join(parts[:-2])
        except (ValueError, IndexError):
            logger.error(f"Invalid ligand ID format: {sanitize_for_log(ligand_id)}")
            return {"error": "Invalid ID"}

        target_ligand, target_atoms, search_atoms = self._find_ligand_and_search_atoms(
            structure, l_chain, l_resi, l_name
        )
        if not target_ligand:
            return {"error": f"Ligand {ligand_id} not found in structure"}

        # Perform Neighbor Search
        ns = NeighborSearch(search_atoms)
        interacting_residues = set()
        for atom in target_atoms:
            interacting_residues.update(ns.search(atom.get_coord(), cutoff, level="R"))

        results = {
            "ligand": ligand_id,
            "interactions": [
                self._interaction_record(res, target_atoms)
                for res in interacting_residues
            ],
            "pocket_sasa": self._pocket_sasa(structure, interacting_residues),
        }
        results["interactions"].sort(key=lambda x: x["distance"])
        return results

    @staticmethod
    def _pocket_sasa(structure, pocket_residues) -> float:
        """Sums per-residue SASA (BioPython's ShrakeRupley, computed once on
        the already-parsed structure) over just the pocket-lining residues -
        how much surface those residues retain while still part of the full
        bound complex, not their SASA in isolation."""
        from Bio.PDB.SASA import ShrakeRupley

        ShrakeRupley().compute(structure[0], level="R")
        return round(
            sum(getattr(res, "sasa", 0.0) or 0.0 for res in pocket_residues), 2
        )

    @staticmethod
    def _find_ligand_and_search_atoms(
        structure, l_chain: str, l_resi: int, l_name: str
    ):
        """Locates the target ligand residue and separates the rest of the
        structure's standard-residue atoms into a NeighborSearch candidate
        pool (excludes solvent/ions, id[0] != " ", from being "interacting
        partners"). Model 0 only, consistent with get_ligands()/
        calculate_sasa() - a multi-model NMR file would otherwise pool
        atoms from every model into one neighbor search, mixing conformers
        together instead of analyzing a single consistent one."""
        target_ligand = None
        target_atoms = []
        search_atoms = []
        for chain in structure[0]:
            for residue in chain:
                is_target = (
                    chain.get_id() == l_chain
                    and residue.get_id()[1] == l_resi
                    and residue.get_resname().strip() == l_name
                )
                if is_target:
                    target_ligand = residue
                    target_atoms = list(residue.get_atoms())
                elif residue.get_id()[0] == " ":
                    search_atoms.extend(residue.get_atoms())
        return target_ligand, target_atoms, search_atoms

    @staticmethod
    def _min_distance(target_atoms, res_atoms) -> float:
        return min((la - ra for la in target_atoms for ra in res_atoms), default=999.9)

    def _interaction_record(self, res, target_atoms) -> Dict[str, Any]:
        resname = res.get_resname()
        res_atoms = list(res.get_atoms())
        return {
            "residue": resname,
            "resn": resname,
            "chain": res.get_parent().get_id(),
            "resi": res.get_id()[1],
            "distance": round(self._min_distance(target_atoms, res_atoms), 2),
            "type": classify_contact(resname, res_atoms, target_atoms),
        }

    def calculate_sasa(self, pdb_file: Path) -> Dict[str, Any]:
        """
        Calculate Solvent Accessible Surface Area (SASA) for a PDB structure.

        Uses BioPython's ShrakeRupley algorithm to compute per-residue and
        total SASA values.

        Args:
            pdb_file: Path to the PDB file.

        Returns:
            Dictionary with total SASA, per-chain SASA, and per-residue breakdown.
        """
        from Bio.PDB.SASA import ShrakeRupley

        pdb_file = Path(pdb_file)

        try:
            structure = parse_structure_file(pdb_file)
        except Exception as e:
            logger.exception(f"SASA: Failed to parse {pdb_file}")
            return {"error": str(e)}

        # Compute SASA using ShrakeRupley
        sr = ShrakeRupley()
        sr.compute(structure[0], level="R")  # Compute at residue level

        total_sasa = 0.0
        chain_sasa: Dict[str, float] = {}
        residue_data: List[Dict[str, Any]] = []

        for chain in structure[0]:
            chain_id = chain.get_id()
            chain_total = 0.0

            for residue in chain:
                # Skip water and non-standard residues
                if residue.get_id()[0] != " ":
                    continue

                res_sasa = residue.sasa if hasattr(residue, "sasa") else 0.0
                chain_total += res_sasa

                residue_data.append(
                    {
                        "chain": chain_id,
                        "residue": residue.get_resname().strip(),
                        "resi": residue.get_id()[1],
                        "sasa": round(res_sasa, 2),
                    }
                )

            chain_sasa[chain_id] = round(chain_total, 2)
            total_sasa += chain_total

        logger.info(f"SASA computed for {pdb_file.name}: {total_sasa:.1f} Å²")

        return {
            "total_sasa": round(total_sasa, 2),
            "chain_sasa": chain_sasa,
            "residues": residue_data,
        }

    # Real binding pockets are commonly hydrophobic/aromatic-enriched - a
    # simple, defensible secondary signal for ranking candidate clusters,
    # separate from HYDROPHOBIC_RESIDUES in interaction_geometry.py (that
    # set serves a different purpose - H-bond/salt-bridge classification -
    # and deliberately excludes aromatic-but-polar TYR).
    _POCKET_LINING_RESIDUES = {
        "ALA",
        "VAL",
        "LEU",
        "ILE",
        "MET",
        "PHE",
        "TRP",
        "PRO",
        "TYR",
        "CYS",
    }
    _SURFACE_SASA_THRESHOLD = 15.0
    _POCKET_CLUSTER_RADIUS = 10.0
    _POCKET_SEQUENCE_GAP = 5
    _MIN_CLUSTER_NEIGHBORS = 3

    def find_candidate_pockets(
        self, pdb_file: Path, top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """Heuristic candidate binding-pocket finder for a ligand-free
        structure (e.g. most AlphaFold/ESM Atlas Discover-mode queries,
        which essentially never have a co-crystallized ligand). This is
        NOT a validated geometric cavity detector (fpocket-equivalent) -
        re-implementing that algorithm is out of scope here. Instead it
        proxies "pocket-like" with two real, defensible signals: surface-
        exposed residues (real per-residue SASA, reusing the same
        ShrakeRupley computation as calculate_sasa()) that cluster
        spatially with residues from a distant part of the sequence (the
        standard signature of a fold packing together to form a concave
        wall, not just an alpha helix's own adjacent turns), ranked by
        cluster size plus hydrophobic/aromatic content (pockets are
        commonly enriched in both). Every result is explicitly labeled
        "heuristic": True - a computational prediction, not an
        experimentally validated pocket.
        """
        from Bio.PDB import NeighborSearch
        from Bio.PDB.SASA import ShrakeRupley

        pdb_file = Path(pdb_file)
        try:
            structure = parse_structure_file(pdb_file)
        except Exception:
            logger.exception(f"Pocket detection: failed to parse {pdb_file}")
            return []

        model = structure[0]
        ShrakeRupley().compute(model, level="R")

        surface_residues = [
            residue
            for chain in model
            for residue in chain
            if residue.get_id()[0] == " "
            and "CA" in residue
            and (getattr(residue, "sasa", 0.0) or 0.0) >= self._SURFACE_SASA_THRESHOLD
        ]
        if not surface_residues:
            return []

        ns = NeighborSearch([r["CA"] for r in surface_residues])

        candidates = []
        for residue in surface_residues:
            neighbors = ns.search(
                residue["CA"].get_coord(), self._POCKET_CLUSTER_RADIUS, level="R"
            )
            distant_neighbors = [
                n
                for n in neighbors
                if n is not residue
                and n.get_parent().get_id() == residue.get_parent().get_id()
                and abs(n.get_id()[1] - residue.get_id()[1]) > self._POCKET_SEQUENCE_GAP
            ]
            if len(distant_neighbors) < self._MIN_CLUSTER_NEIGHBORS:
                continue

            cluster = [residue] + distant_neighbors
            hydrophobic_count = sum(
                1
                for r in cluster
                if r.get_resname().strip() in self._POCKET_LINING_RESIDUES
            )
            score = len(distant_neighbors) + hydrophobic_count
            center = np.mean([r["CA"].get_coord() for r in cluster], axis=0).tolist()
            candidates.append({"residues": cluster, "score": score, "center": center})

        # Greedily keep the highest-scoring clusters that don't share a
        # residue with an already-selected one, so top_n candidates read as
        # distinct pockets rather than N near-duplicates of the same site.
        candidates.sort(key=lambda c: c["score"], reverse=True)
        selected = []
        used = set()
        for candidate in candidates:
            keys = {
                (r.get_parent().get_id(), r.get_id()[1]) for r in candidate["residues"]
            }
            if keys & used:
                continue
            used |= keys
            selected.append(candidate)
            if len(selected) >= top_n:
                break

        return [
            {
                "rank": i + 1,
                "residues": [
                    {
                        "chain": r.get_parent().get_id(),
                        "resi": r.get_id()[1],
                        "resn": r.get_resname().strip(),
                    }
                    for r in c["residues"]
                ],
                "center": c["center"],
                "score": round(c["score"], 2),
                "volume_estimate_a3": self._cluster_convex_hull_volume(c["residues"]),
                "heuristic": True,
            }
            for i, c in enumerate(selected)
        ]

    @staticmethod
    def _cluster_convex_hull_volume(residues: list) -> Optional[float]:
        """Convex-hull volume (Angstrom^3) over a pocket candidate's own CA
        coordinates - a rough size signal, not a validated cavity volume: a
        convex hull always over-estimates a true concave binding cavity
        (which is exactly what makes it a pocket rather than a bump), and
        this app has no real geometric cavity detector (fpocket-equivalent)
        to compare against. Returns None if the cluster is too small or too
        close to coplanar for scipy to construct a hull from (needs >=4
        non-coplanar points in 3D)."""
        from scipy.spatial import ConvexHull
        from scipy.spatial import QhullError

        coords = np.array([r["CA"].get_coord() for r in residues])
        if len(coords) < 4:
            return None
        try:
            return round(float(ConvexHull(coords).volume), 1)
        except QhullError:
            return None

    def calculate_interaction_similarity(
        self, all_interactions: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Calculate pairwise similarity of ligand interaction fingerprints (Jaccard Index).

        Args:
            all_interactions: List of interaction dictionaries (output of calculate_interactions)

        Returns:
            pd.DataFrame: Symmetric similarity matrix
        """

        if not all_interactions:
            return pd.DataFrame()

        # Extract signatures: Set of (ResidueName, Resi) tuples for each ligand
        # Note: We rely on alignment, so we ideally compare "Aligned Residue IDs".
        # But for now, we assume the inputs are from aligned structures where residue numbering might align
        # OR we're just comparing "types" of interactions.
        # BETTER: Use the "Position" if we had the alignment mapping.
        # FALLBACK: Just use ResidueName + ResidueNumber and assume conservation?
        # Actually, without MSA integration here, we can't perfectly map Residue 10 in A to Residue 12 in B.
        # So we'll limit this to: "Comparing ligands within the SAME PDB" OR just generic residue composition similarity.

        # WAIT! The user wants to compare active sites.
        # If we don't have the MSA mapping here, strict residue-to-residue comparison is flawed across different proteins.
        # However, for a "similarity matrix" of *types* of interactions (e.g. "Both hit a Histidine"), we can do that.
        # OR better: The user likely wants to see if the binding pockets look similar.

        # Let's pivot: We will calculate similarity based on Residue Composition of the pocket.
        # e.g. Pocket A has {HIS, ASP, GLU}, Pocket B has {HIS, ASP, ALA}. Jaccard = 2/4 = 0.5.

        # 1. Build Fingerprints (Counts of residue types) -- No, just set of types is too simple.
        # Let's use: Set of "ResidueType_InteractionType" strings.

        ligand_ids = [item["ligand"] for item in all_interactions]
        n = len(ligand_ids)
        matrix = np.zeros((n, n))

        fingerprints = []
        for item in all_interactions:
            # Create a set of "ResName" strings found in the pocket
            # This measures "Is the chemical environment similar?"
            fp = {res["residue"] for res in item["interactions"]}
            fingerprints.append(fp)

        for i in range(n):
            for j in range(n):
                matrix[i][j] = (
                    1.0
                    if i == j
                    else self._jaccard_score(fingerprints[i], fingerprints[j])
                )

        return pd.DataFrame(matrix, index=ligand_ids, columns=ligand_ids)

    @staticmethod
    def _jaccard_score(set_i: set, set_j: set) -> float:
        """Jaccard index of two residue-composition fingerprints; 0.0 (not
        1.0) when both pockets are empty, since "no interactions" isn't a
        meaningful similarity claim."""
        if not set_i and not set_j:
            return 0.0
        union = len(set_i | set_j)
        return len(set_i & set_j) / union if union > 0 else 0.0

    async def fetch_ligand_chemistry(
        self, ligand_code: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """
        Resolves a 3-letter ligand/HETATM code (e.g. "HEM", "STI") to real
        chemistry - name, formula, SMILES - via RCSB's Chemical Component
        Dictionary. Until now this app only ever showed the bare 3-letter
        code with no context ("what is ligand STI?" was a dead end).
        Cached the same way GO-term names already are (this data is
        static, so re-looking it up per request/user is wasteful) via the
        same duck-typed cache_db this constructor now accepts.

        Returns None on any failure (not found, network error, unexpected
        shape, or an unsafe code) - never raises.
        """
        if not _SAFE_LIGAND_CODE.match(ligand_code or ""):
            logger.warning(
                f"Rejected unsafe ligand_code: {sanitize_for_log(ligand_code)!r}"
            )
            return None

        cache_key = f"chemcomp:{ligand_code.upper()}"
        if self.cache_db:
            try:
                cached = self.cache_db.get_annotation_cache(
                    cache_key, self.cache_ttl_days
                )
                if cached is not None:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(
                    f"Ligand chemistry cache read failed for "
                    f"{sanitize_for_log(ligand_code)}: {e}"
                )

        result = await self._fetch_ligand_chemistry_live(ligand_code, client)

        if self.cache_db:
            try:
                self.cache_db.set_annotation_cache(
                    cache_key, "chemcomp", json.dumps(result)
                )
            except Exception as e:
                logger.warning(
                    f"Ligand chemistry cache write failed for "
                    f"{sanitize_for_log(ligand_code)}: {e}"
                )

        return result

    @staticmethod
    async def _fetch_ligand_chemistry_live(
        ligand_code: str, client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        safe_code = quote(ligand_code.upper(), safe="")
        try:
            response = await client.get(
                f"{RCSB_CHEMCOMP_BASE_URL}/{safe_code}",
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200:
                return None

            data = response.json()
            chem = data.get("chem_comp") or {}
            descriptor = data.get("rcsb_chem_comp_descriptor") or {}
            if not chem.get("name") and not chem.get("formula"):
                return None

            return {
                "id": ligand_code.upper(),
                "name": chem.get("name"),
                "formula": chem.get("formula"),
                "formula_weight": chem.get("formula_weight"),
                "smiles": descriptor.get("SMILES"),
                "inchi_key": descriptor.get("InChIKey"),
            }
        except httpx.HTTPError as e:
            logger.warning(
                f"Ligand chemistry lookup failed for "
                f"{sanitize_for_log(ligand_code)}: {e}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Failed to parse ligand chemistry response for "
                f"{sanitize_for_log(ligand_code)}: {e}"
            )
            return None
