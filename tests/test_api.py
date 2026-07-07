import tempfile
import time
import asyncio
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

import src.backend.api as api_module
from src.backend.api import app

client = TestClient(app)


class TestApiKeyAuth:
    """/results and /raw serve generated reports and structure files
    directly off disk (session/run folder names aren't secrets), so they
    must be gated by ALIGNX_API_KEY exactly like /api/* is - a real bug
    once let these two prefixes bypass auth entirely. The SPA shell itself
    (mounted at "/") must stay open regardless, since that's what serves
    the UI a user needs to even reach a login/key-entry flow."""

    def test_results_blocked_without_key_when_configured(self):
        with patch.object(api_module, "_ALIGNX_API_KEY", "secret-key"):
            response = client.get("/results/some_run/alignment.pdb")
        assert response.status_code == 401

    def test_raw_blocked_without_key_when_configured(self):
        with patch.object(api_module, "_ALIGNX_API_KEY", "secret-key"):
            response = client.get("/raw/some_session/1CRN.pdb")
        assert response.status_code == 401

    def test_results_passes_through_with_valid_header(self):
        with patch.object(api_module, "_ALIGNX_API_KEY", "secret-key"):
            response = client.get(
                "/results/some_run/alignment.pdb",
                headers={"X-API-Key": "secret-key"},
            )
        # No such file exists - a 404 (not 401) proves the auth middleware
        # let the request through to StaticFiles.
        assert response.status_code == 404

    def test_results_passes_through_with_valid_query_param(self):
        with patch.object(api_module, "_ALIGNX_API_KEY", "secret-key"):
            response = client.get("/results/some_run/alignment.pdb?api_key=secret-key")
        assert response.status_code == 404

    def test_results_open_when_no_api_key_configured(self):
        with patch.object(api_module, "_ALIGNX_API_KEY", None):
            response = client.get("/results/some_run/alignment.pdb")
        assert response.status_code == 404

    def test_spa_root_never_gated_by_api_key(self):
        with patch.object(api_module, "_ALIGNX_API_KEY", "secret-key"):
            response = client.get("/")
        assert response.status_code != 401


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
        mock_fetch_metadata.return_value = {
            "4RLT": {
                "title": "Test Structure",
                "method": "X-RAY DIFFRACTION",
                "resolution": "2.10 Å",
                "organism": "Homo sapiens",
            }
        }

        response = client.post("/api/chains", json={"pdb_ids": ["4RLT"]})
        assert response.status_code == 200
        data = response.json()
        assert "chains" in data
        assert "4RLT" in data["chains"]
        assert data["chains"]["4RLT"]["chains"][0]["id"] == "A"
        assert data["chains"]["4RLT"]["title"] == "Test Structure"
        assert data["chains"]["4RLT"]["method"] == "X-RAY DIFFRACTION"
        assert data["chains"]["4RLT"]["resolution"] == "2.10 Å"
        assert data["chains"]["4RLT"]["organism"] == "Homo sapiens"
        assert data["chains"]["4RLT"]["source"] == "pdb"


def test_chains_endpoint_tags_source_for_alphafold_id():
    """/api/chains must tag each structure with which database it came from,
    computed directly from the ID prefix (no network call needed)."""
    with patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download, patch(
        "src.backend.coordinator.PDBManager.analyze_structure"
    ) as mock_analyze, patch(
        "src.backend.coordinator.PDBManager.fetch_metadata", new_callable=AsyncMock
    ) as mock_fetch_metadata:
        mock_download.return_value = {
            "AF-P69905-F1": (True, "Downloaded successfully", Path("dummy_path"))
        }
        mock_analyze.return_value = {"chains": [{"id": "A", "residue_count": 141}]}
        mock_fetch_metadata.return_value = {
            "AF-P69905-F1": {
                "title": "[AlphaFold] Hemoglobin subunit alpha",
                "method": "Predicted (AF2)",
                "resolution": "pLDDT Scored",
                "organism": "Homo sapiens",
            }
        }

        response = client.post("/api/chains", json={"pdb_ids": ["AF-P69905-F1"]})
        assert response.status_code == 200
        data = response.json()["chains"]["AF-P69905-F1"]
        assert data["source"] == "alphafold"
        assert data["method"] == "Predicted (AF2)"


