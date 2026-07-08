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
    assert stats["cache_size_mb"] == pytest.approx(0.0)


def test_get_aggregate_stats_empty_db_returns_zeros(db):
    stats = db.get_aggregate_stats()
    assert stats == {
        "total_runs": 0,
        "total_proteins_analyzed": 0,
        "cache_size_mb": 0.0,
    }


def test_get_aggregate_stats_scoped_to_session(db):
    db.save_run(
        "run_1", "Run 1", ["4RLT", "3UG9"], Path("results/run_1"), session_id="s1"
    )
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


class TestMigrationMemoization:
    """DiscoveryCoordinator/AnalysisCoordinator each construct their own
    HistoryDatabase() per job rather than sharing one instance, so under
    concurrent job submissions this constructor runs once per in-flight
    job - a real concurrency test (tests/test_concurrency.py) found that
    re-running the schema migration on every single construction measurably
    serializes concurrent job startup once the database file is large.
    HistoryDatabase._init_db() should only actually touch the database the
    first time a given db_path is seen in this process."""

    def test_second_construction_for_same_path_skips_init(self, tmp_path, monkeypatch):
        calls = []
        original_init_db = HistoryDatabase._init_db

        def spy_init_db(self):
            calls.append(self.db_path)
            return original_init_db(self)

        monkeypatch.setattr(HistoryDatabase, "_init_db", spy_init_db)

        db_path = str(tmp_path / "shared.db")
        HistoryDatabase(db_path)
        HistoryDatabase(db_path)
        HistoryDatabase(db_path)

        assert calls == [db_path]

    def test_different_paths_each_get_migrated_once(self, tmp_path, monkeypatch):
        calls = []
        original_init_db = HistoryDatabase._init_db

        def spy_init_db(self):
            calls.append(self.db_path)
            return original_init_db(self)

        monkeypatch.setattr(HistoryDatabase, "_init_db", spy_init_db)

        path_a = str(tmp_path / "a.db")
        path_b = str(tmp_path / "b.db")
        HistoryDatabase(path_a)
        HistoryDatabase(path_b)
        HistoryDatabase(path_a)

        assert calls == [path_a, path_b]

    def test_skipping_init_still_leaves_a_usable_database(self, tmp_path):
        db_path = str(tmp_path / "usable.db")
        HistoryDatabase(db_path)  # runs the real migration
        db = HistoryDatabase(db_path)  # skips it (memoized)

        db.save_run("run_1", "Run 1", ["4RLT"], Path("results/run_1"))
        assert db.get_aggregate_stats()["total_runs"] == 1


def _save_run_at(db, monkeypatch, when, *args, **kwargs):
    """save_run()'s timestamp column is second-granularity - two real saves
    in the same wall-clock second sort ambiguously. Freeze datetime.now()
    to a specific value so ordering tests aren't flaky/slow (sleeping a
    full second between saves)."""
    import src.backend.database as database_module

    real_datetime = database_module.datetime

    class FrozenDatetime:
        @classmethod
        def now(cls):
            return when

    monkeypatch.setattr(database_module, "datetime", FrozenDatetime)
    db.save_run(*args, **kwargs)
    monkeypatch.setattr(database_module, "datetime", real_datetime)


