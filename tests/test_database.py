import os
from pathlib import Path

import pytest

from src.backend.database import HistoryDatabase


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_history.db"
    return HistoryDatabase(str(db_path))


def test_get_aggregate_stats_sums_proteins_across_runs(db):
    """total_proteins_analyzed must be the sum of pdb_ids length across every
    saved run, not just the run count."""
    db.save_run("run_1", "Run 1", ["4RLT", "3UG9"], Path("results/run_1"))
    db.save_run("run_2", "Run 2", ["1L2Y", "3UG9", "4RLT"], Path("results/run_2"))

    stats = db.get_aggregate_stats()

    assert stats["total_runs"] == 2
    assert stats["total_proteins_analyzed"] == 5
    assert stats["cache_size_mb"] == 0.0


def test_get_aggregate_stats_empty_db_returns_zeros(db):
    stats = db.get_aggregate_stats()
    assert stats == {"total_runs": 0, "total_proteins_analyzed": 0, "cache_size_mb": 0.0}


def test_get_aggregate_stats_scoped_to_session(db):
    db.save_run("run_1", "Run 1", ["4RLT", "3UG9"], Path("results/run_1"), session_id="s1")
    db.save_run("run_2", "Run 2", ["1L2Y"], Path("results/run_2"), session_id="s2")

    stats = db.get_aggregate_stats(session_id="s1")

    assert stats["total_runs"] == 1
    assert stats["total_proteins_analyzed"] == 2
