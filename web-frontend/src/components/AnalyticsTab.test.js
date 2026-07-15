import { describe, it, expect, vi, afterEach } from 'vitest';
import { AnalyticsTab } from './AnalyticsTab.js';

vi.mock('../api.js', () => ({
    fetchAnnotations: vi.fn(),
}));

import { fetchAnnotations } from '../api.js';

function makeTab(overrides = {}) {
    return new AnalyticsTab(overrides);
}

function structuresFor(pdbIds, chainSelections = {}) {
    return pdbIds.map(pdbId => ({ pdbId, chain: chainSelections[pdbId] }));
}

describe('AnalyticsTab', () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('shows the pre-run placeholder for insights before any run', () => {
        const tab = makeTab();
        tab.render();

        expect(tab.element.querySelectorAll('#analytics-insights-list li')).toHaveLength(0);
        const empty = tab.element.querySelector('#analytics-insights-empty');
        expect(empty.classList.contains('hidden')).toBe(false);
        expect(empty.textContent).toContain('Run alignment');
    });

    it('renders insight bullets with **bold** markdown converted to <strong>', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, [], [
            '**Best Match**: `4RLT` and `3UG9` are nearly identical (0.42 Å).',
            'Plain insight with no markdown.',
        ]);

        const items = tab.element.querySelectorAll('#analytics-insights-list li');
        expect(items).toHaveLength(2);
        expect(items[0].innerHTML).toContain('<strong>Best Match</strong>');
        expect(items[1].textContent).toBe('Plain insight with no markdown.');
        expect(tab.element.querySelector('#analytics-insights-empty').classList.contains('hidden')).toBe(true);
    });

    it('escapes HTML in insight text before applying markdown formatting', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, [], [
            '**Bold** <img src=x onerror=alert(1)>',
        ]);

        const item = tab.element.querySelector('#analytics-insights-list li');
        expect(item.querySelector('img')).toBeNull();
        expect(item.innerHTML).toContain('&lt;img');
        expect(item.innerHTML).toContain('<strong>Bold</strong>');
    });

    it('shows the "no insights" empty state for a completed run with none', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, [], []);

        expect(tab.element.querySelectorAll('#analytics-insights-list li')).toHaveLength(0);
        const empty = tab.element.querySelector('#analytics-insights-empty');
        expect(empty.classList.contains('hidden')).toBe(false);
        expect(empty.textContent).toContain('No automated insights available');
    });

    it('renders a TM-score/GDT-TS row per structure when quality_metrics is present', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, [], [], {
            '4RLT': { tm_score: 0.912, gdt_ts: 0.874 },
            '3UG9': { tm_score: 0.885, gdt_ts: 0.831 },
        });

        const card = tab.element.querySelector('#quality-metrics-table-card');
        expect(card.classList.contains('hidden')).toBe(false);
        const rows = tab.element.querySelectorAll('#quality-metrics-table-body tr');
        expect(rows).toHaveLength(2);
        expect(rows[0].textContent).toContain('4RLT');
        expect(rows[0].textContent).toContain('0.912');
        expect(rows[0].textContent).toContain('0.874');
    });

    it('hides the quality-metrics table when no quality_metrics is given', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, [], []);

        const card = tab.element.querySelector('#quality-metrics-table-card');
        expect(card.classList.contains('hidden')).toBe(true);
    });

    it('renders %helix/%sheet/%coil when secondary_structure_stats is present', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, {
            secondaryStructure: { total_residues: 100, helix_percent: 45.5, sheet_percent: 20.25, coil_percent: 34.25 },
        }, [], []);

        const card = tab.element.querySelector('#secondary-structure-card');
        expect(card.classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('#ss-helix-percent').innerText).toBe('45.5%');
        expect(tab.element.querySelector('#ss-sheet-percent').innerText).toBe('20.3%');
        expect(tab.element.querySelector('#ss-coil-percent').innerText).toBe('34.3%');
    });

    it('hides the secondary-structure section when no stats are given, or when total_residues is 0', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, [], []);
        expect(tab.element.querySelector('#secondary-structure-card').classList.contains('hidden')).toBe(true);

        tab.updateResults('run_1', null, { secondaryStructure: { total_residues: 0, helix_percent: 0, sheet_percent: 0, coil_percent: 0 } }, [], []);
        expect(tab.element.querySelector('#secondary-structure-card').classList.contains('hidden')).toBe(true);
    });

    it('still populates the Ramachandran section from the bundled structuralStats.ramachandran', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, {
            ramachandran: { favored_percent: 92.5, outlier_count: 2, outliers_list: ['PRO12 (Chain A)'] },
        }, [], []);

        expect(tab.element.querySelector('#ramachandran-score').innerText).toBe('92.5%');
        expect(tab.element.querySelector('#ramachandran-outliers').innerText).toBe(2);
    });

    it('sub-tab switching still works, including the new insights sub-tab', () => {
        const tab = makeTab();
        tab.render();

        tab.switchSubTab('insights');
        expect(tab.element.querySelector('[data-panel="insights"]').classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('[data-panel="quality"]').classList.contains('hidden')).toBe(true);

        tab.switchSubTab('rmsf');
        expect(tab.element.querySelector('[data-panel="rmsf"]').classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('[data-panel="insights"]').classList.contains('hidden')).toBe(true);
    });

    describe('functional annotation sub-tab', () => {
        it('loads annotations for a single un-aligned structure (no completed run)', async () => {
            // Regression: this sub-tab used to gate entirely on
            // this.currentRunId, which meant it never worked for a lone
            // structure that had never been through a Compare alignment -
            // fetchAnnotations takes no run_id at all, so there was never
            // a backend reason for that gate.
            fetchAnnotations.mockResolvedValue({
                annotation: {
                    pdb_id: '4HHB', chain: 'A', accession: 'P69905',
                    domains: [{ name: 'Globin', type: 'domain' }],
                    go_terms: [], reactome_pathways: [],
                },
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults(null, null, null, [], [], null, structuresFor(['4HHB'], { '4HHB': 'A' }));

            tab.switchSubTab('annotations');
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(fetchAnnotations).toHaveBeenCalledWith('4HHB', 'A');
            expect(tab.element.querySelector('#annotations-content').textContent).toContain('Globin');
        });

        it('populates the structure picker from selectedPDBs', () => {
            const tab = makeTab();
            tab.render();

            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', 'AF-P69905-F1'], { '4HHB': 'A' }));

            const options = Array.from(tab.element.querySelector('#annotations-structure-select').options).map(o => o.value);
            expect(options).toEqual(['4HHB', 'AF-P69905-F1']);
        });

        it('fetches annotation per structure with its chain and renders domains/GO terms', async () => {
            fetchAnnotations.mockImplementation(async (pdbId) => {
                if (pdbId === '4HHB') {
                    return {
                        annotation: {
                            pdb_id: '4HHB', chain: 'A', accession: 'P69905',
                            domains: [{ name: 'Globin', type: 'domain' }],
                            go_terms: [{ id: 'GO:0005344', name: 'oxygen carrier activity', aspect: 'F' }],
                            reactome_pathways: [],
                        },
                    };
                }
                return {
                    annotation: {
                        pdb_id: 'AF-P69905-F1', chain: null, accession: 'P69905',
                        domains: [{ name: 'Globin', type: 'domain' }],
                        go_terms: [],
                        reactome_pathways: [],
                    },
                };
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', 'AF-P69905-F1'], { '4HHB': 'A' }));

            await tab.loadAllAnnotations();

            expect(fetchAnnotations).toHaveBeenCalledWith('4HHB', 'A');
            expect(fetchAnnotations).toHaveBeenCalledWith('AF-P69905-F1', undefined);
            const content = tab.element.querySelector('#annotations-content');
            expect(content.textContent).toContain('P69905');
            expect(content.textContent).toContain('Globin');
            expect(content.textContent).toContain('oxygen carrier activity');
        });

        it('shows a graceful message when no accession resolves (e.g. an ESM Atlas structure)', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: { pdb_id: 'ESM-MGYP1', chain: null, accession: null, domains: [], go_terms: [], reactome_pathways: [] },
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['ESM-MGYP1']));

            await tab.loadAllAnnotations();

            expect(tab.element.querySelector('#annotations-content').textContent).toContain('No UniProt accession could be resolved');
        });

        it('computes a shared-domains summary across structures that share one', async () => {
            fetchAnnotations.mockImplementation(async (pdbId) => ({
                annotation: {
                    pdb_id: pdbId, chain: null, accession: `ACC_${pdbId}`,
                    domains: [{ name: 'Globin', type: 'domain' }],
                    go_terms: [{ id: 'GO:0005344', name: 'oxygen carrier activity', aspect: 'F' }],
                    reactome_pathways: [],
                },
            }));

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));

            await tab.loadAllAnnotations();

            const sharedSection = tab.element.querySelector('#annotations-shared-section');
            expect(sharedSection.classList.contains('hidden')).toBe(false);
            expect(sharedSection.textContent).toContain('Globin');
            expect(sharedSection.textContent).toContain('oxygen carrier activity');
        });

        it('hides the shared-domains summary for a single-structure run', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: { pdb_id: '4HHB', chain: 'A', accession: 'P69905', domains: [{ name: 'Globin', type: 'domain' }], go_terms: [], reactome_pathways: [] },
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB'], { '4HHB': 'A' }));

            await tab.loadAllAnnotations();

            expect(tab.element.querySelector('#annotations-shared-section').classList.contains('hidden')).toBe(true);
        });

        it('shows a "Highlight in 3D" button for a domain with highlight_chains and calls onHighlightResidues when clicked', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: {
                    pdb_id: 'AF-P69905-F1', chain: 'A', accession: 'P69905',
                    domains: [{ name: 'Globin', type: 'domain', highlight_chains: { A: [2, 3, 4, 5] } }],
                    go_terms: [], reactome_pathways: [],
                },
            });
            const onHighlightResidues = vi.fn();
            const tab = makeTab({ onHighlightResidues });
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['AF-P69905-F1'], { 'AF-P69905-F1': 'A' }));

            await tab.loadAllAnnotations();

            const btn = tab.element.querySelector('.domain-highlight-btn');
            expect(btn.textContent).toContain('Highlight in 3D');
            btn.click();
            expect(onHighlightResidues).toHaveBeenCalledWith({ A: [2, 3, 4, 5] });
        });

        it('omits the "Highlight in 3D" button for a domain with no highlight_chains (e.g. a plain PDB structure)', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: {
                    pdb_id: '4HHB', chain: 'A', accession: 'P69905',
                    domains: [{ name: 'Globin', type: 'domain', highlight_chains: null }],
                    go_terms: [], reactome_pathways: [],
                },
            });
            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB'], { '4HHB': 'A' }));

            await tab.loadAllAnnotations();

            expect(tab.element.querySelector('.domain-highlight-btn')).toBeNull();
        });

        it('does not re-fetch when switching back to an already-loaded run', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: { pdb_id: '4HHB', chain: 'A', accession: 'P69905', domains: [], go_terms: [], reactome_pathways: [] },
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB'], { '4HHB': 'A' }));
            await tab.loadAllAnnotations();
            fetchAnnotations.mockClear();

            tab.switchSubTab('quality');
            tab.switchSubTab('annotations');

            expect(fetchAnnotations).not.toHaveBeenCalled();
        });
    });
});
