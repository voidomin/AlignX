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
        expect(url).toContain('sections=summary,insights');
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
});
