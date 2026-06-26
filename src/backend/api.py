import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware

# Ensure working directory is set to project root if run from subdirectories
project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.utils.config_loader import load_config
from src.backend.coordinator import AnalysisCoordinator
from src.backend.pdb_manager import PDBManager
from src.backend.database import HistoryDatabase
from src.backend.ligand_analyzer import LigandAnalyzer

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

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Backend Managers
history_db = HistoryDatabase()
ligand_analyzer = LigandAnalyzer(config)


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
            
    return {"chains": chain_info}


@app.post("/api/align")
def run_alignment(
    pdb_ids: List[str] = Body(..., embed=True),
    chain_selection: Dict[str, str] = Body(default={}, embed=True),
    remove_water: bool = Body(default=True, embed=True),
    remove_heteroatoms: bool = Body(default=True, embed=True),
    session_id: Optional[str] = Query(None)
):
    """
    Run full Mustang multiple structural alignment pipeline.
    """
    if not pdb_ids or len(pdb_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 PDB IDs are required for alignment."
        )
        
    coordinator = AnalysisCoordinator(config, session_id=session_id)
    success, msg, results = coordinator.run_full_pipeline(
        pdb_ids=pdb_ids,
        chain_selection=chain_selection,
        remove_water=remove_water,
        remove_heteroatoms=remove_heteroatoms,
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Alignment failed: {msg}")
        
    # Serialize results to match JSON specs (handling paths & DataFrames)
    serializable_results = {}
    for key, val in results.items():
        if key in ["result_dir"]:
            serializable_results[key] = str(val)
        elif hasattr(val, "to_dict"):  # pandas DataFrame
            serializable_results[key] = val.to_dict(orient="split")
        else:
            serializable_results[key] = val
            
    return {"success": True, "message": msg, "results": serializable_results}


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
    return {"pdb_id": pdb_id, "ligands": ligands}


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
        
    interactions = ligand_analyzer.analyze_interactions(pdb_path, ligand_id)
    return {"pdb_id": pdb_id, "ligand_id": ligand_id, "interactions": interactions}


@app.get("/api/history")
def get_history(session_id: Optional[str] = Query(None)):
    """
    Fetch all runs recorded in the history SQLite database.
    """
    try:
        runs = history_db.get_all_runs(session_id=session_id)
    except Exception:
        runs = history_db.get_all_runs()
        
    return {"runs": runs}


import json
