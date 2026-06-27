const API_BASE = "http://127.0.0.1:8000";

export async function fetchHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error("Health check failed");
    return res.json();
}

export async function fetchSuggestions(q) {
    const res = await fetch(`${API_BASE}/api/suggest?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error("Suggestions fetch failed");
    return res.json();
}

export async function fetchChains(pdbIds) {
    const res = await fetch(`${API_BASE}/api/chains`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pdb_ids: pdbIds })
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Chains fetch failed");
    }
    return res.json();
}

export async function runAlignment(pdbIds, chainSelections, removeWater, removeHeteroatoms) {
    const res = await fetch(`${API_BASE}/api/align`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            pdb_ids: pdbIds,
            chain_selection: chainSelections,
            remove_water: removeWater,
            remove_heteroatoms: removeHeteroatoms
        })
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Alignment execution failed");
    }
    return res.json();
}

export async function fetchLigands(pdbId, runId) {
    const res = await fetch(`${API_BASE}/api/ligands?pdb_id=${pdbId}&run_id=${runId}`);
    if (!res.ok) throw new Error("Ligands fetch failed");
    return res.json();
}

export async function fetchInteractions(pdbId, ligandId, runId) {
    const res = await fetch(`${API_BASE}/api/interactions?pdb_id=${pdbId}&ligand_id=${ligandId}&run_id=${runId}`);
    if (!res.ok) throw new Error("Interactions fetch failed");
    return res.json();
}

export async function fetchMemoryStats() {
    const res = await fetch(`${API_BASE}/api/memory`);
    if (!res.ok) throw new Error("Memory stats fetch failed");
    return res.json();
}

export async function triggerClearMemory() {
    const res = await fetch(`${API_BASE}/api/memory/clear`, { method: 'POST' });
    if (!res.ok) throw new Error("Clear memory execution failed");
    return res.json();
}

export async function fetchHistory() {
    const res = await fetch(`${API_BASE}/api/history`);
    if (!res.ok) throw new Error("History fetch failed");
    return res.json();
}

export async function fetchSequence(runId) {
    const res = await fetch(`${API_BASE}/api/sequence?run_id=${runId}`);
    if (!res.ok) throw new Error("Sequence alignment fetch failed");
    return res.json();
}

export function getAlignmentPdbUrl(runId) {
    return `${API_BASE}/results/${runId}/alignment.pdb`;
}

export function getAlignmentFastaUrl(runId) {
    return `${API_BASE}/results/${runId}/alignment.fasta`;
}

export function getAlignmentReportUrl(runId) {
    return `${API_BASE}/api/report?run_id=${runId}`;
}
