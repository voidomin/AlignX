import os
import sqlite3
from datetime import datetime, timedelta
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


class TestAnnotationCache:
    """Tests for the annotation_cache table (see AnnotationAggregator's
    _get_or_fetch, which uses these two methods to avoid refetching
    InterPro/QuickGO/SIFTS/STRING/Reactome data for an accession someone
    already looked up recently)."""

    def test_round_trips_a_cached_value(self, db):
        db.set_annotation_cache("interpro:P01541", "interpro", '{"foo": "bar"}')
        assert db.get_annotation_cache("interpro:P01541") == '{"foo": "bar"}'

    def test_returns_none_on_cache_miss(self, db):
        assert db.get_annotation_cache("interpro:NOPE") is None

    def test_returns_none_for_expired_entries(self, db, tmp_path):
        db.set_annotation_cache("interpro:P01541", "interpro", '{"foo": "bar"}')

        # Backdate the cached_at timestamp past the TTL directly, since
        # set_annotation_cache always stamps "now".
        old_timestamp = (datetime.now() - timedelta(days=40)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        with sqlite3.connect(db.db_path) as conn:
            conn.execute(
                "UPDATE annotation_cache SET cached_at = ? WHERE cache_key = ?",
                (old_timestamp, "interpro:P01541"),
            )
            conn.commit()

        assert db.get_annotation_cache("interpro:P01541", max_age_days=30) is None

    def test_respects_custom_max_age(self, db, tmp_path):
        db.set_annotation_cache("interpro:P01541", "interpro", '{"foo": "bar"}')
        old_timestamp = (datetime.now() - timedelta(days=5)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        with sqlite3.connect(db.db_path) as conn:
            conn.execute(
                "UPDATE annotation_cache SET cached_at = ? WHERE cache_key = ?",
                (old_timestamp, "interpro:P01541"),
            )
            conn.commit()

        assert db.get_annotation_cache("interpro:P01541", max_age_days=30) is not None
        assert db.get_annotation_cache("interpro:P01541", max_age_days=1) is None

    def test_set_overwrites_existing_entry(self, db):
        db.set_annotation_cache("interpro:P01541", "interpro", '{"v": 1}')
        db.set_annotation_cache("interpro:P01541", "interpro", '{"v": 2}')
        assert db.get_annotation_cache("interpro:P01541") == '{"v": 2}'
