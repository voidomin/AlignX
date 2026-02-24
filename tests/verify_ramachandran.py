import os
import sys
from pathlib import Path
import json
import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from src.backend.ramachandran_service import RamachandranService

def verify_ramachandran():
    print("🧪 Verifying Ramachandran Service Backend...")
    
    service = RamachandranService()
    
    # Use latest run for testing
    results_dir = Path("results")
    if not results_dir.exists():
        print("❌ No results directory found.")
        return
        
    runs = sorted([d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith("run_")], reverse=True)
    if not runs:
        print("❌ No run directories found.")
        return

    latest_run = runs[0]
    alignment_pdb = latest_run / "alignment.pdb"
    
    if not alignment_pdb.exists():
        print(f"❌ Alignment PDB missing in {latest_run}")
        return

    print(f"📂 Analyzing Torsion for: {latest_run.name}")
    torsion_data = service.calculate_torsion_angles(alignment_pdb)
    
    if torsion_data:
        print(f"✅ Calculated Torsion for {len(torsion_data)} chains.")
        
        for chain_id, df in torsion_data.items():
            print(f"\n📊 Chain {chain_id} Statistics:")
            print(f"  - Total Residues: {len(df)}")
            print(f"  - Regions: {df['region'].value_counts().to_dict()}")
            
            # Check for reasonable angle ranges
            valid_phi = (df['phi'].dropna() >= -180) & (df['phi'].dropna() <= 180)
            valid_psi = (df['psi'].dropna() >= -180) & (df['psi'].dropna() <= 180)
            
            if valid_phi.all() and valid_psi.all():
                print("  - Angle Ranges: OK (-180 to 180)")
            else:
                print("  - ⚠️ Error: Angle ranges OUT OF BOUNDS!")
                
        stats = service.aggregate_metrics(torsion_data)
        print("\n📈 Global Summary:")
        print(json.dumps(stats, indent=2))
    else:
        print("❌ Torsion calculation failed (returned empty).")

if __name__ == "__main__":
    verify_ramachandran()
