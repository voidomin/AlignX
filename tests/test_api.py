import time
import asyncio
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

import src.backend.api as api_module
from src.backend.api import app

client = TestClient(app)


def test_health_endpoint():
    """Verify that the health check endpoint returns correct status."""
    with patch(
        "src.backend.mustang_runner.MustangRunner.check_installation"
    ) as mock_check:
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
    """Verify that the history endpoint fetches a page of runs plus pagination metadata."""
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_all_runs.return_value = [
            {
                "id": "run_123",
                "name": "Test Run",
                "pdb_ids": ["1L2Y", "4RLT"],
                "timestamp": "2026-06-26",
            }
        ]
        mock_db.count_runs.return_value = 1
        response = client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["id"] == "run_123"
        assert data["total"] == 1
        assert data["limit"] == 20
        assert data["offset"] == 0
        mock_db.get_all_runs.assert_called_with(limit=20, offset=0, session_id=None)


def test_history_endpoint_pagination_params():
    """Verify that limit/offset query params are forwarded to the database layer."""
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_all_runs.return_value = []
        mock_db.count_runs.return_value = 42
        response = client.get("/api/history?limit=5&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 42
        assert data["limit"] == 5
        assert data["offset"] == 10
        mock_db.get_all_runs.assert_called_with(limit=5, offset=10, session_id=None)


def test_chains_endpoint():
    """Verify that PDB structure chain downloads and analyses execute successfully."""
    with patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.backend.coordinator.PDBManager.analyze_structure"
    ) as mock_analyze, patch(
        "src.backend.coordinator.PDBManager.fetch_metadata", new_callable=AsyncMock
    ) as mock_fetch_metadata:

        # mock asynchronous download return structure
        mock_download.return_value = {
            "4RLT": (True, "Downloaded successfully", Path("dummy_path"))
        }
        mock_analyze.return_value = {"chains": [{"id": "A", "residues_count": 120}]}
        mock_fetch_metadata.return_value = {"4RLT": {"title": "Test Structure"}}

        response = client.post("/api/chains", json={"pdb_ids": ["4RLT"]})
        assert response.status_code == 200
        data = response.json()
        assert "chains" in data
        assert "4RLT" in data["chains"]
        assert data["chains"]["4RLT"]["chains"][0]["id"] == "A"
        assert data["chains"]["4RLT"]["title"] == "Test Structure"


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


def test_interactions_endpoint_adds_aligned_resi_when_run_id_given():
    """Verify /api/interactions translates raw residue numbers into the
    renumbered residue numbers Mustang's aligned structure uses, so the
    frontend 3D viewer highlights the correct atom instead of a nonexistent
    one (raw PDB numbering vs. the cleaned/renumbered aligned structure
    frequently differ)."""
    with patch("src.backend.api.ligand_analyzer") as mock_analyzer, patch(
        "src.backend.api.history_db"
    ) as mock_db, patch(
        "src.backend.api.PDBManager.build_residue_renumber_map"
    ) as mock_remap, patch(
        "pathlib.Path.exists", return_value=True
    ):
        mock_analyzer.calculate_interactions.return_value = {
            "ligand": "RET_A_296",
            "interactions": [
                {"resn": "TYR", "chain": "A", "resi": 191, "distance": 3.2, "type": "H-Bond"},
                {"resn": "LYS", "chain": "A", "resi": 999, "distance": 4.1, "type": "Polar"},
            ],
        }
        mock_db.get_run.return_value = {
            "metadata": {
                "chain_selection": {"4RLT": "A"},
                "clean_params": {"remove_water": True, "remove_heteroatoms": True},
            }
        }
        # resi 191 maps to aligned resi 42; resi 999 was filtered out during cleaning
        mock_remap.return_value = {191: 42}

        response = client.get(
            "/api/interactions?pdb_id=4RLT&ligand_id=RET_A_296&run_id=run_123"
        )
        assert response.status_code == 200
        contacts = response.json()["interactions"]["interactions"]
        assert contacts[0]["resi"] == 191
        assert contacts[0]["aligned_resi"] == 42
        assert contacts[1]["resi"] == 999
        assert contacts[1]["aligned_resi"] is None


def test_sequence_endpoint():
    """Verify that the sequence alignment endpoint returns correct structure and calculations."""
    with patch(
        "src.backend.sequence_viewer.SequenceViewer.parse_afasta"
    ) as mock_parse, patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_conservation"
    ) as mock_cons, patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_identity"
    ) as mock_ident, patch(
        "pathlib.Path.exists", return_value=True
    ):

        mock_parse.return_value = {"4RLT_A": "MVLSPA", "3UG9_A": "MVHLTA"}
        mock_cons.return_value = [1.0, 1.0, 1.0, 0.5, 0.5, 1.0]
        mock_ident.return_value = 66.666

        response = client.get("/api/sequence?run_id=run_123")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run_123"
        assert "4RLT_A" in data["sequences"]
        assert data["identity"] == 66.67
        assert len(data["conservation"]) == 6


