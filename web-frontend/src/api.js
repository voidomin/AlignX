// VITE_API_BASE points the built SPA at a separately-hosted backend (e.g.
// Vercel frontend + Render backend) - unset in local dev, where Vite's dev
// server and the FastAPI backend are both on 127.0.0.1.
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
// Not const: a shared run link (getShareLink()) carries its own api_key as a
// URL param when ALIGNX_API_KEY is set, since the recipient's build has no
// way to know the deployment's key at build time - main.js calls
// setApiKeyOverride() on load if it finds one in the URL.
let API_KEY = import.meta.env.VITE_ALIGNX_API_KEY || null;

export function setApiKeyOverride(key) {
    API_KEY = key;
}

function authHeaders(extra = {}) {
    return API_KEY ? { ...extra, 'X-API-Key': API_KEY } : extra;
}

// Builds a request URL via the URL/URLSearchParams APIs rather than string
// concatenation - path segments are validated (see assertSafeSegment/
// assertValidPdbId below) before ever reaching this, and query values are
// set through searchParams, which handles encoding itself. This is the
// construction pattern static analysis (SonarCloud jssecurity:S8476,
// "client-side requests should not be vulnerable to forging attacks")
// actually recognizes as safe - unlike encodeURIComponent()-into-a-template-
// literal, which only escapes characters without the analyzer being able to
// verify the resulting value was ever checked against an expected shape.
function buildUrl(path, queryParams) {
    const url = new URL(path, API_BASE);
    if (queryParams) {
        for (const [key, value] of Object.entries(queryParams)) {
            if (value !== undefined && value !== null) {
                url.searchParams.set(key, value);
            }
        }
    }
    return url.toString();
}

function withApiKey(url) {
    if (!API_KEY) return url;
    const withKey = new URL(url);
    withKey.searchParams.set('api_key', API_KEY);
    return withKey.toString();
}

// Mirrors PDBManager.validate_pdb_id on the backend: standard 4-char PDB IDs
// (e.g. "1L2Y"), AlphaFold model IDs (e.g. "AF-P12345-F1", optionally
// versioned "-V2"), SWISS-MODEL IDs (e.g. "SM-P69905"), or ESM Metagenomic
// Atlas IDs (e.g. "ESM-MGYP002537940442").
const PDB_ID_PATTERN = /^\d[A-Z0-9]{3}$/;
const ALPHAFOLD_ID_PATTERN = /^AF-[A-Z0-9]+-F\d+(-V\d+)?$/;
const SWISSMODEL_ID_PATTERN = /^SM-[A-Z0-9]+$/;
const ESMFOLD_ID_PATTERN = /^ESM-MGYP\d+$/;
// Synthetic IDs this app mints itself server-side (POST /api/upload,
// POST /api/fold-sequence - see structure_id = f"UPLOAD-{secrets.token_hex(4)...}"/
// f"PRED-{secrets.token_hex(4)...}"), never typed by a user into the search
// box but passed right back into every other per-structure API call (the
// 3D viewer's single-structure preview, badges, etc.) once added to the
// workspace - isValidPdbId has to recognize these too, or every one of
// those calls throws "Invalid pdbId" for an upload/prediction.
const UPLOAD_ID_PATTERN = /^UPLOAD-[A-F0-9]{8}$/;
const PREDICTED_ID_PATTERN = /^PRED-[A-F0-9]{8}$/;

export function isValidPdbId(id) {
    const normalized = (id || "").trim().toUpperCase();
    return (
        PDB_ID_PATTERN.test(normalized) ||
        ALPHAFOLD_ID_PATTERN.test(normalized) ||
        SWISSMODEL_ID_PATTERN.test(normalized) ||
        ESMFOLD_ID_PATTERN.test(normalized) ||
        UPLOAD_ID_PATTERN.test(normalized) ||
        PREDICTED_ID_PATTERN.test(normalized)
    );
}

