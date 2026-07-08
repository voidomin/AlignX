"""
Session Manager for Multi-User Isolation.

Provides per-session file namespacing so multiple users on Streamlit Cloud
don't interfere with each other's data.
"""

import uuid
import time
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import streamlit as st
import sqlite3

# Backend Imports (needed for initialization)
from src.backend.pdb_manager import PDBManager
from src.backend.mustang_runner import MustangRunner
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.sequence_viewer import SequenceViewer
from src.backend.report_generator import ReportGenerator
from src.backend.ligand_analyzer import LigandAnalyzer
from src.backend.database import HistoryDatabase
from src.backend.utilities import SystemManager
from src.backend.coordinator import AnalysisCoordinator

# Utility Imports
from src.utils.logger import setup_logger
from src.utils.config_loader import load_config

logger = logging.getLogger(__name__)


class SessionInitializer:
    """
    Handles all Streamlit session state initialization and background cleanup.
    Provides a clean interface for app.py to manage its state.
    """

    @staticmethod
    def _ensure_default(key: str, factory) -> None:
        if key not in st.session_state:
            st.session_state[key] = factory()

    @staticmethod
    def _init_core_services(session_id: str) -> None:
        SessionInitializer._ensure_default("history_db", HistoryDatabase)

        if "cache_manager" not in st.session_state:
            from src.utils.cache_manager import CacheManager

            st.session_state.cache_manager = CacheManager(
                st.session_state.config, st.session_state.history_db
            )

        SessionInitializer._ensure_default(
            "pdb_manager",
            lambda: PDBManager(
                st.session_state.config,
                st.session_state.cache_manager,
                session_id=session_id,
            ),
        )
        SessionInitializer._ensure_default(
            "mustang_runner", lambda: MustangRunner(st.session_state.config)
        )
        SessionInitializer._ensure_default(
            "rmsd_analyzer", lambda: RMSDAnalyzer(st.session_state.config)
        )
        SessionInitializer._ensure_default("sequence_viewer", SequenceViewer)
        SessionInitializer._ensure_default(
            "report_generator", lambda: ReportGenerator(Path("results") / "latest_run")
        )
        SessionInitializer._ensure_default("pdb_ids", list)
        SessionInitializer._ensure_default("results", lambda: None)
        SessionInitializer._ensure_default(
            "ligand_analyzer", lambda: LigandAnalyzer(st.session_state.config)
        )
        SessionInitializer._ensure_default(
            "coordinator",
            lambda: AnalysisCoordinator(st.session_state.config, session_id=session_id),
        )

    @staticmethod
    def _run_ttl_cleanup() -> None:
        """Purges stale session directories (>24h) and their DB records."""
        try:
            # Open a temporary connection specifically for cleanup
            with sqlite3.connect(st.session_state.history_db.db_path) as conn:
                cleanup_stale_sessions(max_age_hours=24, db_conn=conn)
        except Exception as e:
            st.session_state.logger.warning(
                f"Failed to run TTL cleanup with DB connection: {e}"
            )
            # Fallback to file-only cleanup if DB is locked
            cleanup_stale_sessions(max_age_hours=24)

    @staticmethod
    def _init_startup_state() -> None:
        """One-time-per-session background cleanup and initial HUD/UI
        defaults - only ever reached once, from the caller's single
        "auto_recovered" guard, but each field here keeps its own
        independent guard rather than relying on that alone."""
        if "system_manager" not in st.session_state:
            st.session_state.system_manager = SystemManager(st.session_state.config)
            # Perform automated startup cleanup (runs older than 7 days)
            st.session_state.system_manager.cleanup_old_runs(days=7)
            SessionInitializer._run_ttl_cleanup()

        if "mustang_install_status" not in st.session_state:
            mustang_ok, mustang_msg = (
                st.session_state.mustang_runner.check_installation()
            )
            st.session_state.mustang_install_status = (mustang_ok, mustang_msg)

        for key, value in {
            "guided_mode": False,
            "chain_selection_mode": "Auto (use first chain)",
            "selected_chain": "A",
            "manual_chain_selections": {},
            "metadata_fetched": False,
            "metadata": {},
            "remove_water": True,
            "remove_hetero": True,
            "input_method_radio": "Manual Entry",
            "show_metadata": False,
            "first_visit": True,
            "_confirm_reset": False,
            "_confirm_deep_clean": False,
        }.items():
            SessionInitializer._ensure_default(key, lambda value=value: value)

    @staticmethod
    def initialize():
        """
        Main entry point for session initialization.
        Call this at the top of your Streamlit app.
        """
        if "config" not in st.session_state:
            st.session_state.config = load_config()
            st.session_state.logger, st.session_state.log_file = setup_logger()

        # Session isolation: generate a unique session ID per browser tab
        if "session_id" not in st.session_state:
            st.session_state.session_id = get_session_id()

        SessionInitializer._init_core_services(st.session_state.session_id)

        if "auto_recovered" not in st.session_state:
            st.session_state.auto_recovered = False
            SessionInitializer._init_startup_state()


