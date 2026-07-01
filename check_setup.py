import sys
import os
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console environments
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.append(os.getcwd())

try:
    from src.utils.config_loader import load_config
    from src.backend.coordinator import AnalysisCoordinator
    
    print("🔍 Checking Pipeline Setup...")
    
    config = load_config("config.yaml")
    coordinator = AnalysisCoordinator(config)
    mustang_ok, mustang_msg = coordinator.mustang_runner.check_installation()
    
    print(f"\n✓ Python {sys.version.split()[0]} detected")
    if mustang_ok:
        print(f"✓ Mustang available: {mustang_msg}")
    else:
        print(f"❌ Mustang NOT found: {mustang_msg}")
        print("   Please check docs/setup/WINDOWS_SETUP.md for installation details.")
        
    print("\n🎉 Setup check complete!")
    
except Exception as e:
    print(f"\n❌ Setup check failed: {e}")
    sys.exit(1)
