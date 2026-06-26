import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from src.backend.api import app

client = TestClient(app)


def test_health_endpoint():
    """Verify that the health check endpoint returns correct status."""
    with patch("src.backend.mustang_runner.MustangRunner.check_installation") as mock_check:
        mock_check.return_value = (True, "Mustang is verified")
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["mustang_installed"] is True
        assert "Mustang is verified" in data["mustang_message"]


def test_suggest_endpoint():
    """Verify that the suggestion endpoint calls RCSB suggest API correctly."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_res = MagicMock()
        mock_res.read.return_value = b'{"suggestions": {"rcsb_entry_container_identifiers.entry_id": [{"text": "4RLT"}, {"text": "3UG9"}]}}'
        mock_urlopen.return_value.__enter__.return_value = mock_res
        
        response = client.get("/api/suggest?q=4rl")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "4rl"
        assert "4RLT" in data["suggestions"]
        assert "3UG9" in data["suggestions"]


def test_history_endpoint():
    """Verify that the history endpoint fetches runs from the database mock."""
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_all_runs.return_value = [
            {"id": "run_123", "name": "Test Run", "pdb_ids": ["1L2Y", "4RLT"], "timestamp": "2026-06-26"}
        ]
        response = client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["id"] == "run_123"


def test_chains_endpoint():
    """Verify that PDB structure chain downloads and analyses execute successfully."""
    with patch("src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock) as mock_download, \
         patch("src.backend.coordinator.PDBManager.analyze_structure") as mock_analyze:
        
        # mock asynchronous download return structure
        mock_download.return_value = {"4RLT": (True, "Downloaded successfully", Path("dummy_path"))}
        mock_analyze.return_value = {"chains": [{"id": "A", "residues_count": 120}]}
        
        response = client.post("/api/chains", json={"pdb_ids": ["4RLT"]})
        assert response.status_code == 200
        data = response.json()
        assert "chains" in data
        assert "4RLT" in data["chains"]
        assert data["chains"]["4RLT"]["chains"][0]["id"] == "A"


def test_memory_endpoints():
    """Verify that memory retrieval and clear endpoints return correct structures."""
    response = client.get("/api/memory")
    assert response.status_code == 200
    data = response.json()
    assert "ram_mb" in data
    assert data["status"] in ["ok", "error"]

    response = client.post("/api/memory/clear")
    assert response.status_code == 200
    data = response.json()
    assert "ram_mb" in data
    assert data["status"] in ["cleared"]


def test_interactions_and_ligands_endpoints():
    """Verify that ligands and interactions retrieval endpoints handle mocks successfully."""
    with patch("src.backend.api.ligand_analyzer") as mock_analyzer:
        mock_analyzer.get_ligands.return_value = [{"id": "RET_A_296", "name": "RET"}]
        mock_analyzer.calculate_interactions.return_value = {"interactions": []}
        
        # Mock Path.exists to return True so it finds the PDB file
        with patch("pathlib.Path.exists", return_value=True):
            response = client.get("/api/ligands?pdb_id=4RLT")
            assert response.status_code == 200
            assert response.json()["pdb_id"] == "4RLT"
            
            response = client.get("/api/interactions?pdb_id=4RLT&ligand_id=RET_A_296")
            assert response.status_code == 200
            assert response.json()["ligand_id"] == "RET_A_296"


