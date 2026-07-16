from unittest.mock import MagicMock

import pytest

from src.backend.result_manager import ResultManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results_dir = tmp_path / "results"
    mgr = ResultManager(results_dir)
    mgr.db = MagicMock()
    return mgr


def _write_rmsd_csv(path, proteins=("P1", "P2")):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "," + ",".join(proteins) + "\n"
    rows = "".join(
        f"{p}," + ",".join("0.0" if p == q else "1.0" for q in proteins) + "\n"
        for p in proteins
    )
    path.write_text(header + rows)


class TestListRuns:
    def test_includes_runs_with_existing_dir_and_matrix(self, manager, tmp_path):
        run_dir = tmp_path / "run1"
        _write_rmsd_csv(run_dir / "rmsd_matrix.csv")
        manager.db.get_all_runs.return_value = [
            {
                "id": "run1",
                "timestamp": "2026-01-01 00:00:00",
                "result_path": str(run_dir),
                "pdb_ids": ["P1", "P2"],
            }
        ]

        runs = manager.list_runs()

        assert len(runs) == 1
        assert runs[0]["id"] == "run1"
        assert runs[0]["protein_count"] == 2
        assert runs[0]["proteins"] == ["P1", "P2"]
        assert runs[0]["path"] == run_dir

    def test_skips_run_whose_directory_is_missing(self, manager, tmp_path):
        manager.db.get_all_runs.return_value = [
            {
                "id": "gone",
                "timestamp": "2026-01-01 00:00:00",
                "result_path": str(tmp_path / "does_not_exist"),
                "pdb_ids": ["P1"],
            }
        ]

        assert manager.list_runs() == []

    def test_skips_run_missing_rmsd_matrix(self, manager, tmp_path):
        run_dir = tmp_path / "run_no_matrix"
        run_dir.mkdir()
        manager.db.get_all_runs.return_value = [
            {
                "id": "run_no_matrix",
                "timestamp": "2026-01-01 00:00:00",
                "result_path": str(run_dir),
                "pdb_ids": ["P1"],
            }
        ]

        assert manager.list_runs() == []

    def test_passes_session_id_through_to_database(self, manager):
        manager.db.get_all_runs.return_value = []
        manager.list_runs(session_id="sess-1")
        manager.db.get_all_runs.assert_called_once_with(session_id="sess-1")


class TestGetRunRmsd:
    def test_loads_existing_matrix(self, manager, tmp_path):
        _write_rmsd_csv(tmp_path / "results" / "run1" / "rmsd_matrix.csv")

        df = manager.get_run_rmsd("run1")

        assert df is not None
        assert list(df.columns) == ["P1", "P2"]
        assert df.loc["P1", "P2"] == 1.0

    def test_returns_none_when_matrix_missing(self, manager):
        assert manager.get_run_rmsd("nope") is None

    def test_returns_none_on_read_failure(self, manager, tmp_path, monkeypatch):
        matrix_path = tmp_path / "results" / "run1" / "rmsd_matrix.csv"
        matrix_path.parent.mkdir(parents=True)
        matrix_path.write_text("garbage")
        monkeypatch.setattr(
            "src.backend.result_manager.pd.read_csv",
            MagicMock(side_effect=Exception("bad csv")),
        )

        assert manager.get_run_rmsd("run1") is None


class TestCalculateDifference:
    def test_returns_diff_for_overlapping_proteins(self, manager, tmp_path):
        _write_rmsd_csv(tmp_path / "results" / "run1" / "rmsd_matrix.csv", ("P1", "P2"))
        _write_rmsd_csv(tmp_path / "results" / "run2" / "rmsd_matrix.csv", ("P1", "P2"))

        diff = manager.calculate_difference("run1", "run2")

        assert diff is not None
        assert diff.loc["P1", "P2"] == pytest.approx(0.0)

    def test_returns_none_if_either_run_missing(self, manager, tmp_path):
        _write_rmsd_csv(tmp_path / "results" / "run1" / "rmsd_matrix.csv")

        assert manager.calculate_difference("run1", "does_not_exist") is None

    def test_returns_none_when_no_overlapping_proteins(self, manager, tmp_path):
        _write_rmsd_csv(tmp_path / "results" / "run1" / "rmsd_matrix.csv", ("P1", "P2"))
        _write_rmsd_csv(tmp_path / "results" / "run2" / "rmsd_matrix.csv", ("P3", "P4"))

        assert manager.calculate_difference("run1", "run2") is None


def _mock_run(run_id, timestamp, proteins, result_path):
    return {
        "id": run_id,
        "timestamp": timestamp,
        "result_path": str(result_path),
        "pdb_ids": list(proteins),
    }


class TestGetRunTrend:
    def test_computes_mean_and_max_rmsd_sorted_by_timestamp(self, manager, tmp_path):
        run1_dir = tmp_path / "results" / "run1"
        run2_dir = tmp_path / "results" / "run2"
        _write_rmsd_csv(run1_dir / "rmsd_matrix.csv", ("P1", "P2"))
        _write_rmsd_csv(run2_dir / "rmsd_matrix.csv", ("P1", "P2"))
        manager.db.get_all_runs.return_value = [
            _mock_run("run2", "2026-02-01 00:00:00", ("P1", "P2"), run2_dir),
            _mock_run("run1", "2026-01-01 00:00:00", ("P1", "P2"), run1_dir),
        ]

        trend = manager.get_run_trend(["run1", "run2"])

        assert [t["run_id"] for t in trend] == ["run1", "run2"]
        assert trend[0]["mean_rmsd"] == pytest.approx(1.0)
        assert trend[0]["max_rmsd"] == pytest.approx(1.0)
        assert trend[0]["proteins"] == ["P1", "P2"]

    def test_skips_a_run_id_that_does_not_resolve(self, manager, tmp_path):
        run1_dir = tmp_path / "results" / "run1"
        _write_rmsd_csv(run1_dir / "rmsd_matrix.csv")
        manager.db.get_all_runs.return_value = [
            _mock_run("run1", "2026-01-01 00:00:00", ("P1", "P2"), run1_dir),
        ]

        trend = manager.get_run_trend(["run1", "does_not_exist"])

        assert len(trend) == 1
        assert trend[0]["run_id"] == "run1"

    def test_returns_empty_list_when_nothing_resolves(self, manager):
        manager.db.get_all_runs.return_value = []
        assert manager.get_run_trend(["nope"]) == []
