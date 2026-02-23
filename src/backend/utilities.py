import os
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
        
    def run_diagnostics(self) -> Dict[str, Any]:
        """
        Check for required system dependencies.
        
        Returns:
            Dictionary of check results.
        """
        results = {
            "Mustang": {"status": "FAILED", "version": "Unknown"},
            "Platform": sys.platform,
            "Python Version": sys.version.split()[0]
        }
        
        # 1. Check Mustang
        try:
            # Try to run mustang --version or just mustang
            # Mustang usually prints help to stderr if no args
            proc = subprocess.run(["mustang"], capture_output=True, text=True, timeout=5)
            # Mustang doesn't have a --version flag but help text contains version
            if "MUSTANG" in proc.stderr or "MUSTANG" in proc.stdout:
                results["Mustang"]["status"] = "PASSED"
                # Extract version if possible, e.g., "MUSTANG v.3.2.3"
                full_text = proc.stderr if "MUSTANG" in proc.stderr else proc.stdout
                for line in full_text.split('\n'):
                    if "MUSTANG" in line:
                        results["Mustang"]["version"] = line.strip()
                        break
        except Exception:
            # Try to find it in common paths or session state binary
            pass
            
        return results

    def cleanup_old_runs(self, days: int = 7) -> List[str]:
        """
        Delete results directories older than specified days.
        
        Args:
            days: Age threshold in days.
            
        Returns:
            List of deleted directory names.
        """
        deleted = []
        now = time.time()
        threshold = days * 24 * 60 * 60
        
        if not self.results_dir.exists():
            return []
            
        for d in self.results_dir.iterdir():
            if d.is_dir() and d.name.startswith("run_"):
                # Check modification time
                mtime = d.stat().st_mtime
                if (now - mtime) > threshold:
                    try:
                        shutil.rmtree(d)
                        deleted.append(d.name)
                        logger.info(f"Cleaned up old run directory: {d.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete {d.name}: {e}")
                        
        return deleted
        
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
            total_proteins = sum(len(run.get('pdb_ids', [])) for run in runs)
            
            return {
                "total_runs": total_runs,
                "total_proteins": total_proteins
            }
        except Exception as e:
            logger.error(f"Failed to get aggregate stats: {e}")
            return {"total_runs": 0, "total_proteins": 0}
