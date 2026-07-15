import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

function mockFetchOnce(body, ok = true, status = ok ? 200 : 400) {
    global.fetch = vi.fn().mockResolvedValue({
        ok,
        status,
        json: async () => body,
    });
}

describe('api.js (no API key configured)', () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('fetchClusters posts the rmsd matrix and threshold, no auth header', async () => {
        mockFetchOnce({ threshold: 3.0, clusters: [] });
        const { fetchClusters } = await import('./api.js');

        const rmsdDf = { index: ['A', 'B'], columns: ['A', 'B'], data: [[0, 1], [1, 0]] };
        const result = await fetchClusters(rmsdDf, 3.0);

        expect(result.clusters).toEqual([]);
        const [url, options] = global.fetch.mock.calls[0];
        expect(url).toContain('/api/clusters');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({ rmsd_df: rmsdDf, threshold: 3.0 });
        expect(options.headers['X-API-Key']).toBeUndefined();
    });

    it('runAlignment submits to the job queue endpoint, not the old synchronous one', async () => {
        mockFetchOnce({ job_id: 'abc123', status: 'queued' });
        const { runAlignment } = await import('./api.js');

        const result = await runAlignment(['4RLT', '3UG9'], { '4RLT': 'A' }, true, true);

        expect(result.job_id).toBe('abc123');
        const [url] = global.fetch.mock.calls[0];
        expect(url).toContain('/api/jobs/align');
    });

    it('submitDiscoveryJob posts pdb_id (and optional databases) to the discover endpoint', async () => {
        mockFetchOnce({ job_id: 'disc123', status: 'queued' });
        const { submitDiscoveryJob } = await import('./api.js');

        const result = await submitDiscoveryJob('1CRN', ['pdb100', 'afdb50']);

        expect(result.job_id).toBe('disc123');
        const [url, options] = global.fetch.mock.calls[0];
        expect(url).toContain('/api/jobs/discover');
        expect(JSON.parse(options.body)).toEqual({ pdb_id: '1CRN', databases: ['pdb100', 'afdb50'] });
    });

    it('submitDiscoveryJob omits databases when not provided', async () => {
        mockFetchOnce({ job_id: 'disc456', status: 'queued' });
        const { submitDiscoveryJob } = await import('./api.js');

        await submitDiscoveryJob('1CRN');

        const [, options] = global.fetch.mock.calls[0];
        expect(JSON.parse(options.body)).toEqual({ pdb_id: '1CRN' });
    });

    it('pollJobUntilDone polls until status is completed', async () => {
        const responses = [
            { status: 'queued' },
            { status: 'running' },
            { status: 'completed', results: { id: 'run_1' } },
        ];
        global.fetch = vi.fn().mockImplementation(() => Promise.resolve({
            ok: true,
            json: async () => responses.shift(),
        }));
        const { pollJobUntilDone } = await import('./api.js');

        const ticks = [];
        const final = await pollJobUntilDone('job_1', { intervalMs: 0, onTick: (j) => ticks.push(j.status) });

        expect(final.status).toBe('completed');
        expect(final.results.id).toBe('run_1');
        expect(ticks).toEqual(['queued', 'running', 'completed']);
        expect(global.fetch).toHaveBeenCalledTimes(3);
    });

    it('pollJobUntilDone stops on failed status without throwing', async () => {
        mockFetchOnce({ status: 'failed', error: 'boom' });
        const { pollJobUntilDone } = await import('./api.js');

        const final = await pollJobUntilDone('job_2', { intervalMs: 0 });
        expect(final.status).toBe('failed');
        expect(final.error).toBe('boom');
    });

    it('fetchComparison surfaces the backend error detail on failure', async () => {
        mockFetchOnce({ detail: 'No overlapping proteins found between these runs.' }, false, 400);
        const { fetchComparison } = await import('./api.js');

        await expect(fetchComparison('run_a', 'run_b')).rejects.toThrow(
            'No overlapping proteins found between these runs.'
        );
    });

    it('isValidPdbId accepts standard PDB, AlphaFold, SWISS-MODEL, and ESM Atlas IDs', async () => {
        const { isValidPdbId } = await import('./api.js');
        expect(isValidPdbId('1L2Y')).toBe(true);
        expect(isValidPdbId('AF-P69905-F1')).toBe(true);
        expect(isValidPdbId('af-p69905-f1-v2')).toBe(true);
        expect(isValidPdbId('SM-P69905')).toBe(true);
        expect(isValidPdbId('sm-p69905')).toBe(true);
        expect(isValidPdbId('ESM-MGYP002537940442')).toBe(true);
        expect(isValidPdbId('esm-mgyp002537940442')).toBe(true);
    });

    it('isValidPdbId rejects malformed or unrecognized IDs', async () => {
        const { isValidPdbId } = await import('./api.js');
        expect(isValidPdbId('SM-')).toBe(false);
        expect(isValidPdbId('ESM-P69905')).toBe(false);
        expect(isValidPdbId('not an id')).toBe(false);
        expect(isValidPdbId('')).toBe(false);
    });

    it('getAlignmentReportUrl does not append an api_key param when no key is configured', async () => {
        const { getAlignmentReportUrl } = await import('./api.js');
        expect(getAlignmentReportUrl('run_1')).not.toContain('api_key');
    });

    it('getAlignmentPdbUrl/getAlignmentFastaUrl do not append an api_key param when no key is configured', async () => {
        const { getAlignmentPdbUrl, getAlignmentFastaUrl } = await import('./api.js');
        expect(getAlignmentPdbUrl('run_1')).not.toContain('api_key');
        expect(getAlignmentFastaUrl('run_1')).not.toContain('api_key');
    });

    it('getAlignmentReportUrl omits the sections param by default (unchanged default full-report URL)', async () => {
        const { getAlignmentReportUrl } = await import('./api.js');
        expect(getAlignmentReportUrl('run_1')).not.toContain('sections');
    });

    it('getAlignmentReportUrl appends a comma-joined sections param when a subset is given', async () => {
        const { getAlignmentReportUrl } = await import('./api.js');
        const url = getAlignmentReportUrl('run_1', ['summary', 'insights']);
        // URLSearchParams percent-encodes the comma (%2C) - FastAPI decodes
        // query params automatically, so sections.split(",") still works.
        expect(url).toContain('sections=summary%2Cinsights');
    });

    it('getAlignmentReportUrl rejects a section name outside the known allowlist', async () => {
        const { getAlignmentReportUrl } = await import('./api.js');
        expect(() => getAlignmentReportUrl('run_1', ['summary', 'not-a-real-section']))
            .toThrow('Invalid report section');
    });

    it('getLabNotebookUrl points at the notebook endpoint for the given run', async () => {
        const { getLabNotebookUrl } = await import('./api.js');
        expect(getLabNotebookUrl('run_1')).toContain('/api/notebook?run_id=run_1');
    });

    it('getDiscoveryReportUrl points at the discover report endpoint for the given run', async () => {
        const { getDiscoveryReportUrl } = await import('./api.js');
        expect(getDiscoveryReportUrl('discover_1')).toContain('/api/discover/report?run_id=discover_1');
    });

    it('getDiscoveryExportUrl points at the discover export endpoint for the given run', async () => {
        const { getDiscoveryExportUrl } = await import('./api.js');
        expect(getDiscoveryExportUrl('discover_1')).toContain('/api/discover/export?run_id=discover_1');
    });

    it('fetchStats hits the aggregate stats endpoint', async () => {
        mockFetchOnce({ total_runs: 3, total_proteins_analyzed: 7, cache_size_mb: 1.2 });
        const { fetchStats } = await import('./api.js');

        const result = await fetchStats();
        expect(result.total_runs).toBe(3);
        const [url] = global.fetch.mock.calls[0];
        expect(url).toContain('/api/stats');
    });

    it('fetchRun fetches a single run by ID from /api/runs/{id}', async () => {
        mockFetchOnce({ id: 'run_123', pdb_ids: ['4RLT'] });
        const { fetchRun } = await import('./api.js');

        const result = await fetchRun('run_123');
        expect(result.id).toBe('run_123');
        const [url] = global.fetch.mock.calls[0];
        expect(url).toContain('/api/runs/run_123');
    });

    it('fetchRun throws the backend detail message on a 404', async () => {
        mockFetchOnce({ detail: 'Run run_999 not found in history database.' }, false, 404);
        const { fetchRun } = await import('./api.js');

        await expect(fetchRun('run_999')).rejects.toThrow('not found in history database');
    });

    it('getShareLink points at this origin with a shared_run param, no api_key when none is configured', async () => {
        const { getShareLink } = await import('./api.js');
        const link = getShareLink('run_123');
        expect(link).toContain('shared_run=run_123');
        expect(link).not.toContain('api_key=');
    });

    it('setApiKeyOverride makes subsequent calls attach the header even with no build-time key', async () => {
        const { fetchHistory, setApiKeyOverride } = await import('./api.js');
        setApiKeyOverride('shared-link-key');

        mockFetchOnce({ runs: [] });
        await fetchHistory();

        const [, options] = global.fetch.mock.calls[0];
        expect(options.headers['X-API-Key']).toBe('shared-link-key');
    });
});

