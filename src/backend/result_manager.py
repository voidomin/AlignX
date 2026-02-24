"""
Result management and indexing for batch comparisons.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger()


class ResultManager:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        from src.backend.database import HistoryDatabase

        self.db = HistoryDatabase()

    def list_runs(self) -> List[Dict[str, Any]]:
        """
        Retrieve valid past runs from the database.
        """
        runs = []
        db_runs = self.db.get_all_runs()

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
            except Exception as e:
                logger.error(f"Failed to load RMSD matrix for {run_id}: {e}")

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
                f"Cannot compare runs {run_id_1} and {run_id_2}: No overlapping proteins."
            )
            return None

        return rmsd1_aligned - rmsd2_aligned
