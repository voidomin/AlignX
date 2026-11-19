import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.backend.pdb_manager import PDBManager
from src.utils.config_loader import load_config


@pytest.mark.asyncio
async def test_async_downloads(tmp_path):
    config = load_config("config.yaml")
    manager = PDBManager(config)
    test_ids = ["1L2Y", "1A6M", "1BKV", "4HHB"]

    fake_paths = {}
    for pid in test_ids:
        p = tmp_path / f"{pid}.pdb"
        p.write_text(
            "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
        )
        fake_paths[pid] = p

    async def fake_download(pdb_id, client=None):
        return True, "Downloaded", fake_paths[pdb_id]

    with patch.object(manager, "download_pdb", side_effect=fake_download):
        results = await manager.batch_download(test_ids)

    for pdb_id, (success, _msg, path) in results.items():
        assert pdb_id in test_ids
        assert success
        assert path is not None
        assert path.exists()


@pytest.mark.asyncio
async def test_async_metadata():
    config = load_config("config.yaml")
    manager = PDBManager(config)
    test_ids = ["1L2Y", "1A6M", "1BKV", "4HHB"]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "entries": [
                {
                    "rcsb_id": pid,
                    "struct": {"title": f"Structure of {pid}"},
                    "exptl": [{"method": "X-RAY DIFFRACTION"}],
                    "rcsb_entry_info": {"resolution_combined": [1.8]},
                    "polymer_entities": [
                        {
                            "rcsb_entity_source_organism": [
                                {"scientific_name": "Homo sapiens"}
                            ]
                        }
                    ],
                }
                for pid in test_ids
            ]
        }
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    metadata = await manager.fetch_metadata(test_ids, client=mock_client)

    for pdb_id, info in metadata.items():
        assert info["title"] == f"Structure of {pdb_id}"
        assert info["title"] != "N/A"
        assert info["organism"] == "Homo sapiens"
