import base64
import tempfile
import time
import asyncio
import numpy as np
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock, ANY
from pathlib import Path

import src.backend.api as api_module
from src.backend.api import app

client = TestClient(app)


class TestSanitizeForJsonHelpers:
    """api.py's own sanitize_for_json and its helper functions - a
    separate implementation from coordinator.py's, handling Plotly's
    binary-typed-array trace format and NaN/Infinity replacement, which
    coordinator.py's version doesn't need to deal with."""

    def test_coerce_numpy_scalar_converts_0d_scalar(self):
        assert api_module._coerce_numpy_scalar(np.float64(1.5)) == pytest.approx(1.5)
        assert isinstance(api_module._coerce_numpy_scalar(np.float64(1.5)), float)

    def test_coerce_numpy_scalar_passes_through_ndarray(self):
        arr = np.array([1, 2, 3])
        assert api_module._coerce_numpy_scalar(arr) is arr

    def test_coerce_numpy_scalar_passes_through_plain_value(self):
        assert api_module._coerce_numpy_scalar("hello") == "hello"

    def test_coerce_numpy_scalar_falls_back_on_item_failure(self):
        class FakeScalar:
            dtype = "fake"

            def item(self):
                raise ValueError("boom")

        fake = FakeScalar()
        assert api_module._coerce_numpy_scalar(fake) is fake

    def test_is_plotly_bdata_detects_the_shape(self):
        assert api_module._is_plotly_bdata({"dtype": "f8", "bdata": "abc="}) is True

    def test_is_plotly_bdata_rejects_missing_keys(self):
        assert api_module._is_plotly_bdata({"dtype": "f8"}) is False
        assert api_module._is_plotly_bdata("not-a-dict") is False

    def test_decode_plotly_bdata_flat_array(self):
        raw = np.array([1.0, 2.0, 3.0], dtype="f8")
        encoded = {"dtype": "f8", "bdata": base64.b64encode(raw.tobytes()).decode()}
        assert api_module._decode_plotly_bdata(encoded) == [1.0, 2.0, 3.0]

    def test_decode_plotly_bdata_2d_array_uses_shape(self):
        raw = np.array([[1.0, 2.0], [3.0, 4.0]], dtype="f8")
        encoded = {
            "dtype": "f8",
            "bdata": base64.b64encode(raw.tobytes()).decode(),
            "shape": "2,2",
        }
        assert api_module._decode_plotly_bdata(encoded) == [[1.0, 2.0], [3.0, 4.0]]

    def test_decode_plotly_bdata_falls_back_on_bad_data(self):
        encoded = {"dtype": "f8", "bdata": "not-valid-base64!!!"}
        result = api_module._decode_plotly_bdata(encoded)
        assert result == {"dtype": "f8", "bdata": "not-valid-base64!!!"}

    def test_is_intlike(self):
        assert api_module._is_intlike(5) is True
        assert api_module._is_intlike(np.int64(5)) is True
        assert api_module._is_intlike(5.0) is False

    def test_is_floatlike(self):
        assert api_module._is_floatlike(5.0) is True
        assert api_module._is_floatlike(np.float32(5.0)) is True
        assert api_module._is_floatlike(5) is False

    def test_coerce_float_replaces_nan_and_inf_with_none(self):
        assert api_module._coerce_float(float("nan")) is None
        assert api_module._coerce_float(float("inf")) is None
        assert api_module._coerce_float(1.5) == pytest.approx(1.5)

    def test_coerce_float_returns_none_on_conversion_failure(self):
        assert api_module._coerce_float("not-a-number") is None

    def test_coerce_via_to_dict_handles_dataframe(self):
        df = pd.DataFrame({"a": [1, 2]}, index=["x", "y"])
        result = api_module._coerce_via_to_dict(df)
        assert result["columns"] == ["a"]

    def test_coerce_via_to_dict_falls_back_to_str_on_failure(self):
        class Broken:
            def to_dict(self):
                raise RuntimeError("boom")

        result = api_module._coerce_via_to_dict(Broken())
        assert isinstance(result, str)

    def test_sanitize_for_json_replaces_nan_with_none(self):
        assert api_module.sanitize_for_json(float("nan")) is None

    def test_sanitize_for_json_handles_dict_list_tuple_set(self):
        assert api_module.sanitize_for_json({"a": 1}) == {"a": 1}
        assert api_module.sanitize_for_json([1, 2]) == [1, 2]
        assert api_module.sanitize_for_json((1, 2)) == [1, 2]
        assert api_module.sanitize_for_json({1, 2}) == sorted([1, 2])

    def test_sanitize_for_json_handles_ndarray(self):
        assert api_module.sanitize_for_json(np.array([1, 2, 3])) == [1, 2, 3]

    def test_sanitize_for_json_handles_path(self):
        assert api_module.sanitize_for_json(Path("a/b")) == str(Path("a/b"))

    def test_sanitize_for_json_uses_to_plotly_json_when_available(self):
        class FakeFigure:
            def to_plotly_json(self):
                return {"data": [], "layout": {}}

        assert api_module.sanitize_for_json(FakeFigure()) == {
            "data": [],
            "layout": {},
        }

    def test_sanitize_for_json_uses_to_dict_when_no_to_plotly_json(self):
        df = pd.DataFrame({"a": [1, 2]}, index=["x", "y"])
        result = api_module.sanitize_for_json(df)
        assert result["columns"] == ["a"]

    def test_sanitize_for_json_decodes_plotly_bdata_recursively(self):
        raw = np.array([1.0, 2.0], dtype="f8")
        val = {"x": {"dtype": "f8", "bdata": base64.b64encode(raw.tobytes()).decode()}}
        assert api_module.sanitize_for_json(val) == {"x": [1.0, 2.0]}


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

    def test_options_preflight_never_gated_by_api_key(self):
        """Real bug, live-verified against production (2026-07-15): a
        browser's CORS preflight (OPTIONS) never carries the X-API-Key
        header at all - browsers don't attach custom headers to preflight
        requests - so without this exemption, this middleware 401'd every
        preflight before CORSMiddleware ever got a chance to answer it with
        real CORS headers, which the browser then reports as a CORS
        failure on the actual request. This broke the deployed frontend
        entirely the moment ALIGNX_API_KEY was first configured."""
        with patch.object(api_module, "_ALIGNX_API_KEY", "secret-key"):
            response = client.options(
                "/api/history",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
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


def test_history_endpoint_strips_heavy_results_metadata():
    """/api/history backs the History/Dashboard list views, which never
    render metadata.results (Plotly figures, RMSD matrices, Discover hit
    payloads) - only GET /api/runs/{id} should hand that back, on demand,
    once a specific run is actually reloaded. Regression test for the 42MB
    response this endpoint used to produce once run history accumulated."""
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_all_runs.return_value = [
            {
                "id": "run_123",
                "name": "Test Run",
                "pdb_ids": ["1L2Y", "4RLT"],
                "timestamp": "2026-06-26",
                "metadata": {
                    "run_type": "discover",
                    "chain_selection": {"1L2Y": "A"},
                    "results": {"heatmap_fig": {"data": ["huge"] * 1000}},
                },
            }
        ]
        mock_db.count_runs.return_value = 1
        response = client.get("/api/history")
        assert response.status_code == 200
        run = response.json()["runs"][0]
        assert "results" not in run["metadata"]
        assert run["metadata"]["run_type"] == "discover"
        assert run["metadata"]["chain_selection"] == {"1L2Y": "A"}


def test_get_run_by_id_returns_the_raw_record():
    """Backs shareable run links - fetches one run by ID directly, with no
    session_id/ownership check (matching every other run_id-keyed read
    endpoint's existing behavior)."""
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = {
            "id": "run_1234567890_abcdef0123456789",
            "name": "Test Run",
            "pdb_ids": ["1L2Y", "4RLT"],
            "session_id": "someone_elses_session",
            "metadata": {},
        }
        response = client.get("/api/runs/run_1234567890_abcdef0123456789")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "run_1234567890_abcdef0123456789"
        mock_db.get_run.assert_called_with("run_1234567890_abcdef0123456789")


def test_get_run_by_id_404s_for_unknown_run():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = None
        response = client.get("/api/runs/run_does_not_exist")
        assert response.status_code == 404


def test_get_run_by_id_rejects_path_traversal():
    # A run_id containing "/" doesn't match the {run_id} path segment at
    # all (FastAPI's router 404s before this endpoint ever runs) - a
    # same-segment invalid value exercises _safe_segment() itself instead.
    response = client.get("/api/runs/..%2F..%2Fetc")
    assert response.status_code == 404

    response = client.get("/api/runs/run%20with%20spaces")
    assert response.status_code == 400


def test_delete_history_run_removes_the_record():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = {"id": "run_1", "session_id": "sess_1"}
        response = client.delete("/api/history/run_1?session_id=sess_1")

        assert response.status_code == 200
        assert response.json()["deleted"] == "run_1"
        mock_db.delete_run.assert_called_once_with("run_1")


def test_delete_history_run_404s_for_unknown_run():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = None
        response = client.delete("/api/history/does_not_exist?session_id=sess_1")

        assert response.status_code == 404
        mock_db.delete_run.assert_not_called()


def test_delete_history_run_403s_for_a_different_sessions_run():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = {"id": "run_1", "session_id": "someone_else"}
        response = client.delete("/api/history/run_1?session_id=sess_1")

        assert response.status_code == 403
        mock_db.delete_run.assert_not_called()


def test_delete_history_run_allows_deleting_a_legacy_run_with_no_session_id():
    """A run predating session scoping has no session_id at all - it's
    already unscoped for reads (get_run_by_id), so deletion shouldn't be
    more restrictive than that."""
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = {"id": "run_1", "session_id": None}
        response = client.delete("/api/history/run_1?session_id=sess_1")

        assert response.status_code == 200
        mock_db.delete_run.assert_called_once_with("run_1")


def test_update_run_notes_sets_notes_and_tags():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = {"id": "run_1", "session_id": "sess_1"}
        response = client.put(
            "/api/history/run_1/notes?session_id=sess_1",
            json={"notes": "Interesting fold", "tags": ["kinase", "review"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Interesting fold"
        assert data["tags"] == ["kinase", "review"]
        mock_db.update_run_notes.assert_called_once_with(
            "run_1", notes="Interesting fold", tags=["kinase", "review"]
        )


def test_update_run_notes_404s_for_unknown_run():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = None
        response = client.put(
            "/api/history/does_not_exist/notes?session_id=sess_1",
            json={"notes": "x"},
        )

        assert response.status_code == 404
        mock_db.update_run_notes.assert_not_called()


def test_update_run_notes_403s_for_a_different_sessions_run():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = {"id": "run_1", "session_id": "someone_else"}
        response = client.put(
            "/api/history/run_1/notes?session_id=sess_1",
            json={"notes": "x"},
        )

        assert response.status_code == 403
        mock_db.update_run_notes.assert_not_called()


def test_update_run_notes_allows_editing_a_legacy_run_with_no_session_id():
    with patch("src.backend.api.history_db") as mock_db:
        mock_db.get_run.return_value = {"id": "run_1", "session_id": None}
        response = client.put(
            "/api/history/run_1/notes?session_id=sess_1",
            json={"notes": "x"},
        )

        assert response.status_code == 200
        mock_db.update_run_notes.assert_called_once_with("run_1", notes="x", tags=None)


def test_clear_history_falls_back_to_a_global_wipe_without_a_session_id():
    """The bundled SPA doesn't send session_id anywhere today, so omitting
    it must still work (matching the single-user Streamlit app this is
    ported from) rather than reject the request."""
    with patch("src.backend.api.history_db") as mock_db:
        response = client.delete("/api/history")

        assert response.status_code == 200
        assert response.json()["cleared"] == "all"
        mock_db.clear_all_runs.assert_called_once()
        mock_db.clear_runs_for_session.assert_not_called()


def test_clear_history_clears_only_the_given_session():
    with patch("src.backend.api.history_db") as mock_db:
        response = client.delete("/api/history?session_id=sess_1")

        assert response.status_code == 200
        assert response.json()["cleared"] == "sess_1"
        mock_db.clear_runs_for_session.assert_called_once_with("sess_1")


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
                "citation": {
                    "pubmed_id": 12345,
                    "doi": "10.1000/xyz",
                    "authors": ["Someone, A."],
                    "title": "A paper",
                },
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
        assert data["chains"]["4RLT"]["citation"]["pubmed_id"] == 12345


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


def test_chains_endpoint_rejects_empty_pdb_ids_list():
    response = client.post("/api/chains", json={"pdb_ids": []})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_chains_endpoint_reports_download_failures():
    with patch(
        "src.backend.coordinator.PDBManager.batch_download", new_callable=AsyncMock
    ) as mock_download:
        mock_download.return_value = {"9ZZZ": (False, "404 Not Found", None)}

        response = client.post("/api/chains", json={"pdb_ids": ["9ZZZ"]})

        assert response.status_code == 400
        assert "9ZZZ" in response.json()["detail"]


@pytest.fixture
def restore_config():
    """Settings endpoints mutate api_module.config in place (deliberately -
    see update_settings' docstring) and persist to config.yaml on disk.
    Snapshot and restore both around each test so these tests don't leak
    state into the rest of the suite or overwrite the repo's real
    config.yaml."""
    import copy

    original_config = copy.deepcopy(api_module.config)
    original_yaml = Path("config.yaml").read_text()
    yield
    api_module.config.clear()
    api_module.config.update(original_config)
    Path("config.yaml").write_text(original_yaml)


class TestSettingsEndpoints:
    def test_get_settings_returns_the_current_config_subset(self, restore_config):
        api_module.config["mustang"]["backend"] = "wsl"
        api_module.config["visualization"]["heatmap_colormap"] = "plasma"

        response = client.get("/api/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["mustang_backend"] == "wsl"
        assert data["heatmap_colormap"] == "plasma"

    def test_post_settings_updates_the_shared_config_object_in_place(
        self, restore_config
    ):
        with patch("src.backend.api.save_config"):
            response = client.post(
                "/api/settings",
                json={
                    "mustang_backend": "native",
                    "mustang_timeout": 300,
                    "max_proteins": 10,
                    "max_file_size_mb": 200,
                    "heatmap_colormap": "plasma",
                    "viewer_default_style": "stick",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["mustang_backend"] == "native"
        assert data["max_proteins"] == 10
        # The same dict object every AnalysisCoordinator(config)/PDBManager(config)
        # call already references - confirms the in-place-mutation design
        # actually took effect on the real shared object, not a copy.
        assert api_module.config["mustang"]["backend"] == "native"
        assert api_module.config["core"]["max_proteins"] == 10
        assert api_module.config["pdb"]["max_file_size_mb"] == 200
        assert api_module.config["visualization"]["heatmap_colormap"] == "plasma"
        assert api_module.config["visualization"]["viewer_default_style"] == "stick"

    def test_post_settings_persists_to_disk(self, restore_config):
        response = client.post(
            "/api/settings",
            json={
                "mustang_backend": "wsl",
                "mustang_timeout": 600,
                "max_proteins": 20,
                "max_file_size_mb": 500,
                "heatmap_colormap": "viridis",
                "viewer_default_style": "cartoon",
            },
        )

        assert response.status_code == 200
        import yaml

        on_disk = yaml.safe_load(Path("config.yaml").read_text())
        assert on_disk["mustang"]["backend"] == "wsl"

    def test_post_settings_rejects_an_invalid_mustang_backend(self, restore_config):
        response = client.post(
            "/api/settings",
            json={
                "mustang_backend": "not-a-real-backend",
                "mustang_timeout": 600,
                "max_proteins": 20,
                "max_file_size_mb": 500,
                "heatmap_colormap": "viridis",
                "viewer_default_style": "cartoon",
            },
        )

        assert response.status_code == 400

    def test_post_settings_rejects_max_proteins_out_of_bounds(self, restore_config):
        response = client.post(
            "/api/settings",
            json={
                "mustang_backend": "auto",
                "mustang_timeout": 600,
                "max_proteins": 999,
                "max_file_size_mb": 500,
                "heatmap_colormap": "viridis",
                "viewer_default_style": "cartoon",
            },
        )

        assert response.status_code == 422

    def test_post_settings_500s_when_save_to_disk_fails(self, restore_config):
        with patch("src.backend.api.save_config", side_effect=OSError("disk full")):
            response = client.post(
                "/api/settings",
                json={
                    "mustang_backend": "auto",
                    "mustang_timeout": 600,
                    "max_proteins": 20,
                    "max_file_size_mb": 500,
                    "heatmap_colormap": "viridis",
                    "viewer_default_style": "cartoon",
                },
            )

        assert response.status_code == 500
        assert "disk full" in response.json()["detail"]

    def test_reset_settings_restores_hardcoded_defaults(self, restore_config):
        with patch("src.backend.api.save_config"):
            api_module.config["mustang"]["backend"] = "native"
            api_module.config["core"]["max_proteins"] = 5
            api_module.config["visualization"]["heatmap_colormap"] = "plasma"

            response = client.post("/api/settings/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["mustang_backend"] == "auto"
        assert data["max_proteins"] == 20
        # Regression test: these defaults must match Streamlit's own
        # DEFAULT_SETTINGS (pages/3_Settings.py) - "viridis", not
        # VisualizationConfig's unrelated Pydantic field default
        # ("RdYlBu_r"), which "Restore Defaults" was briefly wired to by
        # mistake and would have silently restored the wrong colormap.
        assert data["heatmap_colormap"] == "viridis"
        assert api_module.config["mustang"]["backend"] == "auto"
        assert api_module.config["core"]["max_proteins"] == 20
        assert api_module.config["visualization"]["heatmap_colormap"] == "viridis"


class TestRateLimitClientKey:
    def test_uses_api_key_header_when_present(self):
        key = api_module._rate_limit_client_key(
            MagicMock(
                headers={"X-API-Key": "secret"},
                query_params={},
            )
        )
        assert key == "key:secret"

    def test_falls_back_to_client_ip_when_no_key(self):
        request = MagicMock(headers={}, query_params={})
        request.client.host = "127.0.0.1"

        key = api_module._rate_limit_client_key(request)

        assert key == "ip:127.0.0.1"


class TestCorsMisconfigurationWarning:
    def test_warns_when_api_key_set_and_cors_still_default(self):
        warning = api_module._cors_misconfiguration_warning("secret-key", "*")
        assert warning is not None
        assert "ALIGNX_CORS_ORIGINS" in warning

    def test_no_warning_when_api_key_unset(self):
        assert api_module._cors_misconfiguration_warning(None, "*") is None

    def test_no_warning_when_cors_restricted(self):
        assert (
            api_module._cors_misconfiguration_warning(
                "secret-key", "https://example.com"
            )
            is None
        )

    def test_no_warning_when_neither_set(self):
        assert api_module._cors_misconfiguration_warning(None, "*") is None


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


def test_find_structure_pdb_path_falls_back_to_run_results_dir():
    """When a structure isn't in the session's raw-download folder (e.g. it
    was uploaded directly into a run rather than downloaded), the lookup
    must fall back to that run's own results folder before giving up."""

    def fake_exists(self):
        return "results" in str(self) and "run_123" in str(self)

    with patch("pathlib.Path.exists", fake_exists):
        result = api_module._find_structure_pdb_path("4RLT", "run_123", None)

    assert result is not None
    assert "run_123" in str(result)


def test_find_structure_pdb_path_returns_none_when_nowhere_found():
    with patch("pathlib.Path.exists", return_value=False):
        result = api_module._find_structure_pdb_path("4RLT", "run_123", None)

    assert result is None


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


def test_interface_endpoint():
    with patch("src.backend.api.interface_analyzer") as mock_analyzer, patch(
        "pathlib.Path.exists", return_value=True
    ):
        mock_analyzer.calculate_interface.return_value = {
            "chain_a": "A",
            "chain_b": "B",
            "chain_a_contacts": [],
            "chain_b_contacts": [],
            "buried_area": 512.3,
        }

        response = client.get(
            "/api/interface?pdb_id=4RLT&chain_a=A&chain_b=B&run_id=run_123"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pdb_id"] == "4RLT"
        assert data["interface"]["buried_area"] == 512.3
        mock_analyzer.calculate_interface.assert_called_once()


def test_interface_endpoint_404s_when_structure_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        response = client.get("/api/interface?pdb_id=4RLT&chain_a=A&chain_b=B")
    assert response.status_code == 404


def test_interface_endpoint_400s_on_invalid_chain_param():
    response = client.get("/api/interface?pdb_id=4RLT&chain_a=../etc&chain_b=B")
    assert response.status_code == 400


def test_annotations_endpoint():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.aggregate_for_structure = AsyncMock(
            return_value={
                "pdb_id": "AF-P69905-F1",
                "chain": None,
                "accession": "P69905",
                "domains": [{"name": "Globin", "type": "domain"}],
                "go_terms": [{"id": "GO:0005344", "name": "oxygen carrier activity"}],
                "reactome_pathways": [],
            }
        )

        response = client.get("/api/annotations?pdb_id=AF-P69905-F1")

        assert response.status_code == 200
        data = response.json()
        assert data["pdb_id"] == "AF-P69905-F1"
        assert data["annotation"]["accession"] == "P69905"
        assert data["annotation"]["domains"][0]["name"] == "Globin"
        mock_aggregator.aggregate_for_structure.assert_called_once()
        call_args = mock_aggregator.aggregate_for_structure.call_args
        assert call_args.args[0] == "AF-P69905-F1"
        assert call_args.args[2] == "alphafold"


def test_annotations_endpoint_with_a_chain_for_a_plain_pdb_id():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.aggregate_for_structure = AsyncMock(
            return_value={
                "pdb_id": "4HHB",
                "chain": "A",
                "accession": None,
                "domains": [],
                "go_terms": [],
                "reactome_pathways": [],
            }
        )

        response = client.get("/api/annotations?pdb_id=4HHB&chain=A")

        assert response.status_code == 200
        call_args = mock_aggregator.aggregate_for_structure.call_args
        assert call_args.args[1] == "A"
        assert call_args.args[2] == "pdb"


def test_annotations_endpoint_400s_on_invalid_chain_param():
    response = client.get("/api/annotations?pdb_id=4HHB&chain=../etc")
    assert response.status_code == 400


def test_pae_endpoint_returns_the_matrix():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.fetch_predicted_aligned_error = AsyncMock(
            return_value=[[0, 5], [5, 0]]
        )

        response = client.get("/api/pae?pdb_id=AF-P69905-F1")

        assert response.status_code == 200
        data = response.json()
        assert data["pdb_id"] == "AF-P69905-F1"
        assert data["pae"] == [[0, 5], [5, 0]]
        mock_aggregator.fetch_predicted_aligned_error.assert_called_once()
        assert mock_aggregator.fetch_predicted_aligned_error.call_args.args[0] == (
            "AF-P69905-F1"
        )


def test_pae_endpoint_404s_when_no_pae_data_is_available():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.fetch_predicted_aligned_error = AsyncMock(return_value=None)

        response = client.get("/api/pae?pdb_id=4HHB")

        assert response.status_code == 404


def test_pae_endpoint_400s_on_invalid_pdb_id():
    response = client.get("/api/pae?pdb_id=../etc")
    assert response.status_code == 400


def test_mutation_impact_endpoint_returns_a_real_looking_result():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.resolve_structure_uniprot_position = AsyncMock(
            return_value=("P68871", 7)
        )
        mock_aggregator.fetch_uniprot_gene_and_sequence = AsyncMock(
            return_value={"gene": "HBB", "sequence": "MVHLTPVEK"}
        )
        mock_aggregator.fetch_clinvar_significance = AsyncMock(
            return_value={
                "variation_id": "15333",
                "accession": "VCV000015333",
                "title": "NM_000518.5(HBB):c.20A>T (p.Glu7Val)",
                "clinical_significance": "Pathogenic",
                "review_status": "criteria provided, multiple submitters, no conflicts",
            }
        )
        mock_aggregator.fetch_uniprot_features = AsyncMock(return_value=[])
        mock_aggregator.fetch_alphamissense_scores = AsyncMock(
            return_value={
                "7": {
                    "wildtype": "E",
                    "scores": {"V": {"pathogenicity": 0.95, "class": "LPath"}},
                }
            }
        )

        response = client.get(
            "/api/mutation-impact?pdb_id=4HHB&chain=A&resi=6&mutant=V"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["accession"] == "P68871"
    assert data["gene"] == "HBB"
    assert data["uniprot_position"] == 7
    assert data["wildtype_residue"] == "V"
    assert data["mutant_residue"] == "V"
    assert data["clinvar"]["clinical_significance"] == "Pathogenic"
    assert data["alphamissense"] == {"pathogenicity": 0.95, "class": "LPath"}
    assert data["highlight_chains"] == {"A": [6]}
    mock_aggregator.fetch_clinvar_significance.assert_called_once_with(
        "HBB", "V7V", ANY
    )


def test_mutation_impact_endpoint_surfaces_a_known_uniprot_variant():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.resolve_structure_uniprot_position = AsyncMock(
            return_value=("P68871", 7)
        )
        mock_aggregator.fetch_uniprot_gene_and_sequence = AsyncMock(
            return_value={"gene": None, "sequence": None}
        )
        mock_aggregator.fetch_clinvar_significance = AsyncMock(return_value=None)
        mock_aggregator.fetch_uniprot_features = AsyncMock(
            return_value=[
                {
                    "type": "Natural variant",
                    "description": "in HBS",
                    "start": 7,
                    "end": 7,
                }
            ]
        )
        mock_aggregator.fetch_alphamissense_scores = AsyncMock(return_value={})

        response = client.get(
            "/api/mutation-impact?pdb_id=4HHB&chain=A&resi=6&mutant=V"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["clinvar"] is None
    assert data["known_uniprot_variant"]["description"] == "in HBS"
    assert data["alphamissense"] is None


def test_mutation_impact_endpoint_returns_none_alphamissense_when_no_scores_exist_for_this_position():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.resolve_structure_uniprot_position = AsyncMock(
            return_value=("P68871", 7)
        )
        mock_aggregator.fetch_uniprot_gene_and_sequence = AsyncMock(
            return_value={"gene": "HBB", "sequence": "MVHLTPVEK"}
        )
        mock_aggregator.fetch_clinvar_significance = AsyncMock(return_value=None)
        mock_aggregator.fetch_uniprot_features = AsyncMock(return_value=[])
        mock_aggregator.fetch_alphamissense_scores = AsyncMock(
            return_value={"3": {"wildtype": "H", "scores": {}}}
        )

        response = client.get(
            "/api/mutation-impact?pdb_id=4HHB&chain=A&resi=6&mutant=V"
        )

    assert response.status_code == 200
    assert response.json()["alphamissense"] is None


def test_mutation_tolerance_endpoint_returns_the_overlay():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.aggregate_mutation_tolerance = AsyncMock(
            return_value={
                "accession": "P69905",
                "per_residue_average": {"1": 0.2, "2": 0.6},
            }
        )

        response = client.get("/api/mutation-tolerance?pdb_id=AF-P69905-F1")

        assert response.status_code == 200
        data = response.json()
        assert data["pdb_id"] == "AF-P69905-F1"
        assert data["tolerance"]["accession"] == "P69905"
        assert data["tolerance"]["per_residue_average"] == {"1": 0.2, "2": 0.6}
        call_args = mock_aggregator.aggregate_mutation_tolerance.call_args
        assert call_args.args[0] == "AF-P69905-F1"
        assert call_args.args[2] == "alphafold"


def test_mutation_tolerance_endpoint_400s_on_invalid_chain_param():
    response = client.get("/api/mutation-tolerance?pdb_id=4HHB&chain=../etc")
    assert response.status_code == 400


def test_mutation_impact_endpoint_404s_when_position_cannot_be_resolved():
    with patch("src.backend.api.annotation_aggregator") as mock_aggregator:
        mock_aggregator.resolve_structure_uniprot_position = AsyncMock(
            return_value=None
        )

        response = client.get(
            "/api/mutation-impact?pdb_id=4HHB&chain=A&resi=6&mutant=V"
        )

    assert response.status_code == 404


def test_mutation_impact_endpoint_400s_on_invalid_chain():
    response = client.get(
        "/api/mutation-impact?pdb_id=4HHB&chain=../etc&resi=6&mutant=V"
    )
    assert response.status_code == 400


def test_mutation_impact_endpoint_400s_on_invalid_mutant():
    response = client.get("/api/mutation-impact?pdb_id=4HHB&chain=A&resi=6&mutant=XX")
    assert response.status_code == 400


def test_validation_endpoint_for_a_real_pdb_entry():
    with patch(
        "src.backend.api.fetch_pdbe_validation",
        AsyncMock(
            return_value={
                "clashscore": {
                    "value": 1.2,
                    "percentile_archive": 85.0,
                    "percentile_similar_resolution": 70.0,
                }
            }
        ),
    ) as mock_fetch:
        response = client.get("/api/validation?pdb_id=4HHB")

    assert response.status_code == 200
    data = response.json()
    assert data["pdb_id"] == "4HHB"
    assert data["validation"]["clashscore"]["value"] == 1.2
    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.args[0] == "4HHB"


def test_validation_endpoint_skips_the_fetch_for_non_pdb_sources():
    with patch("src.backend.api.fetch_pdbe_validation", AsyncMock()) as mock_fetch:
        response = client.get("/api/validation?pdb_id=AF-P69905-F1")

    assert response.status_code == 200
    data = response.json()
    assert data == {"pdb_id": "AF-P69905-F1", "validation": None}
    mock_fetch.assert_not_called()


def test_validation_endpoint_400s_on_invalid_pdb_id():
    response = client.get("/api/validation?pdb_id=../etc")
    assert response.status_code == 400


def test_ligand_info_endpoint():
    with patch(
        "src.backend.api.ligand_analyzer.fetch_ligand_chemistry",
        AsyncMock(
            return_value={
                "id": "HEM",
                "name": "PROTOPORPHYRIN IX CONTAINING FE",
                "formula": "C34 H32 Fe N4 O4",
                "smiles": "CC1=C...",
            }
        ),
    ) as mock_fetch:
        response = client.get("/api/ligand-info?ligand_code=HEM")

    assert response.status_code == 200
    data = response.json()
    assert data["ligand_code"] == "HEM"
    assert data["chemistry"]["name"] == "PROTOPORPHYRIN IX CONTAINING FE"
    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.args[0] == "HEM"


def test_ligand_info_endpoint_returns_none_chemistry_gracefully():
    with patch(
        "src.backend.api.ligand_analyzer.fetch_ligand_chemistry",
        AsyncMock(return_value=None),
    ):
        response = client.get("/api/ligand-info?ligand_code=ZZZ")

    assert response.status_code == 200
    assert response.json() == {"ligand_code": "ZZZ", "chemistry": None}


def test_ligand_info_endpoint_400s_on_invalid_ligand_code():
    response = client.get("/api/ligand-info?ligand_code=../etc")
    assert response.status_code == 400


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
        assert "motif_matches" not in data
        assert "highlight_chains" not in data


def test_sequence_endpoint_with_motif_query_returns_matches_and_highlight_map():
    with patch(
        "src.backend.sequence_viewer.SequenceViewer.parse_afasta"
    ) as mock_parse, patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_conservation",
        return_value=[1.0] * 6,
    ), patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_identity",
        return_value=100.0,
    ), patch(
        "pathlib.Path.exists", return_value=True
    ):
        mock_parse.return_value = {"4RLT": "AC-GHK", "3UG9": "ACYGH-"}

        response = client.get("/api/sequence?run_id=run_123&motif=G.K")

        assert response.status_code == 200
        data = response.json()
        # "4RLT" raw (gap-stripped) = "ACGHK" -> "G.K" matches "GHK" at raw
        # idx 2-4 -> aligned columns 4,5,6 (a gap sits at column 3).
        assert data["motif_matches"] == {"4RLT": [4, 5, 6]}
        assert data["highlight_chains"]["A"] == [3, 4, 5]


def test_sequence_endpoint_motif_with_no_matches_returns_empty_maps():
    with patch(
        "src.backend.sequence_viewer.SequenceViewer.parse_afasta"
    ) as mock_parse, patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_conservation",
        return_value=[1.0] * 4,
    ), patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_identity",
        return_value=100.0,
    ), patch(
        "pathlib.Path.exists", return_value=True
    ):
        mock_parse.return_value = {"4RLT": "ACGT"}

        response = client.get("/api/sequence?run_id=run_123&motif=ZZZZ")

        assert response.status_code == 200
        data = response.json()
        assert data["motif_matches"] == {}
        assert data["highlight_chains"] == {"A": []}


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


def test_comparison_endpoint_400s_when_no_overlapping_proteins():
    with patch("src.backend.api.ResultManager.calculate_difference", return_value=None):
        response = client.get(
            "/api/comparison?current_run_id=run_a&target_run_id=run_b"
        )
        assert response.status_code == 400
        assert "overlapping" in response.json()["detail"].lower()


def test_comparison_endpoint_404s_when_rmsd_matrix_missing():
    with patch(
        "src.backend.api.ResultManager.calculate_difference"
    ) as mock_diff, patch(
        "src.backend.api.ResultManager.get_run_rmsd", return_value=None
    ):
        mock_diff.return_value = pd.DataFrame()
        response = client.get(
            "/api/comparison?current_run_id=run_a&target_run_id=run_b"
        )
        assert response.status_code == 404


def test_ligands_endpoint_404s_when_structure_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        response = client.get("/api/ligands?pdb_id=4RLT")
    assert response.status_code == 404


def test_pockets_endpoint_returns_heuristic_candidates(tmp_path):
    pdb_file = tmp_path / "4rlt.pdb"
    pdb_file.write_text("ATOM      1  N   MET A   1      27.340  24.430   2.614\n")
    fake_pockets = [
        {
            "rank": 1,
            "residues": [{"chain": "A", "resi": 10, "resn": "LEU"}],
            "center": [0.0, 0.0, 0.0],
            "score": 5.0,
            "heuristic": True,
        }
    ]

    with patch(
        "src.backend.api._find_structure_pdb_path", return_value=pdb_file
    ), patch(
        "src.backend.api.ligand_analyzer.find_candidate_pockets",
        return_value=fake_pockets,
    ):
        response = client.get("/api/pockets?pdb_id=4RLT")

    assert response.status_code == 200
    body = response.json()
    assert body["pdb_id"] == "4RLT"
    assert body["pockets"] == fake_pockets


def test_pockets_endpoint_404s_when_structure_not_found():
    with patch("src.backend.api._find_structure_pdb_path", return_value=None):
        response = client.get("/api/pockets?pdb_id=4RLT")
    assert response.status_code == 404


def test_pockets_endpoint_400s_on_invalid_pdb_id():
    response = client.get("/api/pockets?pdb_id=../etc")
    assert response.status_code == 400


def test_qc_endpoint_returns_real_looking_stats_for_a_pdb_entry(tmp_path):
    pdb_file = tmp_path / "4hhb.pdb"
    pdb_file.write_text("ATOM      1  N   MET A   1      27.340  24.430   2.614\n")

    with patch(
        "src.backend.api._find_structure_pdb_path", return_value=pdb_file
    ), patch(
        "src.backend.api.ramachandran_service.calculate_torsion_angles",
        return_value={"A": "dummy_dataframe"},
    ), patch(
        "src.backend.api.ramachandran_service.aggregate_metrics",
        return_value={"favored_percent": 92.5, "outlier_count": 2},
    ), patch(
        "src.backend.api.ramachandran_service.aggregate_secondary_structure",
        return_value={
            "helix_percent": 80.3,
            "sheet_percent": 5.0,
            "coil_percent": 14.7,
        },
    ), patch(
        "src.backend.api.fetch_pdbe_validation",
        AsyncMock(return_value={"clashscore": {"value": 1.2}}),
    ):
        response = client.get("/api/qc?pdb_id=4HHB")

    assert response.status_code == 200
    data = response.json()
    assert data["pdb_id"] == "4HHB"
    assert data["ramachandran_stats"]["favored_percent"] == 92.5
    assert data["secondary_structure_stats"]["helix_percent"] == 80.3
    assert data["validation"]["clashscore"]["value"] == 1.2


def test_qc_endpoint_skips_validation_for_non_pdb_sources(tmp_path):
    pdb_file = tmp_path / "af.cif"
    pdb_file.write_text("dummy")

    with patch(
        "src.backend.api._find_structure_pdb_path", return_value=pdb_file
    ), patch(
        "src.backend.api.ramachandran_service.calculate_torsion_angles",
        return_value=None,
    ), patch(
        "src.backend.api.fetch_pdbe_validation", AsyncMock()
    ) as mock_validation:
        response = client.get("/api/qc?pdb_id=AF-P69905-F1")

    assert response.status_code == 200
    data = response.json()
    assert data["validation"] is None
    assert data["ramachandran_stats"] is None
    assert data["secondary_structure_stats"] is None
    mock_validation.assert_not_called()


def test_qc_endpoint_404s_when_structure_not_found():
    with patch("src.backend.api._find_structure_pdb_path", return_value=None):
        response = client.get("/api/qc?pdb_id=4HHB")
    assert response.status_code == 404


def test_qc_endpoint_400s_on_invalid_pdb_id():
    response = client.get("/api/qc?pdb_id=../etc")
    assert response.status_code == 400


def test_structure_file_endpoint_returns_the_raw_pdb(tmp_path):
    pdb_file = tmp_path / "4rlt.pdb"
    pdb_file.write_text("ATOM      1  N   MET A   1      27.340  24.430   2.614\n")

    with patch("src.backend.api._find_structure_pdb_path", return_value=pdb_file):
        response = client.get("/api/structure-file?pdb_id=4RLT")

    assert response.status_code == 200
    assert response.text == pdb_file.read_text()


def test_structure_file_endpoint_404s_when_structure_not_found():
    with patch("src.backend.api._find_structure_pdb_path", return_value=None):
        response = client.get("/api/structure-file?pdb_id=4RLT")
    assert response.status_code == 404


def test_structure_file_endpoint_400s_on_invalid_pdb_id():
    response = client.get("/api/structure-file?pdb_id=../etc")
    assert response.status_code == 400


def test_list_comparison_runs_excludes_given_run_id():
    with patch("src.backend.api.ResultManager.list_runs") as mock_list_runs:
        mock_list_runs.return_value = [
            {"id": "run1", "timestamp": "2026-01-01", "proteins": ["4RLT"]},
            {"id": "run2", "timestamp": "2026-01-02", "proteins": ["3UG9"]},
        ]

        response = client.get("/api/comparison/runs?exclude_run_id=run1")

        assert response.status_code == 200
        data = response.json()
        assert [r["id"] for r in data["runs"]] == ["run2"]


def test_list_comparison_runs_rejects_path_traversal_session_id():
    response = client.get("/api/comparison/runs?session_id=../../etc")
    assert response.status_code == 400


def test_clusters_endpoint_groups_close_structures():
    rmsd_df = {
        "index": ["A", "B", "C", "D"],
        "columns": ["A", "B", "C", "D"],
        "data": [
            [0.0, 1.0, 8.0, 8.0],
            [1.0, 0.0, 8.0, 8.0],
            [8.0, 8.0, 0.0, 1.0],
            [8.0, 8.0, 1.0, 0.0],
        ],
    }

    response = client.post("/api/clusters", json={"rmsd_df": rmsd_df, "threshold": 3.0})

    assert response.status_code == 200
    data = response.json()
    assert data["threshold"] == 3.0
    families = data["clusters"]
    assert len(families) == 2
    member_sets = [set(f["members"]) for f in families]
    assert {"A", "B"} in member_sets
    assert {"C", "D"} in member_sets
    for f in families:
        assert f["avg_rmsd"] == pytest.approx(1.0)


def test_clusters_endpoint_rejects_malformed_payload():
    response = client.post(
        "/api/clusters",
        json={"rmsd_df": {"index": ["A"], "columns": ["A"]}, "threshold": 3.0},
    )

    assert response.status_code == 400
    assert "Invalid rmsd_df payload" in response.json()["detail"]


def test_clusters_endpoint_rejects_fewer_than_two_structures():
    rmsd_df = {"index": ["A"], "columns": ["A"], "data": [[0.0]]}

    response = client.post("/api/clusters", json={"rmsd_df": rmsd_df})

    assert response.status_code == 400
    assert "At least 2 structures" in response.json()["detail"]


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


def test_submit_alignment_job_rejects_fewer_than_two_ids():
    response = client.post("/api/jobs/align", json={"pdb_ids": ["4RLT"]})
    assert response.status_code == 400
    assert "at least 2" in response.json()["detail"].lower()


def test_get_alignment_job_404s_for_unknown_job_id():
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_execute_alignment_job_marks_failed_on_pipeline_error():
    job_id = "test-job-fail"
    api_module.alignment_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.api.AnalysisCoordinator.run_full_pipeline",
        return_value=(False, "Mustang exited with code 139", None),
    ):
        await api_module._execute_alignment_job(
            job_id,
            pdb_ids=["4RLT", "3UG9"],
            chain_selection={},
            remove_water=True,
            remove_heteroatoms=True,
            session_id=None,
        )

    job = api_module.alignment_jobs.pop(job_id)
    assert job["status"] == "failed"
    assert "Mustang exited with code 139" in job["error"]


@pytest.mark.asyncio
async def test_lifespan_starts_and_cancels_both_sweep_tasks():
    """The lifespan context manager spawns the alignment and discovery
    background sweep tasks on startup and must cancel both on shutdown,
    not leak them."""
    async with api_module.lifespan(app):
        tasks = [
            t
            for t in asyncio.all_tasks()
            if t.get_coro().__name__
            in ("_sweep_alignment_jobs", "_sweep_discovery_jobs")
        ]
        assert len(tasks) == 2
        assert all(not t.done() for t in tasks)

    await asyncio.sleep(0)  # let cancellation propagate
    assert all(t.cancelled() or t.done() for t in tasks)


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


def test_compare_citations_endpoint_returns_a_real_export(tmp_path):
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {"id": "run_123", "pdb_ids": ["4RLT", "3UG9"]}

        response = client.get("/api/report/citations?run_id=run_123")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert b"MUSTANG" in response.content
        assert b"run_123" in response.content


def test_compare_citations_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/report/citations?run_id=does_not_exist")
        assert response.status_code == 404


def test_discover_citations_endpoint_returns_a_real_export():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {
            "id": "discover_123",
            "metadata": {
                "run_type": "discover",
                "results": {"pdb_id": "4RLT", "databases_searched": ["pdb100"]},
            },
        }

        response = client.get("/api/discover/citations?run_id=discover_123")

        assert response.status_code == 200
        assert (
            b"Foldseek" in response.content or b"foldseek" in response.content.lower()
        )


def test_discover_citations_endpoint_rejects_a_compare_run():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {
            "id": "run_123",
            "metadata": {"run_type": "compare"},
        }

        response = client.get("/api/discover/citations?run_id=run_123")

        assert response.status_code == 400


def test_discover_citations_endpoint_500s_on_unexpected_export_error():
    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.citation_exporter.CitationExporter.export"
    ) as mock_export:
        mock_export.side_effect = RuntimeError("disk full")
        mock_get_run.return_value = {
            "id": "discover_123",
            "metadata": {
                "run_type": "discover",
                "results": {"pdb_id": "4RLT", "databases_searched": ["pdb100"]},
            },
        }

        response = client.get("/api/discover/citations?run_id=discover_123")

        assert response.status_code == 500
        assert "disk full" in response.json()["detail"]


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


def test_notebook_endpoint_500s_when_file_not_actually_created(tmp_path):
    missing_html = tmp_path / "never_written.html"

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export"
    ) as mock_export:
        mock_export.return_value = missing_html
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/notebook?run_id=run_123")

        assert response.status_code == 500
        assert "not created successfully" in response.json()["detail"]


def test_notebook_endpoint_500s_on_unexpected_exporter_error():
    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export"
    ) as mock_export:
        mock_export.side_effect = RuntimeError("disk full")
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/notebook?run_id=run_123")

        assert response.status_code == 500
        assert "disk full" in response.json()["detail"]


def test_notebook_ipynb_endpoint_returns_a_real_file(tmp_path):
    dummy_ipynb = tmp_path / "dummy.ipynb"
    dummy_ipynb.write_text('{"cells": [], "nbformat": 4}')

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export_ipynb"
    ) as mock_export:
        mock_export.return_value = dummy_ipynb
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {
                "results": {
                    "stats": {"mean_rmsd": 1.25},
                    "id": "run_123",
                    "pdb_ids": ["4RLT", "3UG9"],
                }
            },
        }

        response = client.get("/api/notebook/ipynb?run_id=run_123")

        assert response.status_code == 200
        assert "dummy.ipynb" not in response.headers["content-disposition"]
        assert "lab_notebook_run_123.ipynb" in response.headers["content-disposition"]
        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args[0][1] == "run_123"
        assert call_args[1]["base_url"] == "http://testserver"


def test_notebook_ipynb_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/notebook/ipynb?run_id=nope")
        assert response.status_code == 404


def test_notebook_ipynb_endpoint_500s_when_file_not_actually_created(tmp_path):
    missing_ipynb = tmp_path / "never_written.ipynb"

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export_ipynb"
    ) as mock_export:
        mock_export.return_value = missing_ipynb
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/notebook/ipynb?run_id=run_123")

        assert response.status_code == 500
        assert "not created successfully" in response.json()["detail"]


