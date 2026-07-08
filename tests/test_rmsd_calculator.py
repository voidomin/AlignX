import numpy as np
import pytest
from pathlib import Path

from src.backend.rmsd_calculator import (
    calculate_tm_score,
    calculate_gdt_ts,
    calculate_rmsd_from_superposition,
    parse_mustang_log_for_rmsd,
    parse_rms_rot_file,
    parse_rmsd_matrix,
    calculate_structure_rmsd,
    calculate_alignment_quality_metrics,
)


class TestTmScore:
    def test_identical_coordinates_score_one_when_l_target_matches_length(self):
        # Each identical point contributes 1/(1+0) = 1 to the sum, so the
        # score is exactly (n points)/l_target - it only reaches 1.0 when
        # l_target equals the actual number of points compared, not any
        # arbitrary target length.
        coords = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0]])
        assert calculate_tm_score(coords, coords, l_target=3) == 1.0

    def test_identical_coordinates_with_larger_target_scores_proportionally_lower(self):
        coords = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0]])
        assert calculate_tm_score(coords, coords, l_target=20) == pytest.approx(3 / 20)

    def test_empty_coords_returns_zero(self):
        empty = np.zeros((0, 3))
        assert calculate_tm_score(empty, empty, l_target=20) == 0.0

    def test_zero_target_length_returns_zero(self):
        coords = np.array([[0.0, 0.0, 0.0]])
        assert calculate_tm_score(coords, coords, l_target=0) == 0.0

    def test_short_target_uses_fixed_d0(self):
        # l_target <= 15 uses a fixed d0 = 0.5 rather than the length-scaled
        # formula - verify by hand-computing the score for a known offset.
        c1 = np.array([[0.0, 0.0, 0.0]])
        c2 = np.array([[0.5, 0.0, 0.0]])  # distance = 0.5 = d0
        score = calculate_tm_score(c1, c2, l_target=10)
        # 1 / (1 + (0.5/0.5)^2) = 1/2, divided by l_target=10
        assert score == pytest.approx(0.5 / 10)

    def test_larger_offset_scores_lower_than_smaller_offset(self):
        target = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        close = np.array([[0.1, 0.0, 0.0], [1.1, 0.0, 0.0]])
        far = np.array([[5.0, 0.0, 0.0], [6.0, 0.0, 0.0]])
        close_score = calculate_tm_score(target, close, l_target=20)
        far_score = calculate_tm_score(target, far, l_target=20)
        assert close_score > far_score


class TestGdtTs:
    def test_identical_coordinates_score_one(self):
        coords = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        assert calculate_gdt_ts(coords, coords, l_target=2) == 1.0

    def test_empty_coords_returns_zero(self):
        empty = np.zeros((0, 3))
        assert calculate_gdt_ts(empty, empty, l_target=5) == 0.0

    def test_zero_target_length_returns_zero(self):
        coords = np.array([[0.0, 0.0, 0.0]])
        assert calculate_gdt_ts(coords, coords, l_target=0) == 0.0

    def test_known_distances_produce_hand_computed_score(self):
        # Two residues: one exactly at the target (distance 0, passes all 4
        # thresholds), one offset by 3.0 (passes the 4A and 8A thresholds
        # only, not 1A/2A).
        target = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        moved = np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
        score = calculate_gdt_ts(target, moved, l_target=2)
        # p1 = 1/2, p2 = 1/2, p4 = 2/2, p8 = 2/2 -> mean = (0.5+0.5+1+1)/4
        assert score == pytest.approx((0.5 + 0.5 + 1.0 + 1.0) / 4.0)


def _write_multi_model_pdb(path: Path, model_coords):
    """Write a minimal multi-MODEL PDB with one CA atom per residue, at the
    given per-model list-of-coordinate-triples."""
    lines = []
    for model_idx, coords in enumerate(model_coords, start=1):
        lines.append(f"MODEL     {model_idx}")
        for i, (x, y, z) in enumerate(coords, start=1):
            lines.append(
                f"ATOM  {i:5d}  CA  ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
            )
        lines.append("ENDMDL")
    lines.append("END\n")
    path.write_text("\n".join(lines))


