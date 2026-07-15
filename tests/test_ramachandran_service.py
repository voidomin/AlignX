import pandas as pd
import pytest

from src.backend.ramachandran_service import RamachandranService


def _atom_line(serial, name, resname, chain, resi, x, y, z):
    name_field = f" {name:<3}"
    element = name.strip()[0]
    return (
        f"ATOM  {serial:>5} {name_field} {resname:>3} {chain}{resi:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.00:6.2f}"
        f"{'':>10}{element:>2}"
    )


def _fixture_pdb_text():
    residues = [
        (1, "ALA", (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.5, 1.4, 0.0)),
        (2, "GLY", (1.9, 1.5, 0.0), (2.5, 2.8, 0.3), (4.0, 2.9, 0.0)),
        (3, "SER", (4.5, 4.2, 0.2), (6.0, 4.4, 0.0), (6.5, 5.8, -0.3)),
    ]
    lines = []
    serial = 1
    for resi, resname, n_xyz, ca_xyz, c_xyz in residues:
        for name, xyz in (("N", n_xyz), ("CA", ca_xyz), ("C", c_xyz)):
            lines.append(_atom_line(serial, name, resname, "A", resi, *xyz))
            serial += 1
    lines.append("TER")
    return "\n".join(lines) + "\n"


@pytest.fixture
def fixture_pdb(tmp_path):
    pdb_file = tmp_path / "fixture.pdb"
    pdb_file.write_text(_fixture_pdb_text())
    return pdb_file


class TestCalculateTorsionAngles:
    def test_returns_dataframe_per_chain_with_expected_columns(self, fixture_pdb):
        service = RamachandranService()

        result = service.calculate_torsion_angles(fixture_pdb)

        assert "A" in result
        df = result["A"]
        assert list(df.columns) == [
            "residue_id",
            "residue_name",
            "phi",
            "psi",
            "region",
            "secondary_structure",
        ]
        assert len(df) == 3
        assert set(df["residue_name"]) == {"ALA", "GLY", "SER"}

    def test_terminal_residues_have_one_none_angle(self, fixture_pdb):
        service = RamachandranService()
        df = service.calculate_torsion_angles(fixture_pdb)["A"]

        first_row = df[df["residue_id"] == 1].iloc[0]
        last_row = df[df["residue_id"] == 3].iloc[0]

        assert pd.isna(first_row["phi"])
        assert pd.isna(last_row["psi"])

    def test_returns_empty_dict_on_parse_failure(self, tmp_path):
        service = RamachandranService()
        assert service.calculate_torsion_angles(tmp_path) == {}

    def test_works_with_a_real_mmcif_file_not_just_pdb(self, tmp_path):
        # Regression: this used to hardcode Bio.PDB.PDBParser, which can't
        # read mmCIF syntax at all - AlphaFold-sourced downloads are cached
        # as .cif, so GET /api/qc (the first caller to feed this a raw
        # downloaded file directly, rather than Mustang's own re-exported
        # always-PDB alignment.pdb) silently got {} for every one of them.
        from tests.conftest import MINIMAL_CIF_HEADER

        residues = [
            (1, "ALA", (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.5, 1.4, 0.0)),
            (2, "GLY", (1.9, 1.5, 0.0), (2.5, 2.8, 0.3), (4.0, 2.9, 0.0)),
            (3, "SER", (4.5, 4.2, 0.2), (6.0, 4.4, 0.0), (6.5, 5.8, -0.3)),
        ]
        lines = []
        serial = 1
        for resi, resname, n_xyz, ca_xyz, c_xyz in residues:
            for name, (x, y, z) in (("N", n_xyz), ("CA", ca_xyz), ("C", c_xyz)):
                element = name[0]
                lines.append(
                    f"ATOM {serial} {element} {name} . {resname} A 1 {resi} ? "
                    f"{x:.3f} {y:.3f} {z:.3f} 1.00 20.00 ? {resi} A 1"
                )
                serial += 1
        cif_file = tmp_path / "fixture.cif"
        cif_file.write_text(MINIMAL_CIF_HEADER + "\n".join(lines) + "\n")
        service = RamachandranService()

        result = service.calculate_torsion_angles(cif_file)

        assert "A" in result
        assert len(result["A"]) == 3
        assert set(result["A"]["residue_name"]) == {"ALA", "GLY", "SER"}


class TestTorsionRow:
    def test_returns_none_when_both_angles_missing(self):
        service = RamachandranService()
        row = service._torsion_row(_FakeResidue(), None, None)
        assert row is None

    def test_returns_terminal_region_when_one_angle_missing(self):
        service = RamachandranService()
        row = service._torsion_row(_FakeResidue(), None, 0.5)
        assert row["region"] == "Terminal"
        assert row["phi"] is None


class _FakeResidue:
    def get_id(self):
        return (" ", 1, " ")

    def get_resname(self):
        return "ALA"


