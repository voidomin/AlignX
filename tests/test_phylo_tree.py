import matplotlib

# generate_tree() lazily imports matplotlib.pyplot without forcing a backend.
# In the real app this is harmless because src/backend/api.py always sets
# Agg first. Run standalone (as this file does), matplotlib instead probes
# for a GUI backend, which intermittently fails on this Windows venv with a
# broken Tk/Tcl install ("Can't find a usable init.tcl"). Force the same
# non-interactive backend the app relies on so this test file behaves the
# same in isolation as it does as part of the full suite.
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from src.backend.phylo_tree import PhyloTreeGenerator


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    matplotlib.pyplot.close("all")


@pytest.fixture
def generator(mock_config):
    return PhyloTreeGenerator(mock_config)


@pytest.fixture
def sample_rmsd_df():
    labels = ["1A6M", "4HHB", "1L2Y"]
    data = np.array(
        [
            [0.0, 1.5, 4.2],
            [1.5, 0.0, 3.8],
            [4.2, 3.8, 0.0],
        ]
    )
    return pd.DataFrame(data, index=labels, columns=labels)


class TestGenerateTree:
    def test_creates_a_real_image_file(self, generator, sample_rmsd_df, tmp_path):
        output = tmp_path / "tree.png"
        success, msg, path = generator.generate_tree(sample_rmsd_df, output)

        assert success is True
        assert path == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_creates_missing_parent_directories(
        self, generator, sample_rmsd_df, tmp_path
    ):
        output = tmp_path / "nested" / "dir" / "tree.png"
        success, _, path = generator.generate_tree(sample_rmsd_df, output)

        assert success is True
        assert path.exists()

    def test_returns_failure_on_malformed_input(self, generator, tmp_path):
        bad_df = pd.DataFrame([[1, 2], [3, 4]])  # not a valid distance matrix
        success, msg, path = generator.generate_tree(bad_df, tmp_path / "tree.png")

        assert success is False
        assert path is None
        assert "failed" in msg.lower()


class TestExportNewick:
    def test_writes_a_valid_newick_file(self, generator, sample_rmsd_df, tmp_path):
        output = tmp_path / "tree.nwk"
        success, msg, path = generator.export_newick(sample_rmsd_df, output)

        assert success is True
        assert path == output
        content = output.read_text()
        assert content.endswith(";")
        # All three leaf labels must appear somewhere in the tree structure.
        for label in sample_rmsd_df.index:
            assert label in content

    def test_creates_missing_parent_directories(
        self, generator, sample_rmsd_df, tmp_path
    ):
        output = tmp_path / "nested" / "dir" / "tree.nwk"
        success, _, path = generator.export_newick(sample_rmsd_df, output)

        assert success is True
        assert path.exists()

    def test_returns_failure_on_malformed_input(self, generator, tmp_path):
        bad_df = pd.DataFrame([[1, 2], [3, 4]])
        success, msg, path = generator.export_newick(bad_df, tmp_path / "tree.nwk")

        assert success is False
        assert path is None


class TestLinkageToNewick:
    def test_two_leaf_tree(self, generator):
        # A single merge event joining leaf 0 and leaf 1 at distance 2.0.
        linkage_matrix = np.array([[0.0, 1.0, 2.0, 2.0]])
        newick = generator._linkage_to_newick(linkage_matrix, ["A", "B"])

        assert newick == "(A:1.0000,B:1.0000)"

    def test_three_leaf_tree_nests_correctly(self, generator):
        # Leaves 0,1 merge first (dist 1.0), then that cluster (id=3) merges
        # with leaf 2 (dist 3.0).
        linkage_matrix = np.array(
            [
                [0.0, 1.0, 1.0, 2.0],
                [2.0, 3.0, 3.0, 3.0],
            ]
        )
        newick = generator._linkage_to_newick(linkage_matrix, ["A", "B", "C"])

        assert newick == "(C:1.5000,(A:0.5000,B:0.5000):1.5000)"


class TestGeneratePlotlyTree:
    def test_returns_a_figure_with_hoverinfo_set_on_every_trace(
        self, generator, sample_rmsd_df
    ):
        fig = generator.generate_plotly_tree(sample_rmsd_df)

        assert fig is not None
        assert len(fig["data"]) > 0
        for trace in fig["data"]:
            assert trace["hoverinfo"] == "y+x"

    def test_attempted_tolist_conversion_does_not_survive_serialization(
        self, generator, sample_rmsd_df
    ):
        """Documents a real, known Plotly quirk (see api.py's
        _decode_plotly_bdata docstring): assigning a plain list back to a
        trace's x/y property doesn't stick through to_plotly_json() -
        Plotly's own validators re-coerce it into the compact binary
        typed-array ("bdata") format regardless of what was assigned. This
        function's attempted fix is therefore a no-op in practice; the app
        stays correct only because sanitize_for_json's _decode_plotly_bdata
        step defensively decodes bdata for every API-returned figure."""
        fig = generator.generate_plotly_tree(sample_rmsd_df)

        serialized_x = fig.to_plotly_json()["data"][0]["x"]

        assert isinstance(serialized_x, dict)
        assert "bdata" in serialized_x

    def test_returns_none_on_malformed_input(self, generator):
        # A single-structure "matrix" has no pairwise distances to cluster.
        bad_df = pd.DataFrame([[0.0]], index=["A"], columns=["A"])
        assert generator.generate_plotly_tree(bad_df) is None