class TestRunCrud:
    def test_get_run_returns_the_saved_record(self, db):
        db.save_run(
            "run_1",
            "Run 1",
            ["4RLT", "3UG9"],
            Path("results/run_1"),
            metadata={"chain_selection": {"4RLT": "A"}},
        )

        run = db.get_run("run_1")

        assert run["id"] == "run_1"
        assert run["pdb_ids"] == ["4RLT", "3UG9"]
        assert run["metadata"]["chain_selection"] == {"4RLT": "A"}

    def test_get_run_returns_none_for_unknown_id(self, db):
        assert db.get_run("does_not_exist") is None

    def test_get_all_runs_sorted_newest_first(self, db, monkeypatch):
        _save_run_at(
            db,
            monkeypatch,
            datetime(2026, 1, 1, 10, 0, 0),
            "run_1",
            "Run 1",
            ["4RLT"],
            Path("results/run_1"),
        )
        _save_run_at(
            db,
            monkeypatch,
            datetime(2026, 1, 1, 10, 0, 1),
            "run_2",
            "Run 2",
            ["3UG9"],
            Path("results/run_2"),
        )

        runs = db.get_all_runs()

        assert [r["id"] for r in runs] == ["run_2", "run_1"]

    def test_get_all_runs_respects_limit_and_offset(self, db):
        for i in range(5):
            db.save_run(f"run_{i}", f"Run {i}", ["4RLT"], Path(f"results/run_{i}"))

        page = db.get_all_runs(limit=2, offset=1)

        assert len(page) == 2

    def test_get_all_runs_scoped_to_session(self, db):
        db.save_run("run_1", "Run 1", ["4RLT"], Path("results/run_1"), session_id="s1")
        db.save_run("run_2", "Run 2", ["3UG9"], Path("results/run_2"), session_id="s2")

        runs = db.get_all_runs(session_id="s1")

        assert [r["id"] for r in runs] == ["run_1"]

    def test_count_runs_matches_saved_count(self, db):
        db.save_run("run_1", "Run 1", ["4RLT"], Path("results/run_1"))
        db.save_run("run_2", "Run 2", ["3UG9"], Path("results/run_2"))

        assert db.count_runs() == 2

    def test_count_runs_scoped_to_session(self, db):
        db.save_run("run_1", "Run 1", ["4RLT"], Path("results/run_1"), session_id="s1")
        db.save_run("run_2", "Run 2", ["3UG9"], Path("results/run_2"), session_id="s2")

        assert db.count_runs(session_id="s1") == 1

    def test_delete_run_removes_it(self, db):
        db.save_run("run_1", "Run 1", ["4RLT"], Path("results/run_1"))

        assert db.delete_run("run_1") is True
        assert db.get_run("run_1") is None

    def test_get_latest_run_returns_the_newest_completed_one(self, db, monkeypatch):
        _save_run_at(
            db,
            monkeypatch,
            datetime(2026, 1, 1, 10, 0, 0),
            "run_1",
            "Run 1",
            ["4RLT"],
            Path("results/run_1"),
            status="completed",
        )
        _save_run_at(
            db,
            monkeypatch,
            datetime(2026, 1, 1, 10, 0, 1),
            "run_2",
            "Run 2",
            ["3UG9"],
            Path("results/run_2"),
            status="completed",
        )

        latest = db.get_latest_run()

        assert latest["id"] == "run_2"

    def test_get_latest_run_ignores_failed_runs(self, db):
        db.save_run(
            "run_1", "Run 1", ["4RLT"], Path("results/run_1"), status="completed"
        )
        db.save_run("run_2", "Run 2", ["3UG9"], Path("results/run_2"), status="failed")

        latest = db.get_latest_run()

        assert latest["id"] == "run_1"

    def test_get_latest_run_returns_none_when_no_runs_exist(self, db):
        assert db.get_latest_run() is None

    def test_get_latest_run_scoped_to_session_ignores_other_sessions(self, db):
        db.save_run(
            "run_1", "Run 1", ["4RLT"], Path("results/run_1"), session_id="sess-A"
        )
        db.save_run(
            "run_2", "Run 2", ["3UG9"], Path("results/run_2"), session_id="sess-B"
        )

        latest = db.get_latest_run(session_id="sess-A")

        assert latest["id"] == "run_1"

    def test_clear_all_runs_empties_the_table(self, db):
        db.save_run("run_1", "Run 1", ["4RLT"], Path("results/run_1"))
        db.save_run("run_2", "Run 2", ["3UG9"], Path("results/run_2"))

        assert db.clear_all_runs() is True
        assert db.count_runs() == 0