def test_notebook_ipynb_endpoint_500s_on_unexpected_exporter_error():
    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export_ipynb"
    ) as mock_export:
        mock_export.side_effect = RuntimeError("disk full")
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/notebook/ipynb?run_id=run_123")

        assert response.status_code == 500
        assert "disk full" in response.json()["detail"]


def test_notebook_ipynb_endpoint_400s_on_invalid_run_id():
    response = client.get("/api/notebook/ipynb?run_id=../etc")
    assert response.status_code == 400


def test_rmsd_csv_endpoint_returns_a_real_csv():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {
            "id": "run_123",
            "metadata": {
                "results": {
                    "rmsd_df": {
                        "index": ["4RLT", "3UG9"],
                        "columns": ["4RLT", "3UG9"],
                        "data": [[0.0, 1.5], [1.5, 0.0]],
                    }
                }
            },
        }

        response = client.get("/api/report/rmsd-csv?run_id=run_123")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        assert "rmsd_matrix_run_123.csv" in response.headers["content-disposition"]
        assert "4RLT" in response.text
        assert "1.5" in response.text


def test_rmsd_csv_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/report/rmsd-csv?run_id=nope")
        assert response.status_code == 404


def test_rmsd_csv_endpoint_404s_when_no_rmsd_matrix_stored():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {"id": "run_123", "metadata": {"results": {}}}
        response = client.get("/api/report/rmsd-csv?run_id=run_123")
        assert response.status_code == 404
        assert "No stored RMSD matrix" in response.json()["detail"]


