import numpy as np
import pytest

from src.backend.interaction_geometry import classify_contact


class _FakeAtom:
    """Minimal stand-in for a Bio.PDB.Atom - just enough for
    classify_contact: .element, .get_name(), and '-' as Euclidean distance
    (matching Bio.PDB.Atom.Atom.__sub__)."""

    def __init__(self, name, element, coord):
        self._name = name
        self.element = element
        self.coord = np.array(coord, dtype=float)

    def get_name(self):
        return self._name

    def __sub__(self, other):
        return float(np.linalg.norm(self.coord - other.coord))


class TestClassifyContact:
    def test_charged_residue_atom_near_heteroatom_is_a_salt_bridge(self):
        # Asp OD1 3.0 A from a ligand nitrogen.
        res_atoms = [_FakeAtom("OD1", "O", [0, 0, 0]), _FakeAtom("CB", "C", [5, 5, 5])]
        target_atoms = [_FakeAtom("N1", "N", [3.0, 0, 0])]
        assert classify_contact("ASP", res_atoms, target_atoms) == "Salt Bridge"

    def test_neutral_polar_atom_near_heteroatom_is_a_hydrogen_bond(self):
        # Ser OG 3.2 A from a ligand oxygen - polar but not charged.
        res_atoms = [_FakeAtom("OG", "O", [0, 0, 0]), _FakeAtom("CB", "C", [5, 5, 5])]
        target_atoms = [_FakeAtom("O1", "O", [3.2, 0, 0])]
        assert classify_contact("SER", res_atoms, target_atoms) == "Hydrogen Bond"

    def test_backbone_atoms_alone_can_form_a_hydrogen_bond(self):
        # Every residue has backbone N/O - GLY has no sidechain at all.
        res_atoms = [_FakeAtom("N", "N", [0, 0, 0]), _FakeAtom("CA", "C", [5, 5, 5])]
        target_atoms = [_FakeAtom("O1", "O", [3.0, 0, 0])]
        assert classify_contact("GLY", res_atoms, target_atoms) == "Hydrogen Bond"

    def test_hydrophobic_residue_far_from_any_heteroatom_is_van_der_waals(self):
        res_atoms = [_FakeAtom("CB", "C", [0, 0, 0])]
        target_atoms = [_FakeAtom("C1", "C", [3.0, 0, 0])]
        assert classify_contact("LEU", res_atoms, target_atoms) == "Van der Waals"

    def test_polar_residue_with_no_qualifying_atom_pair_is_polar_contact(self):
        # LYS is charged/polar but its NZ is too far, and the target has no
        # heteroatom at all (falls through both the salt-bridge and
        # hydrogen-bond checks, and LYS isn't in the hydrophobic set).
        res_atoms = [_FakeAtom("NZ", "N", [0, 0, 0]), _FakeAtom("CB", "C", [1, 0, 0])]
        target_atoms = [_FakeAtom("C1", "C", [1.5, 0, 0])]
        assert classify_contact("LYS", res_atoms, target_atoms) == "Polar Contact"

    def test_charged_atom_too_far_falls_back_to_hydrogen_bond_check(self):
        # Asp OD1 10 A away (too far for a salt bridge) but backbone N is
        # within hydrogen-bond range of the same heteroatom.
        res_atoms = [
            _FakeAtom("OD1", "O", [10.0, 0, 0]),
            _FakeAtom("N", "N", [0, 0, 0]),
        ]
        target_atoms = [_FakeAtom("O1", "O", [3.0, 0, 0])]
        assert classify_contact("ASP", res_atoms, target_atoms) == "Hydrogen Bond"

    def test_no_heteroatoms_on_target_side_skips_polar_checks_entirely(self):
        # Even a charged residue can't form a salt bridge/H-bond with a
        # target that has no N/O/S atoms at all.
        res_atoms = [_FakeAtom("OD1", "O", [0, 0, 0])]
        target_atoms = [_FakeAtom("C1", "C", [1.0, 0, 0])]
        assert classify_contact("ASP", res_atoms, target_atoms) == "Polar Contact"

    @pytest.mark.parametrize(
        "resname,cutoff_dist",
        [("ASP", 4.0), ("GLU", 4.0), ("LYS", 4.0), ("ARG", 4.0), ("HIS", 4.0)],
    )
    def test_salt_bridge_cutoff_boundary_is_inclusive(self, resname, cutoff_dist):
        charged_atom_name = {
            "ASP": "OD1",
            "GLU": "OE1",
            "LYS": "NZ",
            "ARG": "NE",
            "HIS": "ND1",
        }[resname]
        element = "N" if charged_atom_name.startswith("N") else "O"
        res_atoms = [_FakeAtom(charged_atom_name, element, [0, 0, 0])]
        target_atoms = [_FakeAtom("N1", "N", [cutoff_dist, 0, 0])]
        assert classify_contact(resname, res_atoms, target_atoms) == "Salt Bridge"
