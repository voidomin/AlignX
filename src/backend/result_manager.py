"""
Result management and indexing for batch comparisons.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from src.utils.logger import get_logger, sanitize_for_log

logger = get_logger()


class ResultManager:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        from src.backend.database import HistoryDatabase

        self.db = HistoryDatabase()

    def list_runs(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve valid past runs from the database.
        """
        runs = []
        db_runs = self.db.get_all_runs(session_id=session_id)

        for run in db_runs:
            run_path = Path(run["result_path"])
            # Verify the directory still exists and has the RMSD matrix
            # If the database entry exists, we consider it a valid run for indexing
            if run_path.exists() and (run_path / "rmsd_matrix.csv").exists():
                runs.append(
                    {
                        "id": run["id"],
                        "timestamp": run["timestamp"],
                        "protein_count": len(run["pdb_ids"]),
                        "proteins": run["pdb_ids"],
                        "path": run_path,
                    }
                )

        return runs

    def get_run_rmsd(self, run_id: str) -> Optional[pd.DataFrame]:
        """
        Load the RMSD matrix for a specific run.
        """
        run_path = self.results_dir / run_id
        rmsd_path = run_path / "rmsd_matrix.csv"

        if rmsd_path.exists():
            try:
                # Assuming the first column is the index (protein names)
                df = pd.read_csv(rmsd_path, index_col=0)
                return df
            except Exception:
                logger.exception(
                    f"Failed to load RMSD matrix for {sanitize_for_log(run_id)}"
                )

        return None

    def calculate_difference(
        self, run_id_1: str, run_id_2: str
    ) -> Optional[pd.DataFrame]:
        """
        Calculate the difference between two RMSD matrices (run1 - run2).
        Aligns dataframes automatically and returns the difference for the overlapping proteins.
        """
        rmsd1 = self.get_run_rmsd(run_id_1)
        rmsd2 = self.get_run_rmsd(run_id_2)

        if rmsd1 is None or rmsd2 is None:
            return None

        # Align dataframes on common proteins
        # This handles cases where order is different or sets only partially overlap
        rmsd1_aligned, rmsd2_aligned = rmsd1.align(rmsd2, join="inner", axis=None)

        if rmsd1_aligned.empty:
            logger.warning(
                f"Cannot compare runs {sanitize_for_log(run_id_1)} and "
                f"{sanitize_for_log(run_id_2)}: No overlapping proteins."
            )
            return None

        return rmsd1_aligned - rmsd2_aligned

    def get_run_trend(self, run_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Builds a chronological RMSD trend across a user-selected *set* of
        past runs - e.g. "did this protein family's structural similarity
        drift over 5 runs", not just the single most-recent-vs-one-other
        view calculate_difference() already offers. Sorted by timestamp so
        callers can plot it directly as a time series.

        Only RMSD is aggregated here, not TM-score/GDT-TS - those are
        computed at run time (see coordinator.py) and never persisted to
        disk the way rmsd_matrix.csv is, so trending them for arbitrary
        past runs would mean re-running tmtools against each one's stored
        alignment.pdb, a much heavier operation than this view is meant
        for. A run with a missing/unreadable RMSD matrix is silently
        skipped rather than breaking the whole trend.
        """
        runs_by_id = {r["id"]: r for r in self.list_runs()}
        trend = []
        for run_id in run_ids:
            run = runs_by_id.get(run_id)
            if run is None:
                continue
            rmsd_df = self.get_run_rmsd(run_id)
            if rmsd_df is None:
                continue

            mask = np.triu(np.ones(rmsd_df.shape, dtype=bool), k=1)
            values = rmsd_df.to_numpy()[mask]
            values = values[~np.isnan(values)]
            if len(values) == 0:
                continue

            trend.append(
                {
                    "run_id": run_id,
                    "timestamp": run["timestamp"],
                    "proteins": run["proteins"],
                    "mean_rmsd": float(np.mean(values)),
                    "max_rmsd": float(np.max(values)),
                }
            )

        trend.sort(key=lambda r: r["timestamp"])
        return trend