describe('api.js (API key configured)', () => {
    beforeEach(() => {
        vi.stubEnv('VITE_ALIGNX_API_KEY', 'secret-key');
        vi.resetModules();
    });

    afterEach(() => {
        vi.unstubAllEnvs();
        vi.restoreAllMocks();
    });

    it('attaches the X-API-Key header on fetch-based calls', async () => {
        mockFetchOnce({ runs: [] });
        const { fetchHistory } = await import('./api.js');

        await fetchHistory();
        const [, options] = global.fetch.mock.calls[0];
        expect(options.headers['X-API-Key']).toBe('secret-key');
    });

    it('appends api_key as a query param on the report URL', async () => {
        const { getAlignmentReportUrl } = await import('./api.js');
        expect(getAlignmentReportUrl('run_1')).toContain('api_key=secret-key');
    });

    it('appends api_key as a query param on the /results-backed PDB and FASTA URLs', async () => {
        // /results is gated by the same ALIGNX_API_KEY check as /api/* on the
        // backend (see api.py's require_api_key middleware) - these two
        // link/fetch targets must carry the key too, or they 401 once a key
        // is configured.
        const { getAlignmentPdbUrl, getAlignmentFastaUrl } = await import('./api.js');
        expect(getAlignmentPdbUrl('run_1')).toContain('api_key=secret-key');
        expect(getAlignmentFastaUrl('run_1')).toContain('api_key=secret-key');
    });

    it('getShareLink carries the api_key so a recipient without a build-time key can still authenticate', async () => {
        const { getShareLink } = await import('./api.js');
        const link = getShareLink('run_1');
        expect(link).toContain('shared_run=run_1');
        expect(link).toContain('api_key=secret-key');
    });
});

