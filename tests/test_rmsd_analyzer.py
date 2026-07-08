"""Tests for RMSDAnalyzer module."""

import pytest
import numpy as np
import pandas as pd

from src.backend.rmsd_analyzer import RMSDAnalyzer


@pytest.fixture
def analyzer(mock_config):
    """Create an RMSDAnalyzer instance with test config."""
    mock_config["visualization"] = {"dpi": 72, "heatmap_colormap": "RdYlBu_r"}
    return RMSDAnalyzer(mock_config)


@pytest.fixture
def sample_rmsd_df():
    """Create a sample symmetric RMSD matrix."""
    labels = ["1A6M", "4HHB", "1L2Y"]
    data = np.array(
        [
            [0.0, 1.5, 4.2],
            [1.5, 0.0, 3.8],
            [4.2, 3.8, 0.0],
        ]
    )
    return pd.DataFrame(data, index=labels, columns=labels)


class TestRMSDAnalyzerStatistics:
    """Tests for calculate_statistics."""

    def test_basic_statistics(self, analyzer, sample_rmsd_df):
        """Test that statistics are calculated correctly."""
        stats = analyzer.calculate_statistics(sample_rmsd_df)

        assert "mean_rmsd" in stats
        assert "median_rmsd" in stats
        assert "min_rmsd" in stats
        assert "max_rmsd" in stats
        assert "std_rmsd" in stats

    def test_statistics_values(self, analyzer, sample_rmsd_df):
        """Test statistics values against manual calculation."""
        stats = analyzer.calculate_statistics(sample_rmsd_df)

        # Upper triangle values: 1.5, 4.2, 3.8
        expected_mean = np.mean([1.5, 4.2, 3.8])
        assert abs(stats["mean_rmsd"] - expected_mean) < 0.1

    def test_min_max(self, analyzer, sample_rmsd_df):
        """Test min/max RMSD extraction."""
        stats = analyzer.calculate_statistics(sample_rmsd_df)
        assert stats["min_rmsd"] == pytest.approx(1.5, abs=0.01)
        assert stats["max_rmsd"] == pytest.approx(4.2, abs=0.01)


class TestRMSDAnalyzerClusters:
    """Tests for identify_clusters."""

    def test_single_cluster(self, analyzer, sample_rmsd_df):
        """All structures in one cluster at high threshold."""
        clusters = analyzer.identify_clusters(sample_rmsd_df, threshold=10.0)
        assert len(clusters) == 1

    def test_multiple_clusters(self, analyzer, sample_rmsd_df):
        """Structures split into clusters at low threshold."""
        clusters = analyzer.identify_clusters(sample_rmsd_df, threshold=2.0)
        # 1A6M and 4HHB (1.5 Å) should cluster, 1L2Y separate
        assert len(clusters) >= 2

    def test_cluster_contents(self, analyzer, sample_rmsd_df):
        """Verify cluster membership."""
        clusters = analyzer.identify_clusters(sample_rmsd_df, threshold=2.0)
        # Flatten all members
        all_members = [m for members in clusters.values() for m in members]
        assert set(all_members) == {"1A6M", "4HHB", "1L2Y"}


class TestRMSDAnalyzerHeatmap:
    """Tests for heatmap generation."""

    def test_heatmap_creates_file(self, analyzer, sample_rmsd_df, tmp_path):
        """Test that generate_heatmap creates an image file."""
        output = tmp_path / "heatmap.png"
        result = analyzer.generate_heatmap(sample_rmsd_df, output)
        assert result is True
        assert output.exists()
        assert output.stat().st_size > 0

    def test_heatmap_returns_false_on_failure(self, analyzer, sample_rmsd_df, tmp_path):
        # A path inside a nonexistent directory can't be saved to.
        bad_output = tmp_path / "no_such_dir" / "heatmap.png"
        assert analyzer.generate_heatmap(sample_rmsd_df, bad_output) is False

    def test_plotly_heatmap_returns_figure(self, analyzer, sample_rmsd_df):
        """Test that generate_plotly_heatmap returns a Plotly figure."""
        fig = analyzer.generate_plotly_heatmap(sample_rmsd_df)
        assert fig is not None

    def test_plotly_heatmap_returns_none_on_failure(self, analyzer):
        assert analyzer.generate_plotly_heatmap(None) is None


