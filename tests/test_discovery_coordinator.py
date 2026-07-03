from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.backend.discovery_coordinator import DiscoveryCoordinator
from src.backend.foldseek_client import FoldseekError


def test_run_discovery_pipeline_rejects_invalid_id(mock_config):
    coordinator = DiscoveryCoordinator(mock_config)
    success, msg, results = coordinator.run_discovery_pipeline("not-a-valid-id")
    assert success is False
    assert "Invalid structure identifier" in msg
    assert results is None


def test_run_discovery_pipeline_reports_download_failure(mock_config):
    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download:
        mock_download.return_value = (False, "404 Not Found", None)

        coordinator = DiscoveryCoordinator(mock_config)
        success, msg, results = coordinator.run_discovery_pipeline("4RLT")

        assert success is False
        assert "Failed to download 4RLT" in msg
        assert results is None


def test_run_discovery_pipeline_reports_foldseek_failure(mock_config, tmp_path):
    structure_path = tmp_path / "4rlt.pdb"
    structure_path.write_text("ATOM")

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekClient.search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_download.return_value = (True, "ok", structure_path)
        mock_search.side_effect = FoldseekError("Foldseek job failed on the server")

        coordinator = DiscoveryCoordinator(mock_config)
        success, msg, results = coordinator.run_discovery_pipeline("4RLT")

        assert success is False
        assert "Foldseek search failed" in msg
        assert results is None


def test_run_discovery_pipeline_returns_parsed_hits(mock_config, tmp_path):
    structure_path = tmp_path / "af-p69905-f1.pdb"
    structure_path.write_text("ATOM")

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekClient.search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_download.return_value = (True, "ok", structure_path)
        mock_search.return_value = {
            "results": [
                {
                    "alignments": [
                        [{"target": "1ABC", "prob": 1.0}, {"target": "2XYZ", "prob": 0.9}]
                    ]
                }
            ]
        }

        coordinator = DiscoveryCoordinator(mock_config)
        success, msg, results = coordinator.run_discovery_pipeline(
            "AF-P69905-F1", databases=["afdb50"]
        )

        assert success is True
        assert results["pdb_id"] == "AF-P69905-F1"
        assert results["source"] == "alphafold"
        assert results["databases_searched"] == ["afdb50"]
        assert results["hit_count"] == 2
        assert [h["target"] for h in results["hits"]] == ["1ABC", "2XYZ"]


def test_run_discovery_pipeline_defaults_databases_from_config(mock_config, tmp_path):
    structure_path = tmp_path / "4rlt.pdb"
    structure_path.write_text("ATOM")
    mock_config = {
        **mock_config,
        "foldseek": {"default_databases": ["pdb100"]},
    }

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekClient.search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_download.return_value = (True, "ok", structure_path)
        mock_search.return_value = {"alignments": []}

        coordinator = DiscoveryCoordinator(mock_config)
        success, _, results = coordinator.run_discovery_pipeline("4RLT")

        assert success is True
        assert results["databases_searched"] == ["pdb100"]
        mock_search.assert_called_once_with(structure_path, ["pdb100"])
