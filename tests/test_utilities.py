import time
from unittest.mock import patch, MagicMock

from src.backend.utilities import SystemManager


class TestRunDiagnostics:
    @patch("subprocess.run")
    def test_detects_mustang_from_stderr_help_text(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="", stderr="MUSTANG v.3.2.3\nUsage: mustang -i ..."
        )
        manager = SystemManager()

        results = manager.run_diagnostics()

        assert results["Mustang"]["status"] == "PASSED"
        assert "3.2.3" in results["Mustang"]["version"]

    @patch("subprocess.run")
    def test_reports_failed_when_mustang_output_unrecognized(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", stderr="command not found")
        manager = SystemManager()

        results = manager.run_diagnostics()

        assert results["Mustang"]["status"] == "FAILED"

    @patch("subprocess.run", side_effect=FileNotFoundError("no such binary"))
    def test_reports_failed_without_raising_when_binary_missing(self, mock_run):
        manager = SystemManager()
        results = manager.run_diagnostics()
        assert results["Mustang"]["status"] == "FAILED"

    def test_always_includes_platform_and_python_version(self):
        manager = SystemManager()
        with patch("subprocess.run", side_effect=Exception("irrelevant")):
            results = manager.run_diagnostics()
        assert "Platform" in results
        assert "Python Version" in results


class TestCleanupOldRuns:
    def test_returns_empty_list_when_results_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        manager = SystemManager()
        assert manager.cleanup_old_runs(days=7) == []

    def test_deletes_run_dirs_older_than_threshold(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        session_dir = tmp_path / "results" / "session1"
        old_run = session_dir / "run_old"
        old_run.mkdir(parents=True)

        old_time = time.time() - (10 * 24 * 3600)  # 10 days ago
        import os

        os.utime(old_run, (old_time, old_time))

        manager = SystemManager()
        deleted = manager.cleanup_old_runs(days=7)

        assert "session1/run_old" in deleted
        assert not old_run.exists()

    def test_keeps_recent_run_dirs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        session_dir = tmp_path / "results" / "session1"
        recent_run = session_dir / "run_recent"
        recent_run.mkdir(parents=True)

        manager = SystemManager()
        deleted = manager.cleanup_old_runs(days=7)

        assert deleted == []
        assert recent_run.exists()

    def test_skips_legacy_top_level_run_prefixed_directories(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        legacy_dir = tmp_path / "results" / "run_legacy"
        legacy_dir.mkdir(parents=True)
        old_time = time.time() - (10 * 24 * 3600)
        import os

        os.utime(legacy_dir, (old_time, old_time))

        manager = SystemManager()
        deleted = manager.cleanup_old_runs(days=7)

        assert deleted == []
        assert legacy_dir.exists()

    def test_removes_session_dir_once_it_becomes_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        session_dir = tmp_path / "results" / "session1"
        old_run = session_dir / "run_old"
        old_run.mkdir(parents=True)
        old_time = time.time() - (10 * 24 * 3600)
        import os

        os.utime(old_run, (old_time, old_time))

        manager = SystemManager()
        manager.cleanup_old_runs(days=7)

        assert not session_dir.exists()

    def test_keeps_session_dir_if_other_runs_remain(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        session_dir = tmp_path / "results" / "session1"
        old_run = session_dir / "run_old"
        recent_run = session_dir / "run_recent"
        old_run.mkdir(parents=True)
        recent_run.mkdir(parents=True)
        old_time = time.time() - (10 * 24 * 3600)
        import os

        os.utime(old_run, (old_time, old_time))

        manager = SystemManager()
        manager.cleanup_old_runs(days=7)

        assert session_dir.exists()
        assert recent_run.exists()


class TestGetAggregateStats:
    def test_sums_runs_and_proteins(self):
        manager = SystemManager()
        fake_db = MagicMock()
        fake_db.get_all_runs.return_value = [
            {"pdb_ids": ["4RLT", "3UG9"]},
            {"pdb_ids": ["1CRN"]},
        ]

        stats = manager.get_aggregate_stats(fake_db)

        assert stats == {"total_runs": 2, "total_proteins": 3}

    def test_returns_zeros_without_raising_on_db_error(self):
        manager = SystemManager()
        fake_db = MagicMock()
        fake_db.get_all_runs.side_effect = Exception("db locked")

        stats = manager.get_aggregate_stats(fake_db)

        assert stats == {"total_runs": 0, "total_proteins": 0}

    def test_handles_runs_missing_pdb_ids_key(self):
        manager = SystemManager()
        fake_db = MagicMock()
        fake_db.get_all_runs.return_value = [{}]

        stats = manager.get_aggregate_stats(fake_db)

        assert stats == {"total_runs": 1, "total_proteins": 0}