def test_upload_endpoint_returns_chain_info_for_a_valid_structure():
    with patch(
        "src.backend.coordinator.PDBManager.save_uploaded_bytes"
    ) as mock_save, patch(
        "src.backend.coordinator.PDBManager.analyze_structure"
    ) as mock_analyze:
        mock_save.return_value = (True, "ok", Path("dummy_path.pdb"))
        mock_analyze.return_value = {"chains": [{"id": "A", "residue_count": 100}]}

        response = client.post(
            "/api/upload",
            files={"file": ("my_structure.pdb", b"ATOM ...", "chemical/x-pdb")},
        )

        assert response.status_code == 200
        chains = response.json()["chains"]
        assert len(chains) == 1
        structure_id = next(iter(chains))
        assert structure_id.startswith("UPLOAD-")
        assert chains[structure_id]["source"] == "upload"
        assert chains[structure_id]["original_filename"] == "my_structure.pdb"
        assert chains[structure_id]["chains"][0]["id"] == "A"


def test_upload_endpoint_rejects_disallowed_file_extension():
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_endpoint_returns_400_when_content_validation_fails():
    """save_uploaded_bytes() rejects content that doesn't parse as a real
    structure - the endpoint must surface that as a 400 with the reason,
    not a generic 500."""
    with patch("src.backend.coordinator.PDBManager.save_uploaded_bytes") as mock_save:
        mock_save.return_value = (
            False,
            "Couldn't parse 'fake.pdb' as a structure: no chains found",
            None,
        )

        response = client.post(
            "/api/upload",
            files={"file": ("fake.pdb", b"not a structure", "chemical/x-pdb")},
        )

        assert response.status_code == 400
        assert "Couldn't parse" in response.json()["detail"]


def test_upload_endpoint_rejects_path_traversal_session_id():
    response = client.post(
        "/api/upload",
        params={"session_id": "../../etc"},
        files={"file": ("s.pdb", b"ATOM ...", "chemical/x-pdb")},
    )
    assert response.status_code == 400


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
                {
                    "resn": "TYR",
                    "chain": "A",
                    "resi": 191,
                    "distance": 3.2,
                    "type": "H-Bond",
                },
                {
                    "resn": "LYS",
                    "chain": "A",
                    "resi": 999,
                    "distance": 4.1,
                    "type": "Polar",
                },
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
        assert data["identity"] == pytest.approx(66.67)
        assert len(data["conservation"]) == 6