class TestCalculateRmsdFromSuperposition:
    def test_two_models_identical_coords_gives_zero_rmsd(self, tmp_path):
        pdb_file = tmp_path / "aligned.pdb"
        coords = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        _write_multi_model_pdb(pdb_file, [coords, coords])

        result = calculate_rmsd_from_superposition(pdb_file, num_expected=2)

        assert result is not None
        assert result.shape == (2, 2)
        assert result.iloc[0, 1] == pytest.approx(0.0)

    def test_two_models_known_offset_gives_hand_computed_rmsd(self, tmp_path):
        pdb_file = tmp_path / "aligned.pdb"
        coords_a = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        # Every atom offset by (3, 4, 0) -> per-atom distance = 5.0 exactly,
        # so RMSD (sqrt of mean squared distance) is also exactly 5.0.
        coords_b = [[3.0, 4.0, 0.0], [4.0, 4.0, 0.0]]
        _write_multi_model_pdb(pdb_file, [coords_a, coords_b])

        result = calculate_rmsd_from_superposition(pdb_file, num_expected=2)

        assert result is not None
        assert result.iloc[0, 1] == pytest.approx(5.0)
        assert result.iloc[1, 0] == pytest.approx(5.0)
        assert result.iloc[0, 0] == 0.0

    def test_fewer_models_than_expected_falls_back_to_none(self, tmp_path):
        pdb_file = tmp_path / "aligned.pdb"
        _write_multi_model_pdb(pdb_file, [[[0.0, 0.0, 0.0]]])

        result = calculate_rmsd_from_superposition(pdb_file, num_expected=5)

        assert result is None

    def test_single_model_falls_back_to_per_chain_entities(self, tmp_path):
        """When Mustang emits everything as one MODEL (rather than one MODEL
        per structure), the function must fall back to treating each chain
        within that single model as one structure."""
        pdb_file = tmp_path / "aligned.pdb"
        lines = ["MODEL     1"]
        for chain_id, coords in zip(
            "AB",
            (
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            ),
        ):
            for i, (x, y, z) in enumerate(coords, start=1):
                lines.append(
                    f"ATOM  {i:5d}  CA  ALA {chain_id}{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
                )
        lines.append("ENDMDL")
        lines.append("END\n")
        pdb_file.write_text("\n".join(lines))

        result = calculate_rmsd_from_superposition(pdb_file, num_expected=2)

        assert result is not None
        assert result.shape == (2, 2)
        assert result.iloc[0, 1] == pytest.approx(0.0)

    def test_returns_none_on_parse_failure(self, tmp_path):
        result = calculate_rmsd_from_superposition(tmp_path, num_expected=2)
        assert result is None


class TestParseMustangLogForRmsd:
    def test_parses_a_real_shaped_rmsd_table(self, tmp_path):
        log_file = tmp_path / "mustang.log"
        log_file.write_text(
            "Mustang alignment run started.\n"
            "> RMSD TABLE:\n"
            "1   0.00   0.85   1.20\n"
            "2   0.85   0.00   0.90\n"
            "3   1.20   0.90   0.00\n"
            "Alignment complete.\n"
        )

        result = parse_mustang_log_for_rmsd(log_file)

        assert result is not None
        assert result.shape == (3, 3)
        assert result.iloc[0, 1] == 0.85
        assert result.iloc[2, 2] == 0.0

    def test_missing_file_returns_none(self, tmp_path):
        assert parse_mustang_log_for_rmsd(tmp_path / "does_not_exist.log") is None

    def test_no_numeric_table_returns_none(self, tmp_path):
        log_file = tmp_path / "empty.log"
        log_file.write_text("Nothing useful here.\nJust text.\n")
        assert parse_mustang_log_for_rmsd(log_file) is None

    def test_dashes_treated_as_zero(self, tmp_path):
        log_file = tmp_path / "mustang.log"
        log_file.write_text("1   0.00   ---\n2   ---   0.00\n")
        result = parse_mustang_log_for_rmsd(log_file)
        assert result is not None
        assert result.iloc[0, 1] == 0.0

    def test_fewer_rows_than_the_last_rows_width_returns_none(self, tmp_path):
        # The last parsed row has 3 values, but only 2 total valid rows
        # were found - too few to form a 3x3 square submatrix.
        log_file = tmp_path / "mustang.log"
        log_file.write_text("1   0.00   0.85   1.20\n")
        assert parse_mustang_log_for_rmsd(log_file) is None