def get_session_id() -> str:
    """
    Get or create a unique session ID.

    This should be called once per Streamlit session and stored in
    st.session_state. Each browser tab/session gets its own ID.

    Returns:
        A UUID4 string identifying this session.
    """
    return str(uuid.uuid4())[:8]  # Short ID for readable directory names


def get_session_paths(session_id: str) -> Dict[str, Path]:
    """
    Get namespaced directory paths for a given session.

    Args:
        session_id: The unique session identifier.

    Returns:
        Dictionary with 'raw', 'cleaned', and 'results' Path objects.
    """
    paths = {
        "raw": Path("data/raw") / session_id,
        "cleaned": Path("data/cleaned") / session_id,
        "results": Path("results") / session_id,
    }

    # Create directories
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)

    return paths


def _collect_session_ids(session_roots: List[Path]) -> set:
    """Every session subdirectory name (UUID-based) seen across all roots -
    "run_*" dirs are the legacy non-session format and are skipped."""
    seen_sessions = set()
    for root in session_roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith("run_"):
                seen_sessions.add(child.name)
    return seen_sessions


def _newest_session_mtime(
    session_roots: List[Path], session_id: str
) -> Tuple[float, List[Path]]:
    """The most recent mtime across a session's directories (one per root
    that has it), plus the list of dirs found - a session counts as active
    as long as ANY of its directories was touched recently."""
    session_dirs = []
    newest_mtime = 0
    for root in session_roots:
        session_dir = root / session_id
        if session_dir.exists():
            session_dirs.append(session_dir)
            newest_mtime = max(newest_mtime, session_dir.stat().st_mtime)
    return newest_mtime, session_dirs


def _purge_session_dirs(session_dirs: List[Path], age_seconds: float) -> None:
    for d in session_dirs:
        try:
            shutil.rmtree(d)
            logger.info(f"TTL cleanup: removed {d} (age: {age_seconds/3600:.1f}h)")
        except Exception as e:
            logger.warning(f"TTL cleanup failed for {d}: {e}")


def _purge_session_db_records(db_conn, session_id: str) -> None:
    if db_conn is None:
        return
    try:
        cursor = db_conn.cursor()
        cursor.execute("DELETE FROM runs WHERE session_id = ?", (session_id,))
        db_conn.commit()
        logger.info(f"TTL cleanup: removed DB records for session {session_id}")
    except Exception as e:
        logger.warning(f"TTL DB cleanup failed for session {session_id}: {e}")


def cleanup_stale_sessions(max_age_hours: int = 24, db_conn=None) -> List[str]:
    """
    Remove session directories older than max_age_hours and cleanup DB.

    Scans data/raw/, data/cleaned/, and results/ for session subdirectories
    whose modification time exceeds the TTL threshold.

    Args:
        max_age_hours: Maximum age in hours before a session directory is purged.
        db_conn: Optional sqlite3 database connection to clear associated runs.

    Returns:
        List of purged session directory names.
    """
    now = time.time()
    threshold_seconds = max_age_hours * 3600
    session_roots = [Path("data/raw"), Path("data/cleaned"), Path("results")]

    purged = []
    for session_id in _collect_session_ids(session_roots):
        newest_mtime, session_dirs = _newest_session_mtime(session_roots, session_id)
        age_seconds = now - newest_mtime
        if age_seconds <= threshold_seconds or not session_dirs:
            continue

        _purge_session_dirs(session_dirs, age_seconds)
        purged.append(session_id)
        _purge_session_db_records(db_conn, session_id)

    if purged:
        logger.info(f"TTL cleanup: purged {len(purged)} stale sessions")

    return purged