def test_path_traversal_is_rejected():
    """Verify that run_id/session_id/pdb_id values with path-traversal characters are rejected (400), not resolved on disk."""
    traversal_cases = [
        "/api/sequence?run_id=../../../etc",
        "/api/sequence?run_id=run_123&session_id=../../etc",
        "/api/report?run_id=..%2F..%2Fetc",
        "/api/ligands?pdb_id=../../secret",
        "/api/comparison?current_run_id=../x&target_run_id=run_123",
    ]
    for path in traversal_cases:
        response = client.get(path)
        assert (
            response.status_code == 400
        ), f"{path} should be rejected, got {response.status_code}"

    response = client.post("/api/jobs/align", json={"pdb_ids": ["../../etc", "3UG9"]})
    assert response.status_code == 400


def test_legitimate_ids_are_not_rejected_by_path_validation():
    """Verify that well-formed run_id/session_id (matching real formats) pass validation and 404 only because the run doesn't exist."""
    response = client.get("/api/sequence?run_id=run_1234567890")
    assert response.status_code == 404  # not found, but not rejected as invalid


@pytest.mark.asyncio
async def test_job_sweep_drops_old_finished_jobs_but_keeps_recent_and_running():
    """Verify the alignment_jobs TTL sweep removes only finished jobs past the TTL."""
    now = time.time()
    api_module.alignment_jobs.clear()
    api_module.alignment_jobs.update(
        {
            "old_completed": {"status": "completed", "finished_at": now - 10_000},
            "old_failed": {"status": "failed", "finished_at": now - 10_000},
            "recent_completed": {"status": "completed", "finished_at": now},
            "still_running": {"status": "running", "created_at": now - 10_000},
        }
    )

    with patch.object(api_module, "_JOB_TTL_SECONDS", 60), patch(
        "asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        mock_sleep.side_effect = [None, asyncio.CancelledError()]
        with pytest.raises(asyncio.CancelledError):
            await api_module._sweep_alignment_jobs()

    remaining = set(api_module.alignment_jobs.keys())
    assert remaining == {"recent_completed", "still_running"}
    api_module.alignment_jobs.clear()


def test_job_submission_rate_limit():
    """Verify that submitting more than the configured max alignment jobs per window is rejected with 429."""
    api_module._job_submission_timestamps.clear()

    with patch.object(api_module, "_JOB_RATE_LIMIT_MAX", 2), patch(
        "src.backend.coordinator.AnalysisCoordinator.run_full_pipeline"
    ) as mock_run:
        mock_run.return_value = (True, "ok", {"id": "job_test_run"})
        payload = {"pdb_ids": ["4RLT", "3UG9"]}
        r1 = client.post("/api/jobs/align", json=payload)
        r2 = client.post("/api/jobs/align", json=payload)
        r3 = client.post("/api/jobs/align", json=payload)

        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r3.status_code == 429

    api_module._job_submission_timestamps.clear()
    api_module.alignment_jobs.clear()


def test_report_endpoint(tmp_path):
    """Verify that the PDF report endpoint generates and returns a PDF file response."""
    dummy_pdf = tmp_path / "mustang_report_test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.report_generator.ReportGenerator.generate_full_report",
        return_value=dummy_pdf,
    ):

        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {"results": {"stats": {"mean_rmsd": 1.25}, "id": "run_123"}},
        }

        response = client.get("/api/report?run_id=run_123")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert b"%PDF-1.4" in response.content


def test_sanitize_for_json_decodes_plotly_binary_typed_arrays():
    """Plotly 6.x serializes numeric trace data (e.g. dendrogram x/y, heatmap z)
    as a compact {dtype, bdata, shape} binary format that the pinned frontend
    Plotly.js CDN version cannot decode. sanitize_for_json must convert this
    back into plain (possibly nested) JSON arrays."""
    import base64
    import numpy as np
    from src.backend.api import sanitize_for_json

    # 1D array (no "shape" key, matches ff.create_dendrogram's trace x/y)
    flat = np.array([0.0, 5.6, 5.6, 0.0])
    flat_encoded = {"dtype": "f8", "bdata": base64.b64encode(flat.tobytes()).decode()}
    assert sanitize_for_json(flat_encoded) == flat.tolist()

    # 2D array (with "shape" key, matches a Heatmap's z)
    matrix = np.array([[0.0, 6.7], [6.7, 0.0]])
    matrix_encoded = {
        "dtype": "f8",
        "bdata": base64.b64encode(matrix.tobytes()).decode(),
        "shape": "2, 2",
    }
    assert sanitize_for_json(matrix_encoded) == matrix.tolist()

    # A dict that merely looks similar (missing bdata) must pass through untouched
    assert sanitize_for_json({"dtype": "f8", "shape": "2, 2"}) == {
        "dtype": "f8",
        "shape": "2, 2",
    }
