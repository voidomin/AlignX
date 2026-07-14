import copy
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List

from src.backend.interaction_geometry import classify_contact
from src.backend.pdb_manager import parse_structure_file
from src.utils.logger import sanitize_for_log

logger = logging.getLogger(__name__)


class InterfaceAnalyzer:
    """Finds contact residues between two chains of the same (raw,
    pre-cleaning) structure - e.g. a protein-protein complex's interface -
    and estimates the buried surface area of that interface. Operates on
    the raw downloaded structure directly, the same file LigandAnalyzer
    already reads for ligand/interaction analysis, independent of Mustang's
    single-chain-per-structure alignment pipeline."""

    def calculate_interface(
        self, pdb_file: Path, chain_a: str, chain_b: str, cutoff: float = 5.0
    ) -> Dict[str, Any]:
        if chain_a == chain_b:
            return {"error": "chain_a and chain_b must be different chains"}

        from Bio.PDB import NeighborSearch
        from Bio.PDB.PDBExceptions import PDBConstructionWarning

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", PDBConstructionWarning)
                structure = parse_structure_file(Path(pdb_file))
        except Exception as e:
            return {"error": str(e)}

        model = structure[0]
        chain_a_obj = next((c for c in model if c.get_id() == chain_a), None)
        chain_b_obj = next((c for c in model if c.get_id() == chain_b), None)
        if chain_a_obj is None:
            logger.error(
                f"Interface analysis: chain {sanitize_for_log(chain_a)} not found"
            )
            return {"error": f"Chain {chain_a} not found in structure"}
        if chain_b_obj is None:
            logger.error(
                f"Interface analysis: chain {sanitize_for_log(chain_b)} not found"
            )
            return {"error": f"Chain {chain_b} not found in structure"}

        chain_a_atoms = self._standard_residue_atoms(chain_a_obj)
        chain_b_atoms = self._standard_residue_atoms(chain_b_obj)
        if not chain_a_atoms or not chain_b_atoms:
            return {"error": "One or both chains have no standard residues to analyze"}

        ns_a = NeighborSearch(chain_a_atoms)
        ns_b = NeighborSearch(chain_b_atoms)

        a_side_residues = set()
        for atom in chain_b_atoms:
            a_side_residues.update(ns_a.search(atom.get_coord(), cutoff, level="R"))

        b_side_residues = set()
        for atom in chain_a_atoms:
            b_side_residues.update(ns_b.search(atom.get_coord(), cutoff, level="R"))

        return {
            "chain_a": chain_a,
            "chain_b": chain_b,
            "chain_a_contacts": self._contact_records(a_side_residues, chain_b_atoms),
            "chain_b_contacts": self._contact_records(b_side_residues, chain_a_atoms),
            "buried_area": self._buried_interface_area(chain_a_obj, chain_b_obj),
        }

    @staticmethod
    def _standard_residue_atoms(chain) -> List:
        return [atom for res in chain if res.get_id()[0] == " " for atom in res]

    @staticmethod
    def _min_distance(atoms_a, atoms_b) -> float:
        return min((a - b for a in atoms_a for b in atoms_b), default=999.9)

    def _contact_records(self, residues, target_atoms) -> List[Dict[str, Any]]:
        records = []
        for res in residues:
            resname = res.get_resname()
            res_atoms = list(res.get_atoms())
            records.append(
                {
                    "residue": resname,
                    "resn": resname,
                    "chain": res.get_parent().get_id(),
                    "resi": res.get_id()[1],
                    "distance": round(self._min_distance(res_atoms, target_atoms), 2),
                    "type": classify_contact(resname, res_atoms, target_atoms),
                }
            )
        records.sort(key=lambda x: x["distance"])
        return records

    @staticmethod
    def _chain_sasa(chain) -> float:
        """SASA of one chain computed in isolation (as if the other chain
        weren't present) - Bio.PDB's ShrakeRupley only considers atoms
        within the entity it's given, so passing a lone Chain object
        naturally excludes every other chain in the structure."""
        from Bio.PDB.SASA import ShrakeRupley

        ShrakeRupley().compute(chain, level="A")
        return sum(atom.sasa for atom in chain.get_atoms())

    def _buried_interface_area(self, chain_a_obj, chain_b_obj) -> float:
        """Standard total buried-surface-area (BSA) convention:
        SASA(A alone) + SASA(B alone) - SASA(A+B complex). The complex is
        computed on deep copies of just these two chains (not the original
        objects, whose parent links stay attached to the real structure) so
        a structure with more than 2 chains isn't polluted by chain C/D."""
        from Bio.PDB.Model import Model
        from Bio.PDB.SASA import ShrakeRupley

        sasa_a_alone = self._chain_sasa(chain_a_obj)
        sasa_b_alone = self._chain_sasa(chain_b_obj)

        complex_model = Model(0)
        complex_model.add(copy.deepcopy(chain_a_obj))
        complex_model.add(copy.deepcopy(chain_b_obj))
        ShrakeRupley().compute(complex_model, level="A")
        sasa_complex = sum(atom.sasa for atom in complex_model.get_atoms())

        return round(sasa_a_alone + sasa_b_alone - sasa_complex, 2)
