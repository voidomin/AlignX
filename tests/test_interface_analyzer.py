import pytest

from src.backend.interface_analyzer import InterfaceAnalyzer


def _atom_line(serial, name, resname, chain, resi, x, y, z):
    name_field = f" {name:<3}"
    element = name.strip()[0]
    return (
        f"ATOM  {serial:>5} {name_field} {resname:>3} {chain}{resi:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.00:6.2f}"
        f"{'':>10}{element:>2}"
    )


def _fixture_pdb_text():
    # Chain A: a single ALA near the origin.
    # Chain B: a single ASP positioned close enough to A's ALA to contact,
    # plus a GLY far away (never an interface residue).
    lines = [
        _atom_line(1, "N", "ALA", "A", 1, 0.0, 1.0, 0.0),
        _atom_line(2, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(3, "C", "ALA", "A", 1, 1.0, 0.0, 0.0),
        _atom_line(4, "O", "ALA", "A", 1, 1.5, -1.0, 0.0),
        _atom_line(5, "CB", "ALA", "A", 1, -1.0, -1.0, 0.0),
        _atom_line(6, "N", "ASP", "B", 1, 3.0, 0.0, 0.0),
        _atom_line(7, "CA", "ASP", "B", 1, 4.0, 0.0, 0.0),
        _atom_line(8, "C", "ASP", "B", 1, 5.0, 0.0, 0.0),
        _atom_line(9, "O", "ASP", "B", 1, 5.5, 1.0, 0.0),
        _atom_line(10, "CB", "ASP", "B", 1, 4.0, 1.0, 0.0),
        _atom_line(11, "CG", "ASP", "B", 1, 4.0, 2.0, 0.0),
        _atom_line(12, "OD1", "ASP", "B", 1, 3.0, 2.5, 0.0),
        _atom_line(13, "OD2", "ASP", "B", 1, 5.0, 2.5, 0.0),
        _atom_line(14, "N", "GLY", "B", 2, 100.0, 0.0, 0.0),
        _atom_line(15, "CA", "GLY", "B", 2, 101.0, 0.0, 0.0),
        "TER",
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture
def fixture_pdb(tmp_path):
    pdb_file = tmp_path / "fixture.pdb"
    pdb_file.write_text(_fixture_pdb_text())
    return pdb_file


class TestCalculateInterface:
    def test_finds_contact_residues_on_both_sides(self, fixture_pdb):
        analyzer = InterfaceAnalyzer()

        result = analyzer.calculate_interface(fixture_pdb, "A", "B", cutoff=5.0)

        assert result["chain_a"] == "A"
        assert result["chain_b"] == "B"
        a_residues = {c["residue"] for c in result["chain_a_contacts"]}
        b_residues = {c["residue"] for c in result["chain_b_contacts"]}
        assert a_residues == {"ALA"}
        assert b_residues == {"ASP"}

    def test_distant_residue_is_excluded(self, fixture_pdb):
        analyzer = InterfaceAnalyzer()

        result = analyzer.calculate_interface(fixture_pdb, "A", "B", cutoff=5.0)

        b_residues = {c["residue"] for c in result["chain_b_contacts"]}
        assert "GLY" not in b_residues

    def test_buried_area_is_a_positive_number(self, fixture_pdb):
        analyzer = InterfaceAnalyzer()

        result = analyzer.calculate_interface(fixture_pdb, "A", "B", cutoff=5.0)

        assert isinstance(result["buried_area"], float)
        assert result["buried_area"] > 0

    def test_same_chain_twice_reports_error(self, fixture_pdb):
        analyzer = InterfaceAnalyzer()
        result = analyzer.calculate_interface(fixture_pdb, "A", "A", cutoff=5.0)
        assert "error" in result

    def test_unknown_chain_reports_error(self, fixture_pdb):
        analyzer = InterfaceAnalyzer()
        result = analyzer.calculate_interface(fixture_pdb, "A", "Z", cutoff=5.0)
        assert "not found" in result["error"]

    def test_parse_failure_reports_error(self, tmp_path):
        analyzer = InterfaceAnalyzer()
        result = analyzer.calculate_interface(tmp_path, "A", "B")
        assert "error" in result
