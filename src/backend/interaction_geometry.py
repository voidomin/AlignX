"""Heavy-atom-proxy interaction classification, shared by ligand-contact
analysis (`ligand_analyzer.py`) and protein-protein interface analysis
(`interface_analyzer.py`).

PDB files carry no hydrogens, so this doesn't attempt true H-bond geometry
(donor-H...acceptor angle) - it uses the standard practical proxy for
heavy-atom-only structures: distance between a residue's known polar/charged
atom and any heteroatom (N/O/S) on the other side. This is deliberately
scoped to what's derivable from atomic coordinates alone - it does not
attempt pi-stacking (no ligand bond-order/aromaticity data in a PDB file) or
metal coordination (metal ions are filtered out upstream as noise).
"""

from typing import Dict, List, Set

# Present on every standard residue.
BACKBONE_DONOR_ATOMS = {"N"}
BACKBONE_ACCEPTOR_ATOMS = {"O"}

# Sidechain atoms capable of donating/accepting a hydrogen bond, per residue.
SIDECHAIN_DONOR_ACCEPTOR_ATOMS: Dict[str, Set[str]] = {
    "SER": {"OG"},
    "THR": {"OG1"},
    "TYR": {"OH"},
    "ASN": {"ND2", "OD1"},
    "GLN": {"NE2", "OE1"},
    "HIS": {"ND1", "NE2"},
    "TRP": {"NE1"},
    "CYS": {"SG"},
    "LYS": {"NZ"},
    "ARG": {"NE", "NH1", "NH2"},
    "ASP": {"OD1", "OD2"},
    "GLU": {"OE1", "OE2"},
}

# Charged sidechain atoms - the subset of the above capable of a salt bridge
# (ionic interaction), as opposed to a neutral hydrogen bond.
CHARGED_ATOMS: Dict[str, Set[str]] = {
    "ASP": {"OD1", "OD2"},
    "GLU": {"OE1", "OE2"},
    "LYS": {"NZ"},
    "ARG": {"NE", "NH1", "NH2"},
    "HIS": {"ND1", "NE2"},
}

HYDROPHOBIC_RESIDUES = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO"}

HETEROATOM_ELEMENTS = {"N", "O", "S"}

SALT_BRIDGE_CUTOFF = 4.0
HYDROGEN_BOND_CUTOFF = 3.6


def _donor_acceptor_atoms(resname: str) -> Set[str]:
    return (
        BACKBONE_DONOR_ATOMS
        | BACKBONE_ACCEPTOR_ATOMS
        | SIDECHAIN_DONOR_ACCEPTOR_ATOMS.get(resname, set())
    )


def _heteroatoms(atoms) -> List:
    return [a for a in atoms if a.element in HETEROATOM_ELEMENTS]


def classify_contact(resname: str, res_atoms: List, target_atoms: List) -> str:
    """Classifies one residue's contact with a target atom group (a ligand's
    atoms, or another chain's atoms) as "Salt Bridge", "Hydrogen Bond", "Van
    der Waals", or "Polar Contact" (the catch-all for a polar/charged residue
    with no atom pair close enough to qualify as either of the above)."""
    target_hetero = _heteroatoms(target_atoms)

    if target_hetero:
        charged_names = CHARGED_ATOMS.get(resname)
        if charged_names:
            charged_atoms = [a for a in res_atoms if a.get_name() in charged_names]
            if _min_pair_distance(charged_atoms, target_hetero) <= SALT_BRIDGE_CUTOFF:
                return "Salt Bridge"

        donor_acceptor_names = _donor_acceptor_atoms(resname)
        polar_atoms = [a for a in res_atoms if a.get_name() in donor_acceptor_names]
        if _min_pair_distance(polar_atoms, target_hetero) <= HYDROGEN_BOND_CUTOFF:
            return "Hydrogen Bond"

    if resname in HYDROPHOBIC_RESIDUES:
        return "Van der Waals"

    return "Polar Contact"


def _min_pair_distance(atoms_a: List, atoms_b: List) -> float:
    if not atoms_a or not atoms_b:
        return float("inf")
    return min(a - b for a in atoms_a for b in atoms_b)
