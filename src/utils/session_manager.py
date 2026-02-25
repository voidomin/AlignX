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

logger = logging.getLogger(__name__)


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
