import shutil

from streamlit.testing.v1 import AppTest

from src.frontend.tabs.structure import (
    _build_residue_colors,
    _build_residue_colors_from_scores,
    get_conservation_color,
    get_rmsf_color,
)


class TestGetConservationColor:
    def test_zero_is_cool_blue(self):
        assert get_conservation_color(0.0) == "#4a607a"

    def test_returns_hex_color_string_for_full_range(self):
        for v in (0.0, 0.25, 0.5, 0.75, 1.0):
            color = get_conservation_color(v)
            assert color.startswith("#")


class TestGetRmsfColor:
    def test_zero_flexibility_and_max_flexibility_differ(self):
        assert get_rmsf_color(0.0, 5.0) != get_rmsf_color(5.0, 5.0)


class TestBuildResidueColorsFromScores:
    def test_maps_non_gap_residues_only(self):
        sequences = {"s1": "AC-G"}
        scores = [1.0, 0.5, 0.0, 0.8]
        colors = _build_residue_colors_from_scores(sequences, scores, lambda s: f"c{s}")
        # 3 non-gap residues -> renumbered 1, 2, 3 (gap skipped)
        assert colors["A"] == {1: "c1.0", 2: "c0.5", 3: "c0.8"}


class TestBuildResidueColors:
    def test_conservation_density_uses_conservation_scores(self):
        results = {"sequences": {"s1": "AC"}, "conservation": [1.0, 0.0]}
        colors = _build_residue_colors("Conservation Density", results)
        assert colors is not None
        assert colors["A"][1] == get_conservation_color(1.0)

    def test_rmsf_flexibility_uses_rmsf_values(self):
        results = {"sequences": {"s1": "AC"}, "rmsf_values": [0.0, 5.0]}
        colors = _build_residue_colors("RMSF Flexibility", results)
        assert colors is not None

    def test_neon_pro_theme_returns_none(self):
        results = {"sequences": {"s1": "AC"}, "conservation": [1.0, 0.0]}
        assert _build_residue_colors("Neon Pro", results) is None

    def test_missing_sequences_returns_none(self):
        assert _build_residue_colors("Conservation Density", {}) is None


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

_PDB_TEXT = (
    "ATOM      1  CA  ALA A   1      11.000  10.000  10.000  1.00  0.00           C\n"
    "ATOM      2  CA  CYS A   2      12.000  10.000  10.000  1.00  0.00           C\n"
)


class TestRender3dViewerTab:
    def test_shows_unavailable_warning_when_no_alignment_pdb(
        self, tmp_path, monkeypatch
    ):
        script = (
            INIT
            + "from src.frontend.tabs.structure import render_3d_viewer_tab\n"
            + "render_3d_viewer_tab({})\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("not available" in w.value for w in at.warning)

    def test_shows_lazy_load_prompt_before_initializing(self, tmp_path, monkeypatch):
        pdb_path = tmp_path / "alignment.pdb"
        pdb_path.write_text(_PDB_TEXT)
        script = (
            INIT
            + "from pathlib import Path\n"
            + f'results = {{"alignment_pdb": Path(r"{pdb_path}")}}\n'
            + "from src.frontend.tabs.structure import render_3d_viewer_tab\n"
            + "render_3d_viewer_tab(results)\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("Initialize 3D Viewers" in b.label for b in at.button)

    def test_renders_superimposed_viewer_after_initializing(
        self, tmp_path, monkeypatch
    ):
        pdb_path = tmp_path / "alignment.pdb"
        pdb_path.write_text(_PDB_TEXT)
        script = (
            INIT
            + "from pathlib import Path\n"
            + "import pandas as pd\n"
            + f'results = {{"alignment_pdb": Path(r"{pdb_path}"), "rmsd_df": pd.DataFrame([[0.0]], index=["A"], columns=["A"])}}\n'
            + "st.session_state.show_3d_viewer = True\n"
            + "from src.frontend.tabs.structure import render_3d_viewer_tab\n"
            + "render_3d_viewer_tab(results)\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
