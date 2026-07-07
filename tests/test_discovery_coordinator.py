from unittest.mock import patch, AsyncMock

import pytest

from src.backend.discovery_coordinator import DiscoveryCoordinator
from src.backend.foldseek_client import FoldseekError


@pytest.fixture(autouse=True)
def mock_history_db_save():
    """A successful run_discovery_pipeline() now persists to HistoryDatabase
    (real sqlite I/O against run_history.db) so Discover runs show up on
    the Dashboard/History tab. Mock it in every test so the suite doesn't
    write test data into the project's actual history database."""
    with patch(
        "src.backend.discovery_coordinator.HistoryDatabase.save_run", return_value=True
    ) as mock_save:
        yield mock_save


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
                        [
                            {"target": "1ABC", "prob": 1.0},
                            {"target": "2XYZ", "prob": 0.9},
                        ]
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
        assert results["annotations"] is None  # no hits -> nothing to annotate
        mock_search.assert_called_once_with(structure_path, ["pdb100"])


def test_run_discovery_pipeline_includes_annotation_summary(mock_config, tmp_path):
    """When Foldseek returns hits, the pipeline must fetch and attach an
    annotation summary (InterPro domains / QuickGO terms) alongside them."""
    structure_path = tmp_path / "af-p01541-f1.pdb"
    structure_path.write_text("ATOM")

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekClient.search",
        new_callable=AsyncMock,
    ) as mock_search, patch(
        "src.backend.discovery_coordinator.AnnotationAggregator.aggregate_for_hits",
        new_callable=AsyncMock,
    ) as mock_aggregate:
        mock_download.return_value = (True, "ok", structure_path)
        mock_search.return_value = {"alignments": [{"target": "AF-P01541-F1-model_v6"}]}
        mock_aggregate.return_value = {
            "neighbors_considered": 1,
            "annotated_neighbor_count": 1,
            "unannotated_neighbor_count": 0,
            "top_domains": [{"name": "Thionin", "type": "family", "neighbor_count": 1}],
            "top_go_terms": [],
            "per_neighbor": [],
        }

        coordinator = DiscoveryCoordinator(mock_config)
        success, _, results = coordinator.run_discovery_pipeline("AF-P01541-F1")

        assert success is True
        assert results["annotations"]["top_domains"][0]["name"] == "Thionin"
        mock_aggregate.assert_called_once()


def test_run_discovery_pipeline_survives_annotation_failure(mock_config, tmp_path):
    """A flaky InterPro/QuickGO call must not fail a run that already has
    valid Foldseek hits - annotations should just come back None."""
    structure_path = tmp_path / "af-p01541-f1.pdb"
    structure_path.write_text("ATOM")

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekClient.search",
        new_callable=AsyncMock,
    ) as mock_search, patch(
        "src.backend.discovery_coordinator.AnnotationAggregator.aggregate_for_hits",
        new_callable=AsyncMock,
    ) as mock_aggregate:
        mock_download.return_value = (True, "ok", structure_path)
        mock_search.return_value = {"alignments": [{"target": "AF-P01541-F1-model_v6"}]}
        mock_aggregate.side_effect = RuntimeError("EBI is down")

        coordinator = DiscoveryCoordinator(mock_config)
        success, _, results = coordinator.run_discovery_pipeline("AF-P01541-F1")

        assert success is True
        assert results["hit_count"] == 1
        assert results["annotations"] is None


def test_run_discovery_pipeline_uses_local_backend_when_configured(
    mock_config, tmp_path
):
    structure_path = tmp_path / "4rlt.pdb"
    structure_path.write_text("ATOM")
    config = {
        **mock_config,
        "foldseek": {"backend": "local", "local": {"database_dir": "/some/db"}},
    }

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekRunner.search_against_directory"
    ) as mock_local_search, patch(
        "src.backend.discovery_coordinator.FoldseekClient.search",
        new_callable=AsyncMock,
    ) as mock_api_search:
        mock_download.return_value = (True, "ok", structure_path)
        mock_local_search.return_value = (
            True,
            "Local Foldseek search completed successfully",
            [{"target": "2lyz", "eval": 1e-20, "prob": 1.0, "seqId": 100.0}],
        )

        coordinator = DiscoveryCoordinator(config)
        success, msg, results = coordinator.run_discovery_pipeline("4RLT")

        assert success is True
        assert results["hit_count"] == 1
        assert results["hits"][0]["target"] == "2lyz"
        assert results["databases_searched"] == ["local:/some/db"]
        mock_local_search.assert_called_once()
        mock_api_search.assert_not_called()