def test_comparison_endpoint_uses_upper_triangle_mean():
    """Verify /api/comparison's mean RMSD matches the same upper-triangle-only
    convention used everywhere else in the app (3D viewer HUD, RMSD Matrix
    chart), not a full-matrix mean (which double-counts pairs and is diluted
    by the zero diagonal, systematically underestimating by (N-1)/N)."""
    import pandas as pd

    with patch(
        "src.backend.api.ResultManager.calculate_difference"
    ) as mock_diff, patch(
        "src.backend.api.ResultManager.get_run_rmsd"
    ) as mock_get_rmsd:
        # A single off-diagonal pair of 10.0 -> full-matrix mean would be 5.0
        # (double-counted 10.0 + 10.0 + two zeros, /4), but the correct
        # upper-triangle-only mean is 10.0.
        rmsd_df = pd.DataFrame(
            [[0.0, 10.0], [10.0, 0.0]], index=["4RLT", "3UG9"], columns=["4RLT", "3UG9"]
        )
        mock_diff.return_value = pd.DataFrame(
            [[0.0, 0.0], [0.0, 0.0]], index=["4RLT", "3UG9"], columns=["4RLT", "3UG9"]
        )
        mock_get_rmsd.return_value = rmsd_df

        response = client.get(
            "/api/comparison?current_run_id=run_a&target_run_id=run_b"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_mean_rmsd"] == pytest.approx(10.0)
        assert data["target_mean_rmsd"] == pytest.approx(10.0)


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


def test_report_endpoint_reconstructs_types_from_sanitized_metadata(tmp_path):
    """Persisted run metadata has been through sanitize_for_json (Path -> str,
    DataFrame -> {index, columns, data} dict). ReportGenerator's
    heatmap/tree/matrix sections need the original types, so the endpoint
    must reconstruct them rather than pass the sanitized values through
    (regression test for a real bug: passing the raw dict caused
    'builtin_function_or_method' object has no attribute 'ndim' deep inside
    numpy when the insights/matrix sections tried to treat it as a DataFrame)."""
    dummy_pdf = tmp_path / "mustang_report_test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "pathlib.Path.glob", return_value=[]
    ), patch(
        "src.backend.report_generator.ReportGenerator.generate_full_report",
        return_value=dummy_pdf,
    ) as mock_generate:
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {
                "results": {
                    "stats": {"mean_rmsd": 1.25},
                    "id": "run_123",
                    "heatmap_path": "some/stringified/heatmap.png",
                    "tree_path": "some/stringified/tree.png",
                    "rmsd_df": {
                        "index": ["4RLT", "3UG9"],
                        "columns": ["4RLT", "3UG9"],
                        "data": [[0.0, 6.7], [6.7, 0.0]],
                    },
                }
            },
        }

        response = client.get("/api/report?run_id=run_123")
        assert response.status_code == 200

        results_arg = mock_generate.call_args[0][0]
        assert isinstance(results_arg["heatmap_path"], Path)
        assert isinstance(results_arg["tree_path"], Path)
        assert isinstance(results_arg["rmsd_df"], pd.DataFrame)
        assert results_arg["rmsd_df"].loc["4RLT", "3UG9"] == pytest.approx(6.7)


def test_report_endpoint_sections_param_bypasses_cache(tmp_path):
    """Requesting specific report sections must always regenerate the PDF
    (never reuse a cached full report from a prior default request), and the
    parsed sections list must be passed through to the generator."""
    dummy_pdf = tmp_path / "mustang_report_test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "pathlib.Path.glob", return_value=[tmp_path / "mustang_report_cached.pdf"]
    ), patch(
        "src.backend.report_generator.ReportGenerator.generate_full_report",
        return_value=dummy_pdf,
    ) as mock_generate:
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {"results": {"stats": {"mean_rmsd": 1.25}, "id": "run_123"}},
        }

        response = client.get("/api/report?run_id=run_123&sections=summary,insights")
        assert response.status_code == 200
        mock_generate.assert_called_once()
        _, kwargs = mock_generate.call_args
        assert kwargs["sections"] == ["summary", "insights"]


def test_stats_endpoint():
    """Verify the dashboard aggregate-stats endpoint returns totals from
    HistoryDatabase.get_aggregate_stats()."""
    with patch("src.backend.api.history_db.get_aggregate_stats") as mock_stats:
        mock_stats.return_value = {
            "total_runs": 12,
            "total_proteins_analyzed": 30,
            "cache_size_mb": 4.5,
        }
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_runs"] == 12
        assert data["total_proteins_analyzed"] == 30
        assert data["cache_size_mb"] == pytest.approx(4.5)


def test_notebook_endpoint(tmp_path):
    """Verify the lab notebook endpoint generates and returns an HTML file,
    and that Path-typed fields NotebookExporter needs (result_dir,
    alignment_pdb) are reconstructed rather than trusting the sanitized
    (stringified) values in persisted run metadata."""
    dummy_html = tmp_path / "lab_notebook.html"
    dummy_html.write_text("<html>dummy notebook</html>")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export"
    ) as mock_export:
        mock_export.return_value = dummy_html
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {
                "results": {
                    "stats": {"mean_rmsd": 1.25},
                    "id": "run_123",
                    "result_dir": "some/stringified/path",
                    "alignment_pdb": "some/stringified/path/alignment.pdb",
                }
            },
        }

        response = client.get("/api/notebook?run_id=run_123")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert b"dummy notebook" in response.content

        mock_export.assert_called_once()
        results_arg = mock_export.call_args[0][0]
        assert isinstance(results_arg["result_dir"], Path)
        assert isinstance(results_arg["alignment_pdb"], Path)


