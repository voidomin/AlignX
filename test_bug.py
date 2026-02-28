import asyncio
from pathlib import Path
from src.utils.config_loader import load_config
from src.backend.pdb_manager import PDBManager
from src.utils.cache_manager import CacheManager
from src.backend.database import HistoryDatabase
from src.backend.coordinator import AnalysisCoordinator
from src.utils.logger import setup_logger

logger, _ = setup_logger()
config = load_config()

history_db = HistoryDatabase()
cache_manager = CacheManager(config, history_db)
pdb_manager = PDBManager(config, cache_manager)
coordinator = AnalysisCoordinator(config)

pdb_ids = ["1A3Q", "3KBD"]

success, msg, results = coordinator.run_full_pipeline(
    pdb_ids=pdb_ids,
    chain_selection={"1A3Q": "A", "3KBD": "A"},
    remove_water=True,
    remove_heteroatoms=True
)

if not success:
    print(f"FAILED: {msg}")
else:
    print("SUCCESS")