class TestCacheManagementMethods:
    def test_register_and_retrieve_cache_item(self, db):
        db.register_cache_item("4RLT", "/data/raw/4rlt.pdb", 1024)

        items = db.get_oldest_cache_items()

        assert len(items) == 1
        assert items[0]["id"] == "4RLT"
        assert items[0]["size_bytes"] == 1024

    def test_get_total_cache_size_sums_across_items(self, db):
        db.register_cache_item("4RLT", "/data/raw/4rlt.pdb", 1000)
        db.register_cache_item("3UG9", "/data/raw/3ug9.pdb", 2000)

        assert db.get_total_cache_size() == 3000

    def test_get_total_cache_size_is_zero_when_empty(self, db):
        assert db.get_total_cache_size() == 0

    def test_update_cache_access_does_not_raise_for_unknown_item(self, db):
        assert db.update_cache_access("does_not_exist") is True

    def test_remove_cache_item(self, db):
        db.register_cache_item("4RLT", "/data/raw/4rlt.pdb", 1024)

        assert db.remove_cache_item("4RLT") is True
        assert db.get_oldest_cache_items() == []

    def test_oldest_cache_items_ordered_oldest_first(self, db, monkeypatch):
        import src.backend.database as database_module

        real_datetime = database_module.datetime

        class FrozenDatetime:
            _now = real_datetime(2026, 1, 1, 10, 0, 0)

            @classmethod
            def now(cls):
                return cls._now

        monkeypatch.setattr(database_module, "datetime", FrozenDatetime)
        db.register_cache_item("old_item", "/data/old.pdb", 100)

        FrozenDatetime._now = real_datetime(2026, 1, 2, 10, 0, 0)
        db.register_cache_item("new_item", "/data/new.pdb", 200)

        items = db.get_oldest_cache_items()

        assert [i["id"] for i in items] == ["old_item", "new_item"]


class TestConnectionFailuresDegradeGracefully:
    """Every method wraps its sqlite3 calls in a try/except that logs and
    returns a safe default rather than raising - a bad db_path (parent
    directory doesn't exist, so sqlite3 can't even open/create the file)
    exercises that fallback uniformly across the whole class."""

    @pytest.fixture
    def unusable_db(self, tmp_path):
        bad_path = tmp_path / "no_such_dir" / "test_history.db"
        return HistoryDatabase(str(bad_path))

    def test_init_does_not_raise(self, tmp_path):
        bad_path = tmp_path / "no_such_dir" / "test_history.db"
        HistoryDatabase(str(bad_path))  # must not raise

    def test_save_run_returns_false(self, unusable_db):
        assert (
            unusable_db.save_run("run_1", "Run 1", ["4RLT"], Path("results/run_1"))
            is False
        )

    def test_get_all_runs_returns_empty_list(self, unusable_db):
        assert unusable_db.get_all_runs() == []

    def test_count_runs_returns_zero(self, unusable_db):
        assert unusable_db.count_runs() == 0

    def test_get_run_returns_none(self, unusable_db):
        assert unusable_db.get_run("run_1") is None

    def test_delete_run_returns_false(self, unusable_db):
        assert unusable_db.delete_run("run_1") is False

    def test_get_latest_run_returns_none(self, unusable_db):
        assert unusable_db.get_latest_run() is None

    def test_get_latest_run_scoped_to_session_returns_none(self, unusable_db):
        assert unusable_db.get_latest_run(session_id="sess-1") is None

    def test_clear_all_runs_returns_false(self, unusable_db):
        assert unusable_db.clear_all_runs() is False

    def test_register_cache_item_returns_false(self, unusable_db):
        assert unusable_db.register_cache_item("4RLT", "/x.pdb", 100) is False

    def test_update_cache_access_returns_false(self, unusable_db):
        assert unusable_db.update_cache_access("4RLT") is False

    def test_get_oldest_cache_items_returns_empty_list(self, unusable_db):
        assert unusable_db.get_oldest_cache_items() == []

    def test_remove_cache_item_returns_false(self, unusable_db):
        assert unusable_db.remove_cache_item("4RLT") is False

    def test_get_total_cache_size_returns_zero(self, unusable_db):
        assert unusable_db.get_total_cache_size() == 0

    def test_get_annotation_cache_returns_none(self, unusable_db):
        assert unusable_db.get_annotation_cache("key1") is None

    def test_set_annotation_cache_returns_false(self, unusable_db):
        assert unusable_db.set_annotation_cache("key1", "svc", "{}") is False


class TestLegacyDatabaseMigration:
    def test_adds_session_id_column_to_a_pre_existing_db(self, tmp_path):
        db_path = tmp_path / "legacy.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("""
                CREATE TABLE runs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    name TEXT,
                    pdb_ids TEXT NOT NULL,
                    status TEXT,
                    result_path TEXT,
                    metadata TEXT
                )
                """)
            conn.commit()

        db = HistoryDatabase(str(db_path))
        assert db.save_run(
            "run_1", "Run 1", ["4RLT"], Path("results/run_1"), session_id="sess-1"
        )
        assert db.get_all_runs(session_id="sess-1")[0]["id"] == "run_1"
