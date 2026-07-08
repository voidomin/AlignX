import shutil

from streamlit.testing.v1 import AppTest


def _run_page(tmp_path, monkeypatch):
    shutil.copy("config.yaml", tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(str(_page_path()))
    at.run(timeout=60)
    return at


def _page_path():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent / "pages" / "2_Mission_History.py"


class TestRenderHistoryPage:
    def test_renders_without_exception_with_no_runs(self, tmp_path, monkeypatch):
        at = _run_page(tmp_path, monkeypatch)
        assert not at.exception
        assert any("No mission history found" in i.value for i in at.info)

    def test_renders_runs_table_when_history_exists(self, tmp_path, monkeypatch):
        from src.backend.database import HistoryDatabase

        fake_runs = [
            {
                "id": "run_1",
                "timestamp": "2026-01-01 12:00:00",
                "pdb_ids": ["4RLT", "3UG9"],
            }
        ]
        monkeypatch.setattr(
            HistoryDatabase, "get_all_runs", lambda self, limit=20: fake_runs
        )

        at = _run_page(tmp_path, monkeypatch)
        assert not at.exception
        assert any("Past Runs" in s.value for s in at.subheader)
        assert any("Quick Stats" in s.value for s in at.subheader)
