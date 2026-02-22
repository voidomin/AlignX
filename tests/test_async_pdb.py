import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.backend.pdb_manager import PDBManager
from src.utils.config_loader import load_config

async def test_async_downloads():
    print("Testing Async PDB Downloads...")
    config = load_config("config.yaml")
    manager = PDBManager(config)
    
    # Test IDs (some existing, some new)
    test_ids = ["1L2Y", "1A6M", "1BKV", "4HHB"]
    
    print(f"Starting batch download for: {test_ids}")
    results = await manager.batch_download(test_ids)
    
    for pdb_id, (success, msg, path) in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {pdb_id}: {msg} -> {path}")
        if success and path:
            assert path.exists()

async def test_async_metadata():
    print("\nTesting Async Metadata Fetching...")
    config = load_config("config.yaml")
    manager = PDBManager(config)
    
    test_ids = ["1L2Y", "1A6M", "1BKV", "4HHB"]
    
    print(f"Fetching metadata for: {test_ids}")
    metadata = await manager.fetch_metadata(test_ids)
    
    for pdb_id, info in metadata.items():
        print(f"📍 {pdb_id}: {info['title']} ({info['organism']})")
        assert info['title'] != 'N/A'

async def main():
    try:
        await test_async_downloads()
        await test_async_metadata()
        print("\n✨ All async PDB tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
