import shutil

from streamlit.testing.v1 import AppTest

INIT = """
import streamlit as st
from src.utils.session_manager import SessionInitializer
SessionInitializer.initialize()
"""

RENDER = """
from src.frontend.sidebar import render_sidebar
render_sidebar(lambda run_id: st.session_state.__setitem__("load_called", run_id))
"""


def _sidebar_button(at, label):
    return next(b for b in at.sidebar.button if b.label == label)


def _run(script, tmp_path, monkeypatch):
    shutil.copy("config.yaml", tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_string(script)
    at.run(timeout=60)
    return at


class TestRenderSidebarDefaultState:
    def test_renders_without_exception(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER, tmp_path, monkeypatch)
        assert not at.exception

    def test_mustang_failure_shows_error_and_setup_hint(self, tmp_path, monkeypatch):
        script = (
            INIT
            + 'st.session_state.mustang_install_status = (False, "Mustang not found")\n'
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("Mustang not found" in e.value for e in at.sidebar.error)

    def test_mustang_success_shows_success_message(self, tmp_path, monkeypatch):
        script = (
            INIT
            + 'st.session_state.mustang_install_status = (True, "Mustang 3.2.3")\n'
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("Mustang 3.2.3" in s.value for s in at.sidebar.success)

    def test_version_caption_reflects_config(self, tmp_path, monkeypatch):
        script = (
            INIT + 'st.session_state.config = {"app": {"version": "9.9.9"}}\n' + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("9.9.9" in c.value for c in at.sidebar.caption)


class TestSystemHealthDiagnostics:
    def test_run_diagnostics_populates_results(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER, tmp_path, monkeypatch)
        _sidebar_button(at, "🔍 Run Diagnostics").click().run(timeout=60)

        assert not at.exception
        assert "diag_results" in at.session_state

    def test_run_diagnostics_shows_passed_status_when_all_ok(
        self, tmp_path, monkeypatch
    ):
        script = (
            INIT
            + "class _FakeSystemManager:\n"
            + "    def run_diagnostics(self, mustang_executable=None):\n"
            + "        return {\n"
            + '            "Mustang": {"status": "PASSED", "version": "3.2.3"},\n'
            + '            "R environment": {"status": "PASSED"},\n'
            + '            "Platform": "Linux",\n'
            + '            "Python Version": "3.10",\n'
            + "        }\n"
            + "    def cleanup_old_runs(self, days=7):\n"
            + "        return []\n"
            + "st.session_state.system_manager = _FakeSystemManager()\n"
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        _sidebar_button(at, "🔍 Run Diagnostics").click().run(timeout=60)

        assert not at.exception
        oks = [s.value for s in at.sidebar.success if s.value == "OK"]
        assert len(oks) == 2

    def test_free_ram_button_does_not_error(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER, tmp_path, monkeypatch)
        _sidebar_button(at, "🧹 Free RAM").click().run(timeout=60)
        assert not at.exception

    def test_clear_logs_button_does_not_error(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER, tmp_path, monkeypatch)
        _sidebar_button(at, "🧹 Clear Logs").click().run(timeout=60)
        assert not at.exception


class TestSessionControlsSoftReset:
    def test_new_analysis_shows_confirmation(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER, tmp_path, monkeypatch)
        _sidebar_button(at, "🔄 New Analysis").click().run(timeout=60)

        assert not at.exception
        assert at.session_state["_confirm_reset"] is True
        assert any("clear your current results" in w.value for w in at.sidebar.warning)

    def test_confirming_reset_clears_results_and_flag(self, tmp_path, monkeypatch):
        script = (
            INIT
            + 'if "_test_seeded" not in st.session_state:\n'
            + '    st.session_state.pdb_ids = ["1ABC", "2XYZ"]\n'
            + "    st.session_state._test_seeded = True\n"
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        _sidebar_button(at, "🔄 New Analysis").click().run(timeout=60)
        _sidebar_button(at, "✅ Confirm").click().run(timeout=60)

        assert not at.exception
        assert at.session_state["pdb_ids"] == []
        assert at.session_state["_confirm_reset"] is False

    def test_confirming_reset_clears_zip_buffer_keys(self, tmp_path, monkeypatch):
        script = (
            INIT
            + 'if "_test_seeded" not in st.session_state:\n'
            + '    st.session_state.zip_buffer_run1 = b"fake-zip-bytes"\n'
            + "    st.session_state._test_seeded = True\n"
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        assert "zip_buffer_run1" in at.session_state

        _sidebar_button(at, "🔄 New Analysis").click().run(timeout=60)
        _sidebar_button(at, "✅ Confirm").click().run(timeout=60)

        assert not at.exception
        assert "zip_buffer_run1" not in at.session_state

    def test_cancelling_reset_leaves_results_untouched(self, tmp_path, monkeypatch):
        script = INIT + 'st.session_state.pdb_ids = ["1ABC"]\n' + RENDER
        at = _run(script, tmp_path, monkeypatch)
        _sidebar_button(at, "🔄 New Analysis").click().run(timeout=60)
        _sidebar_button(at, "❌ Cancel").click().run(timeout=60)

        assert not at.exception
        assert at.session_state["pdb_ids"] == ["1ABC"]
        assert at.session_state["_confirm_reset"] is False


class TestSessionControlsDeepClean:
    def test_clear_all_files_shows_confirmation(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER, tmp_path, monkeypatch)
        _sidebar_button(at, "🧹 Clear All Files").click().run(timeout=60)

        assert not at.exception
        assert at.session_state["_confirm_deep_clean"] is True
        assert any("delete all downloaded" in e.value for e in at.sidebar.error)

    def test_confirming_deep_clean_wipes_session_dirs(self, tmp_path, monkeypatch):
        script = INIT + RENDER
        at = _run(script, tmp_path, monkeypatch)
        session_id = at.session_state["session_id"]
        raw_dir = tmp_path / "data" / "raw" / session_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "structure.pdb").write_text("ATOM")

        _sidebar_button(at, "🧹 Clear All Files").click().run(timeout=60)
        _sidebar_button(at, "✅ Delete Files").click().run(timeout=60)

        assert not at.exception
        assert not raw_dir.exists()
        assert at.session_state["_confirm_deep_clean"] is False

    def test_cancelling_deep_clean_leaves_files_untouched(self, tmp_path, monkeypatch):
        script = INIT + RENDER
        at = _run(script, tmp_path, monkeypatch)
        session_id = at.session_state["session_id"]
        raw_dir = tmp_path / "data" / "raw" / session_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "structure.pdb").write_text("ATOM")

        _sidebar_button(at, "🧹 Clear All Files").click().run(timeout=60)
        at.sidebar.button(key="cancel_deep").click().run(timeout=60)

        assert not at.exception
        assert raw_dir.exists()
        assert at.session_state["_confirm_deep_clean"] is False


class TestHistoryPanel:
    FAKE_HISTORY_DB = """
if not hasattr(st.session_state.get("history_db"), "deleted"):
    class _FakeHistoryDB:
        def __init__(self):
            self.deleted = []
        def get_all_runs(self, limit=6, session_id=None):
            return [
                {"id": "run1", "name": "Run One", "pdb_ids": ["1ABC", "2XYZ", "3DEF", "4GHI"], "timestamp": "2026-01-01T00:00:00"},
                {"id": "run2", "name": "Run Two", "pdb_ids": ["5JKL"], "timestamp": "2026-01-02T00:00:00"},
            ]
        def delete_run(self, run_id):
            self.deleted.append(run_id)
    st.session_state.history_db = _FakeHistoryDB()
"""

    def test_no_runs_shows_placeholder(self, tmp_path, monkeypatch):
        script = (
            INIT
            + "class _EmptyDB:\n"
            + "    def get_all_runs(self, limit=6, session_id=None):\n"
            + "        return []\n"
            + "st.session_state.history_db = _EmptyDB()\n"
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert any("No saved runs yet" in i.value for i in at.sidebar.info)

    def test_runs_render_cards_with_preview_and_overflow_count(
        self, tmp_path, monkeypatch
    ):
        script = INIT + self.FAKE_HISTORY_DB + RENDER
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        combined = " ".join(m.value for m in at.sidebar.markdown)
        assert "Run One" in combined
        assert "+1 more" in combined  # 4 proteins, only first 3 previewed

    def test_load_button_invokes_callback_with_run_id(self, tmp_path, monkeypatch):
        script = INIT + self.FAKE_HISTORY_DB + RENDER
        at = _run(script, tmp_path, monkeypatch)
        at.sidebar.button(key="load_run1").click().run(timeout=60)

        assert not at.exception
        assert at.session_state["load_called"] == "run1"

    def test_delete_button_removes_single_run(self, tmp_path, monkeypatch):
        script = INIT + self.FAKE_HISTORY_DB + RENDER
        at = _run(script, tmp_path, monkeypatch)
        at.sidebar.button(key="del_run1").click().run(timeout=60)

        assert not at.exception
        assert at.session_state.history_db.deleted == ["run1"]

    def test_clear_all_history_deletes_every_run(self, tmp_path, monkeypatch):
        script = INIT + self.FAKE_HISTORY_DB + RENDER
        at = _run(script, tmp_path, monkeypatch)
        _sidebar_button(at, "🗑️ Clear All History").click().run(timeout=60)

        assert not at.exception
        assert set(at.session_state.history_db.deleted) == {"run1", "run2"}


class TestGuidedModeAndStructureOptions:
    def test_toggle_guided_mode(self, tmp_path, monkeypatch):
        at = _run(INIT + RENDER, tmp_path, monkeypatch)
        assert at.session_state["guided_mode"] is False

        at.sidebar.toggle[0].set_value(True).run(timeout=60)

        assert not at.exception
        assert at.session_state["guided_mode"] is True

    def test_multi_chain_detected_shows_warning_label(self, tmp_path, monkeypatch):
        script = (
            INIT
            + 'st.session_state.chain_info = {"P1": {"chains": ["A", "B"]}}\n'
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        labels = [e.label for e in at.sidebar.expander]
        assert any("⚠️" in label for label in labels)
        assert any(
            "Multi-chain structures detected" in c.value for c in at.sidebar.caption
        )

    def test_specify_chain_id_shows_text_input_and_updates_selection(
        self, tmp_path, monkeypatch
    ):
        script = (
            INIT
            + 'st.session_state.chain_selection_mode = "Specify chain ID"\n'
            + RENDER
        )
        at = _run(script, tmp_path, monkeypatch)
        assert not at.exception
        assert len(at.sidebar.text_input) == 1

        at.sidebar.text_input[0].set_value("b").run(timeout=60)

        assert not at.exception
        assert at.session_state["selected_chain"] == "B"
