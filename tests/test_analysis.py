import shutil

from streamlit.testing.v1 import AppTest

INIT = """
import streamlit as st
from src.utils.session_manager import SessionInitializer
SessionInitializer.initialize()
"""


def _run(script, tmp_path, monkeypatch):
    shutil.copy("config.yaml", tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_string(script)
    at.run(timeout=60)
    return at


class TestRenderDashboard:
    def test_empty_state_renders_without_exception(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "from src.frontend.analysis import render_dashboard\nrender_dashboard()\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception

    def test_with_pdb_ids_no_results_renders_without_exception(
        self, tmp_path, monkeypatch
    ):
        script = (
            INIT
            + 'st.session_state.pdb_ids = ["4RLT", "3UG9"]\n'
            + "st.session_state.chain_info = {}\n"
            + "from src.frontend.analysis import render_dashboard\n"
            + "render_dashboard()\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception

    def test_with_results_shows_results_view(self, tmp_path, monkeypatch):
        script = (
            INIT
            + 'st.session_state.results = {"pdb_ids": ["4RLT", "3UG9"], "stats": {}}\n'
            + 'st.session_state.pdb_ids = ["4RLT", "3UG9"]\n'
            + "from src.frontend.analysis import render_dashboard\n"
            + "render_dashboard()\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception


class TestLoadRunFromHistory:
    def test_run_not_found_shows_error(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "from src.frontend.analysis import load_run_from_history\n"
            + 'load_run_from_history("nonexistent-run-id")\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("Run not found" in e.value for e in at.error)

    def test_run_not_found_is_silent_when_auto(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "from src.frontend.analysis import load_run_from_history\n"
            + 'load_run_from_history("nonexistent-run-id", is_auto=True)\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert len(at.error) == 0
