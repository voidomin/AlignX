import shutil

from streamlit.testing.v1 import AppTest


def _run(script, tmp_path, monkeypatch):
    shutil.copy("config.yaml", tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_string(script)
    at.run(timeout=60)
    return at


INIT = """
import streamlit as st
from src.utils.session_manager import SessionInitializer
SessionInitializer.initialize()
"""


class TestRenderPhyloTreeTab:
    def test_renders_without_exception_with_no_data(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "from src.frontend.tabs.phylo import render_phylo_tree_tab\n"
            + "render_phylo_tree_tab({})\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception

    def test_renders_ramachandran_plot_with_real_torsion_data(
        self, tmp_path, monkeypatch
    ):
        script = (
            INIT
            + "import pandas as pd\n"
            + "torsion = {\n"
            + '    "A": pd.DataFrame({\n'
            + '        "residue_id": [1, 2],\n'
            + '        "residue_name": ["ALA", "GLY"],\n'
            + '        "phi": [-60.0, -80.0],\n'
            + '        "psi": [-45.0, 130.0],\n'
            + '        "region": ["Favored (Alpha)", "Favored (Beta)"],\n'
            + "    })\n"
            + "}\n"
            + "from src.frontend.tabs.phylo import render_phylo_tree_tab\n"
            + 'render_phylo_tree_tab({"torsion_data": torsion, "pdb_ids": ["4RLT"]})\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception

    def test_renders_summary_metrics_when_stats_present(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "stats = {\n"
            + '    "favored_percent": 92.5,\n'
            + '    "outlier_count": 1,\n'
            + '    "total_residues": 100,\n'
            + '    "outliers_list": ["GLY35 (Chain A)"],\n'
            + "}\n"
            + "from src.frontend.tabs.phylo import render_phylo_tree_tab\n"
            + 'render_phylo_tree_tab({"ramachandran_stats": stats})\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("92.5%" in m.value for m in at.metric)
