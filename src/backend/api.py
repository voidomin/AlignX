import os
import sys
import uuid
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use('Agg')

import json
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
from src.backend.coordinator import AnalysisCoordinator
from src.backend.pdb_manager import PDBManager
from src.backend.database import HistoryDatabase
from src.backend.ligand_analyzer import LigandAnalyzer
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.result_manager import ResultManager

# Load application configuration
try:
    config = load_config(str(project_root / "config.yaml"))
except Exception as e:
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

# Initialize FastAPI App
app = FastAPI(
    title="AlignX Web API",
    description="REST API Backend for AlignX Protein Multiple Structural Alignment",
    version="1.0.0",
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
        provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if provided != _ALIGNX_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API key."},
            )
    return await call_next(request)

# Mount static directories for results and raw PDBs
results_dir = project_root / "results"
raw_dir = project_root / "data" / "raw"
results_dir.mkdir(parents=True, exist_ok=True)
raw_dir.mkdir(parents=True, exist_ok=True)

app.mount("/results", StaticFiles(directory=str(results_dir)), name="results")
app.mount("/raw", StaticFiles(directory=str(raw_dir)), name="raw")

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

    query_struct = {
        "type": "basic",
        "suggest": {
            "text": q,
            "size": 6
        }
    }
    try:
        quoted_query = urllib.parse.quote(json.dumps(query_struct))
        url = f"https://search.rcsb.org/rcsbsearch/v2/suggest?json={quoted_query}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as res:
            data = json.loads(res.read().decode())
            suggestions = data.get("suggestions", {})
            pdb_entries = suggestions.get("rcsb_entry_container_identifiers.entry_id", [])
            
            results = []
            for entry in pdb_entries:
                raw_text = entry.get("text", "")
                clean_text = re.sub(r'<[^>]+>', '', raw_text).upper()
                if clean_text and len(clean_text) == 4 and clean_text not in results:
                    results.append(clean_text)
            return {"query": q, "suggestions": results}
    except Exception as e:
        return {"query": q, "suggestions": [], "error": str(e)}


@app.post("/api/chains")
async def analyze_chains(
    pdb_ids: List[str] = Body(..., embed=True),
    session_id: Optional[str] = Query(None)
):
    """
    Download PDB files and analyze their structural chains.
    """
    if not pdb_ids:
        raise HTTPException(status_code=400, detail="pdb_ids list cannot be empty")
        
    coordinator = AnalysisCoordinator(config, session_id=session_id)
    download_results = await coordinator.pdb_manager.batch_download(pdb_ids)
    
    failed = [
        pid for pid, (success, msg, path) in download_results.items() if not success
    ]
    if failed:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch PDBs: {', '.join(failed)}"
        )
        
    chain_info = {}
    for pid, (success, msg, path) in download_results.items():
        if path:
            info = coordinator.pdb_manager.analyze_structure(path)
            chain_info[pid] = info
            
    return {"chains": sanitize_for_json(chain_info)}


def sanitize_for_json(val: Any) -> Any:
    """
    Recursively convert NumPy types and other non-standard types to JSON-friendly standard Python types,
    replacing NaN and Infinity with None.
    """
    import numpy as np
    import math

    # Convert numpy scalars to Python scalars
    if hasattr(val, "dtype") and hasattr(val, "item") and (not hasattr(val, "ndim") or val.ndim == 0):
        try:
            val = val.item()
        except Exception:
            pass

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
alignment_jobs: Dict[str, Dict[str, Any]] = {}


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
    try:
        outcome = await asyncio.to_thread(_run_alignment_pipeline, **pipeline_kwargs)
        alignment_jobs[job_id] = {"status": "completed", **outcome}
    except Exception as e:
        alignment_jobs[job_id] = {"status": "failed", "error": str(e)}


@app.post("/api/jobs/align", status_code=202)
async def submit_alignment_job(
    pdb_ids: List[str] = Body(..., embed=True),
    chain_selection: Dict[str, str] = Body(default={}, embed=True),
    remove_water: bool = Body(default=True, embed=True),
    remove_heteroatoms: bool = Body(default=True, embed=True),
    session_id: Optional[str] = Query(None)
):
    """
    Submit a Mustang multiple structural alignment run as a background job.
    Returns immediately with a job_id; poll GET /api/jobs/{job_id} for status.
    """
    if not pdb_ids or len(pdb_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 PDB IDs are required for alignment."
        )

    job_id = uuid.uuid4().hex
    alignment_jobs[job_id] = {"status": "queued"}

    asyncio.create_task(_execute_alignment_job(
        job_id,
        pdb_ids=pdb_ids,
        chain_selection=chain_selection,
        remove_water=remove_water,
        remove_heteroatoms=remove_heteroatoms,
        session_id=session_id,
    ))

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_alignment_job(job_id: str):
    """
    Poll the status/result of a submitted alignment job.
    """
    job = alignment_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {"job_id": job_id, **job}