def test_heatmap_png_endpoint_returns_the_saved_file(tmp_path):
    heatmap = tmp_path / "rmsd_heatmap.png"
    heatmap.write_bytes(b"\x89PNG\r\n\x1a\ndummy png bytes")

    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123"}, tmp_path),
    ):
        response = client.get("/api/report/heatmap-png?run_id=run_123")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert "rmsd_heatmap_run_123.png" in response.headers["content-disposition"]
        assert response.content == heatmap.read_bytes()


def test_heatmap_png_endpoint_404s_when_file_missing_on_disk(tmp_path):
    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123"}, tmp_path),
    ):
        response = client.get("/api/report/heatmap-png?run_id=run_123")

        assert response.status_code == 404
        assert "No heatmap image found" in response.json()["detail"]


def test_heatmap_png_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/report/heatmap-png?run_id=nope")
        assert response.status_code == 404


def test_newick_endpoint_returns_the_saved_file(tmp_path):
    newick = tmp_path / "tree.newick"
    newick.write_text("(4RLT:0.1,3UG9:0.2);")

    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123"}, tmp_path),
    ):
        response = client.get("/api/report/newick?run_id=run_123")

        assert response.status_code == 200
        assert "tree_run_123.newick" in response.headers["content-disposition"]
        assert response.content == newick.read_bytes()


