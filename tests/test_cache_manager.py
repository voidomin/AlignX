from unittest.mock import MagicMock

from src.utils.cache_manager import CacheManager


def _manager(enabled=True, limit_mb=1000, db=None):
    config = {"cache": {"enabled": enabled, "max_cache_size_mb": limit_mb}}
    return CacheManager(config, db or MagicMock())


class TestDisabledCacheIsANoOp:
    def test_register_item_does_not_touch_the_database(self, tmp_path):
        db = MagicMock()
        manager = _manager(enabled=False, db=db)

        manager.register_item("4RLT", tmp_path / "4rlt.pdb")

        db.register_cache_item.assert_not_called()

    def test_update_access_does_not_touch_the_database(self):
        db = MagicMock()
        manager = _manager(enabled=False, db=db)

        manager.update_access("4RLT")

        db.update_cache_access.assert_not_called()

    def test_enforce_limit_does_not_touch_the_database(self):
        db = MagicMock()
        manager = _manager(enabled=False, db=db)

        manager.enforce_limit()

        db.get_total_cache_size.assert_not_called()


class TestRegisterItem:
    def test_warns_and_skips_for_nonexistent_file(self, tmp_path):
        db = MagicMock()
        manager = _manager(db=db)

        manager.register_item("4RLT", tmp_path / "does_not_exist.pdb")

        db.register_cache_item.assert_not_called()

    def test_registers_a_real_file_and_enforces_limit(self, tmp_path):
        pdb_file = tmp_path / "4rlt.pdb"
        pdb_file.write_bytes(b"ATOM" * 100)
        db = MagicMock()
        db.get_total_cache_size.return_value = 0
        manager = _manager(db=db)

        manager.register_item("4RLT", pdb_file)

        db.register_cache_item.assert_called_once()
        args = db.register_cache_item.call_args[0]
        assert args[0] == "4RLT"
        assert args[2] == 400


class TestEnforceLimit:
    def test_no_eviction_when_under_limit(self):
        db = MagicMock()
        db.get_total_cache_size.return_value = 100
        manager = _manager(limit_mb=1, db=db)

        manager.enforce_limit()

        db.get_oldest_cache_items.assert_not_called()

    def test_evicts_oldest_items_until_under_limit(self, tmp_path):
        item_path = tmp_path / "old.pdb"
        item_path.write_bytes(b"x")
        db = MagicMock()
        # Total starts over the 1MB limit; one eviction brings it under.
        db.get_total_cache_size.return_value = 2 * 1024 * 1024
        db.get_oldest_cache_items.return_value = [
            {"id": "old", "path": str(item_path), "size_bytes": 2 * 1024 * 1024}
        ]
        manager = _manager(limit_mb=1, db=db)

        manager.enforce_limit()

        db.remove_cache_item.assert_called_once_with("old")
        assert not item_path.exists()

    def test_eviction_failure_is_logged_not_raised(self, tmp_path):
        db = MagicMock()
        db.get_total_cache_size.return_value = 2 * 1024 * 1024
        db.remove_cache_item.side_effect = Exception("db locked")
        db.get_oldest_cache_items.return_value = [
            {"id": "old", "path": str(tmp_path / "missing.pdb"), "size_bytes": 1}
        ]
        manager = _manager(limit_mb=1, db=db)

        manager.enforce_limit()  # must not raise


class TestGetCacheStatus:
    def test_reports_usage_percent(self):
        db = MagicMock()
        db.get_total_cache_size.return_value = 500 * 1024 * 1024
        manager = _manager(limit_mb=1000, db=db)

        status = manager.get_cache_status()

        assert status["enabled"] is True
        assert status["limit_mb"] == 1000
        assert status["current_size_mb"] == 500.0
        assert status["usage_percent"] == 50.0

    def test_usage_percent_is_zero_when_limit_is_zero(self):
        db = MagicMock()
        db.get_total_cache_size.return_value = 0
        manager = _manager(limit_mb=0, db=db)

        assert manager.get_cache_status()["usage_percent"] == 0
