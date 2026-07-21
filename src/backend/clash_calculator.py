"""
Geometric all-atom steric-clash score - a real, self-computed van der
Waals overlap detector. No external API - pure geometry on coordinates
already downloaded, the same "no new dependency" pattern
flexibility_calculator.py and pae_domain_calculator.py use. Bulk QC
(/api/bulk-qc) only ever reports a real clashscore for real PDB entries
(fetched from wwPDB validation) - AlphaFold/ESM Atlas/uploaded/predicted
structures get nothing there. This fills that gap for every structure
source, reported in the same nominal units (clashes per 1000 atoms)
wwPDB's own MolProbity-derived clashscore uses.

Live-verified real-data caveat: this is only a rough sanity check against
a real PDB entry's own wwPDB clashscore, not a reproduction of it. Real
MolProbity adds explicit hydrogens before counting overlaps, and
hydrogen-hydrogen/hydrogen-heavy contacts (invisible to a heavy-atom-only
detector like this one) dominate its count - for a modern, well-refined
structure the two numbers land in the same ballpark (4RLT: wwPDB 1.08 vs.
self-computed 2.18), but for an older structure with poor hydrogen/
rotamer packing they can diverge sharply (4HHB, a 1984 1.74 Å structure:
wwPDB 141.11 vs. self-computed 6.84 - correctly low, since none of that
gap is heavy-atom overlap). Every caller should present this as its own
independent signal, not as "the same number wwPDB would report."

Excludes same-residue pairs (bonded intra-residue geometry, e.g. CA-CB,
which would otherwise always register as a "clash") and sequentially
adjacent same-chain residue pairs (the real peptide bond and its
immediate neighbors) - only counts non-hydrogen atoms, following
MolProbity's own "all-atom without added hydrogens" convention for the
atoms it does have. The 0.4 Angstrom overlap tolerance and van der Waals
radii below match MolProbity/wwPDB convention as closely as practical.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from Bio.PDB import NeighborSearch

from src.backend.pdb_manager import parse_structure_file
from src.utils.logger import get_logger

logger = get_logger()

# Standard van der Waals radii (Angstrom) for the elements that dominate
# protein heavy-atom content (MolProbity/wwPDB convention).
_VDW_RADII = {
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "P": 1.80,
}
_DEFAULT_VDW_RADIUS = 1.70
_MAX_VDW_RADIUS = max(_VDW_RADII.values())

# The standard MolProbity/wwPDB clash tolerance - two atoms are only
# flagged once their overlap exceeds this amount beyond their combined
# van der Waals radii (accounts for thermal motion/measurement
# uncertainty, not a hard-sphere collision).
OVERLAP_TOLERANCE_ANGSTROM = 0.4

MAX_CLASHING_PAIRS_RETURNED = 50


def _heavy_atoms(model):
    """Standard-residue (non-HETATM), non-hydrogen atoms only - the same
    "skip water and non-standard residues" convention
    LigandAnalyzer.calculate_sasa already uses, plus a hydrogen exclusion
    since real PDB/AlphaFold files rarely carry them and MolProbity's own
    convention is all-atom-without-added-hydrogens."""
    atoms = []
    for chain in model:
        for residue in chain:
            if residue.get_id()[0] != " ":
                continue
            for atom in residue:
                element = (atom.element or atom.get_name()[:1]).strip().upper()
                if element in ("H", "D"):
                    continue
                atom.xtra["clash_radius"] = _VDW_RADII.get(element, _DEFAULT_VDW_RADIUS)
                atoms.append(atom)
    return atoms


def calculate_clash_score(pdb_path: Path) -> Optional[Dict[str, Any]]:
    """
    Real-time all-atom steric-clash detection for one structure's first
    model. Returns {"clash_count": ..., "atom_count": ..., "clashscore":
    clashes per 1000 atoms, "clashing_pairs": [...worst-first, capped...]}
    - or None if the structure has no heavy atoms in a standard residue,
    or on any parse/computation failure.
    """
    try:
        structure = parse_structure_file(Path(pdb_path))
        model = next(iter(structure))

        atoms = _heavy_atoms(model)
        atom_count = len(atoms)
        if atom_count == 0:
            return None

        ns = NeighborSearch(atoms)
        # Any pair that could possibly clash has distance < the sum of
        # their radii, so the two largest real radii is a safe upper
        # bound for which pairs to even consider.
        candidate_pairs = ns.search_all(2 * _MAX_VDW_RADIUS, level="A")

        clashing_pairs = []
        for atom_a, atom_b in candidate_pairs:
            residue_a = atom_a.get_parent()
            residue_b = atom_b.get_parent()
            if residue_a is residue_b:
                continue

            chain_a = residue_a.get_parent()
            chain_b = residue_b.get_parent()
            if (
                chain_a is chain_b
                and abs(residue_a.get_id()[1] - residue_b.get_id()[1]) <= 1
            ):
                continue

            threshold = (
                atom_a.xtra["clash_radius"]
                + atom_b.xtra["clash_radius"]
                - OVERLAP_TOLERANCE_ANGSTROM
            )
            distance = float(atom_a - atom_b)
            if distance < threshold:
                clashing_pairs.append(
                    {
                        "chain_a": chain_a.get_id(),
                        "residue_a": residue_a.get_id()[1],
                        "atom_a": atom_a.get_name(),
                        "chain_b": chain_b.get_id(),
                        "residue_b": residue_b.get_id()[1],
                        "atom_b": atom_b.get_name(),
                        "distance": round(distance, 2),
                    }
                )

        clash_count = len(clashing_pairs)
        clashing_pairs.sort(key=lambda pair: pair["distance"])

        return {
            "clash_count": clash_count,
            "atom_count": atom_count,
            "clashscore": round(clash_count / atom_count * 1000, 2),
            "clashing_pairs": clashing_pairs[:MAX_CLASHING_PAIRS_RETURNED],
        }
    except Exception:
        logger.exception(f"Failed to calculate clash score for {pdb_path}")
        return None