def test_newick_endpoint_404s_when_file_missing_on_disk(tmp_path):
    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123"}, tmp_path),
    ):
        response = client.get("/api/report/newick?run_id=run_123")

        assert response.status_code == 404
        assert "No phylogenetic tree found" in response.json()["detail"]


def test_newick_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/report/newick?run_id=nope")
        assert response.status_code == 404


def _write_two_structure_alignment(res_dir, coords_a, coords_b):
    lines = ["MODEL     1"]
    for i, (x, y, z) in enumerate(coords_a, start=1):
        lines.append(
            f"ATOM  {i:5d}  CA  ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
        )
    lines.append("ENDMDL")
    lines.append("MODEL     2")
    for i, (x, y, z) in enumerate(coords_b, start=1):
        lines.append(
            f"ATOM  {i:5d}  CA  ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
        )
    lines.append("ENDMDL")
    lines.append("END\n")
    (res_dir / "alignment.pdb").write_text("\n".join(lines))
    seq = "A" * len(coords_a)
    (res_dir / "alignment.fasta").write_text(f">structA\n{seq}\n>structB\n{seq}\n")


def test_contact_map_endpoint_returns_a_real_matrix(tmp_path):
    _write_two_structure_alignment(
        tmp_path,
        [[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [100.0, 0.0, 0.0]],
        [[0.0, 0.0, 0.0], [3.0, 4.0, 0.0], [100.0, 0.0, 0.0]],
    )

    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123", "pdb_ids": ["structA", "structB"]}, tmp_path),
    ):
        response = client.get("/api/contact-map?run_id=run_123&pdb_id=structA")

    assert response.status_code == 200
    data = response.json()
    assert data["pdb_id"] == "structA"
    assert data["residue_count"] == 3
    assert data["matrix"][0][1] == 1
    assert data["matrix"][0][2] == 0


