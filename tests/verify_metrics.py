import os
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.append(os.getcwd())

from src.backend.rmsd_calculator import calculate_alignment_quality_metrics


def verify_metrics():
    print("🧪 Verifying Scientific Metrics Backend...")

    # Use a dummy PDB and FASTA if needed, or point to an existing run
    # Let's try to find the latest run
    results_dir = Path("results")
    runs = sorted(
        [d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith("run_")],
        reverse=True,
    )

    if not runs:
        print("❌ No run directories found for verification.")
        return

    latest_run = runs[0]
    alignment_pdb = latest_run / "alignment.pdb"
    alignment_afasta = latest_run / "alignment.afasta"

    if not alignment_pdb.exists() or not alignment_afasta.exists():
        print(f"❌ Alignment files mapping failed in {latest_run}")
        return

    print(f"📂 Analyzing: {latest_run.name}")
    metrics = calculate_alignment_quality_metrics(alignment_pdb, alignment_afasta)

    if metrics:
        print("✅ Quality Metrics Calculated Successfully:")
        print(json.dumps(metrics, indent=2))

        # Check for TM-score validity
        for pid, vals in metrics.items():
            if 0.0 <= vals["tm_score"] <= 1.0:
                print(f"  - {pid}: TM-score {vals['tm_score']:.3f} (Valid)")
            else:
                print(f"  - {pid}: TM-score {vals['tm_score']} (OUT OF RANGE!)")
    else:
        print("❌ Metrics calculation returned None")


if __name__ == "__main__":
    verify_metrics()