def _discover_run(run_id="discover_123", results_overrides=None):
    results = {
        "id": run_id,
        "pdb_id": "1CRN",
        "source": "pdb",
        "databases_searched": ["pdb100"],
        "hit_count": 1,
        "hits": [
            {"target": "AF-P01541-F1-model_v6", "prob": 1.0, "eval": 1e-5, "seqId": 50}
        ],
        "annotations": {
            "neighbors_considered": 1,
            "total_hit_count": 1,
            "candidates_examined": 1,
            "resolvable_hit_count": 1,
            "annotated_neighbor_count": 1,
            "unannotated_neighbor_count": 0,
            "neighbors_with_interactions_count": 0,
            "neighbors_with_pathways_count": 0,
            "top_domains": [{"name": "Thionin", "type": "family", "neighbor_count": 1}],
            "top_go_terms": [],
            "per_neighbor": [],
        },
    }
    if results_overrides:
        results.update(results_overrides)
    return {
        "id": run_id,
        "pdb_ids": ["1CRN"],
        "metadata": {"run_type": "discover", "results": results},
    }


def test_discover_report_endpoint_generates_html():
    dummy_html_dir = Path(tempfile.mkdtemp())
    dummy_html = dummy_html_dir / "report.html"
    dummy_html.write_text("<html>dummy discover report</html>")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.discovery_report_exporter.DiscoveryReportExporter.export"
    ) as mock_export:
        mock_get_run.return_value = _discover_run()
        mock_export.return_value = dummy_html

        response = client.get("/api/discover/report?run_id=discover_123")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert b"dummy discover report" in response.content
        mock_export.assert_called_once()


def test_discover_report_endpoint_rejects_compare_run():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {"results": {"id": "run_123"}},  # no run_type -> compare
        }
        response = client.get("/api/discover/report?run_id=run_123")
        assert response.status_code == 400
        assert "not a Discover run" in response.json()["detail"]


def test_discover_report_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/discover/report?run_id=nope")
        assert response.status_code == 404


def test_discover_export_json_endpoint_returns_raw_results():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = _discover_run()
        response = client.get("/api/discover/export?run_id=discover_123")

        assert response.status_code == 200
        assert response.json()["pdb_id"] == "1CRN"
        assert "attachment" in response.headers["content-disposition"]
        assert "discover_123.json" in response.headers["content-disposition"]


def test_discover_export_json_endpoint_rejects_compare_run():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {"results": {"id": "run_123"}},
        }
        response = client.get("/api/discover/export?run_id=run_123")
        assert response.status_code == 400


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


def test_discover_endpoint_rejects_missing_pdb_id():
    api_module._job_submission_timestamps.clear()
    response = client.post("/api/jobs/discover", json={"pdb_id": ""})
    assert response.status_code == 400


def test_discover_endpoint_rejects_invalid_pdb_id():
    api_module._job_submission_timestamps.clear()
    response = client.post("/api/jobs/discover", json={"pdb_id": "not-a-valid-id"})
    assert response.status_code == 400


def test_discover_endpoint_rejects_path_traversal():
    api_module._job_submission_timestamps.clear()
    response = client.post("/api/jobs/discover", json={"pdb_id": "../../etc"})
    assert response.status_code == 400


def test_discover_endpoint_rejects_unknown_database():
    api_module._job_submission_timestamps.clear()
    response = client.post(
        "/api/jobs/discover", json={"pdb_id": "4RLT", "databases": ["not-a-real-db"]}
    )
    assert response.status_code == 400