def test_contact_map_endpoint_404s_when_pdb_id_not_in_alignment(tmp_path):
    _write_two_structure_alignment(tmp_path, [[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0]])

    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123", "pdb_ids": ["structA", "structB"]}, tmp_path),
    ):
        response = client.get("/api/contact-map?run_id=run_123&pdb_id=does_not_exist")

    assert response.status_code == 404


def test_contact_map_endpoint_404s_when_alignment_files_missing(tmp_path):
    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123", "pdb_ids": ["structA", "structB"]}, tmp_path),
    ):
        response = client.get("/api/contact-map?run_id=run_123&pdb_id=structA")

    assert response.status_code == 404


def test_contact_map_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/contact-map?run_id=nope&pdb_id=structA")
        assert response.status_code == 404


def test_contact_map_endpoint_400s_on_invalid_run_id():
    response = client.get("/api/contact-map?run_id=../etc&pdb_id=structA")
    assert response.status_code == 400


def test_difference_distance_endpoint_returns_a_real_matrix(tmp_path):
    _write_two_structure_alignment(
        tmp_path,
        [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [0.0, 5.0, 0.0]],
        [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [20.0, 5.0, 0.0]],
    )

    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123", "pdb_ids": ["structA", "structB"]}, tmp_path),
    ):
        response = client.get(
            "/api/difference-distance?run_id=run_123&pdb_id_a=structA&pdb_id_b=structB"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["pdb_id_a"] == "structA"
    assert data["pdb_id_b"] == "structB"
    assert data["column_count"] == 3
    assert data["matrix"][0][1] == pytest.approx(0.0)
    assert data["matrix"][0][2] != pytest.approx(0.0)


def test_difference_distance_endpoint_404s_when_no_shared_columns(tmp_path):
    _write_two_structure_alignment(
        tmp_path, [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]], [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]]
    )
    (tmp_path / "alignment.fasta").write_text(">structA\nAA--\n>structB\n--AA\n")

    with patch(
        "src.backend.api._lookup_run_and_result_dir",
        return_value=({"id": "run_123", "pdb_ids": ["structA", "structB"]}, tmp_path),
    ):
        response = client.get(
            "/api/difference-distance?run_id=run_123&pdb_id_a=structA&pdb_id_b=structB"
        )

    assert response.status_code == 404


