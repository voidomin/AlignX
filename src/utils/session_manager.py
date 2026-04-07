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
from typing import Dict, List

import streamlit as st
from pathlib import Path
from typing import Dict, List, Any, Optional
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

        session_id = st.session_state.session_id

        if "history_db" not in st.session_state:
            st.session_state.history_db = HistoryDatabase()

        if "cache_manager" not in st.session_state:
            from src.utils.cache_manager import CacheManager
            st.session_state.cache_manager = CacheManager(
                st.session_state.config, st.session_state.history_db
            )

        if "pdb_manager" not in st.session_state:
            st.session_state.pdb_manager = PDBManager(
                st.session_state.config, st.session_state.cache_manager,
                session_id=session_id,
            )

        if "mustang_runner" not in st.session_state:
            st.session_state.mustang_runner = MustangRunner(st.session_state.config)

        if "rmsd_analyzer" not in st.session_state:
            st.session_state.rmsd_analyzer = RMSDAnalyzer(st.session_state.config)

        if "sequence_viewer" not in st.session_state:
            st.session_state.sequence_viewer = SequenceViewer()

        if "report_generator" not in st.session_state:
            st.session_state.report_generator = ReportGenerator(
                Path("results") / "latest_run"
            )

        if "pdb_ids" not in st.session_state:
            st.session_state.pdb_ids = []

        if "results" not in st.session_state:
            st.session_state.results = None

        if "ligand_analyzer" not in st.session_state:
            st.session_state.ligand_analyzer = LigandAnalyzer(st.session_state.config)

        if "coordinator" not in st.session_state:
            st.session_state.coordinator = AnalysisCoordinator(
                st.session_state.config, session_id=session_id
            )

        if "auto_recovered" not in st.session_state:
            st.session_state.auto_recovered = False

            if "system_manager" not in st.session_state:
                st.session_state.system_manager = SystemManager(st.session_state.config)
                # Perform automated startup cleanup (runs older than 7 days)
                st.session_state.system_manager.cleanup_old_runs(days=7)
                
                # TTL cleanup: purge stale session directories (>24h) and their DB records
                try:
                    # Open a temporary connection specifically for cleanup
                    with sqlite3.connect(st.session_state.history_db.db_path) as conn:
                        cleanup_stale_sessions(max_age_hours=24, db_conn=conn)
                except Exception as e:
                    st.session_state.logger.warning(f"Failed to run TTL cleanup with DB connection: {e}")
                    # Fallback to file-only cleanup if DB is locked
                    cleanup_stale_sessions(max_age_hours=24)

            # --- INITIAL HUD STATE ---
            if "mustang_install_status" not in st.session_state:
                mustang_ok, mustang_msg = (
                    st.session_state.mustang_runner.check_installation()
                )
                st.session_state.mustang_install_status = (mustang_ok, mustang_msg)

            if "guided_mode" not in st.session_state:
                st.session_state.guided_mode = False

            if "chain_selection_mode" not in st.session_state:
                st.session_state.chain_selection_mode = "Auto (use first chain)"

            if "selected_chain" not in st.session_state:
                st.session_state.selected_chain = "A"

            if "manual_chain_selections" not in st.session_state:
                st.session_state.manual_chain_selections = {}

            if "metadata_fetched" not in st.session_state:
                st.session_state.metadata_fetched = False

            if "metadata" not in st.session_state:
                st.session_state.metadata = {}

            if "remove_water" not in st.session_state:
                st.session_state.remove_water = True

            if "remove_hetero" not in st.session_state:
                st.session_state.remove_hetero = True

            if "input_method_radio" not in st.session_state:
                st.session_state.input_method_radio = "Manual Entry"


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
    purged = []
    now = time.time()
    threshold_seconds = max_age_hours * 3600

    session_roots = [
        Path("data/raw"),
        Path("data/cleaned"),
        Path("results"),
    ]

    # Collect all unique session IDs across all roots
    seen_sessions = set()

    for root in session_roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith("run_"):
                # This looks like a session directory (UUID-based name)
                # Skip non-session dirs like "run_*" (legacy format)
                seen_sessions.add(child.name)

    for session_id in seen_sessions:
        # Check the newest mtime across all roots for this session
        newest_mtime = 0
        session_dirs = []

        for root in session_roots:
            session_dir = root / session_id
            if session_dir.exists():
                session_dirs.append(session_dir)
                mtime = session_dir.stat().st_mtime
                if mtime > newest_mtime:
                    newest_mtime = mtime

        age_seconds = now - newest_mtime
        if age_seconds > threshold_seconds and session_dirs:
            for d in session_dirs:
                try:
                    shutil.rmtree(d)
                    logger.info(f"TTL cleanup: removed {d} (age: {age_seconds/3600:.1f}h)")
                except Exception as e:
                    logger.warning(f"TTL cleanup failed for {d}: {e}")
            purged.append(session_id)

            # Cleanup DB records for this session
            if db_conn is not None:
                try:
                    cursor = db_conn.cursor()
                    cursor.execute("DELETE FROM runs WHERE session_id = ?", (session_id,))
                    db_conn.commit()
                    logger.info(f"TTL cleanup: removed DB records for session {session_id}")
                except Exception as e:
                    logger.warning(f"TTL DB cleanup failed for session {session_id}: {e}")

    if purged:
        logger.info(f"TTL cleanup: purged {len(purged)} stale sessions")

    return purged