def test_discover_job_submission_returns_queued():
    """Submitting a valid discovery job returns a job_id immediately with
    status "queued" - it must not block on the (potentially slow, rate
    limited) Foldseek pipeline."""
    api_module.discovery_jobs.clear()
    api_module._job_submission_timestamps.clear()
    with patch(
        "src.backend.discovery_coordinator.DiscoveryCoordinator.run_discovery_pipeline"
    ) as mock_run:
        mock_run.return_value = (True, "ok", {"pdb_id": "4RLT"})

        response = client.post("/api/jobs/discover", json={"pdb_id": "4RLT"})
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["job_id"] in api_module.discovery_jobs

    api_module.discovery_jobs.clear()


@pytest.mark.asyncio
async def test_discover_job_execution_completes_and_is_pollable():
    """Directly exercises _execute_discovery_job (the background task the
    endpoint schedules via asyncio.create_task) end-to-end, then confirms
    GET /api/jobs/{job_id} - the same endpoint used for alignment jobs -
    surfaces the DiscoveryCoordinator result."""
    api_module.discovery_jobs.clear()
    job_id = "test-discover-job"
    api_module.discovery_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.discovery_coordinator.DiscoveryCoordinator.run_discovery_pipeline"
    ) as mock_run:
        mock_run.return_value = (
            True,
            "Discovery completed successfully",
            {
                "pdb_id": "4RLT",
                "source": "pdb",
                "databases_searched": ["pdb100", "afdb50"],
                "hit_count": 1,
                "hits": [{"target": "1ABC", "prob": 0.99}],
            },
        )
        await api_module._execute_discovery_job(
            job_id, pdb_id="4RLT", databases=None, session_id=None
        )

    poll = client.get(f"/api/jobs/{job_id}")
    assert poll.json()["status"] == "completed"
    assert poll.json()["results"]["hit_count"] == 1
    assert poll.json()["results"]["hits"][0]["target"] == "1ABC"

    api_module.discovery_jobs.clear()


@pytest.mark.asyncio
async def test_discover_job_execution_surfaces_pipeline_failure():
    api_module.discovery_jobs.clear()
    job_id = "test-discover-job-fail"
    api_module.discovery_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.discovery_coordinator.DiscoveryCoordinator.run_discovery_pipeline"
    ) as mock_run:
        mock_run.return_value = (False, "Foldseek search failed: timed out", None)
        await api_module._execute_discovery_job(
            job_id, pdb_id="4RLT", databases=None, session_id=None
        )

    poll = client.get(f"/api/jobs/{job_id}")
    assert poll.json()["status"] == "failed"
    assert "Foldseek search failed" in poll.json()["error"]

    api_module.discovery_jobs.clear()


def test_discover_job_submission_rate_limit():
    api_module._job_submission_timestamps.clear()
    with patch.object(api_module, "_DISCOVERY_RATE_LIMIT_MAX", 1), patch(
        "src.backend.discovery_coordinator.DiscoveryCoordinator.run_discovery_pipeline"
    ) as mock_run:
        mock_run.return_value = (True, "ok", {"pdb_id": "4RLT"})
        r1 = client.post("/api/jobs/discover", json={"pdb_id": "4RLT"})
        r2 = client.post("/api/jobs/discover", json={"pdb_id": "3UG9"})

        assert r1.status_code == 202
        assert r2.status_code == 429

    api_module._job_submission_timestamps.clear()
    api_module.discovery_jobs.clear()


@pytest.mark.asyncio
async def test_discovery_job_sweep_drops_old_finished_jobs_but_keeps_recent_and_running():
    now = time.time()
    api_module.discovery_jobs.clear()
    api_module.discovery_jobs.update(
        {
            "old_completed": {"status": "completed", "finished_at": now - 10_000},
            "recent_completed": {"status": "completed", "finished_at": now},
            "still_running": {"status": "running", "created_at": now - 10_000},
        }
    )

    with patch.object(api_module, "_JOB_TTL_SECONDS", 60), patch(
        "asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        mock_sleep.side_effect = [None, asyncio.CancelledError()]
        with pytest.raises(asyncio.CancelledError):
            await api_module._sweep_discovery_jobs()

    remaining = set(api_module.discovery_jobs.keys())
    assert remaining == {"recent_completed", "still_running"}
    api_module.discovery_jobs.clear()
