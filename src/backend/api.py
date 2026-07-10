import os
import sys
import time
import uuid
import secrets
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, List, Dict, Any, Optional, Tuple

import matplotlib

matplotlib.use("Agg")

import json
import re
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Body, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

# Ensure working directory is set to project root if run from subdirectories
project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.utils.config_loader import load_config, save_config
from src.utils.logger import get_logger, sanitize_for_log
from src.backend.coordinator import AnalysisCoordinator
from src.backend.discovery_coordinator import DiscoveryCoordinator
from src.backend.foldseek_client import FoldseekClient, FoldseekError
from src.backend.database import HistoryDatabase
from src.backend.ligand_analyzer import LigandAnalyzer
from src.backend.interface_analyzer import InterfaceAnalyzer
from src.backend.pdb_manager import PDBManager
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.result_manager import ResultManager

logger = get_logger()

# Load application configuration
try:
    config = load_config(str(project_root / "config.yaml"))
except Exception:
    # Fallback default configuration
    config = {
        "app": {"name": "StructScope API", "max_proteins": 10},
        "pdb": {
            "source_url": "https://files.rcsb.org/download/",
            "timeout": 10,
            "max_file_size_mb": 150,
        },
        "mustang": {"backend": "native", "executable_path": None, "timeout": 60},
        "filtering": {"remove_water": True, "remove_heteroatoms": True},
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweep_task = asyncio.create_task(_sweep_alignment_jobs())
    discovery_sweep_task = asyncio.create_task(_sweep_discovery_jobs())
    yield
    sweep_task.cancel()
    discovery_sweep_task.cancel()


# Initialize FastAPI App
# version reads from config.yaml's app.version rather than a hardcoded
# string, so /docs and /openapi.json can't silently drift out of sync with
# the app's actual release version the way a hardcoded "1.0.0" did before.
app = FastAPI(
    title="StructScope Web API",
    description="REST API backend for StructScope: protein structural alignment and structure-to-function discovery",
    version=config.get("app", {}).get("version", "0.0.0"),
    lifespan=lifespan,
)

# Enable CORS for frontend integration. Defaults to "*" for local development;
# set ALIGNX_CORS_ORIGINS (comma-separated) to restrict this in production.
_cors_origins_env = os.environ.get("ALIGNX_CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key auth for /api/* routes. Disabled (open access) when ALIGNX_API_KEY
# is unset, so local development works unchanged out of the box.
_ALIGNX_API_KEY = os.environ.get("ALIGNX_API_KEY")


def _cors_misconfiguration_warning(
    api_key: Optional[str], cors_origins_env: str
) -> Optional[str]:
    """A configured API key is the signal that this is a real deployment,
    not local development - if CORS is still wide-open in that case, this
    returns a warning to log at startup rather than silently shipping
    credentialed CORS to any origin (see SECURITY.md's "Known Limitations":
    there was previously no CI/deploy-time check for this omission at
    all). Returns None when there's nothing to warn about."""
    if api_key and cors_origins_env == "*":
        return (
            "ALIGNX_API_KEY is set but ALIGNX_CORS_ORIGINS is still the "
            "default '*' - this serves wide-open, credentialed CORS to any "
            "origin. Set ALIGNX_CORS_ORIGINS to your actual frontend "
            "origin(s) for a real deployment."
        )
    return None


_cors_warning = _cors_misconfiguration_warning(_ALIGNX_API_KEY, _cors_origins_env)
if _cors_warning:
    logger.warning(_cors_warning)


_AUTH_REQUIRED_PREFIXES = ("/api/", "/results/", "/raw/")


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    # /results and /raw serve generated reports/notebooks and downloaded
    # structure files directly off disk via StaticFiles - session/run
    # folder names aren't secrets, so without this check anyone who can
    # reach the server could browse or guess their way into another
    # session's files even with an API key configured for everything else.
    if _ALIGNX_API_KEY and request.url.path.startswith(_AUTH_REQUIRED_PREFIXES):
        # Header is preferred; query param fallback exists so plain <a>/window.open
        # links (e.g. the PDF report download) can still authenticate.
        provided = request.headers.get("X-API-Key") or request.query_params.get(
            "api_key"
        )
        if provided != _ALIGNX_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API key."},
            )
    return await call_next(request)


# Rate limit job-submission endpoints specifically — those trigger real
# compute/external calls (Mustang + phylogenetics, or the shared-rate-limited
# Foldseek API), so they're the actual abuse vector, unlike cheap reads such
# as /api/history or /api/jobs/{id} polling. Discovery jobs get a tighter
# ceiling than alignment jobs since they compete for Foldseek's own strict
# rate limit across every StructScope user (see FoldseekClient's rate limiter).
# Applies even when ALIGNX_API_KEY is unset, since that's the default/open state.
_JOB_RATE_LIMIT_MAX = int(os.environ.get("ALIGNX_JOB_RATE_LIMIT_MAX", 5))
_JOB_RATE_LIMIT_WINDOW_SECONDS = int(
    os.environ.get("ALIGNX_JOB_RATE_LIMIT_WINDOW_SECONDS", 60)
)
_DISCOVERY_RATE_LIMIT_MAX = int(os.environ.get("ALIGNX_DISCOVERY_RATE_LIMIT_MAX", 3))
_job_submission_timestamps: Dict[str, List[float]] = {}


def _rate_limit_client_key(request: Request) -> str:
    provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if provided:
        return f"key:{provided}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _job_rate_limit_max(path: str) -> Optional[int]:
    """Resolved per-request (not baked into a dict at import time) so tests
    can patch _JOB_RATE_LIMIT_MAX / _DISCOVERY_RATE_LIMIT_MAX directly."""
    if path == "/api/jobs/align":
        return _JOB_RATE_LIMIT_MAX
    if path == "/api/jobs/discover":
        return _DISCOVERY_RATE_LIMIT_MAX
    return None


@app.middleware("http")
async def rate_limit_job_submissions(request: Request, call_next):
    job_max = _job_rate_limit_max(request.url.path)
    if request.method == "POST" and job_max is not None:
        key = f"{request.url.path}:{_rate_limit_client_key(request)}"
        now = time.time()
        cutoff = now - _JOB_RATE_LIMIT_WINDOW_SECONDS
        timestamps = [t for t in _job_submission_timestamps.get(key, []) if t > cutoff]
        if len(timestamps) >= job_max:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded: max {job_max} submissions to "
                        f"{request.url.path} per {_JOB_RATE_LIMIT_WINDOW_SECONDS}s."
                    )
                },
            )
        timestamps.append(now)
        _job_submission_timestamps[key] = timestamps
    return await call_next(request)


# Mount static directories for results and raw PDBs
results_dir = project_root / "results"
raw_dir = project_root / "data" / "raw"
results_dir.mkdir(parents=True, exist_ok=True)
raw_dir.mkdir(parents=True, exist_ok=True)

app.mount("/results", StaticFiles(directory=str(results_dir)), name="results")
app.mount("/raw", StaticFiles(directory=str(raw_dir)), name="raw")

_SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_segment(value: Optional[str], field_name: str) -> Optional[str]:
    """
    Validate a value that will be concatenated into a filesystem path
    (session_id, run_id, pdb_id, etc). Only alnum/underscore/hyphen are
    allowed, which blocks path traversal ("..", "/", "\\") while still
    accepting every legitimate id format used in this app.
    """
    if value is None:
        return None
    if not _SAFE_PATH_SEGMENT.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value!r}")
    return value