def test_difference_distance_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get(
            "/api/difference-distance?run_id=nope&pdb_id_a=structA&pdb_id_b=structB"
        )
        assert response.status_code == 404


def test_difference_distance_endpoint_400s_on_invalid_pdb_id():
    response = client.get(
        "/api/difference-distance?run_id=run_123&pdb_id_a=../etc&pdb_id_b=structB"
    )
    assert response.status_code == 400


def test_report_zip_endpoint_bundles_every_available_artifact(tmp_path):
    import zipfile
    import io

    (tmp_path / "alignment.pdb").write_text("ATOM dummy pdb")
    (tmp_path / "alignment.afasta").write_text(">a\nAAA\n")
    (tmp_path / "rmsd_heatmap.png").write_bytes(b"\x89PNG\r\n\x1a\ndummy")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export"
    ) as mock_export:
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {
                "results": {
                    "stats": {"mean_rmsd": 1.5},
                    "id": "run_123",
                    "rmsd_df": {
                        "index": ["4RLT", "3UG9"],
                        "columns": ["4RLT", "3UG9"],
                        "data": [[0.0, 1.5], [1.5, 0.0]],
                    },
                }
            },
        }
        notebook_path = tmp_path / "lab_notebook.html"
        notebook_path.write_text("<html>notebook</html>")
        mock_export.return_value = notebook_path

        with patch(
            "src.backend.api._lookup_run_and_result_dir",
            return_value=(mock_get_run.return_value, tmp_path),
        ):
            response = client.get("/api/report/zip?run_id=run_123")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "structscope_run_123.zip" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()
        assert "alignment_run_123.pdb" in names
        assert "alignment_run_123.afasta" in names
        assert "rmsd_matrix_run_123.csv" in names
        assert "rmsd_heatmap_run_123.png" in names
        assert "lab_notebook_run_123.html" in names
        assert "4RLT" in zf.read("rmsd_matrix_run_123.csv").decode()


def test_report_zip_endpoint_skips_missing_pieces_without_failing(tmp_path):
    """A run with no heatmap (e.g. it failed before that stage) or no
    lab-notebook-exportable data still produces a ZIP with whatever is
    actually available, not a 500."""
    import zipfile
    import io

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export",
        side_effect=RuntimeError("no rmsd_df to render"),
    ):
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        with patch(
            "src.backend.api._lookup_run_and_result_dir",
            return_value=(mock_get_run.return_value, tmp_path),
        ):
            response = client.get("/api/report/zip?run_id=run_123")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert zf.namelist() == []


def test_report_zip_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/report/zip?run_id=nope")
        assert response.status_code == 404


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


