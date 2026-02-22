import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class HistoryDatabase:
    """
    Manages a SQLite database to store and retrieve analysis history.
    """
    
    def __init__(self, db_path: str = "run_history.db"):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Create the runs table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        name TEXT,
                        pdb_ids TEXT NOT NULL,
                        status TEXT,
                        result_path TEXT,
                        metadata TEXT
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
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def save_run(self, run_id: str, name: str, pdb_ids: List[str], result_path: Path, status: str = "completed", metadata: Dict = None) -> bool:
        """
        Save a new run to the database.
        
        Args:
            run_id: Unique identifier for the run
            name: Human-readable name (e.g., "GPCR Analysis")
            pdb_ids: List of PDB IDs analyzed
            result_path: Path to the results directory
            status: Status of the run (completed, failed)
            metadata: Additional JSON serializable metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pdb_ids_json = json.dumps(pdb_ids)
            metadata_json = json.dumps(metadata or {})
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO runs (id, timestamp, name, pdb_ids, status, result_path, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (run_id, timestamp, name, pdb_ids_json, status, str(result_path), metadata_json))
                conn.commit()
            
            logger.info(f"Saved run {run_id} to history")
            return True
        except Exception as e:
            logger.error(f"Failed to save run {run_id}: {e}")
            return False

    def get_all_runs(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve saved runs, sorted by timestamp (newest first).
        
        Args:
            limit: Maximum number of runs to return (None for all)
            
        Returns:
            List of run dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM runs ORDER BY timestamp DESC"
                params = ()
                
                if limit:
                    query += " LIMIT ?"
                    params = (limit,)
                    
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                runs = []
                for row in rows:
                    run = dict(row)
                    run['pdb_ids'] = json.loads(run['pdb_ids'])
                    run['metadata'] = json.loads(run['metadata']) if run['metadata'] else {}
                    runs.append(run)
                return runs
        except Exception as e:
            logger.error(f"Failed to retrieve runs: {e}")
            return []

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific run by ID.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
                row = cursor.fetchone()
                
                if row:
                    run = dict(row)
                    run['pdb_ids'] = json.loads(run['pdb_ids'])
                    run['metadata'] = json.loads(run['metadata']) if run['metadata'] else {}
                    return run
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve run {run_id}: {e}")
            return None

    def delete_run(self, run_id: str) -> bool:
        """Delete a run from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM runs WHERE id = ?", (run_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete run {run_id}: {e}")
            return False

    def get_latest_run(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recent successful run.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM runs WHERE status = 'completed' ORDER BY timestamp DESC LIMIT 1")
                row = cursor.fetchone()
                
                if row:
                    run = dict(row)
                    run['pdb_ids'] = json.loads(run['pdb_ids'])
                    run['metadata'] = json.loads(run['metadata']) if run['metadata'] else {}
                    return run
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve latest run: {e}")
            return None

    def clear_all_runs(self) -> bool:
        """Clear all runs from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO pdb_cache (id, path, size_bytes, last_accessed)
                    VALUES (?, ?, ?, ?)
                """, (item_id, path, size_bytes, now))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to register cache item {item_id}: {e}")
            return False

    def update_cache_access(self, item_id: str) -> bool:
        """Update the last accessed timestamp for a cache item."""
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE pdb_cache SET last_accessed = ? WHERE id = ?", (now, item_id))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update cache access for {item_id}: {e}")
            return False

    def get_oldest_cache_items(self) -> List[Dict[str, Any]]:
        """Retrieve cache items ordered by last accessed (oldest first)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(size_bytes) FROM pdb_cache")
                result = cursor.fetchone()
                return result[0] if result and result[0] else 0
        except Exception as e:
            logger.error(f"Failed to get total cache size: {e}")
            return 0
