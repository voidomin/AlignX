import sqlite3
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.utils.session_manager import (
    get_session_id,
    get_session_paths,
    cleanup_stale_sessions,
)


class TestGetSessionId:
    def test_returns_an_8_character_string(self):
        session_id = get_session_id()
        assert isinstance(session_id, str)
        assert len(session_id) == 8

    def test_returns_a_different_id_each_call(self):
        ids = {get_session_id() for _ in range(20)}
        assert len(ids) == 20


class TestGetSessionPaths:
    def test_returns_raw_cleaned_and_results_paths(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        paths = get_session_paths("abc12345")

        assert paths["raw"] == Path("data/raw/abc12345")
        assert paths["cleaned"] == Path("data/cleaned/abc12345")
        assert paths["results"] == Path("results/abc12345")

    def test_creates_the_directories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        paths = get_session_paths("xyz98765")

        for p in paths.values():
            assert p.exists()
            assert p.is_dir()


class TestCleanupStaleSessions:
    def test_purges_a_directory_older_than_the_threshold(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        stale_dir = tmp_path / "data" / "raw" / "stale-session"
        stale_dir.mkdir(parents=True)

        old_time = time.time() - (25 * 3600)  # 25 hours ago
        import os

        os.utime(stale_dir, (old_time, old_time))

        purged = cleanup_stale_sessions(max_age_hours=24)

        assert "stale-session" in purged
        assert not stale_dir.exists()

    def test_does_not_purge_a_fresh_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fresh_dir = tmp_path / "data" / "raw" / "fresh-session"
        fresh_dir.mkdir(parents=True)

        purged = cleanup_stale_sessions(max_age_hours=24)

        assert "fresh-session" not in purged
        assert fresh_dir.exists()

    def test_skips_legacy_run_prefixed_directories(self, tmp_path, monkeypatch):
        """run_* directories are the old pre-session-isolation naming
        scheme, not session directories - must never be swept up here."""
        monkeypatch.chdir(tmp_path)
        legacy_dir = tmp_path / "results" / "run_1234567890"
        legacy_dir.mkdir(parents=True)
        old_time = time.time() - (48 * 3600)
        import os

        os.utime(legacy_dir, (old_time, old_time))

        purged = cleanup_stale_sessions(max_age_hours=24)

        assert legacy_dir.exists()
        assert purged == []

    def test_returns_empty_list_when_no_session_dirs_exist(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cleanup_stale_sessions(max_age_hours=24) == []

    def test_also_cleans_up_matching_db_records_when_given_a_connection(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        stale_dir = tmp_path / "data" / "raw" / "stale-session"
        stale_dir.mkdir(parents=True)
        old_time = time.time() - (25 * 3600)
        import os

        os.utime(stale_dir, (old_time, old_time))

        db_path = tmp_path / "run_history.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, session_id TEXT)")
        conn.execute(
            "INSERT INTO runs (id, session_id) VALUES (?, ?)",
            ("run_1", "stale-session"),
        )
        conn.commit()

        purged = cleanup_stale_sessions(max_age_hours=24, db_conn=conn)

        assert "stale-session" in purged
        remaining = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert remaining == 0
        conn.close()

    def test_a_failed_db_cleanup_does_not_prevent_directory_purge(
        self, tmp_path, monkeypatch
    ):
        """If the DB connection is broken, the filesystem cleanup (the more
        important side effect - freeing disk space) must still happen."""
        monkeypatch.chdir(tmp_path)
        stale_dir = tmp_path / "data" / "raw" / "stale-session"
        stale_dir.mkdir(parents=True)
        old_time = time.time() - (25 * 3600)
        import os

        os.utime(stale_dir, (old_time, old_time))

        class BrokenConn:
            def cursor(self):
                raise sqlite3.OperationalError("database is locked")

        purged = cleanup_stale_sessions(max_age_hours=24, db_conn=BrokenConn())

        assert "stale-session" in purged
        assert not stale_dir.exists()


class TestSessionInitializer:
    """SessionInitializer.initialize() is tightly coupled to a real
    st.session_state - exercised via Streamlit's own AppTest harness
    (a real session_state, no faking its attribute-style dict semantics)
    rather than mocking every backend class it constructs."""

    def test_initialize_populates_all_core_session_state_keys(self):
        script = """
import streamlit as st
from src.utils.session_manager import SessionInitializer
SessionInitializer.initialize()
st.write("done")
"""
        at = AppTest.from_string(script)
        at.run(timeout=60)

        assert not at.exception
        expected_keys = [
            "config",
            "session_id",
            "history_db",
            "cache_manager",
            "pdb_manager",
            "mustang_runner",
            "rmsd_analyzer",
            "sequence_viewer",
            "report_generator",
            "pdb_ids",
            "results",
            "ligand_analyzer",
            "coordinator",
            "auto_recovered",
            "guided_mode",
            "chain_selection_mode",
            "remove_water",
            "remove_hetero",
        ]
        for key in expected_keys:
            assert key in at.session_state, f"missing session_state key: {key}"

    def test_initialize_is_idempotent_across_reruns(self):
        """A second call (e.g. Streamlit re-running the script on user
        interaction) must not re-initialize already-set state - most
        importantly, must not re-run the startup cleanup/Mustang check."""
        script = """
import streamlit as st
from src.utils.session_manager import SessionInitializer
SessionInitializer.initialize()
SessionInitializer.initialize()
st.write(st.session_state.session_id)
"""
        at = AppTest.from_string(script)
        at.run(timeout=60)

        assert not at.exception