@app.post("/api/clusters")
def get_clusters(
    rmsd_df: Dict[str, Any] = Body(..., embed=True),
    threshold: float = Body(default=3.0, embed=True)
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
        raise HTTPException(status_code=400, detail="At least 2 structures are required for clustering.")

    clusters = rmsd_analyzer.identify_clusters(df, threshold=threshold)

    families = []
    for cid, members in clusters.items():
        avg_rmsd = 0.0
        if len(members) > 1:
            subset = df.loc[members, members]
            avg_rmsd = float(subset.values[np.triu_indices(len(members), k=1)].mean())
        families.append({
            "cluster_id": int(cid),
            "members": members,
            "avg_rmsd": round(avg_rmsd, 2),
        })

    return {"threshold": threshold, "clusters": sanitize_for_json(families)}


@app.get("/api/comparison/runs")
def list_comparison_runs(
    exclude_run_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """
    List past runs available as batch-comparison targets.
    """
    res_dir = results_dir / session_id if session_id else results_dir
    manager = ResultManager(res_dir)
    runs = manager.list_runs(session_id=session_id)

    runs = [r for r in runs if r["id"] != exclude_run_id]
    return {"runs": sanitize_for_json([
        {"id": r["id"], "timestamp": r["timestamp"], "proteins": r["proteins"]}
        for r in runs
    ])}


@app.get("/api/comparison")
def compare_runs(
    current_run_id: str = Query(...),
    target_run_id: str = Query(...),
    session_id: Optional[str] = Query(None)
):
    """
    Compute the RMSD difference matrix between two past runs.
    """
    res_dir = results_dir / session_id if session_id else results_dir
    manager = ResultManager(res_dir)

    diff_df = manager.calculate_difference(current_run_id, target_run_id)
    if diff_df is None:
        raise HTTPException(
            status_code=400,
            detail="No overlapping proteins found between these runs."
        )

    current_rmsd = manager.get_run_rmsd(current_run_id)
    target_rmsd = manager.get_run_rmsd(target_run_id)
    if current_rmsd is None or target_rmsd is None:
        raise HTTPException(
            status_code=404,
            detail="RMSD matrix not found for one or both runs."
        )

    current_mean = float(current_rmsd.values.mean())
    target_mean = float(target_rmsd.values.mean())

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
    session_id: Optional[str] = Query(None)
):
    """
    Retrieve ligands present in the specified structure.
    """
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
            detail=f"Structure PDB for {pdb_id} not found in active workspace."
        )
        
    ligands = ligand_analyzer.get_ligands(pdb_path)
    return {"pdb_id": pdb_id, "ligands": sanitize_for_json(ligands)}


@app.get("/api/interactions")
def get_interactions(
    pdb_id: str = Query(...),
    ligand_id: str = Query(...),
    run_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """
    Perform binding site analysis and return interaction details.
    """
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
            detail=f"Structure PDB for {pdb_id} not found in active workspace."
        )
        
    interactions = ligand_analyzer.calculate_interactions(pdb_path, ligand_id)
    return {"pdb_id": pdb_id, "ligand_id": ligand_id, "interactions": sanitize_for_json(interactions)}


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
        return {
            "ram_mb": round(mem_rss_mb, 2),
            "status": "ok"
        }
    except Exception as e:
        return {
            "ram_mb": 150.0,
            "status": "error",
            "message": str(e)
        }


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
        return {
            "ram_mb": round(mem_rss_mb, 2),
            "status": "cleared"
        }
    except Exception as e:
        return {
            "ram_mb": 120.0,
            "status": "cleared",
            "message": str(e)
        }


@app.get("/api/history")
def get_history(session_id: Optional[str] = Query(None)):
    """
    Fetch all runs recorded in the history SQLite database.
    """
    try:
        runs = history_db.get_all_runs(session_id=session_id)
    except Exception:
        runs = history_db.get_all_runs()
        
    return {"runs": sanitize_for_json(runs)}


@app.get("/api/sequence")
def get_sequence(
    run_id: str = Query(...),
    session_id: Optional[str] = Query(None)
):
    """
    Parse the alignment FASTA for a run and return sequences,
    conservation scores, and identity percentage.
    """
    from src.backend.sequence_viewer import SequenceViewer

    res_dir = project_root / "results"
    if session_id:
        res_dir = res_dir / session_id
    res_dir = res_dir / run_id

    fasta_path = res_dir / "alignment.fasta"
    if not fasta_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Alignment FASTA not found for run {run_id}"
        )

    viewer = SequenceViewer()
    sequences = viewer.parse_afasta(fasta_path)
    if not sequences:
        raise HTTPException(
            status_code=500,
            detail="Failed to parse alignment FASTA file"
        )

    conservation = viewer.calculate_conservation(sequences)
    identity = viewer.calculate_identity(sequences)

    return sanitize_for_json({
        "run_id": run_id,
        "sequences": sequences,
        "conservation": conservation,
        "identity": round(identity, 2)
    })


@app.get("/api/report")
def get_pdf_report(
    run_id: str = Query(...),
    session_id: Optional[str] = Query(None)
):
    """
    Generate and retrieve the PDF analysis report for a run.
    """
    from src.backend.report_generator import ReportGenerator
    from fastapi.responses import FileResponse

    # 1. Fetch run details
    run = history_db.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found in history database."
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
        results = {
            "stats": stats,
            "id": run_id,
            "pdb_ids": run.get("pdb_ids", [])
        }

    # 3. Generate report
    try:
        generator = ReportGenerator(res_dir)
        # Use existing generated report if it exists to avoid redundant calculations
        existing_pdfs = list(res_dir.glob("mustang_report_*.pdf"))
        if existing_pdfs:
            report_path = existing_pdfs[0]
        else:
            report_path = generator.generate_full_report(results, pdb_ids=run.get("pdb_ids", []))
        
        if not report_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Report file was not created successfully."
            )
            
        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename=f"mustang_report_{run_id}.pdf"
        )
    except Exception as e:
        import logging
        logger = logging.getLogger("uvicorn")
        logger.error(f"Failed to generate report PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report PDF: {str(e)}"
        )



# Mount static site for frontend SPA
static_frontend_dir = project_root / "static"
static_frontend_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_frontend_dir), html=True), name="frontend")

