import { describe, it, expect, vi, afterEach } from 'vitest';
import { DiscoveryPanel } from './DiscoveryPanel.js';

vi.mock('../api.js', () => ({
    submitDiscoveryJob: vi.fn(),
    pollJobUntilDone: vi.fn(),
    getDiscoveryReportUrl: vi.fn((runId) => `http://mock/api/discover/report?run_id=${runId}`),
    getDiscoveryExportUrl: vi.fn((runId) => `http://mock/api/discover/export?run_id=${runId}`),
    getDiscoveryCitationsUrl: vi.fn((runId) => `http://mock/api/discover/citations?run_id=${runId}`),
}));

import { submitDiscoveryJob, pollJobUntilDone } from '../api.js';

function makeAnnotatedResults(overrides = {}) {
    return {
        id: 'discover_123',
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
            candidates_examined: 20,
            resolvable_hit_count: 18,
            annotated_neighbor_count: 9,
            unannotated_neighbor_count: 1,
            min_confident_probability: 0.5,
            high_confidence_annotated_count: 9,
            top_domains: [
                { name: 'Thionin', type: 'family', interpro_accession: 'IPR001010', neighbor_count: 9 },
            ],
            top_go_terms: [
                { id: 'GO:0006952', name: 'defense response', aspect: 'biological_process', neighbor_count: 9 },
            ],
            high_confidence_top_domains: [
                { name: 'Thionin', type: 'family', interpro_accession: 'IPR001010', neighbor_count: 9 },
            ],
            high_confidence_top_go_terms: [
                { id: 'GO:0006952', name: 'defense response', aspect: 'biological_process', neighbor_count: 9 },
            ],
            neighbors_with_interactions_count: 0,
            neighbors_with_pathways_count: 0,
            per_neighbor: [],
        },
        ...overrides,
    };
}

