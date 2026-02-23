"""
Result management and indexing for batch comparisons.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger()

class ResultManager:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def list_runs(self) -> List[Dict[str, Any]]:
        """
        Scan results directory and return a list of valid past runs.
        """
        runs = []
        for run_path in self.results_dir.iterdir():
            if not run_path.is_dir():
                continue
            
            metadata_path = run_path / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        meta = json.load(f)
                    
                    runs.append({
                        "id": run_path.name,
                        "timestamp": meta.get("timestamp", "Unknown"),
                        "protein_count": meta.get("protein_count", 0),
                        "proteins": meta.get("proteins", []),
                        "path": run_path
                    })
                except Exception as e:
                    logger.warning(f"Failed to read metadata for run {run_path.name}: {e}")
        
        # Sort by timestamp (desc) if available
        return sorted(runs, key=lambda x: x['timestamp'], reverse=True)

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

    def calculate_difference(self, run_id_1: str, run_id_2: str) -> Optional[pd.DataFrame]:
        """
        Calculate the difference between two RMSD matrices (run1 - run2).
        Only works if both runs have identical protein sets.
        """
        rmsd1 = self.get_run_rmsd(run_id_1)
        rmsd2 = self.get_run_rmsd(run_id_2)
        
        if rmsd1 is None or rmsd2 is None:
            return None
            
        # Ensure identical overlap
        if not (rmsd1.index.equals(rmsd2.index) and rmsd1.columns.equals(rmsd2.columns)):
            logger.warning(f"Cannot compare runs {run_id_1} and {run_id_2}: Indices do not match.")
            return None
            
        return rmsd1 - rmsd2