// Mirrors api.py's _safe_segment(): the only shape a run_id, job_id, or
// ligand_id is ever legitimately in. This is a *validator*, not just a
// sanitizer like encodeURIComponent() - it rejects an unexpected value
// outright before it ever reaches a request URL, rather than just
// escaping it so it doesn't break URL syntax. A value reaching here can
// legitimately originate from a server response (e.g. a shared run's
// stored pdb_ids, re-fetched later and fed back into another request) as
// well as direct user input - either way, validating the shape is what
// actually matters, not where the value came from.
const SAFE_SEGMENT_PATTERN = /^[A-Za-z0-9_-]+$/;

function assertSafeSegment(value, fieldName) {
    if (typeof value !== 'string' || !SAFE_SEGMENT_PATTERN.test(value)) {
        throw new Error(`Invalid ${fieldName}: ${JSON.stringify(value)}`);
    }
    return value;
}

function assertValidPdbId(id, fieldName) {
    if (!isValidPdbId(id)) {
        throw new Error(`Invalid ${fieldName}: ${JSON.stringify(id)}`);
    }
    return id;
}

// priority: 'low' (Fetch Priority API, ignored harmlessly where unsupported)
// deprioritizes this background status poll behind user-driven requests
// (chain loads, alignment runs, dashboard stats) competing for the
// browser's limited per-host connection pool.
export async function fetchHealth() {
    const res = await fetch(buildUrl('/health'), { priority: 'low' });
    if (!res.ok) throw new Error("Health check failed");
    return res.json();
}

export async function fetchSuggestions(q) {
    const res = await fetch(buildUrl('/api/suggest', { q }), { headers: authHeaders() });
    if (!res.ok) throw new Error("Suggestions fetch failed");
    return res.json();
}

