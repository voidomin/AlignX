import os
import sys
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional

import matplotlib

matplotlib.use("Agg")

import json
import re
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

# Ensure working directory is set to project root if run from subdirectories
project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.utils.config_loader import load_config
from src.utils.logger import get_logger
from src.backend.coordinator import AnalysisCoordinator
from src.backend.discovery_coordinator import DiscoveryCoordinator
from src.backend.foldseek_client import FoldseekClient, FoldseekError
from src.backend.database import HistoryDatabase
from src.backend.ligand_analyzer import LigandAnalyzer
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
        "app": {"name": "AlignX API", "max_proteins": 10},
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
app = FastAPI(
    title="AlignX Web API",
    description="REST API Backend for AlignX Protein Multiple Structural Alignment",
    version="1.0.0",
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


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if _ALIGNX_API_KEY and request.url.path.startswith("/api/"):
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
# rate limit across every AlignX user (see FoldseekClient's rate limiter).
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


@app.get("/api/suggest")
def get_rcsb_suggestions(q: str = Query(..., min_length=1)):
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


@app.post("/api/chains")
async def analyze_chains(
    pdb_ids: List[str] = Body(..., embed=True), session_id: Optional[str] = Query(None)
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
            info = await asyncio.to_thread(coordinator.pdb_manager.analyze_structure, path)
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


def sanitize_for_json(val: Any) -> Any:
    """
    Recursively convert NumPy types and other non-standard types to JSON-friendly standard Python types,
    replacing NaN and Infinity with None.
    """
    import numpy as np
    import math

    # Convert numpy scalars to Python scalars
    if (
        hasattr(val, "dtype")
        and hasattr(val, "item")
        and (not hasattr(val, "ndim") or val.ndim == 0)
    ):
        try:
            val = val.item()
        except Exception:
            pass

    if (
        isinstance(val, dict)
        and val.keys() >= {"dtype", "bdata"}
        and isinstance(val.get("bdata"), str)
    ):
        # Plotly 6.x's compact binary typed-array format for numeric trace data
        # (emitted for figure_factory dendrograms and some Heatmap traces,
        # regardless of whether the original value was a numpy array or a
        # plain list — Plotly's trace validators re-coerce it internally).
        # "shape" is only present for 2D+ arrays (e.g. a heatmap's z); flat 1D
        # arrays (e.g. a dendrogram trace's x/y) omit it entirely. The pinned
        # frontend Plotly.js CDN version can't decode either form, so decode
        # it back into a plain (possibly nested) list here.
        try:
            import base64

            raw = base64.b64decode(val["bdata"])
            arr = np.frombuffer(raw, dtype=val["dtype"])
            if "shape" in val:
                shape = tuple(int(s) for s in str(val["shape"]).replace(" ", "").split(","))
                arr = arr.reshape(shape)
            return sanitize_for_json(arr)
        except Exception:
            return {str(k): sanitize_for_json(v) for k, v in val.items()}

    if isinstance(val, dict):
        return {str(k): sanitize_for_json(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [sanitize_for_json(item) for item in val]
    elif isinstance(val, (int, np.integer)) or "int" in type(val).__name__.lower():
        return int(val)
    elif isinstance(val, (float, np.floating)) or "float" in type(val).__name__.lower():
        try:
            fval = float(val)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
        except Exception:
            return None
    elif isinstance(val, np.ndarray):
        return sanitize_for_json(val.tolist())
    elif hasattr(val, "to_plotly_json"):
        return sanitize_for_json(val.to_plotly_json())
    elif hasattr(val, "to_dict"):
        try:
            if type(val).__name__ == "DataFrame":
                return sanitize_for_json(val.to_dict(orient="split"))
            return sanitize_for_json(val.to_dict())
        except Exception:
            return str(val)
    elif isinstance(val, Path):
        return str(val)
    return val


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


@app.post("/api/jobs/align", status_code=202)
async def submit_alignment_job(
    pdb_ids: List[str] = Body(..., embed=True),
    chain_selection: Dict[str, str] = Body(default={}, embed=True),
    remove_water: bool = Body(default=True, embed=True),
    remove_heteroatoms: bool = Body(default=True, embed=True),
    session_id: Optional[str] = Query(None),
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

    asyncio.create_task(
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


@app.get("/api/jobs/{job_id}")
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


@app.post("/api/jobs/discover", status_code=202)
async def submit_discovery_job(
    pdb_id: str = Body(..., embed=True),
    databases: Optional[List[str]] = Body(default=None, embed=True),
    session_id: Optional[str] = Query(None),
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

    asyncio.create_task(
        _execute_discovery_job(
            job_id,
            pdb_id=pdb_id,
            databases=databases,
            session_id=session_id,
        )
    )

    return {"job_id": job_id, "status": "queued"}


@app.post("/api/clusters")
def get_clusters(
    rmsd_df: Dict[str, Any] = Body(..., embed=True),
    threshold: float = Body(default=3.0, embed=True),
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


@app.get("/api/comparison/runs")
def list_comparison_runs(
    exclude_run_id: Optional[str] = Query(None), session_id: Optional[str] = Query(None)
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


@app.get("/api/comparison")
def compare_runs(
    current_run_id: str = Query(...),
    target_run_id: str = Query(...),
    session_id: Optional[str] = Query(None),
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


@app.get("/api/ligands")
def get_ligands(
    pdb_id: str = Query(...),
    run_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """
    Retrieve ligands present in the specified structure.
    """
    _safe_segment(pdb_id, "pdb_id")
    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")
    raw_dir = project_root / "data" / "raw"
    if session_id:
        raw_dir = raw_dir / session_id

    pdb_path = None
    possible_names = [f"{pdb_id}.pdb", f"{pdb_id.lower()}.pdb", f"{pdb_id.upper()}.pdb"]

    for name in possible_names:
        p = raw_dir / name
        if p.exists():
            pdb_path = p
            break

    # Fallback to run results folder
    if not pdb_path and run_id:
        res_dir = project_root / "results"
        if session_id:
            res_dir = res_dir / session_id
        res_dir = res_dir / run_id
        for name in possible_names:
            p = res_dir / name
            if p.exists():
                pdb_path = p
                break

    if not pdb_path:
        raise HTTPException(
            status_code=404,
            detail=f"Structure PDB for {pdb_id} not found in active workspace.",
        )

    ligands = ligand_analyzer.get_ligands(pdb_path)
    return {"pdb_id": pdb_id, "ligands": sanitize_for_json(ligands)}


@app.get("/api/interactions")
def get_interactions(
    pdb_id: str = Query(...),
    ligand_id: str = Query(...),
    run_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """
    Perform binding site analysis and return interaction details.
    """
    _safe_segment(pdb_id, "pdb_id")
    _safe_segment(run_id, "run_id")
    _safe_segment(session_id, "session_id")
    raw_dir = project_root / "data" / "raw"
    if session_id:
        raw_dir = raw_dir / session_id

    pdb_path = None
    possible_names = [f"{pdb_id}.pdb", f"{pdb_id.lower()}.pdb", f"{pdb_id.upper()}.pdb"]

    for name in possible_names:
        p = raw_dir / name
        if p.exists():
            pdb_path = p
            break

    # Fallback to run results folder
    if not pdb_path and run_id:
        res_dir = project_root / "results"
        if session_id:
            res_dir = res_dir / session_id
        res_dir = res_dir / run_id
        for name in possible_names:
            p = res_dir / name
            if p.exists():
                pdb_path = p
                break

    if not pdb_path:
        raise HTTPException(
            status_code=404,
            detail=f"Structure PDB for {pdb_id} not found in active workspace.",
        )

    interactions = ligand_analyzer.calculate_interactions(pdb_path, ligand_id)

    # Translate each contact's raw residue number into the number Mustang's
    # aligned/cleaned structure uses, so the frontend 3D viewer (which only
    # ever loads the aligned structure) can highlight the right residue
    # instead of a nonexistent one. Only possible when we know which run
    # (and therefore which chain + cleaning params) produced the alignment.
    if run_id and isinstance(interactions, dict) and interactions.get("interactions"):
        run = history_db.get_run(run_id)
        if run:
            metadata = run.get("metadata") or {}
            chain_selection = metadata.get("chain_selection") or {}
            clean_params = metadata.get("clean_params") or {}
            selected_chain = chain_selection.get(pdb_id)
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

    return {
        "pdb_id": pdb_id,
        "ligand_id": ligand_id,
        "interactions": sanitize_for_json(interactions),
    }


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


@app.get("/api/history")
def get_history(
    session_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Fetch a page of runs recorded in the history SQLite database, newest first.
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
        "runs": sanitize_for_json(runs),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/stats")
def get_aggregate_stats(session_id: Optional[str] = Query(None)):
    """
    Dashboard-level aggregate totals across all runs (total run count,
    total proteins analyzed, cache size).
    """
    _safe_segment(session_id, "session_id")
    return sanitize_for_json(history_db.get_aggregate_stats(session_id=session_id))


@app.get("/api/sequence")
def get_sequence(run_id: str = Query(...), session_id: Optional[str] = Query(None)):
    """
    Parse the alignment FASTA for a run and return sequences,
    conservation scores, and identity percentage.
    """
    from src.backend.sequence_viewer import SequenceViewer

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

    return sanitize_for_json(
        {
            "run_id": run_id,
            "sequences": sequences,
            "conservation": conservation,
            "identity": round(identity, 2),
        }
    )


@app.get("/api/report")
def get_pdf_report(
    run_id: str = Query(...),
    session_id: Optional[str] = Query(None),
    sections: Optional[str] = Query(
        None,
        description="Comma-separated report sections to include (summary,insights,heatmap,tree,matrix). Omit for the full default report.",
    ),
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
        existing_pdfs = list(res_dir.glob("mustang_report_*.pdf")) if not section_list else []
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
        logger.error(f"Failed to generate report PDF: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report PDF: {str(e)}"
        )


@app.get("/api/notebook")
def get_lab_notebook(run_id: str = Query(...), session_id: Optional[str] = Query(None)):
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
                status_code=500, detail="Lab notebook file was not created successfully."
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
        logger.error(f"Failed to generate lab notebook: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate lab notebook: {str(e)}"
        )


# Mount static site for frontend SPA
static_frontend_dir = project_root / "static"
static_frontend_dir.mkdir(exist_ok=True)
app.mount(
    "/", StaticFiles(directory=str(static_frontend_dir), html=True), name="frontend"
)
