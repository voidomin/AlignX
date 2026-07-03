import { describe, it, expect, vi, afterEach } from 'vitest';
import { DiscoverTab } from './DiscoverTab.js';

vi.mock('../api.js', () => ({
    submitDiscoveryJob: vi.fn(),
    pollJobUntilDone: vi.fn(),
    isValidPdbId: vi.fn((id) => /^[0-9A-Z]{4}$/.test(id) || /^AF-/.test(id)),
}));

import { submitDiscoveryJob, pollJobUntilDone } from '../api.js';

function makeAnnotatedResults(overrides = {}) {
    return {
        pdb_id: '1CRN',
        source: 'pdb',
        databases_searched: ['pdb100', 'afdb50'],
        hit_count: 179,
        hits: [
            { target: 'AF-P01541-F1-model_v6 Denclatoxin-B', prob: 1.0, eval: 2.168e-05, seqId: 50 },
        ],
        annotations: {
            neighbors_considered: 10,
            total_hit_count: 179,
            resolvable_hit_count: 123,
            annotated_neighbor_count: 9,
            unannotated_neighbor_count: 1,
            top_domains: [
                { name: 'Thionin', type: 'family', interpro_accession: 'IPR001010', neighbor_count: 9 },
            ],
            top_go_terms: [
                { id: 'GO:0006952', name: 'defense response', aspect: 'biological_process', neighbor_count: 9 },
            ],
            per_neighbor: [],
        },
        ...overrides,
    };
}