class TestParseRmsRotFile:
    def test_parses_pipe_delimited_matrix(self, tmp_path):
        rms_rot = tmp_path / "alignment.rms_rot"
        rms_rot.write_text(
            "Some header text\n"
            "RMSD matrix\n"
            "1 | 0.00  0.85  1.20\n"
            "2 | 0.85  0.00  0.90\n"
            "3 | 1.20  0.90  0.00\n"
        )
        pdb_ids = ["1ABC", "2XYZ", "3DEF"]

        result = parse_rms_rot_file(rms_rot, pdb_ids)

        assert result is not None
        assert list(result.index) == pdb_ids
        assert list(result.columns) == pdb_ids
        assert result.loc["1ABC", "2XYZ"] == 0.85

    def test_no_rmsd_matrix_marker_returns_none(self, tmp_path):
        rms_rot = tmp_path / "alignment.rms_rot"
        rms_rot.write_text("Nothing relevant here.\n")
        assert parse_rms_rot_file(rms_rot, ["1ABC", "2XYZ"]) is None

    def test_dashes_in_matrix_become_zero(self, tmp_path):
        rms_rot = tmp_path / "alignment.rms_rot"
        rms_rot.write_text("RMSD matrix\n1 | 0.00  ---\n2 | ---  0.00\n")
        result = parse_rms_rot_file(rms_rot, ["1ABC", "2XYZ"])
        assert result is not None
        assert result.loc["1ABC", "2XYZ"] == 0.0

    def test_pads_short_rows_to_full_size(self, tmp_path):
        # Fewer pdb_ids-worth of columns present in a row than expected -
        # the parser must pad with 0.0 rather than raising an IndexError.
        rms_rot = tmp_path / "alignment.rms_rot"
        rms_rot.write_text("RMSD matrix\n1 | 0.00\n2 | 0.50  0.00\n")
        result = parse_rms_rot_file(rms_rot, ["1ABC", "2XYZ"])
        assert result is not None
        assert result.shape == (2, 2)

    def test_returns_none_on_read_failure(self, tmp_path):
        # A directory can't be opened as a file - exercises the read
        # failure path rather than a missing-marker/malformed-content one.
        assert parse_rms_rot_file(tmp_path, ["1ABC", "2XYZ"]) is None


class TestParseRmsdMatrix:
    def test_prefers_rms_rot_file_when_present(self, tmp_path):
        (tmp_path / "alignment.rms_rot").write_text(
            "RMSD matrix\n1 | 0.00  0.42\n2 | 0.42  0.00\n"
        )
        # Also drop a log file that would parse differently, to prove the
        # .rms_rot strategy really does win when both exist.
        (tmp_path / "mustang.log").write_text("1   0.00   9.99\n2   9.99   0.00\n")

        result = parse_rmsd_matrix(tmp_path, ["1ABC", "2XYZ"])

        assert result is not None
        assert result.loc["1ABC", "2XYZ"] == 0.42

    def test_falls_back_to_log_file_when_no_rms_rot(self, tmp_path):
        (tmp_path / "mustang.log").write_text("1   0.00   0.77\n2   0.77   0.00\n")

        result = parse_rmsd_matrix(tmp_path, ["1ABC", "2XYZ"])

        assert result is not None
        assert result.shape == (2, 2)

    def test_returns_none_when_nothing_present(self, tmp_path):
        assert parse_rmsd_matrix(tmp_path, ["1ABC", "2XYZ"]) is None

    def test_falls_back_to_structure_calculation_when_no_rms_rot_or_log(self, tmp_path):
        _write_two_structure_alignment_pdb(tmp_path / "alignment.pdb")
        (tmp_path / "alignment.afasta").write_text(">structA\nAAA\n>structB\nAAA\n")

        result = parse_rmsd_matrix(tmp_path, ["1ABC", "2XYZ"])

        assert result is not None
        assert result.loc["structA", "structB"] == pytest.approx(1.0)


def _write_two_structure_alignment_pdb(path: Path):
    """Two 3-residue structures as separate MODELs, offset by (1, 0, 0) so
    RMSD between them is knowable but nonzero."""
    coords_a = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
    coords_b = [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]]
    _write_multi_model_pdb(path, [coords_a, coords_b])


