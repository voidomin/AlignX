import logging
import warnings
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd

from src.backend.interaction_geometry import classify_contact
from src.utils.logger import sanitize_for_log

logger = logging.getLogger(__name__)


class LigandAnalyzer:
    """
    Analyzes ligand-protein interactions in PDB structures.
    Identifies ligands (HETATM) and finds interacting residues.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the LigandAnalyzer.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        # Common ions and solvents to ignore by default
        self.ignored_residues = {
            "HOH",
            "WAT",
            "TIP",
            "SOL",  # Water
            "NA",
            "CL",
            "K",
            "MG",
            "CA",
            "ZN",
            "MN",
            "FE",  # Common Ions
            "SO4",
            "PO4",
            "ACT",
            "EDO",
            "GOL",  # Common crystallization additives
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

        from Bio.PDB import PDBParser
        from Bio.PDB.PDBExceptions import PDBConstructionWarning

        parser = PDBParser(QUIET=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", PDBConstructionWarning)
                structure = parser.get_structure("struct", str(pdb_file))
        except Exception:
            logger.exception(f"Failed to parse {pdb_file}")
            return []

        ligands = [
            ligand_info
            for model in structure
            for chain in model
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
        from Bio.PDB import PDBParser, NeighborSearch
        from Bio.PDB.PDBExceptions import PDBConstructionWarning

        parser = PDBParser(QUIET=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", PDBConstructionWarning)
                structure = parser.get_structure("struct", str(pdb_file))
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
        partners")."""
        target_ligand = None
        target_atoms = []
        search_atoms = []
        for model in structure:
            for chain in model:
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
        from Bio.PDB import PDBParser
        from Bio.PDB.PDBExceptions import PDBConstructionWarning
        from Bio.PDB.SASA import ShrakeRupley

        pdb_file = Path(pdb_file)
        parser = PDBParser(QUIET=True)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", PDBConstructionWarning)
                structure = parser.get_structure("struct", str(pdb_file))
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
