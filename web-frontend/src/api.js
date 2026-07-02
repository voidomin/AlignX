const API_BASE = "http://127.0.0.1:8000";
const API_KEY = import.meta.env.VITE_ALIGNX_API_KEY || null;

function authHeaders(extra = {}) {
    return API_KEY ? { ...extra, 'X-API-Key': API_KEY } : extra;
}

function withApiKey(url) {
    if (!API_KEY) return url;
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}api_key=${encodeURIComponent(API_KEY)}`;
}

// Mirrors PDBManager.validate_pdb_id on the backend: standard 4-char PDB IDs
// (e.g. "1L2Y"), AlphaFold model IDs (e.g. "AF-P12345-F1", optionally
// versioned "-V2"), SWISS-MODEL IDs (e.g. "SM-P69905"), or ESM Metagenomic
// Atlas IDs (e.g. "ESM-MGYP002537940442").
const PDB_ID_PATTERN = /^[0-9][A-Z0-9]{3}$/;
const ALPHAFOLD_ID_PATTERN = /^AF-[A-Z0-9]+-F[0-9]+(-V[0-9]+)?$/;
const SWISSMODEL_ID_PATTERN = /^SM-[A-Z0-9]+$/;
const ESMFOLD_ID_PATTERN = /^ESM-MGYP[0-9]+$/;

export function isValidPdbId(id) {
    const normalized = (id || "").trim().toUpperCase();
    return (
        PDB_ID_PATTERN.test(normalized) ||
        ALPHAFOLD_ID_PATTERN.test(normalized) ||
        SWISSMODEL_ID_PATTERN.test(normalized) ||
        ESMFOLD_ID_PATTERN.test(normalized)
    );
}

export async function fetchHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error("Health check failed");
    return res.json();
}

export async function fetchSuggestions(q) {
    const res = await fetch(`${API_BASE}/api/suggest?q=${encodeURIComponent(q)}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Suggestions fetch failed");
    return res.json();
}

export async function fetchChains(pdbIds) {
    const res = await fetch(`${API_BASE}/api/chains`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ pdb_ids: pdbIds })
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Chains fetch failed");
    }
    return res.json();
}

export async function runAlignment(pdbIds, chainSelections, removeWater, removeHeteroatoms) {
    const res = await fetch(`${API_BASE}/api/jobs/align`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
            pdb_ids: pdbIds,
            chain_selection: chainSelections,
            remove_water: removeWater,
            remove_heteroatoms: removeHeteroatoms
        })
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Alignment submission failed");
    }
    return res.json();
}

export async function fetchJobStatus(jobId) {
    const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, { headers: authHeaders() });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Job status fetch failed");
    }
    return res.json();
}

export async function pollJobUntilDone(jobId, { intervalMs = 1500, onTick = null } = {}) {
    while (true) {
        const job = await fetchJobStatus(jobId);
        if (onTick) onTick(job);
        if (job.status === 'completed' || job.status === 'failed') {
            return job;
        }
        await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
}

export async function fetchClusters(rmsdDf, threshold) {
    const res = await fetch(`${API_BASE}/api/clusters`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ rmsd_df: rmsdDf, threshold })
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Clusters fetch failed");
    }
    return res.json();
}

export async function fetchComparisonRuns(excludeRunId) {
    const res = await fetch(`${API_BASE}/api/comparison/runs?exclude_run_id=${encodeURIComponent(excludeRunId || '')}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Comparison runs fetch failed");
    return res.json();
}

export async function fetchComparison(currentRunId, targetRunId) {
    const res = await fetch(`${API_BASE}/api/comparison?current_run_id=${encodeURIComponent(currentRunId)}&target_run_id=${encodeURIComponent(targetRunId)}`, { headers: authHeaders() });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Comparison fetch failed");
    }
    return res.json();
}

export async function fetchLigands(pdbId, runId) {
    const res = await fetch(`${API_BASE}/api/ligands?pdb_id=${pdbId}&run_id=${runId}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Ligands fetch failed");
    return res.json();
}

export async function fetchInteractions(pdbId, ligandId, runId) {
    const res = await fetch(`${API_BASE}/api/interactions?pdb_id=${pdbId}&ligand_id=${ligandId}&run_id=${runId}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Interactions fetch failed");
    return res.json();
}

export async function fetchMemoryStats() {
    const res = await fetch(`${API_BASE}/api/memory`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Memory stats fetch failed");
    return res.json();
}

export async function triggerClearMemory() {
    const res = await fetch(`${API_BASE}/api/memory/clear`, { method: 'POST', headers: authHeaders() });
    if (!res.ok) throw new Error("Clear memory execution failed");
    return res.json();
}

export async function fetchHistory(limit = 20, offset = 0) {
    const res = await fetch(`${API_BASE}/api/history?limit=${limit}&offset=${offset}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("History fetch failed");
    return res.json();
}

export async function fetchStats() {
    const res = await fetch(`${API_BASE}/api/stats`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Stats fetch failed");
    return res.json();
}

export async function fetchSequence(runId) {
    const res = await fetch(`${API_BASE}/api/sequence?run_id=${runId}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("Sequence alignment fetch failed");
    return res.json();
}

export function getAlignmentPdbUrl(runId) {
    return `${API_BASE}/results/${runId}/alignment.pdb`;
}

export function getAlignmentFastaUrl(runId) {
    return `${API_BASE}/results/${runId}/alignment.fasta`;
}

// `sections` is optional - omit (or pass all 5 known sections) to get the
// default full report; pass a subset array to generate a trimmed one.
export function getAlignmentReportUrl(runId, sections) {
    const base = `${API_BASE}/api/report?run_id=${runId}`;
    const url = (sections && sections.length > 0)
        ? `${base}&sections=${sections.join(',')}`
        : base;
    return withApiKey(url);
}

export function getLabNotebookUrl(runId) {
    return withApiKey(`${API_BASE}/api/notebook?run_id=${runId}`);
}
