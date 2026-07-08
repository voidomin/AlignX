import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.utils.logger import get_logger

logger = get_logger()


class SystemManager:
    """
    Manages system-level tasks like diagnostics and housekeeping.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.results_dir = Path("results")
        self.temp_dir = Path("temp")

    def run_diagnostics(self, mustang_executable: str = "mustang") -> Dict[str, Any]:
        """
        Check for required system dependencies.

        Args:
            mustang_executable: Path to the mustang binary to test.

        Returns:
            Dictionary of check results.
        """
        results = {
            "Mustang": {"status": "FAILED", "version": "Unknown"},
            "R environment": {"status": "FAILED", "version": "Unknown"},
            "Platform": sys.platform,
            "Python Version": sys.version.split()[0],
        }

        # 1. Check Mustang
        try:
            # Try to run mustang --version or just mustang
            # Mustang usually prints help to stderr if no args
            proc = subprocess.run(
                [mustang_executable], capture_output=True, text=True, timeout=5
            )
            # Mustang doesn't have a --version flag but help text contains version
            if "MUSTANG" in proc.stderr or "MUSTANG" in proc.stdout:
                results["Mustang"]["status"] = "PASSED"
                # Extract version if possible, e.g., "MUSTANG v.3.2.3"
                full_text = proc.stderr if "MUSTANG" in proc.stderr else proc.stdout
                for line in full_text.split("\n"):
                    if "MUSTANG" in line:
                        results["Mustang"]["version"] = line.strip()
                        break
        except Exception as exc:
            logger.debug(f"Mustang diagnostic check failed: {exc}")

        return results

    def cleanup_old_runs(self, days: int = 7) -> List[str]:
        """
        Delete results directories older than specified days.

        Args:
            days: Age threshold in days.

        Returns:
            List of deleted directory names.
        """
        if not self.results_dir.exists():
            return []

        now = time.time()
        threshold = days * 24 * 60 * 60

        deleted = []
        # In v2.4, results are nested under session_id: results/{session_id}/run_{timestamp}
        # Iterate over session directories
        for session_dir in self.results_dir.iterdir():
            if not session_dir.is_dir() or session_dir.name.startswith("run_"):
                # Skip legacy run folders if any, we only process session dirs
                continue
            deleted.extend(self._cleanup_session_runs(session_dir, now, threshold))
            self._remove_if_empty(session_dir)

        return deleted

    def _cleanup_session_runs(
        self, session_dir: Path, now: float, threshold: float
    ) -> List[str]:
        """Deletes every run directory under `session_dir` older than
        `threshold` seconds, returning the ones actually deleted."""
        deleted = []
        for run_dir in session_dir.iterdir():
            if not (run_dir.is_dir() and run_dir.name.startswith("run_")):
                continue
            if (now - run_dir.stat().st_mtime) <= threshold:
                continue
            try:
                shutil.rmtree(run_dir)
                deleted.append(f"{session_dir.name}/{run_dir.name}")
                logger.info(f"Cleaned up old run directory: {run_dir.name}")
            except Exception:
                logger.exception(f"Failed to delete {run_dir.name}")
        return deleted

    @staticmethod
    def _remove_if_empty(session_dir: Path) -> None:
        if list(session_dir.iterdir()):
            return
        try:
            shutil.rmtree(session_dir)
        except Exception:
            pass

    def get_aggregate_stats(self, db: Any) -> Dict[str, Any]:
        """
        Calculate aggregate statistics from the history database.

        Args:
            db: HistoryDatabase instance.

        Returns:
            Dictionary with counts.
        """
        try:
            runs = db.get_all_runs()
            total_runs = len(runs)
            total_proteins = sum(len(run.get("pdb_ids", [])) for run in runs)

            return {"total_runs": total_runs, "total_proteins": total_proteins}
        except Exception:
            logger.exception("Failed to get aggregate stats")
            return {"total_runs": 0, "total_proteins": 0}
