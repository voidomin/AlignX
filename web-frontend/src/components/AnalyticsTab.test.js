import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AnalyticsTab } from './AnalyticsTab.js';

vi.mock('../api.js', () => ({
    fetchAnnotations: vi.fn(),
    fetchContactMap: vi.fn(),
    fetchDifferenceDistance: vi.fn(),
    fetchMutationImpact: vi.fn(),
}));

import { fetchAnnotations, fetchContactMap, fetchDifferenceDistance, fetchMutationImpact } from '../api.js';

function makeTab(overrides = {}) {
    return new AnalyticsTab(overrides);
}

function structuresFor(pdbIds, chainSelections = {}) {
    return pdbIds.map(pdbId => ({ pdbId, chain: chainSelections[pdbId] }));
}

describe('AnalyticsTab', () => {
    beforeEach(() => {
        global.Plotly = { newPlot: vi.fn() };
    });

    afterEach(() => {
        vi.clearAllMocks();
        delete global.Plotly;
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

    it('renders a pairwise TM-score row per pair when tmScoreMatrix is present', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, {
            tmScoreMatrix: {
                index: ['4RLT', '3UG9', '1ABC'],
                columns: ['4RLT', '3UG9', '1ABC'],
                data: [
                    [1.0, 0.812, 0.55],
                    [0.812, 1.0, 0.61],
                    [0.55, 0.61, 1.0],
                ],
            },
        }, [], []);

        const card = tab.element.querySelector('#pairwise-tm-score-card');
        expect(card.classList.contains('hidden')).toBe(false);
        const rows = tab.element.querySelectorAll('#pairwise-tm-score-table-body tr');
        expect(rows).toHaveLength(3);
        expect(rows[0].textContent).toContain('4RLT');
        expect(rows[0].textContent).toContain('3UG9');
        expect(rows[0].textContent).toContain('0.812');
    });

    it('hides the pairwise TM-score table when no tmScoreMatrix is given, or for a single structure', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, [], []);
        expect(tab.element.querySelector('#pairwise-tm-score-card').classList.contains('hidden')).toBe(true);

        tab.updateResults('run_1', null, { tmScoreMatrix: { index: ['4RLT'], columns: ['4RLT'], data: [[1.0]] } }, [], []);
        expect(tab.element.querySelector('#pairwise-tm-score-card').classList.contains('hidden')).toBe(true);
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

        it('shows a "Highlight in 3D" button for a UniProt feature with highlight_chains and calls onHighlightResidues when clicked', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: {
                    pdb_id: 'AF-P69905-F1', chain: 'A', accession: 'P69905',
                    domains: [], go_terms: [], reactome_pathways: [],
                    uniprot_features: [{ type: 'Binding site', description: 'proximal binding residue', start: 88, end: 88, highlight_chains: { A: [88] } }],
                },
            });
            const onHighlightResidues = vi.fn();
            const tab = makeTab({ onHighlightResidues });
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['AF-P69905-F1'], { 'AF-P69905-F1': 'A' }));

            await tab.loadAllAnnotations();

            const btn = tab.element.querySelector('.feature-highlight-btn');
            expect(btn.textContent).toContain('Highlight in 3D');
            btn.click();
            expect(onHighlightResidues).toHaveBeenCalledWith({ A: [88] });
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

    describe('contact map & difference-distance matrix', () => {
        it('populates both selectors from the structure list', () => {
            const tab = makeTab();
            tab.render();

            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));

            const single = tab.element.querySelector('#contact-map-pdb-select');
            expect(Array.from(single.options).map(o => o.value)).toEqual(['4HHB', '2HHB']);
            const pairB = tab.element.querySelector('#diff-distance-pdb-b-select');
            expect(pairB.value).toBe('2HHB');
        });

        it('loads and renders a dense contact map heatmap on button click', async () => {
            fetchContactMap.mockResolvedValue({
                pdb_id: '4HHB', residue_count: 2, capped: false,
                matrix: [[0, 1], [1, 0]], contacts: null,
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));

            tab.element.querySelector('#contact-map-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(fetchContactMap).toHaveBeenCalledWith('run_1', '4HHB');
            expect(global.Plotly.newPlot).toHaveBeenCalled();
        });

        it('shows a message instead of a heatmap when the contact map is capped', async () => {
            fetchContactMap.mockResolvedValue({
                pdb_id: '4HHB', residue_count: 5000, capped: true,
                matrix: null, contacts: [[0, 1], [2, 3]],
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));

            tab.element.querySelector('#contact-map-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(global.Plotly.newPlot).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#contact-map-plotly').textContent).toContain('5000 residues');
        });

        it('shows a graceful message when the contact map fetch fails', async () => {
            fetchContactMap.mockRejectedValue(new Error('boom'));

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));

            tab.element.querySelector('#contact-map-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#contact-map-plotly').textContent).toContain('Failed to load contact map.');
        });

        it('loads and renders a dense difference-distance heatmap on button click', async () => {
            fetchDifferenceDistance.mockResolvedValue({
                pdb_id_a: '4HHB', pdb_id_b: '2HHB', column_count: 2, capped: false,
                matrix: [[0, 1.2], [1.2, 0]], differences: null,
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));

            tab.element.querySelector('#diff-distance-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(fetchDifferenceDistance).toHaveBeenCalledWith('run_1', '4HHB', '2HHB');
            expect(global.Plotly.newPlot).toHaveBeenCalled();
        });

        it('refuses to load a difference-distance matrix for the same structure twice', async () => {
            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));
            tab.element.querySelector('#diff-distance-pdb-b-select').value = '4HHB';

            tab.element.querySelector('#diff-distance-load-btn').click();
            await Promise.resolve();

            expect(fetchDifferenceDistance).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#diff-distance-plotly').textContent)
                .toContain('Select two different structures.');
        });

        it('shows a message instead of a heatmap when the difference-distance matrix is capped', async () => {
            fetchDifferenceDistance.mockResolvedValue({
                pdb_id_a: '4HHB', pdb_id_b: '2HHB', column_count: 5000, capped: true,
                matrix: null, differences: [[0, 1, 4.2]],
            });

            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB', '2HHB']));

            tab.element.querySelector('#diff-distance-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(global.Plotly.newPlot).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#diff-distance-plotly').textContent).toContain('5000 aligned columns');
        });
    });

    describe('map a mutation', () => {
        function setUpForMutation(tab) {
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB'], { '4HHB': 'A' }));
            tab.element.querySelector('#mutation-resi-input').value = '6';
            tab.element.querySelector('#mutation-mutant-input').value = 'V';
        }

        it('fetches and renders a real-looking mutation impact result', async () => {
            fetchMutationImpact.mockResolvedValue({
                accession: 'P68871', uniprot_position: 7, wildtype_residue: 'V', mutant_residue: 'V',
                gene: 'HBB',
                clinvar: { clinical_significance: 'Pathogenic', review_status: 'reviewed by expert panel' },
                known_uniprot_variant: null,
                highlight_chains: { A: [6] },
            });

            const tab = makeTab();
            tab.render();
            setUpForMutation(tab);

            tab.element.querySelector('#mutation-map-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(fetchMutationImpact).toHaveBeenCalledWith('4HHB', 'A', 6, 'V');
            const result = tab.element.querySelector('#mutation-impact-result');
            expect(result.textContent).toContain('P68871');
            expect(result.textContent).toContain('Pathogenic');
        });

        it('shows a known UniProt variant when ClinVar has no match', async () => {
            fetchMutationImpact.mockResolvedValue({
                accession: 'P68871', uniprot_position: 7, wildtype_residue: 'V', mutant_residue: 'V',
                gene: 'HBB', clinvar: null,
                known_uniprot_variant: { type: 'Natural variant', description: 'in HBS', start: 7, end: 7 },
                highlight_chains: { A: [6] },
            });

            const tab = makeTab();
            tab.render();
            setUpForMutation(tab);

            tab.element.querySelector('#mutation-map-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            const result = tab.element.querySelector('#mutation-impact-result');
            expect(result.textContent).toContain('No matching ClinVar record found.');
            expect(result.textContent).toContain('in HBS');
        });

        it('triggers onHighlightResidues when "Highlight in 3D" is clicked', async () => {
            fetchMutationImpact.mockResolvedValue({
                accession: 'P68871', uniprot_position: 7, wildtype_residue: 'V', mutant_residue: 'V',
                gene: 'HBB', clinvar: null, known_uniprot_variant: null,
                highlight_chains: { A: [6] },
            });
            const onHighlightResidues = vi.fn();
            const tab = makeTab({ onHighlightResidues });
            tab.render();
            setUpForMutation(tab);

            tab.element.querySelector('#mutation-map-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            tab.element.querySelector('#mutation-impact-result button').click();
            expect(onHighlightResidues).toHaveBeenCalledWith({ A: [6] });
        });

        it('shows a validation message instead of fetching when inputs are incomplete', async () => {
            const tab = makeTab();
            tab.render();
            tab.updateResults('run_1', null, null, [], [], null, structuresFor(['4HHB'], { '4HHB': 'A' }));
            tab.element.querySelector('#mutation-resi-input').value = '';
            tab.element.querySelector('#mutation-mutant-input').value = 'V';

            tab.element.querySelector('#mutation-map-btn').click();
            await Promise.resolve();

            expect(fetchMutationImpact).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#mutation-impact-result').textContent)
                .toContain('Enter a residue number and a mutant residue.');
        });

        it('shows a graceful message when the fetch fails', async () => {
            fetchMutationImpact.mockRejectedValue(new Error('boom'));

            const tab = makeTab();
            tab.render();
            setUpForMutation(tab);

            tab.element.querySelector('#mutation-map-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#mutation-impact-result').textContent)
                .toContain('Failed to map this mutation.');
        });
    });
});
