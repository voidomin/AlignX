from pathlib import Path

from src.backend.flexibility_calculator import calculate_gnm_flexibility


def _write_pdb(path: Path, coords, b_factors=None, chain_id="A"):
    """A minimal single-MODEL, single-chain PDB with one CA atom per
    residue - same shape test_tm_score_calculator.py's _write_single_model_pdb
    uses, extended with a per-residue B-factor column since this module
    reads that back off the parsed structure."""
    if b_factors is None:
        b_factors = [0.0] * len(coords)
    lines = []
    for i, ((x, y, z), b) in enumerate(zip(coords, b_factors), start=1):
        lines.append(
            f"ATOM  {i:5d}  CA  ALA {chain_id}{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00{b:6.2f}           C"
        )
    lines.append("END\n")
    path.write_text("\n".join(lines))


# A straight 15-residue CA chain at standard ~3.8 A spacing - long enough
# that the default 10 A cutoff connects each residue to several neighbors
# on each side, giving the network enough structure for a real (not
# degenerate) GNM prediction.
_CHAIN_15 = [[i * 3.8, 0.0, 0.0] for i in range(15)]


class TestCalculateGnmFlexibility:
    def test_returns_none_for_fewer_than_three_residues(self, tmp_path):
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(pdb_file, [[0.0, 0.0, 0.0], [3.8, 0.0, 0.0]])

        result = calculate_gnm_flexibility(pdb_file)

        assert result is None

    def test_returns_none_on_parse_failure(self, tmp_path):
        result = calculate_gnm_flexibility(tmp_path / "does_not_exist.pdb")
        assert result is None

    def test_returns_a_flexibility_score_per_residue_normalized_0_to_1(self, tmp_path):
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(pdb_file, _CHAIN_15)

        result = calculate_gnm_flexibility(pdb_file)

        assert result is not None
        assert len(result["residue_numbers"]) == 15
        assert len(result["flexibility"]) == 15
        assert result["residue_numbers"] == list(range(1, 16))
        assert min(result["flexibility"]) == 0.0
        assert max(result["flexibility"]) == 1.0
        assert all(0.0 <= f <= 1.0 for f in result["flexibility"])

    def test_terminal_residues_are_predicted_more_flexible_than_the_middle(
        self, tmp_path
    ):
        # The standard, well-documented GNM result: a chain terminus has
        # fewer within-cutoff neighbors than an interior residue, so its
        # predicted mean-square fluctuation is higher - a real sanity
        # check on the computation, not just "it returns something."
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(pdb_file, _CHAIN_15)

        result = calculate_gnm_flexibility(pdb_file)

        flexibility = result["flexibility"]
        middle = flexibility[len(flexibility) // 2]
        assert flexibility[0] > middle
        assert flexibility[-1] > middle

    def test_b_factor_is_none_when_the_structure_carries_no_real_values(self, tmp_path):
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(pdb_file, _CHAIN_15, b_factors=[0.0] * 15)

        result = calculate_gnm_flexibility(pdb_file)

        assert result["b_factor"] is None

    def test_b_factor_is_returned_when_the_structure_carries_real_values(
        self, tmp_path
    ):
        pdb_file = tmp_path / "structure.pdb"
        real_b_factors = [20.0 + i for i in range(15)]
        _write_pdb(pdb_file, _CHAIN_15, b_factors=real_b_factors)

        result = calculate_gnm_flexibility(pdb_file)

        assert result["b_factor"] == real_b_factors

    def test_a_denser_cutoff_still_produces_a_valid_result(self, tmp_path):
        pdb_file = tmp_path / "structure.pdb"
        _write_pdb(pdb_file, _CHAIN_15)

        result = calculate_gnm_flexibility(pdb_file, cutoff_angstrom=20.0)

        assert result is not None
        assert len(result["flexibility"]) == 15