describe('api.js request-ID validation', () => {
    // SonarCloud jssecurity:S8476 ("client-side requests should not be
    // vulnerable to forging attacks"): a value must be validated against
    // its expected shape *before* it reaches a request URL, not just
    // percent-encoded into it - encodeURIComponent() alone would still let
    // a value like "../other-endpoint" through, just escaped. These tests
    // prove the validators actually reject malformed/malicious values
    // rather than silently passing them through.
    beforeEach(() => {
        global.fetch = vi.fn();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    const maliciousRunIds = ['../admin', 'a/b', 'a b', 'run_1?x=y', ''];

    it.each(maliciousRunIds)('fetchRun rejects a malformed run_id: %j', async (bad) => {
        const { fetchRun } = await import('./api.js');
        await expect(fetchRun(bad)).rejects.toThrow('Invalid runId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it.each(maliciousRunIds)('fetchSequence rejects a malformed run_id: %j', async (bad) => {
        const { fetchSequence } = await import('./api.js');
        await expect(fetchSequence(bad)).rejects.toThrow('Invalid runId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it.each(maliciousRunIds)('fetchJobStatus rejects a malformed job_id: %j', async (bad) => {
        const { fetchJobStatus } = await import('./api.js');
        await expect(fetchJobStatus(bad)).rejects.toThrow('Invalid jobId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('getAlignmentPdbUrl throws rather than building a URL from a malformed run_id', async () => {
        const { getAlignmentPdbUrl } = await import('./api.js');
        expect(() => getAlignmentPdbUrl('../../etc/passwd')).toThrow('Invalid runId');
    });

    it('getShareLink throws rather than building a link from a malformed run_id', async () => {
        const { getShareLink } = await import('./api.js');
        expect(() => getShareLink('not a real id')).toThrow('Invalid runId');
    });

    it('fetchLigands rejects a pdbId that is not a recognized structure ID format', async () => {
        const { fetchLigands } = await import('./api.js');
        await expect(fetchLigands('../evil', 'run_1')).rejects.toThrow('Invalid pdbId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('accepts genuinely valid IDs without throwing', async () => {
        mockFetchOnce({ ligands: [] });
        const { fetchLigands } = await import('./api.js');
        await expect(fetchLigands('4RLT', 'run_1783414603_2b797f99f0bee74f')).resolves.toBeDefined();
    });

    it('getNewickUrl throws rather than building a URL from a malformed run_id', async () => {
        const { getNewickUrl } = await import('./api.js');
        expect(() => getNewickUrl('../../etc/passwd')).toThrow('Invalid runId');
    });

    it('getStructureFileUrl throws rather than building a URL from a malformed pdbId', async () => {
        const { getStructureFileUrl } = await import('./api.js');
        expect(() => getStructureFileUrl('../evil')).toThrow('Invalid pdbId');
    });

    it('getStructureFileUrl works with just a pdbId, no session_id required', async () => {
        const { getStructureFileUrl } = await import('./api.js');
        expect(getStructureFileUrl('4RLT')).toContain('pdb_id=4RLT');
    });

    it('fetchInterface rejects a malformed chain_a', async () => {
        const { fetchInterface } = await import('./api.js');
        await expect(fetchInterface('4RLT', '../evil', 'B', 'run_1')).rejects.toThrow('Invalid chainA');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchInterface rejects a pdbId that is not a recognized structure ID format', async () => {
        const { fetchInterface } = await import('./api.js');
        await expect(fetchInterface('../evil', 'A', 'B', 'run_1')).rejects.toThrow('Invalid pdbId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchLigands works with no runId (a Discover-mode/uploaded structure has no run at all)', async () => {
        mockFetchOnce({ ligands: [] });
        const { fetchLigands } = await import('./api.js');
        await expect(fetchLigands('4RLT')).resolves.toBeDefined();
        expect(global.fetch.mock.calls[0][0]).not.toContain('run_id');
    });

    it('fetchLigands still rejects a malformed runId when one is actually given', async () => {
        const { fetchLigands } = await import('./api.js');
        await expect(fetchLigands('4RLT', '../evil')).rejects.toThrow('Invalid runId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchPockets rejects a pdbId that is not a recognized structure ID format', async () => {
        const { fetchPockets } = await import('./api.js');
        await expect(fetchPockets('../evil')).rejects.toThrow('Invalid pdbId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchPockets works with no runId', async () => {
        mockFetchOnce({ pockets: [] });
        const { fetchPockets } = await import('./api.js');
        await expect(fetchPockets('4RLT')).resolves.toBeDefined();
        expect(global.fetch.mock.calls[0][0]).not.toContain('run_id');
    });

    it('fetchPockets still rejects a malformed runId when one is actually given', async () => {
        const { fetchPockets } = await import('./api.js');
        await expect(fetchPockets('4RLT', '../evil')).rejects.toThrow('Invalid runId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchInteractions works with no runId', async () => {
        mockFetchOnce({ interactions: { interactions: [] } });
        const { fetchInteractions } = await import('./api.js');
        await expect(fetchInteractions('4RLT', 'LIG_A_1')).resolves.toBeDefined();
        expect(global.fetch.mock.calls[0][0]).not.toContain('run_id');
    });

    it('fetchInterface works with no runId', async () => {
        mockFetchOnce({ interface: {} });
        const { fetchInterface } = await import('./api.js');
        await expect(fetchInterface('4RLT', 'A', 'B')).resolves.toBeDefined();
        expect(global.fetch.mock.calls[0][0]).not.toContain('run_id');
    });

    it('fetchAnnotations rejects a pdbId that is not a recognized structure ID format', async () => {
        const { fetchAnnotations } = await import('./api.js');
        await expect(fetchAnnotations('../evil', 'A')).rejects.toThrow('Invalid pdbId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchAnnotations rejects a malformed chain', async () => {
        const { fetchAnnotations } = await import('./api.js');
        await expect(fetchAnnotations('4RLT', '../etc')).rejects.toThrow('Invalid chain');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchAnnotations works with no chain given (AlphaFold/SWISS-MODEL structures)', async () => {
        mockFetchOnce({ annotation: {} });
        const { fetchAnnotations } = await import('./api.js');
        await expect(fetchAnnotations('AF-P69905-F1')).resolves.toBeDefined();
    });

    it('fetchValidation rejects a pdbId that is not a recognized structure ID format', async () => {
        const { fetchValidation } = await import('./api.js');
        await expect(fetchValidation('../evil')).rejects.toThrow('Invalid pdbId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchValidation resolves with the { pdb_id, validation } shape', async () => {
        mockFetchOnce({ pdb_id: '4HHB', validation: { clashscore: { value: 1.2 } } });
        const { fetchValidation } = await import('./api.js');
        await expect(fetchValidation('4HHB')).resolves.toEqual({
            pdb_id: '4HHB',
            validation: { clashscore: { value: 1.2 } },
        });
        expect(global.fetch.mock.calls[0][0]).toContain('/api/validation');
        expect(global.fetch.mock.calls[0][0]).toContain('pdb_id=4HHB');
    });

    it('fetchLigandInfo rejects an unsafe ligand code', async () => {
        const { fetchLigandInfo } = await import('./api.js');
        await expect(fetchLigandInfo('../evil')).rejects.toThrow('Invalid ligandCode');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchLigandInfo resolves with the { ligand_code, chemistry } shape', async () => {
        mockFetchOnce({ ligand_code: 'HEM', chemistry: { name: 'HEME', formula: 'C34 H32 Fe N4 O4' } });
        const { fetchLigandInfo } = await import('./api.js');
        await expect(fetchLigandInfo('HEM')).resolves.toEqual({
            ligand_code: 'HEM',
            chemistry: { name: 'HEME', formula: 'C34 H32 Fe N4 O4' },
        });
        expect(global.fetch.mock.calls[0][0]).toContain('/api/ligand-info');
        expect(global.fetch.mock.calls[0][0]).toContain('ligand_code=HEM');
    });

    it('fetchContactMap rejects an unsafe pdbId', async () => {
        const { fetchContactMap } = await import('./api.js');
        await expect(fetchContactMap('run_1', '../evil')).rejects.toThrow('Invalid pdbId');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchContactMap resolves with the run/pdb-scoped contact map shape', async () => {
        mockFetchOnce({ pdb_id: '4HHB', residue_count: 3, capped: false, matrix: [[0, 1, 0], [1, 0, 0], [0, 0, 0]], contacts: null });
        const { fetchContactMap } = await import('./api.js');
        const data = await fetchContactMap('run_1', '4HHB', 8.0);
        expect(data.residue_count).toBe(3);
        expect(global.fetch.mock.calls[0][0]).toContain('/api/contact-map');
        expect(global.fetch.mock.calls[0][0]).toContain('run_id=run_1');
        expect(global.fetch.mock.calls[0][0]).toContain('pdb_id=4HHB');
        expect(global.fetch.mock.calls[0][0]).toContain('threshold=8');
    });

    it('fetchDifferenceDistance rejects an unsafe pdbIdB', async () => {
        const { fetchDifferenceDistance } = await import('./api.js');
        await expect(fetchDifferenceDistance('run_1', '4HHB', '../evil')).rejects.toThrow('Invalid pdbIdB');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchDifferenceDistance resolves with the pairwise difference-matrix shape', async () => {
        mockFetchOnce({ pdb_id_a: '4HHB', pdb_id_b: '3UG9', column_count: 2, capped: false, matrix: [[0, 1.2], [1.2, 0]], differences: null });
        const { fetchDifferenceDistance } = await import('./api.js');
        const data = await fetchDifferenceDistance('run_1', '4HHB', '3UG9');
        expect(data.column_count).toBe(2);
        expect(global.fetch.mock.calls[0][0]).toContain('/api/difference-distance');
        expect(global.fetch.mock.calls[0][0]).toContain('pdb_id_a=4HHB');
        expect(global.fetch.mock.calls[0][0]).toContain('pdb_id_b=3UG9');
    });

    it('fetchMutationImpact rejects an unsafe chain', async () => {
        const { fetchMutationImpact } = await import('./api.js');
        await expect(fetchMutationImpact('4HHB', '../evil', 6, 'V')).rejects.toThrow('Invalid chain');
        expect(global.fetch).not.toHaveBeenCalled();
    });

    it('fetchMutationImpact resolves with the mutation-impact shape', async () => {
        mockFetchOnce({
            accession: 'P68871', uniprot_position: 7, wildtype_residue: 'V', mutant_residue: 'V',
            gene: 'HBB', clinvar: { clinical_significance: 'Pathogenic' }, known_uniprot_variant: null,
            highlight_chains: { A: [6] },
        });
        const { fetchMutationImpact } = await import('./api.js');
        const data = await fetchMutationImpact('4HHB', 'A', 6, 'V');
        expect(data.gene).toBe('HBB');
        expect(global.fetch.mock.calls[0][0]).toContain('/api/mutation-impact');
        expect(global.fetch.mock.calls[0][0]).toContain('pdb_id=4HHB');
        expect(global.fetch.mock.calls[0][0]).toContain('chain=A');
        expect(global.fetch.mock.calls[0][0]).toContain('resi=6');
        expect(global.fetch.mock.calls[0][0]).toContain('mutant=V');
    });
});