class TestCalculateStructureRmsd:
    def test_full_gapless_alignment_matches_hand_computed_rmsd(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        _write_two_structure_alignment_pdb(pdb_file)
        fasta_file.write_text(">structA\nAAA\n>structB\nAAA\n")

        result = calculate_structure_rmsd(pdb_file, fasta_file)

        assert result is not None
        assert list(result.index) == ["structA", "structB"]
        # Every residue offset by exactly 1.0 along x -> RMSD is exactly 1.0
        assert result.loc["structA", "structB"] == pytest.approx(1.0)

    def test_single_sequence_returns_none(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        _write_multi_model_pdb(pdb_file, [[[0.0, 0.0, 0.0]]])
        fasta_file.write_text(">only_one\nA\n")

        assert calculate_structure_rmsd(pdb_file, fasta_file) is None

    def test_gapped_alignment_only_compares_common_columns(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        # structA has 3 residues, structB has 2 (one gap) - the gapped
        # column must be excluded from the RMSD calculation entirely.
        coords_a = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        coords_b = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        _write_multi_model_pdb(pdb_file, [coords_a, coords_b])
        fasta_file.write_text(">structA\nAAA\n>structB\nA-A\n")

        result = calculate_structure_rmsd(pdb_file, fasta_file)

        assert result is not None
        # Only columns 0 and 2 are common; both structA/structB residues
        # there are identical (0,0,0) and (2,0,0) once the gap is excluded.
        assert result.loc["structA", "structB"] == pytest.approx(0.0)

    def test_falls_back_to_chains_when_pdb_uses_a_single_model(self, tmp_path):
        """Mustang sometimes emits everything as one MODEL with one chain
        per structure, rather than one MODEL per structure - _select_structures
        must fall back to per-chain entities when the model count alone
        doesn't match the alignment's structure count."""
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        lines = ["MODEL     1"]
        for chain_id, coords in zip(
            "AB",
            (
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            ),
        ):
            for i, (x, y, z) in enumerate(coords, start=1):
                lines.append(
                    f"ATOM  {i:5d}  CA  ALA {chain_id}{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
                )
        lines.append("ENDMDL")
        lines.append("END\n")
        pdb_file.write_text("\n".join(lines))
        fasta_file.write_text(">structA\nAA\n>structB\nAA\n")

        result = calculate_structure_rmsd(pdb_file, fasta_file)

        assert result is not None
        assert result.loc["structA", "structB"] == pytest.approx(1.0)

    def test_returns_none_on_parse_failure(self, tmp_path):
        fasta_file = tmp_path / "alignment.afasta"
        fasta_file.write_text(">structA\nAAA\n>structB\nAAA\n")

        result = calculate_structure_rmsd(tmp_path, fasta_file)

        assert result is None


class TestCalculateAlignmentQualityMetrics:
    def test_identical_structures_score_perfect_tm_and_gdt(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        coords = [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [10.0, 0.0, 0.0]]
        _write_multi_model_pdb(pdb_file, [coords, coords])
        fasta_file.write_text(">structA\nAAA\n>structB\nAAA\n")

        result = calculate_alignment_quality_metrics(pdb_file, fasta_file)

        assert result is not None
        assert set(result.keys()) == {"structA", "structB"}
        assert result["structA"]["tm_score"] == pytest.approx(1.0)
        assert result["structA"]["gdt_ts"] == pytest.approx(1.0)

    def test_single_sequence_returns_none(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        _write_multi_model_pdb(pdb_file, [[[0.0, 0.0, 0.0]]])
        fasta_file.write_text(">only_one\nA\n")

        assert calculate_alignment_quality_metrics(pdb_file, fasta_file) is None

    def test_divergent_structure_scores_lower_than_identical_one(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        base = [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [10.0, 0.0, 0.0]]
        identical = base
        far = [[c[0] + 20, c[1], c[2]] for c in base]
        _write_multi_model_pdb(pdb_file, [base, identical, far])
        fasta_file.write_text(">reference\nAAA\n>close_copy\nAAA\n>far_copy\nAAA\n")

        result = calculate_alignment_quality_metrics(pdb_file, fasta_file)

        assert result is not None
        # Each structure's score is averaged across ALL other structures,
        # not just its best match - "reference" and "close_copy" each get
        # averaged against one identical partner and one very divergent
        # partner, while "far_copy" gets averaged against two divergent
        # partners, so far_copy's score should end up lower than both.
        assert result["far_copy"]["tm_score"] < result["close_copy"]["tm_score"]
        assert result["far_copy"]["tm_score"] < result["reference"]["tm_score"]
        assert result["reference"]["tm_score"] == pytest.approx(
            result["close_copy"]["tm_score"]
        )

    def test_falls_back_to_chains_when_pdb_uses_a_single_model(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        lines = ["MODEL     1"]
        for chain_id, coords in zip(
            "AB",
            (
                [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]],
            ),
        ):
            for i, (x, y, z) in enumerate(coords, start=1):
                lines.append(
                    f"ATOM  {i:5d}  CA  ALA {chain_id}{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
                )
        lines.append("ENDMDL")
        lines.append("END\n")
        pdb_file.write_text("\n".join(lines))
        fasta_file.write_text(">structA\nAA\n>structB\nAA\n")

        result = calculate_alignment_quality_metrics(pdb_file, fasta_file)

        assert result is not None
        assert result["structA"]["tm_score"] == pytest.approx(1.0)

    def test_no_common_columns_scores_zero_not_an_error(self, tmp_path):
        # Fully complementary gaps: no alignment column has both structures'
        # residues present, so there's nothing to compare - must degrade to
        # a zero score rather than raising.
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        coords = [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]]
        _write_multi_model_pdb(pdb_file, [coords, coords])
        fasta_file.write_text(">structA\nAA--\n>structB\n--AA\n")

        result = calculate_alignment_quality_metrics(pdb_file, fasta_file)

        assert result is not None
        assert result["structA"] == {"tm_score": 0.0, "gdt_ts": 0.0}

    def test_returns_none_on_parse_failure(self, tmp_path):
        fasta_file = tmp_path / "alignment.afasta"
        fasta_file.write_text(">structA\nAAA\n>structB\nAAA\n")

        result = calculate_alignment_quality_metrics(tmp_path, fasta_file)

        assert result is None