def test_run_discovery_pipeline_local_backend_requires_database_dir(
    mock_config, tmp_path
):
    structure_path = tmp_path / "4rlt.pdb"
    structure_path.write_text("ATOM")
    config = {**mock_config, "foldseek": {"backend": "local", "local": {}}}

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download:
        mock_download.return_value = (True, "ok", structure_path)

        coordinator = DiscoveryCoordinator(config)
        success, msg, results = coordinator.run_discovery_pipeline("4RLT")

        assert success is False
        assert "database_dir is not configured" in msg
        assert results is None


def test_run_discovery_pipeline_reports_local_backend_search_failure(
    mock_config, tmp_path
):
    structure_path = tmp_path / "4rlt.pdb"
    structure_path.write_text("ATOM")
    config = {
        **mock_config,
        "foldseek": {"backend": "local", "local": {"database_dir": "/some/db"}},
    }

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekRunner.search_against_directory"
    ) as mock_local_search:
        mock_download.return_value = (True, "ok", structure_path)
        mock_local_search.return_value = (False, "Foldseek binary not found", [])

        coordinator = DiscoveryCoordinator(config)
        success, msg, results = coordinator.run_discovery_pipeline("4RLT")

        assert success is False
        assert "Foldseek binary not found" in msg
        assert results is None


def test_run_discovery_pipeline_saves_to_history_on_success(
    mock_config, tmp_path, mock_history_db_save
):
    """Discover runs must show up on the Dashboard/History tab the same way
    Compare runs already do - unlike Compare, there's no result directory
    to reload, so the full results dict is stashed in metadata.results and
    "run_type": "discover" tells the frontend how to route a click on it."""
    structure_path = tmp_path / "af-p01541-f1.pdb"
    structure_path.write_text("ATOM")

    with patch(
        "src.backend.discovery_coordinator.PDBManager.download_pdb",
        new_callable=AsyncMock,
    ) as mock_download, patch(
        "src.backend.discovery_coordinator.FoldseekClient.search",
        new_callable=AsyncMock,
    ) as mock_search, patch(
        "src.backend.discovery_coordinator.AnnotationAggregator.aggregate_for_hits",
        new_callable=AsyncMock,
    ) as mock_aggregate:
        mock_download.return_value = (True, "ok", structure_path)
        mock_search.return_value = {"alignments": [{"target": "AF-P01541-F1-model_v6"}]}
        mock_aggregate.return_value = {
            "neighbors_considered": 1,
            "annotated_neighbor_count": 1,
            "unannotated_neighbor_count": 0,
            "top_domains": [],
            "top_go_terms": [],
            "per_neighbor": [],
        }

        coordinator = DiscoveryCoordinator(mock_config, session_id="session-1")
        success, _, results = coordinator.run_discovery_pipeline("AF-P01541-F1")

        assert success is True
        mock_history_db_save.assert_called_once()
        args, kwargs = mock_history_db_save.call_args
        assert args[0] == results["id"]
        assert args[1] == results["name"]
        assert args[2] == ["AF-P01541-F1"]
        assert kwargs["metadata"]["run_type"] == "discover"
        assert kwargs["metadata"]["results"]["pdb_id"] == "AF-P01541-F1"
        assert kwargs["session_id"] == "session-1"


def test_run_discovery_pipeline_does_not_save_to_history_on_failure(
    mock_config, mock_history_db_save
):
    coordinator = DiscoveryCoordinator(mock_config)
    success, _, _ = coordinator.run_discovery_pipeline("not-a-valid-id")

    assert success is False
    mock_history_db_save.assert_not_called()