class TestClassifyRegion:
    def test_none_angle_is_terminal(self):
        service = RamachandranService()
        assert service._classify_region(None, None) == "Terminal"

    def test_alpha_helix_region(self):
        service = RamachandranService()
        assert service._classify_region(-60, -40) == "Favored (Alpha)"

    def test_beta_sheet_region(self):
        service = RamachandranService()
        assert service._classify_region(-120, 130) == "Favored (Beta)"

    def test_left_handed_alpha_region(self):
        service = RamachandranService()
        assert service._classify_region(60, 60) == "Favored (L-Alpha)"

    def test_allowed_region(self):
        service = RamachandranService()
        assert service._classify_region(-170, 10) == "Allowed"

    def test_outlier_region(self):
        service = RamachandranService()
        assert service._classify_region(170, -170) == "Outlier"


class TestClassifySecondaryStructure:
    def test_none_angle_is_terminal(self):
        service = RamachandranService()
        assert service._classify_secondary_structure(None, None) == "Terminal"

    def test_alpha_helix_region(self):
        service = RamachandranService()
        assert service._classify_secondary_structure(-60, -40) == "Helix"

    def test_beta_sheet_region(self):
        service = RamachandranService()
        assert service._classify_secondary_structure(-120, 130) == "Sheet"

    def test_beta_sheet_region_wrapping_psi(self):
        service = RamachandranService()
        assert service._classify_secondary_structure(-120, -170) == "Sheet"

    def test_outside_both_regions_is_coil(self):
        service = RamachandranService()
        assert service._classify_secondary_structure(60, 60) == "Coil"


class TestAggregateSecondaryStructure:
    def test_empty_input_returns_zeros(self):
        service = RamachandranService()
        result = service.aggregate_secondary_structure({})
        assert result == {
            "total_residues": 0,
            "helix_percent": 0,
            "sheet_percent": 0,
            "coil_percent": 0,
            "per_chain": {},
        }

    def test_computes_percentages_and_excludes_terminal_residues(self):
        service = RamachandranService()
        df = pd.DataFrame(
            [
                {"residue_id": 1, "secondary_structure": "Terminal"},
                {"residue_id": 2, "secondary_structure": "Helix"},
                {"residue_id": 3, "secondary_structure": "Helix"},
                {"residue_id": 4, "secondary_structure": "Sheet"},
                {"residue_id": 5, "secondary_structure": "Coil"},
            ]
        )

        result = service.aggregate_secondary_structure({"A": df})

        assert result["total_residues"] == 4
        assert result["helix_percent"] == pytest.approx(50.0)
        assert result["sheet_percent"] == pytest.approx(25.0)
        assert result["coil_percent"] == pytest.approx(25.0)
        assert result["per_chain"]["A"]["residue_count"] == 4
        assert result["per_chain"]["A"]["helix_percent"] == pytest.approx(50.0)

    def test_combines_multiple_chains(self):
        service = RamachandranService()
        df_a = pd.DataFrame([{"residue_id": 1, "secondary_structure": "Helix"}])
        df_b = pd.DataFrame(
            [
                {"residue_id": 1, "secondary_structure": "Sheet"},
                {"residue_id": 2, "secondary_structure": "Sheet"},
            ]
        )

        result = service.aggregate_secondary_structure({"A": df_a, "B": df_b})

        assert result["total_residues"] == 3
        assert result["helix_percent"] == pytest.approx(100 / 3)
        assert result["sheet_percent"] == pytest.approx(200 / 3)
        assert set(result["per_chain"].keys()) == {"A", "B"}


class TestAggregateMetrics:
    def test_empty_input_returns_zeros(self):
        service = RamachandranService()
        result = service.aggregate_metrics({})
        assert result == {
            "quality_score": 0,
            "total_residues": 0,
            "favored_percent": 0,
            "outlier_count": 0,
            "outliers_list": [],
        }

    def test_computes_quality_score_and_outliers(self):
        service = RamachandranService()
        df = pd.DataFrame(
            [
                {"residue_id": 1, "residue_name": "ALA", "region": "Favored (Alpha)"},
                {"residue_id": 2, "residue_name": "GLY", "region": "Favored (Beta)"},
                {"residue_id": 3, "residue_name": "PRO", "region": "Outlier"},
            ]
        )

        result = service.aggregate_metrics({"A": df})

        assert result["total_residues"] == 3
        assert result["quality_score"] == pytest.approx(200 / 3)
        assert result["outlier_count"] == 1
        assert result["outliers_list"] == ["PRO3 (Chain A)"]

    def test_outliers_list_capped_at_ten(self):
        service = RamachandranService()
        df = pd.DataFrame(
            [
                {"residue_id": i, "residue_name": "PRO", "region": "Outlier"}
                for i in range(12)
            ]
        )

        result = service.aggregate_metrics({"A": df})

        assert result["outlier_count"] == 12
        assert len(result["outliers_list"]) == 10