def test_clustalo_job_submission_returns_queued():
    """Submitting a valid Clustal Omega job returns a job_id immediately
    with status "queued" - it must not block on the (slow, EBI-rate-
    limited) submit/poll/fetch pipeline."""
    api_module.clustalo_jobs.clear()
    response = client.post(
        "/api/jobs/clustalo", json={"sequences": {"4RLT": "MVHL", "3UG9": "MVLS"}}
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"] in api_module.clustalo_jobs
    api_module.clustalo_jobs.clear()


def test_clustalo_job_submission_rejects_fewer_than_two_sequences():
    response = client.post("/api/jobs/clustalo", json={"sequences": {"4RLT": "MVHL"}})
    assert response.status_code == 400


def test_clustalo_job_submission_rejects_an_unsafe_sequence_id():
    response = client.post(
        "/api/jobs/clustalo",
        json={"sequences": {"../etc": "MVHL", "3UG9": "MVLS"}},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_clustalo_job_execution_completes_and_is_pollable():
    """Directly exercises _execute_clustalo_job (the background task the
    endpoint schedules) end-to-end, then confirms GET /api/jobs/{job_id} -
    the same polling endpoint used for alignment/discovery jobs - surfaces
    the real aligned FASTA result."""
    api_module.clustalo_jobs.clear()
    job_id = "test-clustalo-job"
    api_module.clustalo_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.api.ClustalOmegaClient.align", new_callable=AsyncMock
    ) as mock_align:
        mock_align.return_value = ">4RLT\nMV--HL\n>3UG9\n-MVLSH"
        await api_module._execute_clustalo_job(
            job_id, {"4RLT": "MVHL", "3UG9": "MVLSH"}
        )

    poll = client.get(f"/api/jobs/{job_id}")
    assert poll.json()["status"] == "completed"
    assert poll.json()["aligned_fasta"] == ">4RLT\nMV--HL\n>3UG9\n-MVLSH"

    api_module.clustalo_jobs.clear()


@pytest.mark.asyncio
async def test_clustalo_job_execution_surfaces_pipeline_failure():
    api_module.clustalo_jobs.clear()
    job_id = "test-clustalo-job-fail"
    api_module.clustalo_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.api.ClustalOmegaClient.align", new_callable=AsyncMock
    ) as mock_align:
        from src.backend.clustalo_client import ClustalOmegaError

        mock_align.side_effect = ClustalOmegaError("Clustal Omega submission failed")
        await api_module._execute_clustalo_job(
            job_id, {"4RLT": "MVHL", "3UG9": "MVLSH"}
        )

    poll = client.get(f"/api/jobs/{job_id}")
    assert poll.json()["status"] == "failed"
    assert "Clustal Omega submission failed" in poll.json()["error"]

    api_module.clustalo_jobs.clear()


@pytest.mark.asyncio
async def test_clustalo_job_sweep_drops_old_finished_jobs_but_keeps_recent_and_running():
    now = time.time()
    api_module.clustalo_jobs.clear()
    api_module.clustalo_jobs.update(
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
            await api_module._sweep_clustalo_jobs()

    remaining = set(api_module.clustalo_jobs.keys())
    assert remaining == {"recent_completed", "still_running"}
    api_module.clustalo_jobs.clear()


def test_conservation_job_submission_returns_queued():
    """Submitting a valid conservation job returns a job_id immediately
    with status "queued" - it must not block on the (very slow,
    minutes-long) BLAST submit/poll/fetch pipeline."""
    api_module.blast_jobs.clear()
    response = client.post(
        "/api/jobs/conservation",
        json={"sequence": "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLS"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"] in api_module.blast_jobs
    api_module.blast_jobs.clear()


def test_conservation_job_submission_rejects_a_too_short_sequence():
    response = client.post("/api/jobs/conservation", json={"sequence": "MVHL"})
    assert response.status_code == 400


def test_conservation_job_submission_rejects_non_amino_acid_characters():
    response = client.post(
        "/api/jobs/conservation", json={"sequence": "MVHL123$%^EEKSAVTALWG"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_conservation_job_execution_completes_and_is_pollable():
    """Directly exercises _execute_blast_job (the background task the
    endpoint schedules) end-to-end, then confirms GET /api/jobs/{job_id} -
    the same polling endpoint used for every other job type - surfaces the
    real conservation profile result."""
    api_module.blast_jobs.clear()
    job_id = "test-blast-job"
    api_module.blast_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.api.BlastClient.find_homologs_and_score_conservation",
        new_callable=AsyncMock,
    ) as mock_find:
        mock_find.return_value = {
            "rid": "rid-1",
            "num_hits": 10,
            "conservation_profile": [
                {
                    "position": 1,
                    "conservation": 1.0,
                    "num_homologs": 10,
                    "most_common": "M",
                }
            ],
        }
        await api_module._execute_blast_job(job_id, "MVHLTPEEK")

    poll = client.get(f"/api/jobs/{job_id}")
    assert poll.json()["status"] == "completed"
    assert poll.json()["num_hits"] == 10
    assert poll.json()["conservation_profile"][0]["most_common"] == "M"

    api_module.blast_jobs.clear()


@pytest.mark.asyncio
async def test_conservation_job_execution_surfaces_pipeline_failure():
    api_module.blast_jobs.clear()
    job_id = "test-blast-job-fail"
    api_module.blast_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.api.BlastClient.find_homologs_and_score_conservation",
        new_callable=AsyncMock,
    ) as mock_find:
        from src.backend.blast_client import BlastError

        mock_find.side_effect = BlastError(
            "BLAST job rid-1 did not complete within 1200s"
        )
        await api_module._execute_blast_job(job_id, "MVHLTPEEK")

    poll = client.get(f"/api/jobs/{job_id}")
    assert poll.json()["status"] == "failed"
    assert "did not complete within 1200s" in poll.json()["error"]

    api_module.blast_jobs.clear()


@pytest.mark.asyncio
async def test_blast_job_sweep_drops_old_finished_jobs_but_keeps_recent_and_running():
    now = time.time()
    api_module.blast_jobs.clear()
    api_module.blast_jobs.update(
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
            await api_module._sweep_blast_jobs()

    remaining = set(api_module.blast_jobs.keys())
    assert remaining == {"recent_completed", "still_running"}
    api_module.blast_jobs.clear()


@pytest.mark.asyncio
async def test_execute_alignment_job_marks_completed_on_success():
    """Mirrors test_execute_alignment_job_marks_failed_on_pipeline_error but
    for the success branch - the TestClient-driven job-submission tests
    schedule this as a fire-and-forget background task, which the sync test
    client's event loop doesn't necessarily run to completion before the
    request returns, so the success dict-assignment itself needs a direct
    await to actually execute."""
    job_id = "test-job-success"
    api_module.alignment_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    with patch(
        "src.backend.api.AnalysisCoordinator.run_full_pipeline",
        return_value=(True, "ok", {"id": "run_abc", "stats": {"mean_rmsd": 1.1}}),
    ):
        await api_module._execute_alignment_job(
            job_id,
            pdb_ids=["4RLT", "3UG9"],
            chain_selection={},
            remove_water=True,
            remove_heteroatoms=True,
            session_id=None,
        )

    job = api_module.alignment_jobs.pop(job_id)
    assert job["status"] == "completed"
    assert job["results"]["id"] == "run_abc"


def test_suggest_endpoint_returns_error_payload_on_request_failure():
    """A network failure calling RCSB's suggest API shouldn't 500 - the
    autocomplete box degrades to no suggestions instead."""
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        response = client.get("/api/suggest?q=hemogl")

    assert response.status_code == 200
    data = response.json()
    assert data["suggestions"] == []
    assert "connection refused" in data["error"]


def test_chains_endpoint_metadata_fetch_failure_is_non_fatal():
    """Best-effort title/method/resolution/organism enrichment must not
    break chain analysis if RCSB's metadata GraphQL endpoint fails."""
    with patch(
        "src.backend.pdb_manager.PDBManager.batch_download"
    ) as mock_download, patch(
        "src.backend.pdb_manager.PDBManager.analyze_structure"
    ) as mock_analyze, patch(
        "src.backend.pdb_manager.PDBManager.fetch_metadata",
        new_callable=AsyncMock,
    ) as mock_metadata:
        mock_download.return_value = {"4RLT": (True, "ok", Path("4rlt.pdb"))}
        mock_analyze.return_value = {"chains": [{"id": "A", "residue_count": 100}]}
        mock_metadata.side_effect = RuntimeError("RCSB GraphQL timeout")

        response = client.post("/api/chains", json={"pdb_ids": ["4RLT"]})

        assert response.status_code == 200
        assert "title" not in response.json()["chains"]["4RLT"]


def test_find_structure_pdb_path_scopes_lookups_by_session_id():
    """Both the raw-download-folder lookup and the run-results-folder
    fallback must be scoped under the session's own subfolder when a
    session_id is given, not just the top-level raw/results dirs."""

    def fake_exists(self):
        return "session_xyz" in str(self) and "run_123" in str(self)

    with patch("pathlib.Path.exists", fake_exists):
        result = api_module._find_structure_pdb_path("4RLT", "run_123", "session_xyz")

    assert result is not None
    assert "session_xyz" in str(result)
    assert "run_123" in str(result)


def test_interactions_endpoint_404s_when_structure_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        response = client.get("/api/interactions?pdb_id=4RLT&ligand_id=RET_A_296")
    assert response.status_code == 404


def test_add_aligned_resi_noop_when_run_not_found():
    """If run_id was given but doesn't resolve to a real run (e.g. it was
    deleted), skip the renumber-map enrichment silently rather than error -
    the raw interactions are still useful without aligned_resi."""
    interactions = {"interactions": [{"resi": 191}]}
    with patch("src.backend.api.history_db.get_run", return_value=None):
        api_module._add_aligned_resi(interactions, "4RLT", Path("4rlt.pdb"), "run_123")

    assert "aligned_resi" not in interactions["interactions"][0]


def test_add_aligned_resi_swallows_renumber_map_failure():
    """A failure while rebuilding the residue renumber map (e.g. the aligned
    structure file went missing) must not break the whole /api/interactions
    response - it's a nice-to-have enrichment, not the core result."""
    interactions = {"interactions": [{"resi": 191}]}
    with patch(
        "src.backend.api.history_db.get_run",
        return_value={"metadata": {"chain_selection": {"4RLT": "A"}}},
    ), patch(
        "src.backend.api.PDBManager.build_residue_renumber_map",
        side_effect=RuntimeError("structure file missing"),
    ):
        api_module._add_aligned_resi(interactions, "4RLT", Path("4rlt.pdb"), "run_123")

    assert "aligned_resi" not in interactions["interactions"][0]


def test_memory_endpoints_report_error_status_on_psutil_failure():
    """Both /api/memory and /api/memory/clear degrade to a fixed placeholder
    RAM value with an error message rather than 500ing, since memory
    reporting is diagnostic, not core functionality."""
    with patch("psutil.Process", side_effect=RuntimeError("no such process")):
        response = client.get("/api/memory")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "no such process" in data["message"]

        response = client.post("/api/memory/clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"
        assert "no such process" in data["message"]


def test_history_endpoint_falls_back_when_session_scoped_query_fails():
    """A malformed/legacy session_id shouldn't break the whole history list
    - fall back to the unscoped query rather than 500."""
    with patch("src.backend.api.history_db.get_all_runs") as mock_get_all, patch(
        "src.backend.api.history_db.count_runs"
    ) as mock_count:

        def get_all_side_effect(*args, **kwargs):
            if kwargs.get("session_id"):
                raise RuntimeError("bad session scope")
            return []

        mock_get_all.side_effect = get_all_side_effect
        mock_count.side_effect = lambda **kwargs: 0 if kwargs.get("session_id") else 3

        response = client.get("/api/history?session_id=weird")

        assert response.status_code == 200
        assert response.json()["total"] == 3


def test_sequence_endpoint_scopes_by_session_id():
    with patch(
        "src.backend.sequence_viewer.SequenceViewer.parse_afasta"
    ) as mock_parse, patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_conservation",
        return_value=[1.0],
    ), patch(
        "src.backend.sequence_viewer.SequenceViewer.calculate_identity",
        return_value=100.0,
    ), patch(
        "pathlib.Path.exists"
    ) as mock_exists:
        mock_parse.return_value = {"4RLT_A": "M"}
        mock_exists.side_effect = lambda self=None: True

        response = client.get("/api/sequence?run_id=run_123&session_id=sess_1")

        assert response.status_code == 200
        # parse_afasta is called with the session-scoped fasta path.
        called_path = str(mock_parse.call_args[0][0])
        assert "sess_1" in called_path


def test_sequence_endpoint_500s_when_fasta_fails_to_parse():
    with patch(
        "src.backend.sequence_viewer.SequenceViewer.parse_afasta", return_value={}
    ), patch("pathlib.Path.exists", return_value=True):
        response = client.get("/api/sequence?run_id=run_123")

    assert response.status_code == 500
    assert "Failed to parse" in response.json()["detail"]


def test_report_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/report?run_id=nope")
    assert response.status_code == 404


def test_report_endpoint_reconstructs_minimal_results_when_metadata_has_no_results(
    tmp_path,
):
    """An older run recorded before metadata.results existed (or one where it
    was dropped) should still produce a report from whatever stats survived,
    rather than crashing on a missing key."""
    dummy_pdf = tmp_path / "mustang_report_test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "pathlib.Path.glob", return_value=[]
    ), patch("src.backend.report_generator.ReportGenerator") as mock_generator_cls:
        mock_generator_cls.return_value.generate_full_report.return_value = dummy_pdf
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT", "3UG9"],
            "metadata": {"stats": {"mean_rmsd": 2.5}},
        }

        response = client.get("/api/report?run_id=run_123&session_id=sess_1")

        assert response.status_code == 200
        results_arg = mock_generator_cls.return_value.generate_full_report.call_args[0][
            0
        ]
        assert results_arg["stats"] == {"mean_rmsd": 2.5}
        assert results_arg["id"] == "run_123"
        res_dir_arg = mock_generator_cls.call_args[0][0]
        assert "sess_1" in str(res_dir_arg)


def test_report_endpoint_reuses_cached_pdf_for_default_request(tmp_path):
    """A default (no ?sections=) request must reuse an already-generated
    report on disk instead of regenerating it every time the tab is
    reopened."""
    cached_pdf = tmp_path / "mustang_report_cached.pdf"
    cached_pdf.write_bytes(b"%PDF-1.4 cached content")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "pathlib.Path.glob", return_value=[cached_pdf]
    ), patch(
        "src.backend.report_generator.ReportGenerator.generate_full_report"
    ) as mock_generate:
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/report?run_id=run_123")

        assert response.status_code == 200
        assert b"cached content" in response.content
        mock_generate.assert_not_called()


def test_report_endpoint_500s_when_generated_file_missing(tmp_path):
    never_written = tmp_path / "never_written.pdf"

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "pathlib.Path.glob", return_value=[]
    ), patch(
        "src.backend.report_generator.ReportGenerator.generate_full_report",
        return_value=never_written,
    ):
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/report?run_id=run_123")

        assert response.status_code == 500
        assert "not created successfully" in response.json()["detail"]