describe('DiscoveryPanel', () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('renders with no pdbId/results and a close button', () => {
        const panel = new DiscoveryPanel();
        panel.render();

        expect(panel.element.querySelector('#discovery-panel-close-btn')).toBeTruthy();
        expect(panel.element.querySelector('#discover-results').innerHTML).toBe('');
    });

    it('calls onClose when the close button is clicked', () => {
        const onClose = vi.fn();
        const panel = new DiscoveryPanel({ onClose });
        panel.render();

        panel.element.querySelector('#discovery-panel-close-btn').click();

        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('renders an attribution/ToS note crediting every annotation source', () => {
        const panel = new DiscoveryPanel();
        panel.render();

        const text = panel.element.textContent;
        expect(text).toContain('Foldseek');
        expect(text).toContain('InterPro');
        expect(text).toContain('QuickGO');
        expect(text).toContain('STRING');
        expect(text).toContain('Reactome');
        expect(text).toContain('GMGC');
        const links = Array.from(panel.element.querySelectorAll('a')).map(a => a.href);
        expect(links.some(h => h.includes('search.foldseek.com'))).toBe(true);
        expect(links.some(h => h.includes('ebi.ac.uk'))).toBe(true);
        expect(links.some(h => h.includes('string-db.org'))).toBe(true);
        expect(links.some(h => h.includes('reactome.org'))).toBe(true);
        expect(links.some(h => h.includes('gmgc.embl.de'))).toBe(true);
    });

    it('shows a distinct message while a job is queued vs. actively running', async () => {
        submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
        let capturedOnTick;
        pollJobUntilDone.mockImplementation((jobId, { onTick }) => {
            capturedOnTick = onTick;
            return new Promise(() => {}); // never resolves - we only care about status text mid-flight
        });

        const panel = new DiscoveryPanel();
        panel.render();

        panel.runFor('1CRN');
        await Promise.resolve();

        const queuedText = panel.element.querySelector('#discover-status-text').textContent;
        expect(queuedText.toLowerCase()).toContain('queued');
        expect(queuedText.toLowerCase()).toContain('rate-limited');

        capturedOnTick({ status: 'running' });
        const runningText = panel.element.querySelector('#discover-status-text').textContent;
        expect(runningText.toLowerCase()).toContain('searching');
        expect(runningText.toLowerCase()).not.toContain('queued');
    });

    it('runs for the given pdbId, polls to completion, and renders results', async () => {
        submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
        pollJobUntilDone.mockResolvedValue({ status: 'completed', results: makeAnnotatedResults() });

        const panel = new DiscoveryPanel();
        panel.render();

        await panel.runFor('1CRN');

        expect(submitDiscoveryJob).toHaveBeenCalledWith('1CRN', ['pdb100', 'afdb50']);
        expect(panel.results.pdb_id).toBe('1CRN');
        expect(panel.element.querySelector('#discovery-panel-pdbid').textContent).toBe('1CRN');
        expect(panel.element.querySelector('#discover-results').textContent).toContain('1CRN');
        expect(panel.element.querySelector('#discover-error').classList.contains('hidden')).toBe(true);
    });

    it('passes the webhook URL through when one is entered', async () => {
        submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
        pollJobUntilDone.mockResolvedValue({ status: 'completed', results: makeAnnotatedResults() });

        const panel = new DiscoveryPanel();
        panel.render();
        panel.element.querySelector('#discover-webhook-url').value = 'https://example.com/hook';

        await panel.runFor('1CRN');

        expect(submitDiscoveryJob).toHaveBeenCalledWith('1CRN', ['pdb100', 'afdb50'], 'https://example.com/hook');
    });

    it('surfaces a failed job as an error message', async () => {
        submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
        pollJobUntilDone.mockResolvedValue({ status: 'failed', error: 'Foldseek search failed: timed out' });

        const panel = new DiscoveryPanel();
        panel.render();

        await panel.runFor('1CRN');

        expect(panel.element.querySelector('#discover-error').textContent).toContain('Foldseek search failed');
        expect(panel.element.querySelector('#discover-error').classList.contains('hidden')).toBe(false);
    });

    it('shows an empty-annotations message when no neighbor could be annotated', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults({
            annotations: {
                neighbors_considered: 3,
                total_hit_count: 5,
                candidates_examined: 3,
                resolvable_hit_count: 0,
                annotated_neighbor_count: 0,
                unannotated_neighbor_count: 3,
                top_domains: [],
                top_go_terms: [],
                per_neighbor: [],
            },
        });
        panel.renderResults();

        expect(panel.element.querySelector('#discover-results').textContent)
            .toContain('none could be resolved to a protein with known functional annotations');
    });

    it('shows a low-confidence message instead of a hypothesis when annotations exist but none clear the confidence gate', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults({
            annotations: {
                neighbors_considered: 3,
                total_hit_count: 5,
                candidates_examined: 3,
                resolvable_hit_count: 3,
                annotated_neighbor_count: 2,
                unannotated_neighbor_count: 1,
                min_confident_probability: 0.5,
                high_confidence_annotated_count: 0,
                neighbors_with_interactions_count: 0,
                neighbors_with_pathways_count: 0,
                top_domains: [{ name: 'Thionin', type: 'family', neighbor_count: 2 }],
                top_go_terms: [],
                high_confidence_top_domains: [],
                high_confidence_top_go_terms: [],
                per_neighbor: [],
            },
        });
        panel.renderResults();

        const text = panel.element.querySelector('#discover-results').textContent;
        expect(text).toContain('none matched with high enough structural confidence');
        expect(text).not.toContain('most confident structural neighbors');
        // The low-confidence domain data must not leak into the narrative,
        // even though it's technically present in the unfiltered top_domains.
        expect(text).not.toContain('This structure looks similar to');
    });

    it('researcher view is never blocked by the confidence gate, even with zero high-confidence matches', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults({
            annotations: {
                neighbors_considered: 3,
                total_hit_count: 5,
                candidates_examined: 3,
                resolvable_hit_count: 3,
                annotated_neighbor_count: 2,
                unannotated_neighbor_count: 1,
                min_confident_probability: 0.5,
                high_confidence_annotated_count: 0,
                neighbors_with_interactions_count: 0,
                neighbors_with_pathways_count: 0,
                top_domains: [{ name: 'Thionin', type: 'family', neighbor_count: 2 }],
                top_go_terms: [],
                high_confidence_top_domains: [],
                high_confidence_top_go_terms: [],
                per_neighbor: [],
            },
        });
        panel.renderResults();
        panel.element.querySelector('[data-level="researcher"]').click();

        const text = panel.element.querySelector('#discover-results').textContent;
        expect(text).toContain('Thionin');
        expect(text).toContain('Total hits');
        expect(text).not.toContain('none matched with high enough structural confidence');
    });

    it('shows download report/JSON links pointing at the run id when a result has one', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults();
        panel.renderResults();

        const links = Array.from(panel.element.querySelectorAll('#discover-results a')).map(a => a.href);
        expect(links.some(h => h.includes('/api/discover/report?run_id=discover_123'))).toBe(true);
        expect(links.some(h => h.includes('/api/discover/export?run_id=discover_123'))).toBe(true);
    });

    it('omits download links when a result has no id', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults({ id: undefined });
        panel.renderResults();

        const text = panel.element.querySelector('#discover-results').textContent;
        expect(text).not.toContain('Download Report');
        expect(text).not.toContain('Download JSON');
    });

    it('defaults to the student detail level and shows the narrative explanation', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults();
        panel.renderResults();

        expect(panel.detailLevel).toBe('student');
        expect(panel.element.querySelector('#discover-results').textContent).toContain('most confident structural neighbors');
        expect(panel.element.querySelector('#discover-results').textContent).toContain('Thionin');
    });

    it('student and public views degrade gracefully when there are GO terms but no domain matches', () => {
        // annotated_neighbor_count > 0 only guarantees SOME signal (domains
        // OR go_terms), not both - top_domains can be empty on its own.
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults({
            annotations: {
                neighbors_considered: 5,
                total_hit_count: 50,
                candidates_examined: 20,
                resolvable_hit_count: 20,
                annotated_neighbor_count: 3,
                unannotated_neighbor_count: 2,
                min_confident_probability: 0.5,
                high_confidence_annotated_count: 3,
                neighbors_with_interactions_count: 0,
                neighbors_with_pathways_count: 0,
                top_domains: [],
                top_go_terms: [
                    { id: 'GO:0006952', name: 'defense response', aspect: 'biological_process', neighbor_count: 3 },
                ],
                high_confidence_top_domains: [],
                high_confidence_top_go_terms: [
                    { id: 'GO:0006952', name: 'defense response', aspect: 'biological_process', neighbor_count: 3 },
                ],
                per_neighbor: [],
            },
        });

        expect(() => panel.renderResults()).not.toThrow();
        expect(panel.element.querySelector('#discover-results').textContent).toContain('defense response');

        panel.element.querySelector('[data-level="public"]').click();
        expect(panel.element.querySelector('#discover-results').textContent).toContain('defense response');
    });

    it('switching to the public detail level shows the plain-language summary with a caveat', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults();
        panel.renderResults();

        panel.element.querySelector('[data-level="public"]').click();

        const text = panel.element.querySelector('#discover-results').textContent;
        expect(panel.detailLevel).toBe('public');
        expect(text).toContain('Thionin');
        expect(text).toContain('not a confirmed experimental result');
    });

    it('switching to the researcher detail level shows the raw hit table', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults();
        panel.renderResults();

        panel.element.querySelector('[data-level="researcher"]').click();

        const text = panel.element.querySelector('#discover-results').textContent;
        expect(panel.detailLevel).toBe('researcher');
        expect(text).toContain('Total hits');
        expect(text).toContain('Top structural matches');
        expect(panel.element.querySelectorAll('table tbody tr').length).toBeGreaterThan(0);
    });

    it('researcher view shows per-neighbor STRING partners and Reactome pathways when present', () => {
        const panel = new DiscoveryPanel();
        panel.render();
        panel.results = makeAnnotatedResults({
            annotations: {
                neighbors_considered: 10,
                total_hit_count: 1000,
                candidates_examined: 20,
                resolvable_hit_count: 18,
                annotated_neighbor_count: 8,
                unannotated_neighbor_count: 2,
                min_confident_probability: 0.5,
                high_confidence_annotated_count: 8,
                neighbors_with_interactions_count: 1,
                neighbors_with_pathways_count: 0,
                top_domains: [],
                top_go_terms: [],
                high_confidence_top_domains: [],
                high_confidence_top_go_terms: [],
                per_neighbor: [
                    {
                        target: 'AF-P04637-F1-model_v6 Cellular tumor antigen p53',
                        accession: 'P04637',
                        domains: [],
                        go_terms: [],
                        string_partners: [
                            { partner_name: 'MDM2', score: 0.999 },
                            { partner_name: 'MDM4', score: 0.999 },
                        ],
                        reactome_pathways: [],
                    },
                    {
                        target: 'AF-A0A000-F1-model_v6 Some other neighbor',
                        accession: 'A0A000',
                        domains: [],
                        go_terms: [],
                        string_partners: [],
                        reactome_pathways: [],
                    },
                ],
            },
        });
        panel.renderResults();
        panel.element.querySelector('[data-level="researcher"]').click();

        const text = panel.element.querySelector('#discover-results').textContent;
        expect(text).toContain('With STRING interactions');
        expect(text).toContain('MDM2');
        expect(text).toContain('MDM4');
        // The neighbor with no partners/pathways shouldn't clutter the list
        expect(text).not.toContain('A0A000-F1-model_v6 Some other neighbor');
    });

    it('disables the rerun button while a job is in flight and re-enables it after', async () => {
        let resolveSubmit;
        submitDiscoveryJob.mockReturnValue(new Promise((resolve) => { resolveSubmit = resolve; }));

        const panel = new DiscoveryPanel();
        panel.render();

        const runPromise = panel.runFor('1CRN');
        expect(panel.element.querySelector('#discover-rerun-btn').disabled).toBe(true);

        resolveSubmit({ job_id: 'job1', status: 'queued' });
        pollJobUntilDone.mockResolvedValue({ status: 'completed', results: makeAnnotatedResults() });
        await runPromise;

        expect(panel.element.querySelector('#discover-rerun-btn').disabled).toBe(false);
    });

    it('loadSavedResults populates the header and renders a past Discover run when the panel is already rendered', () => {
        const panel = new DiscoveryPanel();
        panel.render();

        panel.loadSavedResults(makeAnnotatedResults());

        expect(panel.element.querySelector('#discovery-panel-pdbid').textContent).toBe('1CRN');
        expect(panel.element.querySelector('#discover-results').textContent).toContain('1CRN');
        expect(panel.detailLevel).toBe('student');
    });

    it('loadSavedResults before the panel has ever rendered still shows results once render() runs', () => {
        const panel = new DiscoveryPanel();
        panel.loadSavedResults(makeAnnotatedResults());

        const el = panel.render();

        expect(el.querySelector('#discovery-panel-pdbid').textContent).toBe('1CRN');
        expect(el.querySelector('#discover-results').textContent).toContain('1CRN');
    });

    describe('database picker', () => {
        it('defaults to pdb100 and afdb50 checked, everything else unchecked', () => {
            const panel = new DiscoveryPanel();
            panel.render();

            const checked = Array.from(panel.element.querySelectorAll('.discover-db-checkbox:checked')).map(cb => cb.dataset.db);
            expect(checked.sort()).toEqual(['afdb50', 'pdb100']);
            expect(panel.element.querySelector('#discover-db-summary').textContent).toContain('2 of');
        });

        it('unchecking/checking a database updates the selection and the summary text', () => {
            const panel = new DiscoveryPanel();
            panel.render();

            const cathBox = panel.element.querySelector('.discover-db-checkbox[data-db="cath50"]');
            cathBox.checked = true;
            cathBox.dispatchEvent(new Event('change'));

            expect(panel.selectedDatabases.has('cath50')).toBe(true);
            expect(panel.element.querySelector('#discover-db-summary').textContent).toContain('3 of');

            const pdbBox = panel.element.querySelector('.discover-db-checkbox[data-db="pdb100"]');
            pdbBox.checked = false;
            pdbBox.dispatchEvent(new Event('change'));

            expect(panel.selectedDatabases.has('pdb100')).toBe(false);
        });

        it('blocks the run with an error when no database is selected', async () => {
            const panel = new DiscoveryPanel();
            panel.render();
            panel.selectedDatabases.clear();

            await panel.runFor('1CRN');

            expect(submitDiscoveryJob).not.toHaveBeenCalled();
            expect(panel.element.querySelector('#discover-error').textContent).toContain('at least one database');
        });

        it('submits whichever databases are currently checked, not just the default set', async () => {
            submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({ status: 'completed', results: makeAnnotatedResults() });

            const panel = new DiscoveryPanel();
            panel.render();

            const mgnifyBox = panel.element.querySelector('.discover-db-checkbox[data-db="mgnify_esm30"]');
            mgnifyBox.checked = true;
            mgnifyBox.dispatchEvent(new Event('change'));

            await panel.runFor('1CRN');

            expect(submitDiscoveryJob).toHaveBeenCalledWith('1CRN', expect.arrayContaining(['pdb100', 'afdb50', 'mgnify_esm30']));
        });

        it("loadSavedResults re-checks the boxes to match the reopened run's actual database list", () => {
            const panel = new DiscoveryPanel();
            panel.render();

            panel.loadSavedResults(makeAnnotatedResults({ databases_searched: ['pdb100', 'cath50'] }));

            const checked = Array.from(panel.element.querySelectorAll('.discover-db-checkbox:checked')).map(cb => cb.dataset.db);
            expect(checked.sort()).toEqual(['cath50', 'pdb100']);
        });

        it('loadSavedResults leaves the picker selection alone for a local-backend run with no recognizable database name', () => {
            const panel = new DiscoveryPanel();
            panel.render();

            panel.loadSavedResults(makeAnnotatedResults({ databases_searched: ['local:/some/db/dir'] }));

            const checked = Array.from(panel.element.querySelectorAll('.discover-db-checkbox:checked')).map(cb => cb.dataset.db);
            expect(checked.sort()).toEqual(['afdb50', 'pdb100']);
        });
    });
});
