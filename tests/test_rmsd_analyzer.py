"""Tests for RMSDAnalyzer module."""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.backend.rmsd_analyzer import RMSDAnalyzer


@pytest.fixture
def analyzer(mock_config):
    """Create an RMSDAnalyzer instance with test config."""
    mock_config['visualization'] = {'dpi': 72, 'heatmap_colormap': 'RdYlBu_r'}
    return RMSDAnalyzer(mock_config)


@pytest.fixture
def sample_rmsd_df():
    """Create a sample symmetric RMSD matrix."""
    labels = ['1A6M', '4HHB', '1L2Y']
    data = np.array([
        [0.0, 1.5, 4.2],
        [1.5, 0.0, 3.8],
        [4.2, 3.8, 0.0],
    ])
    return pd.DataFrame(data, index=labels, columns=labels)


class TestRMSDAnalyzerStatistics:
    """Tests for calculate_statistics."""

    def test_basic_statistics(self, analyzer, sample_rmsd_df):
        """Test that statistics are calculated correctly."""
        stats = analyzer.calculate_statistics(sample_rmsd_df)

        assert 'mean_rmsd' in stats
        assert 'median_rmsd' in stats
        assert 'min_rmsd' in stats
        assert 'max_rmsd' in stats
        assert 'std_rmsd' in stats

    def test_statistics_values(self, analyzer, sample_rmsd_df):
        """Test statistics values against manual calculation."""
        stats = analyzer.calculate_statistics(sample_rmsd_df)

        # Upper triangle values: 1.5, 4.2, 3.8
        expected_mean = np.mean([1.5, 4.2, 3.8])
        assert abs(stats['mean_rmsd'] - expected_mean) < 0.1

    def test_min_max(self, analyzer, sample_rmsd_df):
        """Test min/max RMSD extraction."""
        stats = analyzer.calculate_statistics(sample_rmsd_df)
        assert stats['min_rmsd'] == pytest.approx(1.5, abs=0.01)
        assert stats['max_rmsd'] == pytest.approx(4.2, abs=0.01)


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
        assert set(all_members) == {'1A6M', '4HHB', '1L2Y'}


class TestRMSDAnalyzerHeatmap:
    """Tests for heatmap generation."""

    def test_heatmap_creates_file(self, analyzer, sample_rmsd_df, tmp_path):
        """Test that generate_heatmap creates an image file."""
        output = tmp_path / "heatmap.png"
        result = analyzer.generate_heatmap(sample_rmsd_df, output)
        assert result is True
        assert output.exists()
        assert output.stat().st_size > 0

    def test_plotly_heatmap_returns_figure(self, analyzer, sample_rmsd_df):
        """Test that generate_plotly_heatmap returns a Plotly figure."""
        fig = analyzer.generate_plotly_heatmap(sample_rmsd_df)
        assert fig is not None


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
        first_line = content.strip().split('\n')[0].strip()
        assert first_line == '3'
