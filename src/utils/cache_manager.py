import os
import logging
from pathlib import Path
from typing import Dict, Any
from src.backend.database import HistoryDatabase

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages local storage for PDB files with Least Recently Used (LRU) eviction.
    """

    def __init__(self, config: Dict[str, Any], database: HistoryDatabase):
        """
        Initialize the Cache Manager.

        Args:
            config: Configuration dictionary (containing cache settings)
            database: HistoryDatabase instance for persistent tracking
        """
        cache_config = config.get("cache", {})
        self.enabled = cache_config.get("enabled", True)
        self.limit_mb = cache_config.get("max_cache_size_mb", 1000)
        self.db = database

    def register_item(self, item_id: str, file_path: Path):
        """
        Register a new file in the cache and enforce size limits.
        """
        if not self.enabled:
            return

        # Use absolute paths internally to avoid ambiguity
        abs_path = os.path.abspath(str(file_path))

        if not os.path.exists(abs_path):
            logger.warning(
                f"Attempted to register non-existent file in cache: {abs_path}"
            )
            return

        size_bytes = os.path.getsize(abs_path)
        self.db.register_cache_item(item_id, abs_path, size_bytes)
        self.enforce_limit()

    def update_access(self, item_id: str):
        """
        Mark an item as recently accessed.
        """
        if not self.enabled:
            return
        self.db.update_cache_access(item_id)

    def enforce_limit(self):
        """
        Evict oldest items if total cache size exceeds limit.
        """
        if not self.enabled:
            return

        limit_bytes = self.limit_mb * 1024 * 1024
        total_size = self.db.get_total_cache_size()

        if total_size <= limit_bytes:
            return

        logger.info(
            f"Cache limit exceeded ({total_size / (1024*1024):.2f} MB > {self.limit_mb} MB). Evicting old items..."
        )

        oldest_items = self.db.get_oldest_cache_items()

        for item in oldest_items:
            item_id = item["id"]
            item_path = item["path"]
            item_size = item["size_bytes"]

            try:
                # Use os.path methods for better Windows compatibility with spaces
                if os.path.exists(item_path):
                    os.remove(item_path)
                    logger.info(f"Evicted {item_id} from cache: {item_path}")

                self.db.remove_cache_item(item_id)
                total_size -= item_size

                if total_size <= limit_bytes:
                    break
            except Exception as e:
                logger.error(f"Failed to evict {item_id}: {e}")

        logger.info(
            f"Cache cleanup complete. Current size: {total_size / (1024*1024):.2f} MB"
        )

    def get_cache_status(self) -> Dict[str, Any]:
        """Get current cache metrics for reporting."""
        total_size = self.db.get_total_cache_size()
        return {
            "enabled": self.enabled,
            "limit_mb": self.limit_mb,
            "current_size_mb": total_size / (1024 * 1024),
            "usage_percent": (
                (total_size / (self.limit_mb * 1024 * 1024)) * 100
                if self.limit_mb > 0
                else 0
            ),
        }