def test_report_endpoint_500s_on_unexpected_generator_error():
    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "pathlib.Path.glob", return_value=[]
    ), patch(
        "src.backend.report_generator.ReportGenerator.generate_full_report",
        side_effect=RuntimeError("disk full"),
    ):
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/report?run_id=run_123")

        assert response.status_code == 500
        assert "disk full" in response.json()["detail"]


def test_notebook_endpoint_404s_for_unknown_run():
    with patch("src.backend.api.history_db.get_run", return_value=None):
        response = client.get("/api/notebook?run_id=nope")
    assert response.status_code == 404


def test_notebook_endpoint_scopes_result_dir_by_session_id(tmp_path):
    dummy_html = tmp_path / "lab_notebook.html"
    dummy_html.write_text("<html>dummy notebook</html>")

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.notebook_exporter.NotebookExporter.export"
    ) as mock_export:
        mock_export.return_value = dummy_html
        mock_get_run.return_value = {
            "id": "run_123",
            "pdb_ids": ["4RLT"],
            "metadata": {"results": {"stats": {}, "id": "run_123"}},
        }

        response = client.get("/api/notebook?run_id=run_123&session_id=sess_1")

        assert response.status_code == 200
        results_arg = mock_export.call_args[0][0]
        assert "sess_1" in str(results_arg["result_dir"])


def test_compare_citations_endpoint_500s_on_unexpected_export_error():
    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.citation_exporter.CitationExporter.export"
    ) as mock_export:
        mock_export.side_effect = RuntimeError("disk full")
        mock_get_run.return_value = {"id": "run_123", "pdb_ids": ["4RLT", "3UG9"]}

        response = client.get("/api/report/citations?run_id=run_123")

        assert response.status_code == 500
        assert "disk full" in response.json()["detail"]


def test_discover_export_json_endpoint_404s_when_no_stored_results():
    with patch("src.backend.api.history_db.get_run") as mock_get_run:
        mock_get_run.return_value = {
            "id": "discover_123",
            "metadata": {"run_type": "discover", "results": None},
        }
        response = client.get("/api/discover/export?run_id=discover_123")
        assert response.status_code == 404


def test_discover_report_endpoint_500s_when_file_not_actually_created():
    missing_html = Path(tempfile.mkdtemp()) / "never_written.html"

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.discovery_report_exporter.DiscoveryReportExporter.export"
    ) as mock_export:
        mock_get_run.return_value = _discover_run()
        mock_export.return_value = missing_html

        response = client.get("/api/discover/report?run_id=discover_123")

        assert response.status_code == 500
        assert "not created" in response.json()["detail"]


def test_discover_report_endpoint_500s_on_unexpected_export_error():
    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.discovery_report_exporter.DiscoveryReportExporter.export"
    ) as mock_export:
        mock_get_run.return_value = _discover_run()
        mock_export.side_effect = RuntimeError("disk full")

        response = client.get("/api/discover/report?run_id=discover_123")

        assert response.status_code == 500
        assert "disk full" in response.json()["detail"]


def test_discover_citations_endpoint_passes_through_http_exceptions_unwrapped():
    """If the export step itself raises an HTTPException (as opposed to a
    generic failure), it must be re-raised as-is, not swallowed and
    rewrapped by the generic exception handler's own message formatting."""
    from fastapi import HTTPException

    with patch("src.backend.api.history_db.get_run") as mock_get_run, patch(
        "src.backend.citation_exporter.CitationExporter.export",
        side_effect=HTTPException(status_code=502, detail="upstream boom"),
    ):
        mock_get_run.return_value = _discover_run()

        response = client.get("/api/discover/citations?run_id=discover_123")

        assert response.status_code == 502
        assert response.json()["detail"] == "upstream boom"
    api_module.discovery_jobs.clear()