# Initialize Backend Managers
history_db = HistoryDatabase()
ligand_analyzer = LigandAnalyzer(config)
interface_analyzer = InterfaceAnalyzer()
rmsd_analyzer = RMSDAnalyzer(config)


@app.get("/health")
def health_check():
    """Health check endpoint to verify backend service is running."""
    coordinator = AnalysisCoordinator(config)
    mustang_ok, mustang_msg = coordinator.mustang_runner.check_installation()
    return {
        "status": "healthy",
        "mustang_installed": mustang_ok,
        "mustang_message": mustang_msg,
    }


def _current_settings() -> Dict[str, Any]:
    """The runtime-editable subset of `config` - mirrors the Streamlit
    Settings page's exact field set (pages/3_Settings.py)."""
    return {
        "mustang_backend": config.get("mustang", {}).get("backend", "auto"),
        "mustang_timeout": config.get("mustang", {}).get("timeout", 600),
        "max_proteins": config.get("core", {}).get("max_proteins", 20),
        "max_file_size_mb": config.get("pdb", {}).get("max_file_size_mb", 500),
        "heatmap_colormap": config.get("visualization", {}).get(
            "heatmap_colormap", "RdYlBu_r"
        ),
        "viewer_default_style": config.get("visualization", {}).get(
            "viewer_default_style", "cartoon"
        ),
    }


class SettingsUpdate(BaseModel):
    """Field defaults here are deliberately Streamlit's own DEFAULT_SETTINGS
    (pages/3_Settings.py), not VisualizationConfig's Pydantic defaults
    (config_models.py) - the two disagree on heatmap_colormap ("viridis"
    vs "RdYlBu_r"), and it's Streamlit's "Restore Defaults" button
    behavior this class's un-set fields are meant to mirror."""

    mustang_backend: str = "auto"
    mustang_timeout: int = Field(600, ge=1)
    max_proteins: int = Field(20, ge=2, le=100)
    max_file_size_mb: int = Field(500, ge=1)
    heatmap_colormap: str = "viridis"
    viewer_default_style: str = "cartoon"


@app.get("/api/settings")
def get_settings():
    """Read the runtime-editable subset of the pipeline config. There's no
    settings page anywhere in the SPA today (the Streamlit app's
    pages/3_Settings.py is the only place these are currently editable) -
    this is the first step toward porting that."""
    return _current_settings()


@app.post("/api/settings", responses={400: {"description": "Invalid settings"}})
def update_settings(update: SettingsUpdate):
    """Apply and persist new settings. `config` is a single shared dict
    every request-scoped coordinator/manager already reads from at
    construction time (AnalysisCoordinator(config), PDBManager(config),
    etc. all just store a reference, never a deep copy) - mutating its
    nested sections in place, rather than introducing a second parallel
    settings object, means every future request automatically picks up
    the change with no extra wiring or cache invalidation needed (unlike
    Streamlit, which caches a MustangRunner in session state and has to
    explicitly drop it after a save)."""
    from src.backend.config_models import MustangConfig

    try:
        MustangConfig(backend=update.mustang_backend, timeout=update.mustang_timeout)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    config.setdefault("mustang", {})["backend"] = update.mustang_backend.lower()
    config["mustang"]["timeout"] = update.mustang_timeout
    config.setdefault("core", {})["max_proteins"] = update.max_proteins
    config.setdefault("pdb", {})["max_file_size_mb"] = update.max_file_size_mb
    config.setdefault("visualization", {})["heatmap_colormap"] = update.heatmap_colormap
    config["visualization"]["viewer_default_style"] = update.viewer_default_style

    try:
        save_config(config)
    except Exception as e:
        logger.warning(f"Failed to persist settings to config.yaml: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to save settings: {str(e)}"
        )

    return _current_settings()


@app.post("/api/settings/reset")
def reset_settings():
    """Restore the same hardcoded defaults Streamlit's "Restore Defaults"
    button uses (pages/3_Settings.py's DEFAULT_SETTINGS)."""
    defaults = SettingsUpdate()
    return update_settings(defaults)


@app.get("/api/suggest")
def get_rcsb_suggestions(q: Annotated[str, Query(..., min_length=1)]):
    """
    Fetch matching PDB IDs from RCSB Suggest API.
    """
    import urllib.request
    import urllib.parse
    import re

    query_struct = {"type": "basic", "suggest": {"text": q, "size": 6}}
    try:
        quoted_query = urllib.parse.quote(json.dumps(query_struct))
        url = f"https://search.rcsb.org/rcsbsearch/v2/suggest?json={quoted_query}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as res:
            data = json.loads(res.read().decode())
            suggestions = data.get("suggestions", {})
            pdb_entries = suggestions.get(
                "rcsb_entry_container_identifiers.entry_id", []
            )

            results = []
            for entry in pdb_entries:
                raw_text = entry.get("text", "")
                clean_text = re.sub(r"<[^>]+>", "", raw_text).upper()
                if clean_text and len(clean_text) == 4 and clean_text not in results:
                    results.append(clean_text)
            return {"query": q, "suggestions": results}
    except Exception as e:
        return {"query": q, "suggestions": [], "error": str(e)}


