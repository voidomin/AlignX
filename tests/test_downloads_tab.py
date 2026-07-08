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

RENDER_EMPTY_RESULTS = """
from src.frontend.tabs.downloads import render_downloads_tab
render_downloads_tab({"id": "run_1"})
"""


class TestRenderDownloadsTab:
    def test_renders_without_exception_with_no_artifacts(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER_EMPTY_RESULTS, tmp_path, monkeypatch)
        assert not at.exception

    def test_shows_csv_download_when_rmsd_df_present(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "import pandas as pd\n"
            + 'st.session_state["_test_df"] = pd.DataFrame({"a": [1, 2]})\n'
            + "from src.frontend.tabs.downloads import render_downloads_tab\n"
            + 'render_downloads_tab({"id": "run_1", "rmsd_df": st.session_state["_test_df"]})\n'
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("Raw Data" in m.value for m in at.markdown)
