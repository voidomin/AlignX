import shutil

from streamlit.testing.v1 import AppTest

from src.frontend.components.input_section import _badge_style_for_id, _clean_id_list


class TestCleanIdList:
    def test_uppercases_standard_pdb_ids(self):
        assert _clean_id_list(["4rlt", "3ug9"]) == ["4RLT", "3UG9"]

    def test_preserves_alphafold_id_case(self):
        assert _clean_id_list(["af-p69905-f1"]) == ["af-p69905-f1"]

    def test_mixed_batch(self):
        assert _clean_id_list(["4rlt", "af-p69905-f1", "3UG9"]) == [
            "4RLT",
            "af-p69905-f1",
            "3UG9",
        ]


class TestBadgeStyleForId:
    def test_alphafold_id_is_valid(self):
        *_rest, is_valid = _badge_style_for_id("AF-P69905-F1")
        assert is_valid is True

    def test_four_char_alnum_is_valid_pdb(self):
        *_rest, is_valid = _badge_style_for_id("4RLT")
        assert is_valid is True

    def test_wrong_length_is_invalid(self):
        *_rest, is_valid = _badge_style_for_id("ABCDE")
        assert is_valid is False


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


class TestRenderInputSection:
    def test_renders_without_exception(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "from src.frontend.components.input_section import render_input_section\n"
            + "render_input_section(st.session_state.pdb_manager)\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception

    def test_entering_ids_updates_session_state_and_resets_metadata(
        self, tmp_path, monkeypatch
    ):
        script = (
            INIT
            + 'if "seeded" not in st.session_state:\n'
            + "    st.session_state.metadata_fetched = True\n"
            + '    st.session_state.metadata = {"stale": "data"}\n'
            + "    st.session_state.seeded = True\n"
            + "from src.frontend.components.input_section import render_input_section\n"
            + "render_input_section(st.session_state.pdb_manager)\n"
        )
        at = _run(script, tmp_path, monkeypatch)
        at.text_input(key="input_pdb_text_dashboard").set_value("4rlt, 3ug9").run()
        assert not at.exception
        st_state = at.session_state
        assert st_state["pdb_ids"] == ["4RLT", "3UG9"]
        assert st_state["metadata_fetched"] is False
        assert st_state["metadata"] == {}