@app.post(
    "/api/chains",
    responses={
        400: {
            "description": "Invalid pdb_id/session_id, an empty pdb_ids list, or a structure failed to download"
        }
    },
)
async def analyze_chains(
    pdb_ids: Annotated[List[str], Body(..., embed=True)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Download PDB files and analyze their structural chains.
    """
    if not pdb_ids:
        raise HTTPException(status_code=400, detail="pdb_ids list cannot be empty")
    for pid in pdb_ids:
        _safe_segment(pid, "pdb_id")
    _safe_segment(session_id, "session_id")

    coordinator = AnalysisCoordinator(config, session_id=session_id)
    download_results = await coordinator.pdb_manager.batch_download(pdb_ids)

    failed = [
        pid for pid, (success, msg, path) in download_results.items() if not success
    ]
    if failed:
        raise HTTPException(
            status_code=400, detail=f"Failed to fetch PDBs: {', '.join(failed)}"
        )

    # analyze_structure() does synchronous Bio.PDB parsing (CPU + file I/O
    # bound). Called directly inside this async handler it would block
    # uvicorn's single event loop for its full duration, stalling every
    # other concurrent request (health/memory polling, other tabs' fetches)
    # - not just this one. asyncio.to_thread offloads it to a worker thread.
    chain_info = {}
    for pid, (success, msg, path) in download_results.items():
        if path:
            info = await asyncio.to_thread(
                coordinator.pdb_manager.analyze_structure, path
            )
            info["source"] = PDBManager.detect_source(pid)
            chain_info[pid] = info

    # Best-effort metadata enrichment (title/method/resolution/organism, used
    # by e.g. ClustersTab's structure labels and the Overview PDB list) — a
    # network failure here shouldn't break chain analysis.
    try:
        metadata = await coordinator.pdb_manager.fetch_metadata(list(chain_info.keys()))
        for pid, meta in metadata.items():
            if pid in chain_info:
                chain_info[pid]["title"] = meta.get("title", "N/A")
                chain_info[pid]["method"] = meta.get("method", "N/A")
                chain_info[pid]["resolution"] = meta.get("resolution", "N/A")
                chain_info[pid]["organism"] = meta.get("organism", "N/A")
    except Exception as e:
        logger.warning(f"Failed to fetch PDB title metadata: {e}")

    return {"chains": sanitize_for_json(chain_info)}


@app.post(
    "/api/upload",
    responses={
        400: {
            "description": "Invalid session_id, an unsupported file extension, or the uploaded file failed to parse as a real structure"
        }
    },
)
async def upload_structure(
    file: Annotated[UploadFile, File(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Accept a user-uploaded .pdb/.ent/.cif structure file (rather than
    fetching one of the four public databases by ID), validate it actually
    parses as a structure, and return the same {"chains": {...}} shape
    /api/chains does so the frontend can merge it in identically.
    """
    _safe_segment(session_id, "session_id")

    if not file.filename or not file.filename.lower().endswith(
        (".pdb", ".ent", ".cif")
    ):
        raise HTTPException(
            status_code=400, detail="Only .pdb, .ent, or .cif files are accepted."
        )

    content = await file.read()
    # Random, not derived from the filename - a stable ID keyed on user input
    # would let two uploads collide (or let an ID be guessed/reused).
    structure_id = f"UPLOAD-{secrets.token_hex(4).upper()}"

    coordinator = AnalysisCoordinator(config, session_id=session_id)
    # save_uploaded_bytes() does file I/O plus a real Bio.PDB parse to
    # validate the content - both blocking, offloaded like analyze_structure
    # below (see that call's comment for why this matters under uvicorn).
    success, msg, path = await asyncio.to_thread(
        coordinator.pdb_manager.save_uploaded_bytes,
        file.filename,
        content,
        structure_id,
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    info = await asyncio.to_thread(coordinator.pdb_manager.analyze_structure, path)
    info["source"] = "upload"
    info["original_filename"] = file.filename

    return {"chains": {structure_id: sanitize_for_json(info)}}


def _coerce_numpy_scalar(val: Any) -> Any:
    """A 0-d numpy scalar (has dtype/item, no ndim or ndim==0) converts to
    its plain Python equivalent; anything else passes through unchanged."""
    if (
        hasattr(val, "dtype")
        and hasattr(val, "item")
        and (not hasattr(val, "ndim") or val.ndim == 0)
    ):
        try:
            return val.item()
        except Exception:
            return val
    return val


def _is_plotly_bdata(val: Any) -> bool:
    return (
        isinstance(val, dict)
        and val.keys() >= {"dtype", "bdata"}
        and isinstance(val.get("bdata"), str)
    )


def _decode_plotly_bdata(val: Dict[str, Any]) -> Any:
    """Plotly 6.x's compact binary typed-array format for numeric trace data
    (emitted for figure_factory dendrograms and some Heatmap traces,
    regardless of whether the original value was a numpy array or a plain
    list — Plotly's trace validators re-coerce it internally).
    "shape" is only present for 2D+ arrays (e.g. a heatmap's z); flat 1D
    arrays (e.g. a dendrogram trace's x/y) omit it entirely. The pinned
    frontend Plotly.js CDN version can't decode either form, so decode it
    back into a plain (possibly nested) list here."""
    import base64
    import numpy as np

    try:
        raw = base64.b64decode(val["bdata"])
        arr = np.frombuffer(raw, dtype=val["dtype"])
        if "shape" in val:
            shape = tuple(int(s) for s in str(val["shape"]).replace(" ", "").split(","))
            arr = arr.reshape(shape)
        return sanitize_for_json(arr)
    except Exception:
        return {str(k): sanitize_for_json(v) for k, v in val.items()}


def _is_intlike(val: Any) -> bool:
    import numpy as np

    return isinstance(val, (int, np.integer)) or "int" in type(val).__name__.lower()


def _is_floatlike(val: Any) -> bool:
    import numpy as np

    return (
        isinstance(val, (float, np.floating)) or "float" in type(val).__name__.lower()
    )


def _coerce_float(val: Any) -> Optional[float]:
    import math

    try:
        fval = float(val)
        return None if (math.isnan(fval) or math.isinf(fval)) else fval
    except Exception:
        return None


def _coerce_via_to_dict(val: Any) -> Any:
    try:
        if type(val).__name__ == "DataFrame":
            return sanitize_for_json(val.to_dict(orient="split"))
        return sanitize_for_json(val.to_dict())
    except Exception:
        return str(val)


def sanitize_for_json(val: Any) -> Any:
    """
    Recursively convert NumPy types and other non-standard types to JSON-friendly standard Python types,
    replacing NaN and Infinity with None.
    """
    import numpy as np

    val = _coerce_numpy_scalar(val)

    if _is_plotly_bdata(val):
        return _decode_plotly_bdata(val)
    if isinstance(val, dict):
        return {str(k): sanitize_for_json(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [sanitize_for_json(item) for item in val]
    if _is_intlike(val):
        return int(val)
    if _is_floatlike(val):
        return _coerce_float(val)
    if isinstance(val, np.ndarray):
        return sanitize_for_json(val.tolist())
    if hasattr(val, "to_plotly_json"):
        return sanitize_for_json(val.to_plotly_json())
    if hasattr(val, "to_dict"):
        return _coerce_via_to_dict(val)
    if isinstance(val, Path):
        return str(val)
    return val


# asyncio.create_task() returns a Task the event loop only holds a WEAK
# reference to - with nothing else keeping it alive, it can be garbage
# collected mid-execution (a real, documented asyncio footgun: "Save a
# reference to the result of this function, to avoid a task disappearing
# mid-execution" - https://docs.python.org/3/library/asyncio-task.html).
# Both job-submission endpoints fire their execution coroutine and
# immediately discard create_task()'s return value, so every job launched
# this way runs that risk. This module-level set holds a strong reference
# until the task finishes, then the done-callback removes it.
_background_tasks: set = set()


def _spawn_background_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


# In-memory job registry for the async alignment pipeline. Alignment runs can take
# minutes (Mustang + phylogenetics + rendering), so they're executed on a background
# thread and polled via job_id rather than blocking the HTTP request.
#
# Jobs are swept periodically (see _sweep_alignment_jobs) so a long-lived server
# doesn't accumulate unbounded memory from old job records.
alignment_jobs: Dict[str, Dict[str, Any]] = {}
_JOB_TTL_SECONDS = int(os.environ.get("ALIGNX_JOB_TTL_SECONDS", 3600))
_JOB_SWEEP_INTERVAL_SECONDS = 300


async def _sweep_alignment_jobs():
    """Periodically drop finished jobs older than _JOB_TTL_SECONDS."""
    while True:
        await asyncio.sleep(_JOB_SWEEP_INTERVAL_SECONDS)
        now = time.time()
        stale_ids = [
            jid
            for jid, job in alignment_jobs.items()
            if job.get("status") in ("completed", "failed")
            and now - job.get("finished_at", now) > _JOB_TTL_SECONDS
        ]
        for jid in stale_ids:
            alignment_jobs.pop(jid, None)


def _run_alignment_pipeline(
    pdb_ids: List[str],
    chain_selection: Dict[str, str],
    remove_water: bool,
    remove_heteroatoms: bool,
    session_id: Optional[str],
) -> Dict[str, Any]:
    """Blocking pipeline execution, run on a worker thread by the job runner."""
    coordinator = AnalysisCoordinator(config, session_id=session_id)
    success, msg, results = coordinator.run_full_pipeline(
        pdb_ids=pdb_ids,
        chain_selection=chain_selection,
        remove_water=remove_water,
        remove_heteroatoms=remove_heteroatoms,
    )
    if not success:
        raise RuntimeError(f"Alignment failed: {msg}")
    return {"message": msg, "results": sanitize_for_json(results)}


async def _execute_alignment_job(job_id: str, **pipeline_kwargs):
    alignment_jobs[job_id]["status"] = "running"
    created_at = alignment_jobs[job_id].get("created_at", time.time())
    try:
        outcome = await asyncio.to_thread(_run_alignment_pipeline, **pipeline_kwargs)
        alignment_jobs[job_id] = {
            "status": "completed",
            "created_at": created_at,
            "finished_at": time.time(),
            **outcome,
        }
    except Exception as e:
        alignment_jobs[job_id] = {
            "status": "failed",
            "created_at": created_at,
            "finished_at": time.time(),
            "error": str(e),
        }


@app.post(
    "/api/jobs/align",
    status_code=202,
    responses={
        400: {"description": "Fewer than 2 PDB IDs, or an invalid pdb_id/session_id"}
    },
)
async def submit_alignment_job(
    pdb_ids: Annotated[List[str], Body(..., embed=True)],
    chain_selection: Annotated[Dict[str, str], Body(embed=True)] = {},
    remove_water: Annotated[bool, Body(embed=True)] = True,
    remove_heteroatoms: Annotated[bool, Body(embed=True)] = True,
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Submit a Mustang multiple structural alignment run as a background job.
    Returns immediately with a job_id; poll GET /api/jobs/{job_id} for status.
    """
    if not pdb_ids or len(pdb_ids) < 2:
        raise HTTPException(
            status_code=400, detail="At least 2 PDB IDs are required for alignment."
        )
    for pid in pdb_ids:
        _safe_segment(pid, "pdb_id")
    _safe_segment(session_id, "session_id")

    job_id = uuid.uuid4().hex
    alignment_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    _spawn_background_task(
        _execute_alignment_job(
            job_id,
            pdb_ids=pdb_ids,
            chain_selection=chain_selection,
            remove_water=remove_water,
            remove_heteroatoms=remove_heteroatoms,
            session_id=session_id,
        )
    )

    return {"job_id": job_id, "status": "queued"}


@app.get(
    "/api/jobs/{job_id}",
    responses={
        404: {"description": "No alignment or discovery job exists with this job_id"}
    },
)
def get_alignment_job(job_id: str):
    """
    Poll the status/result of a submitted job (alignment or discovery - job
    IDs are unique uuid4 hex strings, so one polling endpoint covers both).
    """
    job = alignment_jobs.get(job_id) or discovery_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {"job_id": job_id, **job}


# In-memory job registry for the async single-structure discovery pipeline
# (Foldseek structural search). Mirrors alignment_jobs above: Foldseek jobs
# can take a while (upload + poll + fetch, plus the shared rate limiter -
# see FoldseekClient), so they run on a background thread and are polled via
# job_id rather than blocking the HTTP request.
discovery_jobs: Dict[str, Dict[str, Any]] = {}


async def _sweep_discovery_jobs():
    """Periodically drop finished discovery jobs older than _JOB_TTL_SECONDS."""
    while True:
        await asyncio.sleep(_JOB_SWEEP_INTERVAL_SECONDS)
        now = time.time()
        stale_ids = [
            jid
            for jid, job in discovery_jobs.items()
            if job.get("status") in ("completed", "failed")
            and now - job.get("finished_at", now) > _JOB_TTL_SECONDS
        ]
        for jid in stale_ids:
            discovery_jobs.pop(jid, None)


def _run_discovery_pipeline(
    pdb_id: str,
    databases: Optional[List[str]],
    session_id: Optional[str],
) -> Dict[str, Any]:
    """Blocking pipeline execution, run on a worker thread by the job runner."""
    coordinator = DiscoveryCoordinator(config, session_id=session_id)
    success, msg, results = coordinator.run_discovery_pipeline(
        pdb_id=pdb_id, databases=databases
    )
    if not success:
        raise RuntimeError(f"Discovery failed: {msg}")
    return {"message": msg, "results": sanitize_for_json(results)}


async def _execute_discovery_job(job_id: str, **pipeline_kwargs):
    discovery_jobs[job_id]["status"] = "running"
    created_at = discovery_jobs[job_id].get("created_at", time.time())
    try:
        outcome = await asyncio.to_thread(_run_discovery_pipeline, **pipeline_kwargs)
        discovery_jobs[job_id] = {
            "status": "completed",
            "created_at": created_at,
            "finished_at": time.time(),
            **outcome,
        }
    except Exception as e:
        discovery_jobs[job_id] = {
            "status": "failed",
            "created_at": created_at,
            "finished_at": time.time(),
            "error": str(e),
        }


@app.post(
    "/api/jobs/discover",
    status_code=202,
    responses={
        400: {
            "description": "Missing/invalid pdb_id, invalid structure identifier, invalid databases list, or invalid session_id"
        }
    },
)
async def submit_discovery_job(
    pdb_id: Annotated[str, Body(..., embed=True)],
    databases: Annotated[Optional[List[str]], Body(embed=True)] = None,
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Submit a single-structure Foldseek discovery run as a background job:
    finds structurally similar proteins for one query structure. Unlike
    /api/jobs/align, this takes exactly one structure, not 2+.
    Returns immediately with a job_id; poll GET /api/jobs/{job_id} for status.
    """
    if not pdb_id or not pdb_id.strip():
        raise HTTPException(status_code=400, detail="pdb_id is required.")
    _safe_segment(pdb_id, "pdb_id")
    if not PDBManager.validate_pdb_id(pdb_id):
        raise HTTPException(
            status_code=400, detail=f"Invalid structure identifier: {pdb_id}"
        )
    if databases:
        try:
            FoldseekClient.validate_databases(databases)
        except FoldseekError as e:
            raise HTTPException(status_code=400, detail=str(e))
    _safe_segment(session_id, "session_id")

    job_id = uuid.uuid4().hex
    discovery_jobs[job_id] = {"status": "queued", "created_at": time.time()}

    _spawn_background_task(
        _execute_discovery_job(
            job_id,
            pdb_id=pdb_id,
            databases=databases,
            session_id=session_id,
        )
    )

    return {"job_id": job_id, "status": "queued"}


@app.post(
    "/api/clusters",
    responses={
        400: {"description": "Malformed rmsd_df payload or fewer than 2 structures"}
    },
)
def get_clusters(
    rmsd_df: Annotated[Dict[str, Any], Body(..., embed=True)],
    threshold: Annotated[float, Body(embed=True)] = 3.0,
):
    """
    Identify structural clusters from an RMSD matrix at a given threshold.

    Args:
        rmsd_df: RMSD matrix in pandas "split" orient (index, columns, data),
            as returned by /api/align.
        threshold: RMSD cutoff (Angstroms) for grouping structures together.
    """
    try:
        df = pd.DataFrame(
            data=rmsd_df["data"],
            index=rmsd_df["index"],
            columns=rmsd_df["columns"],
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid rmsd_df payload: {e}")

    if len(df) < 2:
        raise HTTPException(
            status_code=400, detail="At least 2 structures are required for clustering."
        )

    clusters = rmsd_analyzer.identify_clusters(df, threshold=threshold)

    families = []
    for cid, members in clusters.items():
        avg_rmsd = 0.0
        if len(members) > 1:
            subset = df.loc[members, members]
            avg_rmsd = float(subset.values[np.triu_indices(len(members), k=1)].mean())
        families.append(
            {
                "cluster_id": int(cid),
                "members": members,
                "avg_rmsd": round(avg_rmsd, 2),
            }
        )

    return {"threshold": threshold, "clusters": sanitize_for_json(families)}


@app.get(
    "/api/comparison/runs",
    responses={400: {"description": "Invalid exclude_run_id or session_id"}},
)
def list_comparison_runs(
    exclude_run_id: Annotated[Optional[str], Query()] = None,
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    List past runs available as batch-comparison targets.
    """
    _safe_segment(exclude_run_id, "exclude_run_id")
    _safe_segment(session_id, "session_id")
    res_dir = results_dir / session_id if session_id else results_dir
    manager = ResultManager(res_dir)
    runs = manager.list_runs(session_id=session_id)

    runs = [r for r in runs if r["id"] != exclude_run_id]
    return {
        "runs": sanitize_for_json(
            [
                {"id": r["id"], "timestamp": r["timestamp"], "proteins": r["proteins"]}
                for r in runs
            ]
        )
    }


@app.get(
    "/api/comparison",
    responses={
        400: {
            "description": "Invalid run_id/session_id, or no overlapping proteins between the two runs"
        },
        404: {"description": "RMSD matrix not found for one or both runs"},
    },
)
def compare_runs(
    current_run_id: Annotated[str, Query(...)],
    target_run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Compute the RMSD difference matrix between two past runs.
    """
    _safe_segment(current_run_id, "current_run_id")
    _safe_segment(target_run_id, "target_run_id")
    _safe_segment(session_id, "session_id")
    res_dir = results_dir / session_id if session_id else results_dir
    manager = ResultManager(res_dir)

    diff_df = manager.calculate_difference(current_run_id, target_run_id)
    if diff_df is None:
        raise HTTPException(
            status_code=400, detail="No overlapping proteins found between these runs."
        )

    current_rmsd = manager.get_run_rmsd(current_run_id)
    target_rmsd = manager.get_run_rmsd(target_run_id)
    if current_rmsd is None or target_rmsd is None:
        raise HTTPException(
            status_code=404, detail="RMSD matrix not found for one or both runs."
        )

    # Use the same upper-triangle-only mean as everywhere else in the app
    # (rmsd_analyzer.calculate_statistics powers the 3D viewer HUD, Sequence
    # tab, and RMSD Matrix chart) rather than a full-matrix mean, which
    # double-counts each pair and dilutes the average with the zero
    # diagonal — systematically underestimating by a factor of (N-1)/N.
    current_mean = rmsd_analyzer.calculate_statistics(current_rmsd)["mean_rmsd"]
    target_mean = rmsd_analyzer.calculate_statistics(target_rmsd)["mean_rmsd"]

    return {
        "current_run_id": current_run_id,
        "target_run_id": target_run_id,
        "diff": sanitize_for_json(diff_df.to_dict(orient="split")),
        "current_mean_rmsd": round(current_mean, 3),
        "target_mean_rmsd": round(target_mean, 3),
        "mean_rmsd_shift": round(current_mean - target_mean, 3),
    }


@app.get(
    "/api/ligands",
    responses={
        400: {"description": "Invalid pdb_id, run_id, or session_id"},
        404: {"description": "Structure PDB not found in the active workspace"},
    },
)
def get_ligands(
    pdb_id: Annotated[str, Query(...)],
    run_id: Annotated[Optional[str], Query()] = None,
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Retrieve ligands present in the specified structure.
    """
    _safe_segment(pdb_id, "pdb_id")
    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    pdb_path = _find_structure_pdb_path(pdb_id, run_id, session_id)
    if not pdb_path:
        raise HTTPException(
            status_code=404,
            detail=f"Structure PDB for {pdb_id} not found in active workspace.",
        )

    ligands = ligand_analyzer.get_ligands(pdb_path)
    return {"pdb_id": pdb_id, "ligands": sanitize_for_json(ligands)}


def _find_structure_pdb_path(
    pdb_id: str, run_id: Optional[str], session_id: Optional[str]
) -> Optional[Path]:
    """Locates a previously-downloaded structure's PDB file: first in the
    session's raw-download folder, then (if a run_id is given) that run's
    own results folder, trying the id's as-given/lowercase/uppercase
    filename in each. Shared by /api/ligands and /api/interactions, which
    both need a structure's PDB file by id rather than by run."""
    possible_names = [f"{pdb_id}.pdb", f"{pdb_id.lower()}.pdb", f"{pdb_id.upper()}.pdb"]

    raw_dir = project_root / "data" / "raw"
    if session_id:
        raw_dir = raw_dir / session_id
    for name in possible_names:
        p = raw_dir / name
        if p.exists():
            return p

    if run_id:
        res_dir = project_root / "results"
        if session_id:
            res_dir = res_dir / session_id
        res_dir = res_dir / run_id
        for name in possible_names:
            p = res_dir / name
            if p.exists():
                return p

    return None


@app.get(
    "/api/interactions",
    responses={
        400: {"description": "Invalid pdb_id, ligand_id, run_id, or session_id"},
        404: {"description": "Structure PDB not found in the active workspace"},
    },
)
def get_interactions(
    pdb_id: Annotated[str, Query(...)],
    ligand_id: Annotated[str, Query(...)],
    run_id: Annotated[Optional[str], Query()] = None,
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Perform binding site analysis and return interaction details.
    """
    _safe_segment(pdb_id, "pdb_id")
    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    pdb_path = _find_structure_pdb_path(pdb_id, run_id, session_id)
    if not pdb_path:
        raise HTTPException(
            status_code=404,
            detail=f"Structure PDB for {pdb_id} not found in active workspace.",
        )

    interactions = ligand_analyzer.calculate_interactions(pdb_path, ligand_id)
    _add_aligned_resi(interactions, pdb_id, pdb_path, run_id)

    return {
        "pdb_id": pdb_id,
        "ligand_id": ligand_id,
        "interactions": sanitize_for_json(interactions),
    }


def _add_aligned_resi(
    interactions: Any, pdb_id: str, pdb_path: Path, run_id: Optional[str]
) -> None:
    """Mutates `interactions["interactions"]` in place, adding an
    "aligned_resi" to each contact - the residue number Mustang's
    aligned/cleaned structure uses, so the frontend 3D viewer (which only
    ever loads the aligned structure) can highlight the right residue
    instead of a nonexistent one. Only possible when we know which run
    (and therefore which chain + cleaning params) produced the alignment."""
    if not (
        run_id and isinstance(interactions, dict) and interactions.get("interactions")
    ):
        return

    run = history_db.get_run(run_id)
    if not run:
        return

    metadata = run.get("metadata") or {}
    clean_params = metadata.get("clean_params") or {}
    selected_chain = (metadata.get("chain_selection") or {}).get(pdb_id)
    try:
        pdb_manager = PDBManager(config)
        renumber_map = pdb_manager.build_residue_renumber_map(
            pdb_path,
            chain=selected_chain,
            remove_heteroatoms=clean_params.get("remove_heteroatoms", True),
            remove_water=clean_params.get("remove_water", True),
        )
        for item in interactions["interactions"]:
            item["aligned_resi"] = renumber_map.get(item["resi"])
    except Exception as e:
        logger.warning(f"Failed to build residue renumber map: {e}")


@app.get(
    "/api/interface",
    responses={
        400: {"description": "Invalid pdb_id, chain_a, chain_b, run_id, or session_id"},
        404: {"description": "Structure PDB not found in the active workspace"},
    },
)
def get_interface(
    pdb_id: Annotated[str, Query(...)],
    chain_a: Annotated[str, Query(...)],
    chain_b: Annotated[str, Query(...)],
    run_id: Annotated[Optional[str], Query()] = None,
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Find contact residues between two chains of the same raw structure
    (e.g. a protein-protein complex's interface) and estimate the buried
    interface area.
    """
    _safe_segment(pdb_id, "pdb_id")
    _safe_segment(chain_a, "chain_a")
    _safe_segment(chain_b, "chain_b")
    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    pdb_path = _find_structure_pdb_path(pdb_id, run_id, session_id)
    if not pdb_path:
        raise HTTPException(
            status_code=404,
            detail=f"Structure PDB for {pdb_id} not found in active workspace.",
        )

    interface = interface_analyzer.calculate_interface(pdb_path, chain_a, chain_b)
    return {"pdb_id": pdb_id, "interface": sanitize_for_json(interface)}


@app.get("/api/memory")
def get_memory_stats():
    """
    Get backend process memory footprint (RSS) in MB.
    """
    try:
        import psutil
        import os

        process = psutil.Process(os.getpid())
        mem_rss_mb = process.memory_info().rss / (1024 * 1024)
        return {"ram_mb": round(mem_rss_mb, 2), "status": "ok"}
    except Exception as e:
        return {"ram_mb": 150.0, "status": "error", "message": str(e)}


@app.post("/api/memory/clear")
def clear_memory():
    """
    Trigger garbage collection to release unused memory.
    """
    import gc

    gc.collect()
    try:
        import psutil
        import os

        process = psutil.Process(os.getpid())
        mem_rss_mb = process.memory_info().rss / (1024 * 1024)
        return {"ram_mb": round(mem_rss_mb, 2), "status": "cleared"}
    except Exception as e:
        return {"ram_mb": 120.0, "status": "cleared", "message": str(e)}


def _lighten_run_for_list(run: Dict[str, Any]) -> Dict[str, Any]:
    """
    The History tab and Dashboard's recent-activity list only ever render a
    run's id/name/timestamp/pdb_ids/status and metadata's run_type - never
    the full per-run results blob (Plotly heatmap/tree figures, RMSD
    matrices, Discover hit/annotation payloads) that reloadPastRun() only
    needs once a user actually clicks into a specific run. Dropping that
    blob here is what keeps a page of runs from ballooning into tens of MB;
    the frontend re-fetches the full record via GET /api/runs/{id} on
    click (see main.js's reloadPastRun).
    """
    metadata = run.get("metadata") or {}
    lightened = dict(run)
    lightened["metadata"] = {k: v for k, v in metadata.items() if k != "results"}
    return lightened


@app.get("/api/history")
def get_history(
    session_id: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    Fetch a page of runs recorded in the history SQLite database, newest
    first. Each run's heavy metadata.results blob is stripped - see
    _lighten_run_for_list() - fetch a single run's full record via
    GET /api/runs/{run_id} when the full payload is actually needed.
    """
    try:
        runs = history_db.get_all_runs(
            limit=limit, offset=offset, session_id=session_id
        )
        total = history_db.count_runs(session_id=session_id)
    except Exception:
        runs = history_db.get_all_runs(limit=limit, offset=offset)
        total = history_db.count_runs()

    return {
        "runs": sanitize_for_json([_lighten_run_for_list(r) for r in runs]),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.delete(
    "/api/history/{run_id}",
    responses={
        400: {"description": "Invalid run_id"},
        403: {"description": "Run belongs to a different session"},
        404: {"description": "Run not found in the history database"},
    },
)
def delete_history_run(
    run_id: str, session_id: Annotated[Optional[str], Query()] = None
):
    """
    Delete a single run's history record. Unlike every read endpoint keyed
    on run_id (get_run_by_id, get_pdf_report, etc.), which deliberately
    have no ownership check to support shareable run links, deletion is
    scoped to the run's own session: anyone with a shared-run link could
    otherwise delete a run they don't own. A run with no session_id at all
    (a legacy/anonymous run predating session scoping) can still be
    deleted by anyone, matching its already-unscoped read access.
    """
    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found in history database."
        )
    if run.get("session_id") and run["session_id"] != session_id:
        raise HTTPException(
            status_code=403, detail="This run belongs to a different session."
        )

    history_db.delete_run(run_id)
    return {"deleted": run_id}


@app.delete("/api/history")
def clear_history(session_id: Annotated[Optional[str], Query()] = None):
    """
    Clear run history. When session_id is given, scopes the wipe to that
    session only (`clear_runs_for_session`) - the safe choice for a
    multi-tenant deployment that actually tracks sessions per caller.
    The bundled SPA doesn't send session_id anywhere today (no client-side
    session tracking exists yet - a separate, larger feature of its own),
    so omitting it falls back to `clear_all_runs()`, a global wipe -
    matching the single-user Streamlit app this is ported from, and
    matching every run created by the SPA today having no session_id set
    in the first place.
    """
    if session_id:
        _safe_segment(session_id, "session_id")
        history_db.clear_runs_for_session(session_id)
        return {"cleared": session_id}

    history_db.clear_all_runs()
    return {"cleared": "all"}


@app.get(
    "/api/runs/{run_id}",
    responses={
        400: {"description": "Invalid run_id"},
        404: {"description": "Run not found in the history database"},
    },
)
def get_run_by_id(run_id: str):
    """
    Fetch a single run's raw history record by ID, regardless of which
    session created it - this is what backs shareable run links. Every
    read endpoint keyed on run_id already has no ownership check (see
    get_pdf_report, get_sequence, etc.), so this doesn't loosen access;
    it just gives the frontend a way to look up one run directly instead
    of scanning the unscoped /api/history list for it.
    """
    _safe_segment(run_id, "run_id")

    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found in history database."
        )
    return sanitize_for_json(run)


@app.get("/api/stats", responses={400: {"description": "Invalid session_id"}})
def get_aggregate_stats(session_id: Annotated[Optional[str], Query()] = None):
    """
    Dashboard-level aggregate totals across all runs (total run count,
    total proteins analyzed, cache size).
    """
    _safe_segment(session_id, "session_id")
    return sanitize_for_json(history_db.get_aggregate_stats(session_id=session_id))


@app.get(
    "/api/sequence",
    responses={
        400: {"description": "Invalid run_id or session_id"},
        404: {"description": "Alignment FASTA not found for this run"},
        500: {"description": "Failed to parse the alignment FASTA file"},
    },
)
def get_sequence(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
    motif: Annotated[
        Optional[str],
        Query(
            description="Optional sequence motif query (e.g. 'RYY', 'G.G', 'G-X-P' - 'X'/'.'/'-' act as single-residue wildcards). When given, the response also includes motif_matches (per-structure matched alignment columns) and highlight_chains (a ready-to-use {chain_id: [residue_numbers]} map for the 3D viewer)."
        ),
    ] = None,
):
    """
    Parse the alignment FASTA for a run and return sequences,
    conservation scores, and identity percentage.
    """
    from src.backend.sequence_viewer import (
        SequenceViewer,
        find_motif_matches,
        _build_chain_mapping_from_matches,
    )

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")
    res_dir = project_root / "results"
    if session_id:
        res_dir = res_dir / session_id
    res_dir = res_dir / run_id

    fasta_path = res_dir / "alignment.fasta"
    if not fasta_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Alignment FASTA not found for run {run_id}"
        )

    viewer = SequenceViewer()
    sequences = viewer.parse_afasta(fasta_path)
    if not sequences:
        raise HTTPException(
            status_code=500, detail="Failed to parse alignment FASTA file"
        )

    conservation = viewer.calculate_conservation(sequences)
    identity = viewer.calculate_identity(sequences)

    response = {
        "run_id": run_id,
        "sequences": sequences,
        "conservation": conservation,
        "identity": round(identity, 2),
    }

    if motif:
        matches = find_motif_matches(sequences, motif)
        response["motif_matches"] = matches
        response["highlight_chains"] = _build_chain_mapping_from_matches(
            sequences, matches
        )

    return sanitize_for_json(response)


@app.get(
    "/api/report",
    responses={
        400: {"description": "Invalid run_id or session_id"},
        404: {"description": "Run not found in the history database"},
        500: {"description": "Report generation failed"},
    },
)
def get_pdf_report(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
    sections: Annotated[
        Optional[str],
        Query(
            description="Comma-separated report sections to include (summary,insights,heatmap,tree,matrix). Omit for the full default report."
        ),
    ] = None,
):
    """
    Generate and retrieve the PDF analysis report for a run.
    """
    from src.backend.report_generator import ReportGenerator
    from fastapi.responses import FileResponse

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    section_list = None
    if sections:
        section_list = [s.strip() for s in sections.split(",") if s.strip()]

    # 1. Fetch run details
    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found in history database."
        )

    res_dir = project_root / "results"
    if session_id:
        res_dir = res_dir / session_id
    res_dir = res_dir / run_id

    # 2. Extract or reconstruct results dict
    metadata = run.get("metadata", {})
    results = metadata.get("results")

    if not results:
        # Reconstruct minimal results dict from stats if present in metadata
        stats = metadata.get("stats", {})
        results = {"stats": stats, "id": run_id, "pdb_ids": run.get("pdb_ids", [])}

    # metadata["results"] has been through sanitize_for_json (Path -> str,
    # DataFrame -> {index, columns, data} dict). ReportGenerator's
    # heatmap/tree/matrix sections need the original types back.
    results = dict(results)
    if isinstance(results.get("heatmap_path"), str):
        results["heatmap_path"] = Path(results["heatmap_path"])
    if isinstance(results.get("tree_path"), str):
        results["tree_path"] = Path(results["tree_path"])
    if isinstance(results.get("rmsd_df"), dict):
        rmsd_dict = results["rmsd_df"]
        results["rmsd_df"] = pd.DataFrame(
            data=rmsd_dict.get("data"),
            index=rmsd_dict.get("index"),
            columns=rmsd_dict.get("columns"),
        )

    # 3. Generate report
    try:
        generator = ReportGenerator(res_dir)
        # Reuse an existing generated report only for the default (all
        # sections) request — a cached full report must not be served back
        # for a caller that explicitly asked for a subset of sections.
        existing_pdfs = (
            list(res_dir.glob("mustang_report_*.pdf")) if not section_list else []
        )
        if existing_pdfs:
            report_path = existing_pdfs[0]
        else:
            report_path = generator.generate_full_report(
                results, pdb_ids=run.get("pdb_ids", []), sections=section_list
            )

        if not report_path.exists():
            raise HTTPException(
                status_code=500, detail="Report file was not created successfully."
            )

        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename=f"mustang_report_{run_id}.pdf",
        )
    except Exception as e:
        import logging

        logger = logging.getLogger("uvicorn")
        logger.exception("Failed to generate report PDF")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report PDF: {str(e)}"
        )


@app.get(
    "/api/notebook",
    responses={
        400: {"description": "Invalid run_id or session_id"},
        404: {"description": "Run not found in the history database"},
        500: {"description": "Lab notebook generation failed"},
    },
)
def get_lab_notebook(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Generate and retrieve the standalone HTML lab notebook for a run.
    """
    from src.backend.notebook_exporter import NotebookExporter
    from fastapi.responses import FileResponse

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found in history database."
        )

    res_dir = project_root / "results"
    if session_id:
        res_dir = res_dir / session_id
    res_dir = res_dir / run_id

    metadata = run.get("metadata", {})
    results = metadata.get("results") or {
        "stats": metadata.get("stats", {}),
        "id": run_id,
        "pdb_ids": run.get("pdb_ids", []),
    }
    # metadata["results"] has been through sanitize_for_json (Path -> str),
    # but NotebookExporter needs real Path objects for these two fields -
    # reconstruct them from the run_id rather than trust stringified values.
    results = dict(results)
    results["result_dir"] = res_dir
    results["alignment_pdb"] = res_dir / "alignment.pdb"

    try:
        exporter = NotebookExporter()
        notebook_path = exporter.export(results, insights=results.get("insights"))

        if not notebook_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Lab notebook file was not created successfully.",
            )

        return FileResponse(
            path=str(notebook_path),
            media_type="text/html",
            filename=f"lab_notebook_{run_id}.html",
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging

        logger = logging.getLogger("uvicorn")
        logger.exception("Failed to generate lab notebook")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate lab notebook: {str(e)}"
        )


def _lookup_run_and_result_dir(
    run_id: str, session_id: Optional[str]
) -> Tuple[Dict[str, Any], Path]:
    """Shared lookup for the raw-export endpoints below (CSV/PNG/ZIP): finds
    the run, 404s if missing, and resolves its results/<run_id> directory -
    the same two steps get_pdf_report/get_lab_notebook each inline
    separately; factored out here since a third+ caller would otherwise
    triplicate it."""
    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found in history database."
        )
    res_dir = project_root / "results"
    if session_id:
        res_dir = res_dir / session_id
    res_dir = res_dir / run_id
    return run, res_dir


def _reconstruct_rmsd_df(run: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """metadata.results.rmsd_df has been through sanitize_for_json
    ({index, columns, data} dict) - rebuild the real DataFrame, matching
    get_pdf_report's own reconstruction of the same field."""
    results = run.get("metadata", {}).get("results") or {}
    rmsd_dict = results.get("rmsd_df")
    if not isinstance(rmsd_dict, dict):
        return None
    return pd.DataFrame(
        data=rmsd_dict.get("data"),
        index=rmsd_dict.get("index"),
        columns=rmsd_dict.get("columns"),
    )


@app.get(
    "/api/report/rmsd-csv",
    responses={
        400: {"description": "Invalid run_id or session_id"},
        404: {"description": "Run not found, or has no stored RMSD matrix"},
    },
)
def get_rmsd_csv(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """Download the run's pairwise RMSD matrix as a raw CSV file."""
    from fastapi.responses import PlainTextResponse

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    run, _ = _lookup_run_and_result_dir(run_id, session_id)
    rmsd_df = _reconstruct_rmsd_df(run)
    if rmsd_df is None:
        raise HTTPException(
            status_code=404, detail=f"No stored RMSD matrix for run {run_id}."
        )

    return PlainTextResponse(
        content=rmsd_df.to_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="rmsd_matrix_{run_id}.csv"'
        },
    )


@app.get(
    "/api/report/heatmap-png",
    responses={
        400: {"description": "Invalid run_id or session_id"},
        404: {"description": "Run not found, or its heatmap image is missing on disk"},
    },
)
def get_heatmap_png(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """Download the run's RMSD heatmap as a raw PNG file - already saved
    to disk during the pipeline run (process_result_directory), just
    never exposed via a direct download route until now."""
    from fastapi.responses import FileResponse

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    _, res_dir = _lookup_run_and_result_dir(run_id, session_id)
    heatmap_path = res_dir / "rmsd_heatmap.png"
    if not heatmap_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No heatmap image found for run {run_id}."
        )

    return FileResponse(
        path=str(heatmap_path),
        media_type="image/png",
        filename=f"rmsd_heatmap_{run_id}.png",
    )


@app.get(
    "/api/report/newick",
    responses={
        400: {"description": "Invalid run_id or session_id"},
        404: {
            "description": "Run not found, or its phylogenetic tree is missing on disk"
        },
    },
)
def get_newick_tree(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """Download the run's phylogenetic tree in Newick format - already
    saved to disk during the pipeline run (process_result_directory), just
    never exposed via a direct download route until now."""
    from fastapi.responses import FileResponse

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    _, res_dir = _lookup_run_and_result_dir(run_id, session_id)
    newick_path = res_dir / "tree.newick"
    if not newick_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No phylogenetic tree found for run {run_id}."
        )

    return FileResponse(
        path=str(newick_path),
        media_type="text/plain",
        filename=f"tree_{run_id}.newick",
    )


@app.get(
    "/api/report/zip",
    responses={400: {"description": "Invalid run_id or session_id"}},
)
def get_report_zip(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """Bundle every generated artifact for a run into one ZIP: alignment
    PDB/FASTA, the RMSD matrix CSV, the heatmap PNG, and an auto-generated
    lab notebook HTML - each included on a best-effort basis (a run
    missing one piece, e.g. no heatmap for a single-structure run, still
    gets a ZIP with everything else rather than a 404 for the whole
    bundle)."""
    import io
    import zipfile

    from fastapi.responses import StreamingResponse
    from src.backend.notebook_exporter import NotebookExporter

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    run, res_dir = _lookup_run_and_result_dir(run_id, session_id)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        alignment_pdb = res_dir / "alignment.pdb"
        if alignment_pdb.exists():
            zip_file.write(alignment_pdb, arcname=f"alignment_{run_id}.pdb")

        alignment_afasta = res_dir / "alignment.afasta"
        if alignment_afasta.exists():
            zip_file.write(alignment_afasta, arcname=f"alignment_{run_id}.afasta")

        rmsd_df = _reconstruct_rmsd_df(run)
        if rmsd_df is not None:
            zip_file.writestr(f"rmsd_matrix_{run_id}.csv", rmsd_df.to_csv())

        heatmap_path = res_dir / "rmsd_heatmap.png"
        if heatmap_path.exists():
            zip_file.write(heatmap_path, arcname=f"rmsd_heatmap_{run_id}.png")

        try:
            metadata = run.get("metadata", {})
            results = metadata.get("results") or {
                "stats": metadata.get("stats", {}),
                "id": run_id,
                "pdb_ids": run.get("pdb_ids", []),
            }
            results = dict(results)
            results["result_dir"] = res_dir
            results["alignment_pdb"] = alignment_pdb
            notebook_path = NotebookExporter().export(results)
            if notebook_path and notebook_path.exists():
                zip_file.write(notebook_path, arcname=f"lab_notebook_{run_id}.html")
        except Exception as e:
            logger.warning(
                f"Skipping lab notebook in ZIP for {sanitize_for_log(run_id)}: {e}"
            )

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="structscope_{run_id}.zip"'
        },
    )


@app.get(
    "/api/report/citations",
    responses={
        400: {"description": "Invalid run_id or session_id"},
        404: {"description": "Run not found in the history database"},
        500: {"description": "Citation export failed"},
    },
)
def get_compare_citations(
    run_id: Annotated[str, Query(...)],
    session_id: Annotated[Optional[str], Query()] = None,
):
    """
    Generate and retrieve the Methods & Citations export (plain text +
    BibTeX) for a Compare run.
    """
    from src.backend.citation_exporter import (
        CitationExporter,
        citations_for_compare_run,
    )
    from fastapi.responses import FileResponse

    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")

    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found in history database."
        )

    pdb_ids = run.get("pdb_ids", [])
    version = config.get("app", {}).get("version", "0.0.0")

    try:
        citation_ids = citations_for_compare_run(pdb_ids)
        exporter = CitationExporter()
        citations_path = exporter.export(citation_ids, run_id, version=version)
        return FileResponse(
            path=str(citations_path),
            media_type="text/plain",
            filename=f"citations_{run_id}.txt",
        )
    except Exception as e:
        logger.exception("Failed to generate citations export")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate citations export: {str(e)}"
        )


def _get_discover_run_results(run_id: str) -> Dict[str, Any]:
    """Shared lookup for the two Discover export endpoints below: finds the
    saved run, confirms it's actually a Discover run (not a Compare run -
    the two have unrelated result shapes), and returns its results dict."""
    _safe_segment(run_id, "run_id")
    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found in history database."
        )
    metadata = run.get("metadata", {})
    if metadata.get("run_type") != "discover":
        raise HTTPException(
            status_code=400,
            detail=f"Run {run_id} is not a Discover run (use /api/report for Compare runs).",
        )
    results = metadata.get("results")
    if not results:
        raise HTTPException(
            status_code=404, detail=f"No stored results for Discover run {run_id}."
        )
    return results


@app.get(
    "/api/discover/report",
    responses={
        400: {"description": "Invalid run_id, or the run isn't a Discover run"},
        404: {"description": "Run not found, or has no stored Discover results"},
        500: {"description": "Discovery report generation failed"},
    },
)
def get_discovery_report(run_id: Annotated[str, Query(...)]):
    """
    Generate and retrieve a standalone HTML report for a Discover run -
    the export/report parity Compare mode has always had.
    """
    from src.backend.discovery_report_exporter import DiscoveryReportExporter
    from fastapi.responses import FileResponse

    results = _get_discover_run_results(run_id)

    try:
        exporter = DiscoveryReportExporter()
        report_path = exporter.export(results)
        if not report_path.exists():
            raise HTTPException(
                status_code=500, detail="Discovery report file was not created."
            )
        return FileResponse(
            path=str(report_path),
            media_type="text/html",
            filename=f"discover_report_{run_id}.html",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate discovery report")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate discovery report: {str(e)}"
        )


@app.get(
    "/api/discover/export",
    responses={
        400: {"description": "Invalid run_id, or the run isn't a Discover run"},
        404: {"description": "Run not found, or has no stored Discover results"},
    },
)
def export_discovery_json(run_id: Annotated[str, Query(...)]):
    """Downloads the raw JSON result for a Discover run - for programmatic
    reuse, unlike the human-readable HTML report above."""
    from fastapi.responses import JSONResponse

    results = _get_discover_run_results(run_id)
    return JSONResponse(
        content=results,
        headers={
            "Content-Disposition": f'attachment; filename="discover_{run_id}.json"'
        },
    )


@app.get(
    "/api/discover/citations",
    responses={
        400: {"description": "Invalid run_id, or the run isn't a Discover run"},
        404: {"description": "Run not found, or has no stored Discover results"},
        500: {"description": "Citation export failed"},
    },
)
def get_discover_citations(run_id: Annotated[str, Query(...)]):
    """
    Generate and retrieve the Methods & Citations export (plain text +
    BibTeX) for a Discover run.
    """
    from src.backend.citation_exporter import (
        CitationExporter,
        citations_for_discover_run,
    )
    from fastapi.responses import FileResponse

    results = _get_discover_run_results(run_id)
    version = config.get("app", {}).get("version", "0.0.0")

    try:
        citation_ids = citations_for_discover_run(results)
        exporter = CitationExporter()
        citations_path = exporter.export(citation_ids, run_id, version=version)
        return FileResponse(
            path=str(citations_path),
            media_type="text/plain",
            filename=f"discover_citations_{run_id}.txt",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate discovery citations export")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate citations export: {str(e)}"
        )


# Mount static site for frontend SPA
static_frontend_dir = project_root / "static"
static_frontend_dir.mkdir(exist_ok=True)
app.mount(
    "/", StaticFiles(directory=str(static_frontend_dir), html=True), name="frontend"
)
