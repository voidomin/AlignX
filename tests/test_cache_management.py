import os
import sys
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.backend.database import HistoryDatabase
from src.utils.cache_manager import CacheManager

def test_lru_logic():
    print("Testing LRU Cache Eviction Logic...")
    
    # Setup a test database and directory
    test_db_path = "test_cache.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    test_raw_dir = os.path.abspath("test_raw_pdb")
    if os.path.exists(test_raw_dir):
        shutil.rmtree(test_raw_dir)
    os.makedirs(test_raw_dir)
    
    db = HistoryDatabase(test_db_path)
    
    # Mock config with small limit (2MB)
    config = {
        'cache': {
            'enabled': True,
            'max_cache_size_mb': 2
        }
    }
    
    cache_mgr = CacheManager(config, db)
    
    # Files: A (oldest), B (middle), C (newest)
    # Each 1MB. Registering C should evict A.
    
    files = ["A", "B", "C"]
    for name in files:
        file_path = os.path.join(test_raw_dir, f"{name}.pdb")
        with open(file_path, "wb") as f:
            f.write(os.urandom(1024 * 1024))
            
        print(f"Registering {name} (1MB)...")
        cache_mgr.register_item(name, Path(file_path))
        
        # Manually back-date last_accessed to ensure order
        # A: now - 3h
        # B: now - 2h
        # C: now - 1h
        ts = (datetime.now() - timedelta(hours=3 - files.index(name))).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(test_db_path) as conn:
            conn.execute("UPDATE pdb_cache SET last_accessed = ? WHERE id = ?", (ts, name))
            conn.commit()

    # Total 3MB > 2MB. A should be evicted.
    # Note: enforce_limit was called when C was added, 
    # but at THAT moment A, B, C had same timestamp (now).
    # Since we want to test RE-EVICTION after metadata update:
    
    print("Forcing enforcement check...")
    cache_mgr.enforce_limit()
    
    path_a = os.path.join(test_raw_dir, "A.pdb")
    path_b = os.path.join(test_raw_dir, "B.pdb")
    path_c = os.path.join(test_raw_dir, "C.pdb")
    
    exists_a = os.path.exists(path_a)
    print(f"A.pdb exists: {exists_a}")
    assert not exists_a, "A.pdb should have been evicted"
    assert os.path.exists(path_b), "B.pdb should remain"
    assert os.path.exists(path_c), "C.pdb should remain"
    
    print("✅ Initial eviction successful.")
    
    # Now update access for B (make it newest)
    print("Updating access for B...")
    cache_mgr.update_access("B")
    
    # Add D (1MB). Total B(1MB) + C(1MB) + D(1MB) = 3MB > 2MB.
    # C (1h ago) is now oldest.
    print("Registering D (1MB)...")
    path_d = os.path.join(test_raw_dir, "D.pdb")
    with open(path_d, "wb") as f:
        f.write(os.urandom(1024 * 1024))
    cache_mgr.register_item("D", Path(path_d))
    
    assert not os.path.exists(path_c), "C.pdb should have been evicted"
    assert os.path.exists(path_b), "B.pdb should remain"
    assert os.path.exists(path_d), "D.pdb should remain"
    print("✅ Access update respected successful.")

    # Cleanup
    print("\n✨ LRU Cache Tests Passed!")

if __name__ == "__main__":
    try:
        test_lru_logic()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