class TestRMSDAnalyzerExport:
    """Tests for export_to_phylip."""

    def test_phylip_export(self, analyzer, sample_rmsd_df, tmp_path):
        """Test Phylip format export."""
        output = tmp_path / "matrix.phy"
        result = analyzer.export_to_phylip(sample_rmsd_df, output)
        assert result is True
        assert output.exists()

        content = output.read_text()
        # First line should be the count
        first_line = content.strip().split("\n")[0].strip()
        assert first_line == "3"

    def test_phylip_export_returns_false_on_failure(
        self, analyzer, sample_rmsd_df, tmp_path
    ):
        bad_output = tmp_path / "no_such_dir" / "matrix.phy"
        assert analyzer.export_to_phylip(sample_rmsd_df, bad_output) is False


def _rmsf_atom_line(serial, name, resname, chain, resi, x, y, z):
    name_field = f" {name:<3}"
    element = name.strip()[0]
    return (
        f"ATOM  {serial:>5} {name_field} {resname:>3} {chain}{resi:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.00:6.2f}"
        f"{'':>10}{element:>2}"
    )


class TestCalculateResidueRmsf:
    """calculate_residue_rmsf's real end-to-end path against a hand-built
    2-structure/1-gap fixture, with hand-computed expected RMSF values -
    exercises _parse_afasta_sequences, _build_structure_maps,
    _parse_ca_coords, and _rmsf_for_column together."""

    def test_computes_expected_rmsf_per_column_with_a_gap(self, analyzer, tmp_path):
        afasta = tmp_path / "alignment.afasta"
        afasta.write_text(">structA\nAAAA\n>structB\nA-AA\n")

        # structA: 4 residues, all at origin.
        # structB: 3 residues (gapped at column 1) - column 0 and 3 match
        # structA exactly (RMSF 0), column 2 is offset by 3.0 along z
        # (RMSF = sqrt(mean((±1.5)^2)) = 1.5), column 1 has only structA's
        # atom (fewer than 2 points -> RMSF 0 by definition).
        lines = [
            _rmsf_atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
            _rmsf_atom_line(2, "CA", "ALA", "A", 2, 0.0, 0.0, 0.0),
            _rmsf_atom_line(3, "CA", "ALA", "A", 3, 0.0, 0.0, 0.0),
            _rmsf_atom_line(4, "CA", "ALA", "A", 4, 0.0, 0.0, 0.0),
            _rmsf_atom_line(5, "CA", "ALA", "B", 1, 0.0, 0.0, 0.0),
            _rmsf_atom_line(6, "CA", "ALA", "B", 2, 0.0, 0.0, 3.0),
            _rmsf_atom_line(7, "CA", "ALA", "B", 3, 0.0, 0.0, 0.0),
        ]
        alignment_pdb = tmp_path / "alignment.pdb"
        alignment_pdb.write_text("\n".join(lines) + "\n")

        rmsf_values, labels = analyzer.calculate_residue_rmsf(alignment_pdb, afasta)

        assert labels == ["structA", "structB"]
        assert rmsf_values == pytest.approx([0.0, 0.0, 1.5, 0.0])

    def test_empty_afasta_returns_empty_lists(self, analyzer, tmp_path):
        afasta = tmp_path / "alignment.afasta"
        afasta.write_text("")
        alignment_pdb = tmp_path / "alignment.pdb"
        alignment_pdb.write_text("")

        rmsf_values, labels = analyzer.calculate_residue_rmsf(alignment_pdb, afasta)

        assert rmsf_values == []
        assert labels == []

    def test_returns_empty_lists_on_parse_failure(self, analyzer, tmp_path):
        afasta = tmp_path / "alignment.afasta"
        afasta.write_text(">structA\nAAAA\n>structB\nAAAA\n")

        rmsf_values, labels = analyzer.calculate_residue_rmsf(
            tmp_path / "does_not_exist.pdb", afasta
        )

        assert rmsf_values == []
        assert labels == []
