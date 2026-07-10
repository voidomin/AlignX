import pandas as pd
import pytest

from src.backend.ligand_analyzer import LigandAnalyzer


def _atom_line(serial, name, resname, chain, resi, x, y, z, hetatm=False):
    record = "HETATM" if hetatm else "ATOM  "
    name_field = f" {name:<3}"
    element = name.strip()[0]
    return (
        f"{record}{serial:>5} {name_field} {resname:>3} {chain}{resi:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.00:6.2f}"
        f"{'':>10}{element:>2}"
    )


def _fixture_pdb_text():
    lines = [
        _atom_line(1, "N", "ALA", "A", 1, 0.0, 1.0, 0.0),
        _atom_line(2, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(3, "C", "ALA", "A", 1, 1.0, 0.0, 0.0),
        _atom_line(4, "O", "ALA", "A", 1, 1.5, -1.0, 0.0),
        _atom_line(5, "CB", "ALA", "A", 1, -1.0, -1.0, 0.0),
        _atom_line(6, "N", "GLY", "A", 2, 50.0, 0.0, 0.0),
        _atom_line(7, "CA", "GLY", "A", 2, 51.0, 0.0, 0.0),
        _atom_line(8, "C1", "LIG", "A", 100, 0.5, 0.5, 0.5, hetatm=True),
        _atom_line(9, "C2", "LIG", "A", 100, 1.0, 1.0, 1.0, hetatm=True),
        _atom_line(10, "O", "HOH", "A", 200, 100.0, 100.0, 100.0, hetatm=True),
        "TER",
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture
def fixture_pdb(tmp_path):
    pdb_file = tmp_path / "fixture.pdb"
    pdb_file.write_text(_fixture_pdb_text())
    return pdb_file


class TestGetLigands:
    def test_finds_ligand_and_ignores_water(self, fixture_pdb):
        analyzer = LigandAnalyzer()

        ligands = analyzer.get_ligands(fixture_pdb)

        assert len(ligands) == 1
        assert ligands[0]["name"] == "LIG"
        assert ligands[0]["id"] == "LIG_A_100"
        assert ligands[0]["chain"] == "A"
        assert ligands[0]["resi"] == 100
        assert ligands[0]["atom_count"] == 2
        assert ligands[0]["center"] == pytest.approx([0.75, 0.75, 0.75])

    def test_returns_empty_list_for_missing_file(self, tmp_path):
        analyzer = LigandAnalyzer()
        assert analyzer.get_ligands(tmp_path / "nope.pdb") == []

    def test_returns_empty_list_on_parse_failure(self, tmp_path):
        analyzer = LigandAnalyzer()
        assert analyzer.get_ligands(tmp_path) == []


class TestCalculateInteractions:
    def test_finds_nearby_residue_and_excludes_far_one(self, fixture_pdb):
        analyzer = LigandAnalyzer()

        result = analyzer.calculate_interactions(fixture_pdb, "LIG_A_100", cutoff=5.0)

        assert result["ligand"] == "LIG_A_100"
        residues = {i["residue"] for i in result["interactions"]}
        assert residues == {"ALA"}
        entry = result["interactions"][0]
        assert entry["type"] == "Van der Waals"
        assert entry["distance"] < 5.0
        assert result["pocket_sasa"] >= 0

    def test_invalid_ligand_id_format_reports_error(self, fixture_pdb):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interactions(fixture_pdb, "badformat")
        assert result == {"error": "Invalid ID"}

    def test_ligand_not_found_reports_error(self, fixture_pdb):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interactions(fixture_pdb, "XXX_A_999")
        assert "not found" in result["error"]

    def test_parse_failure_reports_error(self, tmp_path):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interactions(tmp_path, "LIG_A_100")
        assert "error" in result


class TestCalculateSasa:
    def test_returns_total_chain_and_residue_breakdown(self, fixture_pdb):
        analyzer = LigandAnalyzer()

        result = analyzer.calculate_sasa(fixture_pdb)

        assert result["total_sasa"] >= 0
        assert "A" in result["chain_sasa"]
        residue_names = {r["residue"] for r in result["residues"]}
        assert residue_names == {"ALA", "GLY"}

    def test_returns_error_on_parse_failure(self, tmp_path):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_sasa(tmp_path)
        assert "error" in result


class TestCalculateInteractionSimilarity:
    def test_empty_input_returns_empty_dataframe(self):
        analyzer = LigandAnalyzer()
        result = analyzer.calculate_interaction_similarity([])
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_diagonal_is_one_and_off_diagonal_is_jaccard(self):
        analyzer = LigandAnalyzer()
        all_interactions = [
            {
                "ligand": "L1",
                "interactions": [{"residue": "ALA"}, {"residue": "GLY"}],
            },
            {
                "ligand": "L2",
                "interactions": [{"residue": "ALA"}, {"residue": "SER"}],
            },
        ]

        result = analyzer.calculate_interaction_similarity(all_interactions)

        assert result.loc["L1", "L1"] == 1.0
        assert result.loc["L2", "L2"] == 1.0
        assert result.loc["L1", "L2"] == pytest.approx(1 / 3)

    def test_empty_fingerprint_scores_zero_not_undefined(self):
        analyzer = LigandAnalyzer()
        all_interactions = [
            {"ligand": "L1", "interactions": [{"residue": "ALA"}]},
            {"ligand": "L2", "interactions": []},
        ]

        result = analyzer.calculate_interaction_similarity(all_interactions)

        assert result.loc["L1", "L2"] == 0.0


class TestJaccardScore:
    def test_both_empty_scores_zero(self):
        assert LigandAnalyzer._jaccard_score(set(), set()) == 0.0

    def test_identical_sets_score_one(self):
        assert LigandAnalyzer._jaccard_score({"A", "B"}, {"A", "B"}) == 1.0

    def test_disjoint_sets_score_zero(self):
        assert LigandAnalyzer._jaccard_score({"A"}, {"B"}) == 0.0

    def test_partial_overlap(self):
        assert LigandAnalyzer._jaccard_score({"A", "B"}, {"A", "C"}) == pytest.approx(
            1 / 3
        )
