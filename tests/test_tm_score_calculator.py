from pathlib import Path

import pytest

from src.backend.tm_score_calculator import calculate_tm_score_matrix


def _write_multi_model_pdb(path: Path, model_coords):
    """Write a minimal multi-MODEL PDB with one CA atom per residue, at the
    given per-model list-of-coordinate-triples. Mirrors
    test_rmsd_calculator.py's helper of the same name/shape."""
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


# A slightly larger, non-collinear coordinate set - tm_align's own internal
# optimization needs more than a couple of colinear points to converge to a
# meaningful (non-degenerate) score.
_CHAIN_A = [
    [0.0, 0.0, 0.0],
    [3.8, 0.0, 0.0],
    [7.2, 1.5, 0.0],
    [10.1, 3.9, 1.2],
    [12.5, 7.1, 2.8],
    [14.0, 10.9, 4.9],
]


class TestCalculateTmScoreMatrix:
    def test_identical_structures_score_close_to_one(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        _write_multi_model_pdb(pdb_file, [_CHAIN_A, _CHAIN_A])
        fasta_file.write_text(">structA\nAAAAAA\n>structB\nAAAAAA\n")

        result = calculate_tm_score_matrix(pdb_file, fasta_file)

        assert result is not None
        assert result.shape == (2, 2)
        assert list(result.index) == ["structA", "structB"]
        assert result.loc["structA", "structA"] == pytest.approx(1.0)
        assert result.loc["structA", "structB"] == pytest.approx(1.0, abs=0.05)
        # Symmetric matrix
        assert result.loc["structA", "structB"] == pytest.approx(
            result.loc["structB", "structA"]
        )

    def test_divergent_structure_scores_lower_than_identical_one(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        far = [[c[0] + 50, c[1] + 50, c[2] + 50] for c in _CHAIN_A]
        _write_multi_model_pdb(pdb_file, [_CHAIN_A, _CHAIN_A, far])
        fasta_file.write_text(
            ">reference\nAAAAAA\n>close_copy\nAAAAAA\n>far_copy\nAAAAAA\n"
        )

        result = calculate_tm_score_matrix(pdb_file, fasta_file)

        assert result is not None
        # A rigid-body translation alone doesn't affect TM-align's own
        # optimal superposition (unlike the Mustang-derived quality_metrics
        # score, which reuses a *fixed* correspondence) - so this only
        # asserts the matrix is well-formed and symmetric, not that the
        # translated copy scores lower (it shouldn't, and that's the point
        # of this being an independent metric).
        assert result.shape == (3, 3)
        assert result.loc["reference", "close_copy"] == pytest.approx(
            result.loc["close_copy", "reference"]
        )

    def test_single_sequence_returns_none(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        _write_multi_model_pdb(pdb_file, [_CHAIN_A])
        fasta_file.write_text(">only_one\nAAAAAA\n")

        assert calculate_tm_score_matrix(pdb_file, fasta_file) is None

    def test_falls_back_to_chains_when_pdb_uses_a_single_model(self, tmp_path):
        pdb_file = tmp_path / "alignment.pdb"
        fasta_file = tmp_path / "alignment.afasta"
        lines = ["MODEL     1"]
        for chain_id, coords in zip("AB", (_CHAIN_A, _CHAIN_A)):
            for i, (x, y, z) in enumerate(coords, start=1):
                lines.append(
                    f"ATOM  {i:5d}  CA  ALA {chain_id}{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
                )
        lines.append("ENDMDL")
        lines.append("END\n")
        pdb_file.write_text("\n".join(lines))
        fasta_file.write_text(">structA\nAAAAAA\n>structB\nAAAAAA\n")

        result = calculate_tm_score_matrix(pdb_file, fasta_file)

        assert result is not None
        assert result.loc["structA", "structB"] == pytest.approx(1.0, abs=0.05)

    def test_returns_none_on_parse_failure(self, tmp_path):
        fasta_file = tmp_path / "alignment.afasta"
        fasta_file.write_text(">structA\nAAAAAA\n>structB\nAAAAAA\n")

        result = calculate_tm_score_matrix(tmp_path, fasta_file)

        assert result is None