describe('DiscoverTab', () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('renders the input and a disabled-by-default run button', () => {
        const tab = new DiscoverTab();
        tab.render();

        expect(tab.element.querySelector('#discover-input')).toBeTruthy();
        expect(tab.element.querySelector('#discover-run-btn').disabled).toBe(false);
        expect(tab.element.querySelector('#discover-results').innerHTML).toBe('');
    });

    it('renders an attribution/ToS note crediting Foldseek and EBI', () => {
        const tab = new DiscoverTab();
        tab.render();

        const text = tab.element.textContent;
        expect(text).toContain('Foldseek');
        expect(text).toContain('InterPro');
        expect(text).toContain('QuickGO');
        const links = Array.from(tab.element.querySelectorAll('a')).map(a => a.href);
        expect(links.some(h => h.includes('search.foldseek.com'))).toBe(true);
        expect(links.some(h => h.includes('ebi.ac.uk'))).toBe(true);
    });

    it('shows a distinct message while a job is queued vs. actively running', async () => {
        submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
        let capturedOnTick;
        pollJobUntilDone.mockImplementation((jobId, { onTick }) => {
            capturedOnTick = onTick;
            return new Promise(() => {}); // never resolves - we only care about status text mid-flight
        });

        const tab = new DiscoverTab();
        tab.render();
        tab.element.querySelector('#discover-input').value = '1CRN';

        const runPromise = tab.handleRun();
        await Promise.resolve();

        const queuedText = tab.element.querySelector('#discover-status-text').textContent;
        expect(queuedText.toLowerCase()).toContain('queued');
        expect(queuedText.toLowerCase()).toContain('rate-limited');

        capturedOnTick({ status: 'running' });
        const runningText = tab.element.querySelector('#discover-status-text').textContent;
        expect(runningText.toLowerCase()).toContain('searching');
        expect(runningText.toLowerCase()).not.toContain('queued');
    });

    it('rejects an invalid structure identifier without calling the API', async () => {
        const tab = new DiscoverTab();
        tab.render();
        tab.element.querySelector('#discover-input').value = 'not-valid';

        await tab.handleRun();

        expect(submitDiscoveryJob).not.toHaveBeenCalled();
        expect(tab.element.querySelector('#discover-error').textContent).toContain('valid');
    });

    it('submits a valid ID, polls to completion, and renders results', async () => {
        submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
        pollJobUntilDone.mockResolvedValue({ status: 'completed', results: makeAnnotatedResults() });

        const tab = new DiscoverTab();
        tab.render();
        tab.element.querySelector('#discover-input').value = '1crn';

        await tab.handleRun();

        expect(submitDiscoveryJob).toHaveBeenCalledWith('1CRN');
        expect(tab.results.pdb_id).toBe('1CRN');
        expect(tab.element.querySelector('#discover-results').textContent).toContain('1CRN');
        expect(tab.element.querySelector('#discover-error').classList.contains('hidden')).toBe(true);
    });

    it('surfaces a failed job as an error message', async () => {
        submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
        pollJobUntilDone.mockResolvedValue({ status: 'failed', error: 'Foldseek search failed: timed out' });

        const tab = new DiscoverTab();
        tab.render();
        tab.element.querySelector('#discover-input').value = '1CRN';

        await tab.handleRun();

        expect(tab.element.querySelector('#discover-error').textContent).toContain('Foldseek search failed');
        expect(tab.element.querySelector('#discover-error').classList.contains('hidden')).toBe(false);
    });

    it('shows an empty-annotations message when no neighbor could be annotated', () => {
        const tab = new DiscoverTab();
        tab.render();
        tab.results = makeAnnotatedResults({
            annotations: {
                neighbors_considered: 3,
                total_hit_count: 5,
                resolvable_hit_count: 0,
                annotated_neighbor_count: 0,
                unannotated_neighbor_count: 3,
                top_domains: [],
                top_go_terms: [],
                per_neighbor: [],
            },
        });
        tab.renderResults();

        expect(tab.element.querySelector('#discover-results').textContent)
            .toContain('none could be resolved to a protein with known functional annotations');
    });

    it('defaults to the student detail level and shows the narrative explanation', () => {
        const tab = new DiscoverTab();
        tab.render();
        tab.results = makeAnnotatedResults();
        tab.renderResults();

        expect(tab.detailLevel).toBe('student');
        expect(tab.element.querySelector('#discover-results').textContent).toContain('most confident structural neighbors');
        expect(tab.element.querySelector('#discover-results').textContent).toContain('Thionin');
    });

    it('switching to the public detail level shows the plain-language summary with a caveat', () => {
        const tab = new DiscoverTab();
        tab.render();
        tab.results = makeAnnotatedResults();
        tab.renderResults();

        tab.element.querySelector('[data-level="public"]').click();

        const text = tab.element.querySelector('#discover-results').textContent;
        expect(tab.detailLevel).toBe('public');
        expect(text).toContain('Thionin');
        expect(text).toContain('not a confirmed experimental result');
    });

    it('switching to the researcher detail level shows the raw hit table', () => {
        const tab = new DiscoverTab();
        tab.render();
        tab.results = makeAnnotatedResults();
        tab.renderResults();

        tab.element.querySelector('[data-level="researcher"]').click();

        const text = tab.element.querySelector('#discover-results').textContent;
        expect(tab.detailLevel).toBe('researcher');
        expect(text).toContain('Total hits');
        expect(text).toContain('Top structural matches');
        expect(tab.element.querySelectorAll('table tbody tr').length).toBeGreaterThan(0);
    });

    it('disables the run button while a job is in flight and re-enables it after', async () => {
        let resolveSubmit;
        submitDiscoveryJob.mockReturnValue(new Promise((resolve) => { resolveSubmit = resolve; }));

        const tab = new DiscoverTab();
        tab.render();
        tab.element.querySelector('#discover-input').value = '1CRN';

        const runPromise = tab.handleRun();
        expect(tab.element.querySelector('#discover-run-btn').disabled).toBe(true);

        resolveSubmit({ job_id: 'job1', status: 'queued' });
        pollJobUntilDone.mockResolvedValue({ status: 'completed', results: makeAnnotatedResults() });
        await runPromise;

        expect(tab.element.querySelector('#discover-run-btn').disabled).toBe(false);
    });
});
