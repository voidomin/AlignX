import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

from src.utils.logger import sanitize_for_log

logger = logging.getLogger(__name__)


class HistoryDatabase:
    """
    Manages a SQLite database to store and retrieve analysis history.
    """

    # Both DiscoveryCoordinator and AnalysisCoordinator construct their own
    # HistoryDatabase() per job rather than sharing api.py's module-level
    # instance, so under concurrent job submissions this constructor runs
    # once per in-flight job. Retrying the CREATE TABLE/ALTER TABLE
    # migration every single time - each needing its own SQLite write lock
    # - measurably serializes concurrent job startup once run_history.db
    # has grown large (found via a real concurrency test hitting a ~170MB
    # dev database: a handful of concurrent job submissions took minutes
    # instead of seconds). Once a given db_path has been migrated in this
    # process, every later HistoryDatabase() for that same path can skip
    # straight through without re-running the migration attempt.
    _migrated_db_paths: set = set()

    def __init__(self, db_path: str = "run_history.db"):
        """
        Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        if db_path not in HistoryDatabase._migrated_db_paths:
            self._init_db()
            HistoryDatabase._migrated_db_paths.add(db_path)

    def _init_db(self):
        """Create the runs table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        name TEXT,
                        pdb_ids TEXT NOT NULL,
                        status TEXT,
                        result_path TEXT,
                        metadata TEXT,
                        session_id TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pdb_cache (
                        id TEXT PRIMARY KEY,
                        path TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        last_accessed TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS annotation_cache (
                        cache_key TEXT PRIMARY KEY,
                        service TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        cached_at TEXT NOT NULL
                    )
                """)
                # Migration: add session_id column if missing (existing DBs)
                try:
                    cursor.execute("ALTER TABLE runs ADD COLUMN session_id TEXT")
                    logger.info("Migrated runs table: added session_id column")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def save_run(
        self,
        run_id: str,
        name: str,
        pdb_ids: List[str],
        result_path: Path,
        status: str = "completed",
        metadata: Dict = None,
        session_id: str = None,
    ) -> bool:
        """
        Save a new run to the database.

        Args:
            run_id: Unique identifier for the run
            name: Human-readable name (e.g., "GPCR Analysis")
            pdb_ids: List of PDB IDs analyzed
            result_path: Path to the results directory
            status: Status of the run (completed, failed)
            metadata: Additional JSON serializable metadata
            session_id: Session ID for multi-user isolation

        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pdb_ids_json = json.dumps(pdb_ids)
            metadata_json = json.dumps(metadata or {})

            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO runs (id, timestamp, name, pdb_ids, status, result_path, metadata, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        run_id,
                        timestamp,
                        name,
                        pdb_ids_json,
                        status,
                        str(result_path),
                        metadata_json,
                        session_id,
                    ),
                )
                conn.commit()

            logger.info(
                f"Saved run {sanitize_for_log(run_id)} to history "
                f"(session: {sanitize_for_log(session_id)})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save run {sanitize_for_log(run_id)}: {e}")
            return False

    def get_all_runs(
        self,
        limit: int = None,
        session_id: str = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve saved runs, sorted by timestamp (newest first).

        Args:
            limit: Maximum number of runs to return (None for all)
            session_id: If provided, only return runs for this session
            offset: Number of runs to skip (for pagination), ignored if limit is None

        Returns:
            List of run dictionaries
        """
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if session_id:
                    query = "SELECT * FROM runs WHERE session_id = ? ORDER BY timestamp DESC"
                    params = (session_id,)
                else:
                    query = "SELECT * FROM runs ORDER BY timestamp DESC"
                    params = ()

                if limit:
                    query += " LIMIT ? OFFSET ?"
                    params = params + (limit, offset)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                runs = []
                for row in rows:
                    run = dict(row)
                    run["pdb_ids"] = json.loads(run["pdb_ids"])
                    run["metadata"] = (
                        json.loads(run["metadata"]) if run["metadata"] else {}
                    )
                    runs.append(run)
                return runs
        except Exception as e:
            logger.error(f"Failed to retrieve runs: {e}")
            return []

    def count_runs(self, session_id: str = None) -> int:
        """
        Count total saved runs, optionally scoped to a session. Used for
        pagination metadata alongside get_all_runs.
        """
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                if session_id:
                    cursor.execute(
                        "SELECT COUNT(*) FROM runs WHERE session_id = ?",
                        (session_id,),
                    )
                else:
                    cursor.execute("SELECT COUNT(*) FROM runs")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to count runs: {e}")
            return 0

    def get_aggregate_stats(self, session_id: str = None) -> Dict[str, Any]:
        """
        Compute dashboard-level totals across all runs: total run count and
        total proteins analyzed (summed pdb_ids length per run). Computed in
        Python over get_all_runs() rather than SQL, since pdb_ids is stored
        as a JSON string column and run volume here is personal-scale.
        """
        runs = self.get_all_runs(session_id=session_id)
        return {
            "total_runs": len(runs),
            "total_proteins_analyzed": sum(len(r["pdb_ids"]) for r in runs),
            "cache_size_mb": round(self.get_total_cache_size() / (1024 * 1024), 2),
        }

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific run by ID.
        """
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
                row = cursor.fetchone()

                if row:
                    run = dict(row)
                    run["pdb_ids"] = json.loads(run["pdb_ids"])
                    run["metadata"] = (
                        json.loads(run["metadata"]) if run["metadata"] else {}
                    )
                    return run
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve run {sanitize_for_log(run_id)}: {e}")
            return None

    def delete_run(self, run_id: str) -> bool:
        """Delete a run from the database."""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM runs WHERE id = ?", (run_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete run {sanitize_for_log(run_id)}: {e}")
            return False

    def get_latest_run(self, session_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recent successful run.

        Args:
            session_id: If provided, only return runs for this session
        """
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if session_id:
                    cursor.execute(
                        "SELECT * FROM runs WHERE status = 'completed' AND session_id = ? ORDER BY timestamp DESC LIMIT 1",
                        (session_id,),
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM runs WHERE status = 'completed' ORDER BY timestamp DESC LIMIT 1"
                    )

                row = cursor.fetchone()

                if row:
                    run = dict(row)
                    run["pdb_ids"] = json.loads(run["pdb_ids"])
                    run["metadata"] = (
                        json.loads(run["metadata"]) if run["metadata"] else {}
                    )
                    return run
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve latest run: {e}")
            return None

    def clear_all_runs(self) -> bool:
        """Clear all runs from the database."""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM runs")
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to clear all runs: {e}")
            return False

    # -------------------------------------------------------------------------
    # CACHE MANAGEMENT METHODS
    # -------------------------------------------------------------------------

    def register_cache_item(self, item_id: str, path: str, size_bytes: int) -> bool:
        """Register or update a PDB file in the cache table."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO pdb_cache (id, path, size_bytes, last_accessed)
                    VALUES (?, ?, ?, ?)
                """,
                    (item_id, path, size_bytes, now),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to register cache item {item_id}: {e}")
            return False

    def update_cache_access(self, item_id: str) -> bool:
        """Update the last accessed timestamp for a cache item."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE pdb_cache SET last_accessed = ? WHERE id = ?",
                    (now, item_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update cache access for {item_id}: {e}")
            return False

    def get_oldest_cache_items(self) -> List[Dict[str, Any]]:
        """Retrieve cache items ordered by last accessed (oldest first)."""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM pdb_cache ORDER BY last_accessed ASC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to retrieve oldest cache items: {e}")
            return []

    def remove_cache_item(self, item_id: str) -> bool:
        """Remove an item from the cache database."""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM pdb_cache WHERE id = ?", (item_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to remove cache item {item_id}: {e}")
            return False

    def get_total_cache_size(self) -> int:
        """Get the total size of all items in the cache (bytes)."""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(size_bytes) FROM pdb_cache")
                result = cursor.fetchone()
                return result[0] if result and result[0] else 0
        except Exception as e:
            logger.error(f"Failed to get total cache size: {e}")
            return 0

    def get_annotation_cache(
        self, cache_key: str, max_age_days: int = 30
    ) -> Optional[str]:
        """
        Retrieve a cached annotation API response (raw JSON string) if
        present and not older than max_age_days. Used by AnnotationAggregator
        to avoid refetching InterPro/QuickGO/SIFTS/STRING/Reactome data for
        an accession/entry someone already looked up recently - this data
        changes rarely, so a multi-week TTL is appropriate.

        Returns None on a cache miss OR an expired entry (the caller is
        expected to refetch and call set_annotation_cache() either way).
        """
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT payload, cached_at FROM annotation_cache WHERE cache_key = ?",
                    (cache_key,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                payload, cached_at = row
                age_days = (
                    datetime.now() - datetime.strptime(cached_at, "%Y-%m-%d %H:%M:%S")
                ).total_seconds() / 86400
                if age_days > max_age_days:
                    return None
                return payload
        except Exception as e:
            logger.error(f"Failed to read annotation cache for {cache_key}: {e}")
            return None

    def set_annotation_cache(self, cache_key: str, service: str, payload: str) -> bool:
        """Stores a raw JSON string response under cache_key. `service` is
        purely descriptive (e.g. "interpro", "sifts") for debugging/cache
        inspection - lookups are always by cache_key alone."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO annotation_cache (cache_key, service, payload, cached_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (cache_key, service, payload, now),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to write annotation cache for {cache_key}: {e}")
            return False