export async function fetchChains(pdbIds) {
    const res = await fetch(buildUrl('/api/chains'), {
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

// A "reference vs many" pairwise batch screen - one reference structure
// diffed independently against every target, ranked by TM-score. Distinct
// from the N-way Mustang alignment/comparison workflow: no shared
// superposition, no 3D view, just a ranked table - see
// src.backend.api.screen_structures / tm_score_calculator.calculate_pairwise_tm_score.
export async function screenStructures(referencePdbId, targetPdbIds) {
    referencePdbId = assertValidPdbId(referencePdbId, 'referencePdbId');
    const res = await fetch(buildUrl('/api/screen'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ reference_pdb_id: referencePdbId, target_pdb_ids: targetPdbIds })
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Structure screen failed");
    }
    return res.json();
}

export async function uploadStructure(file) {
    const formData = new FormData();
    formData.append('file', file);

    // No Content-Type header here - the browser sets its own multipart
    // boundary on FormData bodies; overriding it would break the upload.
    const res = await fetch(buildUrl('/api/upload'), {
        method: 'POST',
        headers: authHeaders(),
        body: formData
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Upload failed");
    }
    return res.json();
}

// Real ab-initio structure prediction directly from a raw amino-acid
// sequence via ESM Atlas's public ESMFold API - no existing accession
// needed, unlike every other structure source. Synchronous (not a
// background job): returns the same {"chains": {...}} shape
// uploadStructure() does.
export async function predictFromSequence(sequence) {
    const res = await fetch(buildUrl('/api/fold-sequence'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ sequence })
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Structure prediction failed");
    }
    return res.json();
}

export async function runAlignment(pdbIds, chainSelections, removeWater, removeHeteroatoms) {
    const res = await fetch(buildUrl('/api/jobs/align'), {
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
    jobId = assertSafeSegment(jobId, 'jobId');
    const res = await fetch(buildUrl(`/api/jobs/${jobId}`), { headers: authHeaders() });
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

// True sequence-only MSA via EBI's Clustal Omega, independent of Mustang's
// structural alignment - see clustalo_client.py. `sequences` should be each
// structure's own ungapped sequence (not a Mustang-aligned one), keyed by a
// caller-chosen id (typically the pdb_id). Poll the returned job_id with
// pollJobUntilDone(); the completed job's `aligned_fasta` field is the real
// gap-padded aligned FASTA text.
export async function submitClustalOmegaJob(sequences, webhookUrl) {
    const body = { sequences };
    if (webhookUrl) body.webhook_url = webhookUrl;
    const res = await fetch(buildUrl('/api/jobs/clustalo'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Clustal Omega submission failed");
    }
    return res.json();
}

// Real per-column evolutionary conservation via NCBI BLAST homolog search -
// see blast_client.py. `sequence` should be one structure's own raw (ungapped)
// sequence; the job searches for real homologs and scores conservation per
// query position from their real alignments. Real BLAST searches commonly
// take several minutes - poll the returned job_id with pollJobUntilDone()
// using a generous interval. The completed job's `conservation_profile`
// field is a list of {position, conservation, num_homologs, most_common}.
export async function submitConservationJob(sequence, webhookUrl) {
    const body = { sequence };
    if (webhookUrl) body.webhook_url = webhookUrl;
    const res = await fetch(buildUrl('/api/jobs/conservation'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Conservation search submission failed");
    }
    return res.json();
}

// Real mutation-stability (ddG) prediction via DDMut - see ddmut_client.py.
// resi/chain are the structure's own author numbering (matching
// fetchMutationImpact's convention); the wildtype residue is read
// server-side directly from the structure's file, not resolved via
// UniProt, so this works for any structure source. Poll the returned
// job_id with pollJobUntilDone(); the completed job's `prediction.prediction`
// field is the real predicted ddG in kcal/mol (DDMut's own convention:
// positive = stabilizing, negative = destabilizing).
export async function submitDdgStabilityJob(pdbId, chain, resi, mutant, webhookUrl) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    chain = assertSafeSegment(chain, 'chain');
    const body = { pdb_id: pdbId, chain, resi, mutant };
    if (webhookUrl) body.webhook_url = webhookUrl;
    const res = await fetch(buildUrl('/api/jobs/ddg-stability'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Stability prediction submission failed");
    }
    return res.json();
}

// Real geometric pocket detection via PrankWeb - see prankweb_client.py.
// A second, slower, opt-in action alongside the existing fast, synchronous
// fetchPockets heuristic finder, the same relationship submitDdgStabilityJob
// has to the existing fast/synchronous mutation-impact lookup.
export async function submitPrankwebJob(pdbId, runId, sessionId, webhookUrl) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const body = { pdb_id: pdbId };
    if (runId) body.run_id = assertSafeSegment(runId, 'runId');
    if (sessionId) body.session_id = assertSafeSegment(sessionId, 'sessionId');
    if (webhookUrl) body.webhook_url = webhookUrl;
    const res = await fetch(buildUrl('/api/jobs/pocket-detection'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Pocket detection submission failed");
    }
    return res.json();
}

// Real domain/GO-term annotation via InterProScan5, from a structure's
// own sequence (extracted server-side) - see interproscan_client.py/
// api.py's _extract_structure_sequence. The one annotation path
// available for structures with no resolvable UniProt accession at all
// (ESM Atlas/uploaded/ESMFold-predicted structures).
export async function submitInterproscanJob(pdbId, chain, runId, sessionId, webhookUrl) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const body = { pdb_id: pdbId };
    if (chain) body.chain = assertSafeSegment(chain, 'chain');
    if (runId) body.run_id = assertSafeSegment(runId, 'runId');
    if (sessionId) body.session_id = assertSafeSegment(sessionId, 'sessionId');
    if (webhookUrl) body.webhook_url = webhookUrl;
    const res = await fetch(buildUrl('/api/jobs/sequence-annotation'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Sequence annotation submission failed");
    }
    return res.json();
}

export async function submitDiscoveryJob(pdbId, databases, webhookUrl) {
    const body = { pdb_id: pdbId };
    if (databases && databases.length > 0) body.databases = databases;
    if (webhookUrl) body.webhook_url = webhookUrl;
    const res = await fetch(buildUrl('/api/jobs/discover'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Discovery submission failed");
    }
    return res.json();
}

export async function fetchClusters(rmsdDf, threshold) {
    const res = await fetch(buildUrl('/api/clusters'), {
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
    excludeRunId = excludeRunId ? assertSafeSegment(excludeRunId, 'excludeRunId') : '';
    const res = await fetch(buildUrl('/api/comparison/runs', { exclude_run_id: excludeRunId }), { headers: authHeaders() });
    if (!res.ok) throw new Error("Comparison runs fetch failed");
    return res.json();
}

export async function fetchComparison(currentRunId, targetRunId) {
    currentRunId = assertSafeSegment(currentRunId, 'currentRunId');
    targetRunId = assertSafeSegment(targetRunId, 'targetRunId');
    const res = await fetch(
        buildUrl('/api/comparison', { current_run_id: currentRunId, target_run_id: targetRunId }),
        { headers: authHeaders() }
    );
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Comparison fetch failed");
    }
    return res.json();
}

// runId is optional (Discover-mode/uploaded structures reachable in the raw
// download folder have no run at all) - the backend already treats it as
// optional, resolving the raw folder first regardless.
export async function fetchLigands(pdbId, runId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (runId) params.run_id = assertSafeSegment(runId, 'runId');
    const res = await fetch(buildUrl('/api/ligands', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Ligands fetch failed");
    return res.json();
}

// Resolves a bare 3-letter ligand/HETATM code (not the composite
// RESNAME_CHAIN_RESI id fetchLigands() returns) to real chemistry - name,
// formula, SMILES - via RCSB's Chemical Component Dictionary. Not tied to
// any structure/run - works from the ligand code alone. Always returns
// { ligand_code, chemistry } - chemistry is null if nothing resolved,
// never a 404, so callers don't need a special error path for that case.
export async function fetchLigandInfo(ligandCode) {
    ligandCode = assertSafeSegment(ligandCode, 'ligandCode');
    const res = await fetch(buildUrl('/api/ligand-info', { ligand_code: ligandCode }), { headers: authHeaders() });
    if (!res.ok) throw new Error("Ligand info fetch failed");
    return res.json();
}

// Heuristic candidate-pocket detection for a structure with no real bound
// ligand (see src/backend/ligand_analyzer.py's find_candidate_pockets) -
// not a validated tool-grade result, so callers should only reach for this
// once fetchLigands() has already come back empty.
export async function fetchPockets(pdbId, runId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (runId) params.run_id = assertSafeSegment(runId, 'runId');
    const res = await fetch(buildUrl('/api/pockets', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Pocket detection failed");
    return res.json();
}

export async function fetchInteractions(pdbId, ligandId, runId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    ligandId = assertSafeSegment(ligandId, 'ligandId');
    const params = { pdb_id: pdbId, ligand_id: ligandId };
    if (runId) params.run_id = assertSafeSegment(runId, 'runId');
    const res = await fetch(buildUrl('/api/interactions', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Interactions fetch failed");
    return res.json();
}

// See fetchHealth's note on priority: 'low' - same rationale.
export async function fetchMemoryStats() {
    const res = await fetch(buildUrl('/api/memory'), { headers: authHeaders(), priority: 'low' });
    if (!res.ok) throw new Error("Memory stats fetch failed");
    return res.json();
}

export async function triggerClearMemory() {
    const res = await fetch(buildUrl('/api/memory/clear'), { method: 'POST', headers: authHeaders() });
    if (!res.ok) throw new Error("Clear memory execution failed");
    return res.json();
}

export async function fetchRun(runId) {
    runId = assertSafeSegment(runId, 'runId');
    const res = await fetch(buildUrl(`/api/runs/${runId}`), { headers: authHeaders() });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Run fetch failed");
    }
    return res.json();
}

export function getShareLink(runId) {
    // A shared link points at this same SPA's own origin with a query
    // param main.js checks on load - it's world-readable by design (see
    // docs/ROADMAP_V4.md Phase 4/1), not gated by session_id. withApiKey()
    // carries the API key through when one is set, matching every other
    // shareable download link (getAlignmentPdbUrl, getAlignmentFastaUrl, etc).
    runId = assertSafeSegment(runId, 'runId');
    const url = new URL(window.location.origin);
    url.searchParams.set('shared_run', runId);
    return withApiKey(url.toString());
}

export async function fetchHistory(limit = 20, offset = 0) {
    const res = await fetch(buildUrl('/api/history', { limit, offset }), { headers: authHeaders() });
    if (!res.ok) throw new Error("History fetch failed");
    return res.json();
}

export async function deleteRun(runId) {
    runId = assertSafeSegment(runId, 'runId');
    const res = await fetch(buildUrl(`/api/history/${runId}`), { method: 'DELETE', headers: authHeaders() });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to delete run");
    }
    return res.json();
}

// Adds/updates a run's free-text notes and/or tags, stored in the run's
// existing metadata (see HistoryDatabase.update_run_notes - no schema
// change involved). Pass notes/tags as null to leave that field untouched;
// pass "" or [] to explicitly clear it.
export async function updateRunNotes(runId, { notes, tags } = {}) {
    runId = assertSafeSegment(runId, 'runId');
    const res = await fetch(buildUrl(`/api/history/${runId}/notes`), {
        method: 'PUT',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: notes ?? null, tags: tags ?? null }),
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to update run notes");
    }
    return res.json();
}

export async function clearAllHistory() {
    const res = await fetch(buildUrl('/api/history'), { method: 'DELETE', headers: authHeaders() });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to clear history");
    }
    return res.json();
}

export async function fetchStats() {
    const res = await fetch(buildUrl('/api/stats'), { headers: authHeaders() });
    if (!res.ok) throw new Error("Stats fetch failed");
    return res.json();
}

export async function fetchSequence(runId, motif) {
    runId = assertSafeSegment(runId, 'runId');
    const params = { run_id: runId };
    if (motif) params.motif = motif;
    const res = await fetch(buildUrl('/api/sequence', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Sequence alignment fetch failed");
    return res.json();
}

export function getAlignmentPdbUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl(`/results/${runId}/alignment.pdb`));
}

export function getAlignmentFastaUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl(`/results/${runId}/alignment.fasta`));
}

// A synthetic multi-model PDB morphing pdbIdA into pdbIdB over their
// commonly-aligned columns - see the backend's get_morph_frames(). Served
// as plain text (not an attachment), fetched the same way as
// getAlignmentPdbUrl above, then fed straight into 3Dmol's addModelsAsFrames.
export function getMorphFramesUrl(runId, pdbIdA, pdbIdB, numFrames) {
    runId = assertSafeSegment(runId, 'runId');
    pdbIdA = assertValidPdbId(pdbIdA, 'pdbIdA');
    pdbIdB = assertValidPdbId(pdbIdB, 'pdbIdB');
    const params = { run_id: runId, pdb_id_a: pdbIdA, pdb_id_b: pdbIdB };
    if (numFrames) params.num_frames = numFrames;
    return withApiKey(buildUrl('/api/morph', params));
}

// Unlike getAlignmentPdbUrl (Mustang's alignment output, only exists for a
// completed Compare-mode run), this resolves any downloaded structure by
// id alone - e.g. a Discover-mode query structure that was never part of
// an alignment - via the same backend lookup /api/ligands already uses.
export function getStructureFileUrl(pdbId, sessionId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (sessionId) params.session_id = assertSafeSegment(sessionId, 'sessionId');
    return withApiKey(buildUrl('/api/structure-file', params));
}

// The fixed set of report sections the backend understands - not free text,
// so any value outside this allowlist is rejected rather than merely encoded.
const VALID_REPORT_SECTIONS = new Set(['summary', 'insights', 'heatmap', 'tree', 'matrix']);

// `sections` is optional - omit (or pass all 5 known sections) to get the
// default full report; pass a subset array to generate a trimmed one.
export function getAlignmentReportUrl(runId, sections) {
    runId = assertSafeSegment(runId, 'runId');
    if (!sections || sections.length === 0) {
        return withApiKey(buildUrl('/api/report', { run_id: runId }));
    }

    sections.forEach(s => {
        if (!VALID_REPORT_SECTIONS.has(s)) {
            throw new Error(`Invalid report section: ${JSON.stringify(s)}`);
        }
    });
    return withApiKey(buildUrl('/api/report', { run_id: runId, sections: sections.join(',') }));
}

export function getLabNotebookUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/notebook', { run_id: runId }));
}

// A real, runnable Jupyter notebook for this run - unlike getLabNotebookUrl's
// static HTML snapshot, every code cell re-fetches this run's data live from
// this same deployment's own documented REST API (see /api/notebook/ipynb).
export function getLabNotebookIpynbUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/notebook/ipynb', { run_id: runId }));
}

export function getCitationsUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/report/citations', { run_id: runId }));
}

export function getRmsdCsvUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/report/rmsd-csv', { run_id: runId }));
}

export function getHeatmapPngUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/report/heatmap-png', { run_id: runId }));
}

export function getReportZipUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/report/zip', { run_id: runId }));
}

export function getNewickUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/report/newick', { run_id: runId }));
}

export function getPymolScriptUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/report/pymol-script', { run_id: runId }));
}

export function getChimeraxScriptUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/report/chimerax-script', { run_id: runId }));
}

export async function fetchAnnotations(pdbId, chain) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (chain) params.chain = assertSafeSegment(chain, 'chain');
    const res = await fetch(buildUrl('/api/annotations', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Annotation fetch failed");
    return res.json();
}

// wwPDB/PDBe validation metrics (clashscore, Ramachandran/rotamer outlier
// percentiles) for a real, experimentally-solved PDB entry. Always returns
// { pdb_id, validation } - validation is null for non-"pdb"-source
// structures (AlphaFold/SWISS-MODEL/ESMFold have no experimental
// validation report) rather than a 404, so callers don't need a special
// error path for that expected case.
// Maps a structure's own author-numbered residue to its real UniProt
// position, then looks up the real wild-type residue/gene from UniProt and
// (if a matching record exists) the real ClinVar clinical significance of
// the wildtype->mutant substitution - see AnnotationAggregator.
// resolve_structure_uniprot_position()/fetch_clinvar_significance().
export async function fetchMutationImpact(pdbId, chain, resi, mutant) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    chain = assertSafeSegment(chain, 'chain');
    const params = { pdb_id: pdbId, chain, resi, mutant };
    const res = await fetch(buildUrl('/api/mutation-impact', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Mutation impact fetch failed");
    return res.json();
}

export async function fetchValidation(pdbId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const res = await fetch(buildUrl('/api/validation', { pdb_id: pdbId }), { headers: authHeaders() });
    if (!res.ok) throw new Error("Validation fetch failed");
    return res.json();
}

// Standalone per-structure QC (Ramachandran + secondary structure +, for
// real PDB entries, wwPDB validation) - no alignment required, unlike the
// same computations inside a completed run's results. Powers the Workspace
// tab's "Run QC on all" sweep.
export async function fetchQc(pdbId, runId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (runId) params.run_id = assertSafeSegment(runId, 'runId');
    const res = await fetch(buildUrl('/api/qc', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("QC fetch failed");
    return res.json();
}

// One structure's own CA-CA contact map from a completed run's alignment -
// see rmsd_calculator.get_structure_contact_map(). Returns either a dense
// `matrix` or, above the residue cap, a sparse `contacts` list - never both.
export async function fetchRunsTrend(runIds) {
    const res = await fetch(buildUrl('/api/runs/trend'), {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_ids: runIds }),
    });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Run trend fetch failed");
    }
    return res.json();
}

export async function fetchMutationTolerance(pdbId, chain) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (chain) params.chain = assertSafeSegment(chain, 'chain');
    const res = await fetch(buildUrl('/api/mutation-tolerance', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Mutation tolerance fetch failed");
    return res.json();
}

// Real sequence-based intrinsic-disorder prediction (MobiDB) - see the
// backend's AnnotationAggregator.aggregate_disorder_prediction(). Same
// shape as fetchMutationTolerance above.
export async function fetchDisorderPrediction(pdbId, chain) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (chain) params.chain = assertSafeSegment(chain, 'chain');
    const res = await fetch(buildUrl('/api/disorder', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Disorder prediction fetch failed");
    return res.json();
}

// Real-time Gaussian Network Model flexibility prediction - see the
// backend's flexibility_calculator.calculate_gnm_flexibility(). No
// external service call at all, unlike every other annotation fetch here -
// pure coordinate math on a structure already downloaded, same
// run_id/session_id resolution /api/pockets and /api/contact-map use.
export async function fetchFlexibility(pdbId, runId, sessionId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const params = { pdb_id: pdbId };
    if (runId) params.run_id = assertSafeSegment(runId, 'runId');
    if (sessionId) params.session_id = assertSafeSegment(sessionId, 'sessionId');
    const res = await fetch(buildUrl('/api/flexibility', params), { headers: authHeaders() });
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Flexibility prediction fetch failed");
    }
    return res.json();
}

export async function fetchCathClassification(pdbId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const res = await fetch(buildUrl('/api/cath', { pdb_id: pdbId }), { headers: authHeaders() });
    if (!res.ok) throw new Error("CATH classification fetch failed");
    return res.json();
}

export async function fetchAssemblyInfo(pdbId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const res = await fetch(buildUrl('/api/assembly', { pdb_id: pdbId }), { headers: authHeaders() });
    if (!res.ok) throw new Error("Assembly info fetch failed");
    return res.json();
}

export async function fetchPae(pdbId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    const res = await fetch(buildUrl('/api/pae', { pdb_id: pdbId }), { headers: authHeaders() });
    if (!res.ok) throw new Error("PAE fetch failed");
    return res.json();
}

export async function fetchContactMap(runId, pdbId, threshold) {
    runId = assertSafeSegment(runId, 'runId');
    pdbId = assertSafeSegment(pdbId, 'pdbId');
    const params = { run_id: runId, pdb_id: pdbId };
    if (threshold !== undefined) params.threshold = threshold;
    const res = await fetch(buildUrl('/api/contact-map', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Contact map fetch failed");
    return res.json();
}

// Difference-distance matrix between two structures in a completed run's
// alignment - see rmsd_calculator.get_difference_distance_matrix(). Returns
// either a dense `matrix` or, above the column cap, a sparse `differences`
// list - never both.
export async function fetchDifferenceDistance(runId, pdbIdA, pdbIdB) {
    runId = assertSafeSegment(runId, 'runId');
    pdbIdA = assertSafeSegment(pdbIdA, 'pdbIdA');
    pdbIdB = assertSafeSegment(pdbIdB, 'pdbIdB');
    const params = { run_id: runId, pdb_id_a: pdbIdA, pdb_id_b: pdbIdB };
    const res = await fetch(buildUrl('/api/difference-distance', params), { headers: authHeaders() });
    if (!res.ok) throw new Error("Difference-distance fetch failed");
    return res.json();
}

export async function fetchInterface(pdbId, chainA, chainB, runId) {
    pdbId = assertValidPdbId(pdbId, 'pdbId');
    chainA = assertSafeSegment(chainA, 'chainA');
    chainB = assertSafeSegment(chainB, 'chainB');
    const params = { pdb_id: pdbId, chain_a: chainA, chain_b: chainB };
    if (runId) params.run_id = assertSafeSegment(runId, 'runId');
    const res = await fetch(
        buildUrl('/api/interface', params),
        { headers: authHeaders() }
    );
    if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Interface analysis fetch failed");
    }
    return res.json();
}

export async function fetchSettings() {
    const res = await fetch(buildUrl('/api/settings'), { headers: authHeaders() });
    if (!res.ok) throw new Error("Settings fetch failed");
    return res.json();
}

export async function saveSettings(settings) {
    const res = await fetch(buildUrl('/api/settings'), {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(settings),
    });
    if (!res.ok) {
        const errData = await res.json();
        const detail = errData.detail;
        throw new Error(typeof detail === 'string' ? detail : "Failed to save settings");
    }
    return res.json();
}

export async function resetSettings() {
    const res = await fetch(buildUrl('/api/settings/reset'), {
        method: 'POST',
        headers: authHeaders(),
    });
    if (!res.ok) throw new Error("Failed to reset settings");
    return res.json();
}

export function getDiscoveryReportUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/discover/report', { run_id: runId }));
}

export function getDiscoveryExportUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/discover/export', { run_id: runId }));
}

export function getDiscoveryCitationsUrl(runId) {
    runId = assertSafeSegment(runId, 'runId');
    return withApiKey(buildUrl('/api/discover/citations', { run_id: runId }));
}
