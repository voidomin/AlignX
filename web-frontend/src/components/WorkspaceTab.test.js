import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WorkspaceTab } from './WorkspaceTab.js';

vi.mock('../api.js', () => ({
    fetchSuggestions: vi.fn(),
    isValidPdbId: vi.fn((id) => /^[0-9A-Z]{4}$/.test(id) || /^(AF|SM|ESM)-/.test(id)),
    submitDiscoveryJob: vi.fn(),
    pollJobUntilDone: vi.fn(),
    getDiscoveryReportUrl: vi.fn((runId) => `http://mock/api/discover/report?run_id=${runId}`),
    getDiscoveryExportUrl: vi.fn((runId) => `http://mock/api/discover/export?run_id=${runId}`),
    getDiscoveryCitationsUrl: vi.fn((runId) => `http://mock/api/discover/citations?run_id=${runId}`),
    fetchValidation: vi.fn(),
    fetchQc: vi.fn(),
    fetchCathClassification: vi.fn(),
    fetchAssemblyInfo: vi.fn(),
}));

import { submitDiscoveryJob, pollJobUntilDone, fetchValidation, fetchQc, fetchCathClassification, fetchAssemblyInfo } from '../api.js';

function makeTab(overrides = {}) {
    return new WorkspaceTab({
        selectedPDBs: [],
        chainSelections: {},
        pdbMetadata: {},
        onAddPDB: vi.fn(),
        onAddManyPDBs: vi.fn().mockResolvedValue({ added: [], overCap: 0 }),
        onUploadStructure: vi.fn().mockResolvedValue(undefined),
        onPredictFromSequence: vi.fn().mockResolvedValue(undefined),
        onRemovePDB: vi.fn(),
        onChainSelection: vi.fn(),
        onRunAlignment: vi.fn(),
        onQuickStart: vi.fn(),
        ...overrides,
    });
}

describe('WorkspaceTab', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('shows the empty-state message and a "0 Proteins" badge with no structures selected', () => {
        const tab = makeTab();
        tab.render();

        expect(tab.element.querySelector('#workspace-pdb-count-badge').innerText).toBe('0 Proteins');
        expect(tab.element.querySelector('#workspace-pdb-list-container').textContent)
            .toContain('Add a structure to analyze it on its own, or 2+ to align them');
    });

    describe('first-run onboarding hint', () => {
        it('shows the hint on a fresh visit and dismisses it permanently on click', () => {
            const tab = makeTab();
            tab.render();

            const hint = tab.element.querySelector('#workspace-onboarding-hint');
            expect(hint).not.toBeNull();

            hint.querySelector('#workspace-onboarding-dismiss-btn').click();

            expect(tab.element.querySelector('#workspace-onboarding-hint')).toBeNull();
            expect(localStorage.getItem('structscope:onboarding-dismissed')).toBe('true');
        });

        it('does not show the hint again after a previous dismissal, even across a workspace reset', () => {
            localStorage.setItem('structscope:onboarding-dismissed', 'true');
            const tab = makeTab();
            tab.render();

            expect(tab.element.querySelector('#workspace-onboarding-hint')).toBeNull();

            // Simulate the empty state re-rendering after a "New Workspace" reset.
            tab.selectedPDBs = [];
            tab.refreshPDBList();
            expect(tab.element.querySelector('#workspace-onboarding-hint')).toBeNull();
        });

        it('never shows the hint in a shared/read-only view', () => {
            const tab = makeTab({ isSharedView: true });
            tab.render();

            expect(tab.element.querySelector('#workspace-onboarding-hint')).toBeNull();
        });
    });

    it('shows quick-start example buttons in the empty state', () => {
        const tab = makeTab();
        tab.render();

        const buttons = tab.element.querySelectorAll('#workspace-quick-start .quick-start-btn');
        expect(buttons.length).toBeGreaterThan(0);
    });

    it('clicking a quick-start example calls onQuickStart with its PDB IDs', () => {
        const onQuickStart = vi.fn();
        const tab = makeTab({ onQuickStart });
        tab.render();

        tab.element.querySelector('#workspace-quick-start .quick-start-btn').click();

        expect(onQuickStart).toHaveBeenCalledWith(expect.any(Array));
    });

    it('hides quick-start examples once structures are selected', () => {
        const tab = makeTab({ selectedPDBs: ['4RLT', '3UG9'] });
        tab.render();

        expect(tab.element.querySelector('#workspace-quick-start')).toBeNull();
    });

    it('calls onAddPDB with the uppercased 4-char input on Add click, and clears the input', () => {
        const onAddPDB = vi.fn();
        const tab = makeTab({ onAddPDB });
        tab.render();

        const input = tab.element.querySelector('#workspace-add-pdb-input');
        input.value = '4rlt';
        tab.element.querySelector('#workspace-add-pdb-btn').click();

        expect(onAddPDB).toHaveBeenCalledWith('4RLT');
        expect(input.value).toBe('');
    });

    it('does not call onAddPDB for input that is not exactly 4 characters', () => {
        const onAddPDB = vi.fn();
        const tab = makeTab({ onAddPDB });
        tab.render();

        tab.element.querySelector('#workspace-add-pdb-input').value = '4rl';
        tab.element.querySelector('#workspace-add-pdb-btn').click();

        expect(onAddPDB).not.toHaveBeenCalled();
    });

    it('adds a PDB on Enter keypress in the input field', () => {
        const onAddPDB = vi.fn();
        const tab = makeTab({ onAddPDB });
        tab.render();

        const input = tab.element.querySelector('#workspace-add-pdb-input');
        input.value = '3ug9';
        input.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter' }));

        expect(onAddPDB).toHaveBeenCalledWith('3UG9');
    });

    it('accepts AlphaFold, SWISS-MODEL, and ESM Atlas accessions, not just 4-char PDB IDs', () => {
        const onAddPDB = vi.fn();
        const tab = makeTab({ onAddPDB });
        tab.render();
        const input = tab.element.querySelector('#workspace-add-pdb-input');
        const addBtn = tab.element.querySelector('#workspace-add-pdb-btn');

        input.value = 'af-p69905-f1';
        addBtn.click();
        expect(onAddPDB).toHaveBeenCalledWith('AF-P69905-F1');

        input.value = 'sm-p69905';
        addBtn.click();
        expect(onAddPDB).toHaveBeenCalledWith('SM-P69905');

        input.value = 'esm-mgyp002537940442';
        addBtn.click();
        expect(onAddPDB).toHaveBeenCalledWith('ESM-MGYP002537940442');
    });

    it('renders one row per selected PDB with chain options from metadata', () => {
        const tab = makeTab({
            selectedPDBs: ['4RLT', '3UG9'],
            chainSelections: { '4RLT': 'B' },
            pdbMetadata: {
                '4RLT': { chains: [{ id: 'A', residue_count: 100 }, { id: 'B', residue_count: 90 }] },
            },
        });
        tab.render();

        expect(tab.element.querySelector('#workspace-pdb-count-badge').innerText).toBe('2 Proteins');
        const rows = tab.element.querySelectorAll('#workspace-pdb-list-container > div');
        expect(rows).toHaveLength(2);

        const select4RLT = rows[0].querySelector('select');
        expect(select4RLT.querySelectorAll('option')).toHaveLength(2);
        expect(select4RLT.querySelector('option[value="B"]').selected).toBe(true);
        expect(select4RLT.querySelector('option[value="A"]').textContent).toBe('Chain A (100 residues)');

        // 3UG9 has no metadata -> falls back to a single Chain A option
        const select3UG9 = rows[1].querySelector('select');
        expect(select3UG9.querySelectorAll('option')).toHaveLength(1);
    });

    it('shows a source badge and metadata line for each structure once metadata loads', () => {
        const tab = makeTab({
            selectedPDBs: ['4RLT', 'AF-P69905-F1'],
            pdbMetadata: {
                '4RLT': {
                    chains: [{ id: 'A', residue_count: 100 }],
                    source: 'pdb',
                    method: 'X-RAY DIFFRACTION',
                    resolution: '2.10 Å',
                    organism: 'Homo sapiens',
                },
                'AF-P69905-F1': {
                    chains: [{ id: 'A', residue_count: 141 }],
                    source: 'alphafold',
                    method: 'Predicted (AF2)',
                    resolution: 'pLDDT Scored',
                    organism: 'Homo sapiens',
                },
            },
        });
        tab.render();

        const rows = tab.element.querySelectorAll('#workspace-pdb-list-container > div');
        expect(rows[0].querySelector('.source-badge').textContent).toBe('PDB');
        expect(rows[0].querySelector('.pdb-meta-line').textContent)
            .toBe('X-RAY DIFFRACTION · 2.10 Å · Homo sapiens');

        expect(rows[1].querySelector('.source-badge').textContent).toBe('AlphaFold');
        expect(rows[1].querySelector('.pdb-meta-line').textContent)
            .toBe('Predicted (AF2) · pLDDT Scored · Homo sapiens');
    });

    describe('wwPDB validation badge', () => {
        function makePdbTab(overrides = {}) {
            return makeTab({
                selectedPDBs: ['4HHB'],
                pdbMetadata: {
                    '4HHB': { chains: [{ id: 'A', residue_count: 141 }], source: 'pdb' },
                },
                ...overrides,
            });
        }

        it('shows a "checking" placeholder immediately, then the real metrics once the fetch resolves', async () => {
            let resolveFetch;
            fetchValidation.mockReturnValue(new Promise(r => { resolveFetch = r; }));
            const tab = makePdbTab();
            tab.render();

            const badge = tab.element.querySelector('#validation-badge-4HHB');
            expect(badge.textContent).toBe('Checking wwPDB validation…');

            resolveFetch({
                pdb_id: '4HHB',
                validation: {
                    clashscore: { value: 1.2, percentile_archive: 85.4 },
                    percent_rama_outliers: { value: 1.24, percentile_archive: 12.8 },
                },
            });
            await Promise.resolve();
            await Promise.resolve();

            expect(badge.textContent).toContain('Clashscore 1.2');
            expect(badge.textContent).toContain('archive percentile 85');
            expect(badge.textContent).toContain('Rama outliers 1.2%');
        });

        it('shows a graceful message when no validation report is available', async () => {
            fetchValidation.mockResolvedValue({ pdb_id: '4HHB', validation: null });
            const tab = makePdbTab();
            tab.render();

            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#validation-badge-4HHB').textContent)
                .toBe('No wwPDB validation report available');
        });

        it('shows a graceful message when the fetch itself fails', async () => {
            fetchValidation.mockRejectedValue(new Error('network down'));
            const tab = makePdbTab();
            tab.render();

            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#validation-badge-4HHB').textContent)
                .toBe('No wwPDB validation report available');
        });

        it('omits the badge entirely for non-"pdb"-source structures', () => {
            fetchValidation.mockClear();
            const tab = makeTab({
                selectedPDBs: ['AF-P69905-F1'],
                pdbMetadata: { 'AF-P69905-F1': { chains: [{ id: 'A', residue_count: 141 }], source: 'alphafold' } },
            });
            tab.render();

            expect(tab.element.querySelector('.pdb-validation-badge')).toBeNull();
            expect(fetchValidation).not.toHaveBeenCalled();
        });

        it('only fetches once per structure across re-renders', async () => {
            fetchValidation.mockResolvedValue({ pdb_id: '4HHB', validation: null });
            const tab = makePdbTab();
            tab.render();
            await Promise.resolve();
            await Promise.resolve();
            fetchValidation.mockClear();

            tab.updateState(['4HHB'], {}, { '4HHB': { chains: [{ id: 'A', residue_count: 141 }], source: 'pdb' } });

            expect(fetchValidation).not.toHaveBeenCalled();
        });
    });

    describe('CATH classification badge', () => {
        function makePdbTab(overrides = {}) {
            fetchValidation.mockResolvedValue({ pdb_id: '4HHB', validation: null });
            return makeTab({
                selectedPDBs: ['4HHB'],
                pdbMetadata: {
                    '4HHB': { chains: [{ id: 'A', residue_count: 141 }], source: 'pdb' },
                },
                ...overrides,
            });
        }

        it('shows a "checking" placeholder immediately, then the classification once the fetch resolves', async () => {
            let resolveFetch;
            fetchCathClassification.mockReturnValue(new Promise(r => { resolveFetch = r; }));
            const tab = makePdbTab();
            tab.render();

            const badge = tab.element.querySelector('#cath-badge-4HHB');
            expect(badge.textContent).toBe('Checking CATH classification…');

            resolveFetch({
                pdb_id: '4HHB',
                domains: [
                    { chain_id: 'A', domain: '4hhbA00', classification: '1.10.490.10' },
                    { chain_id: 'B', domain: '4hhbB00', classification: '1.10.490.10' },
                ],
            });
            await Promise.resolve();
            await Promise.resolve();

            expect(badge.textContent).toBe('CATH 1.10.490.10');
        });

        it('shows a "+N more" suffix when more than one distinct classification exists', async () => {
            fetchCathClassification.mockResolvedValue({
                pdb_id: '1ABC',
                domains: [
                    { chain_id: 'A', domain: '1abcA00', classification: '1.10.490.10' },
                    { chain_id: 'A', domain: '1abcA01', classification: '2.40.50.140' },
                ],
            });
            const tab = makePdbTab();
            tab.render();

            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#cath-badge-4HHB').textContent)
                .toBe('CATH 1.10.490.10 (+1 more)');
        });

        it('shows a graceful message when no classification is available', async () => {
            fetchCathClassification.mockResolvedValue({ pdb_id: '4HHB', domains: [] });
            const tab = makePdbTab();
            tab.render();

            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#cath-badge-4HHB').textContent)
                .toBe('No CATH classification available');
        });

        it('shows a graceful message when the fetch itself fails', async () => {
            fetchCathClassification.mockRejectedValue(new Error('network down'));
            const tab = makePdbTab();
            tab.render();

            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#cath-badge-4HHB').textContent)
                .toBe('No CATH classification available');
        });

        it('omits the badge entirely for non-"pdb"-source structures', () => {
            fetchCathClassification.mockClear();
            const tab = makeTab({
                selectedPDBs: ['AF-P69905-F1'],
                pdbMetadata: { 'AF-P69905-F1': { chains: [{ id: 'A', residue_count: 141 }], source: 'alphafold' } },
            });
            tab.render();

            expect(tab.element.querySelector('.pdb-cath-badge')).toBeNull();
            expect(fetchCathClassification).not.toHaveBeenCalled();
        });

        it('only fetches once per structure across re-renders', async () => {
            fetchCathClassification.mockResolvedValue({ pdb_id: '4HHB', domains: [] });
            const tab = makePdbTab();
            tab.render();
            await Promise.resolve();
            await Promise.resolve();
            fetchCathClassification.mockClear();

            tab.updateState(['4HHB'], {}, { '4HHB': { chains: [{ id: 'A', residue_count: 141 }], source: 'pdb' } });

            expect(fetchCathClassification).not.toHaveBeenCalled();
        });
    });

    describe('oligomeric assembly badge', () => {
        function makePdbTab(overrides = {}) {
            fetchValidation.mockResolvedValue({ pdb_id: '4HHB', validation: null });
            fetchCathClassification.mockResolvedValue({ pdb_id: '4HHB', domains: [] });
            return makeTab({
                selectedPDBs: ['4HHB'],
                pdbMetadata: {
                    '4HHB': { chains: [{ id: 'A', residue_count: 141 }], source: 'pdb' },
                },
                ...overrides,
            });
        }

        it('shows a "checking" placeholder immediately, then the oligomeric state once the fetch resolves', async () => {
            let resolveFetch;
            fetchAssemblyInfo.mockReturnValue(new Promise(r => { resolveFetch = r; }));
            const tab = makePdbTab();
            tab.render();

            const badge = tab.element.querySelector('#assembly-badge-4HHB');
            expect(badge.textContent).toBe('Checking assembly state…');

            resolveFetch({
                pdb_id: '4HHB',
                assembly: { oligomeric_count: 4, oligomeric_details: 'tetrameric' },
            });
            await Promise.resolve();
            await Promise.resolve();

            expect(badge.textContent).toBe('Tetrameric');
        });

        it('shows a graceful message when no assembly state is available', async () => {
            fetchAssemblyInfo.mockResolvedValue({ pdb_id: '4HHB', assembly: null });
            const tab = makePdbTab();
            tab.render();

            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#assembly-badge-4HHB').textContent)
                .toBe('No assembly state available');
        });

        it('shows a graceful message when the fetch itself fails', async () => {
            fetchAssemblyInfo.mockRejectedValue(new Error('network down'));
            const tab = makePdbTab();
            tab.render();

            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#assembly-badge-4HHB').textContent)
                .toBe('No assembly state available');
        });

        it('omits the badge entirely for non-"pdb"-source structures', () => {
            fetchAssemblyInfo.mockClear();
            const tab = makeTab({
                selectedPDBs: ['AF-P69905-F1'],
                pdbMetadata: { 'AF-P69905-F1': { chains: [{ id: 'A', residue_count: 141 }], source: 'alphafold' } },
            });
            tab.render();

            expect(tab.element.querySelector('.pdb-assembly-badge')).toBeNull();
            expect(fetchAssemblyInfo).not.toHaveBeenCalled();
        });

        it('only fetches once per structure across re-renders', async () => {
            fetchAssemblyInfo.mockResolvedValue({ pdb_id: '4HHB', assembly: null });
            const tab = makePdbTab();
            tab.render();
            await Promise.resolve();
            await Promise.resolve();
            fetchAssemblyInfo.mockClear();

            tab.updateState(['4HHB'], {}, { '4HHB': { chains: [{ id: 'A', residue_count: 141 }], source: 'pdb' } });

            expect(fetchAssemblyInfo).not.toHaveBeenCalled();
        });
    });

    it('shows an NMR badge when the structure is a multi-model ensemble', () => {
        const tab = makeTab({
            selectedPDBs: ['1AJU'],
            pdbMetadata: {
                '1AJU': {
                    chains: [{ id: 'A', residue_count: 40, gaps: [] }],
                    is_nmr: true,
                    num_models: 20,
                },
            },
        });
        tab.render();

        const row = tab.element.querySelector('#workspace-pdb-list-container > div');
        expect(row.querySelector('.pdb-nmr-badge').textContent).toBe('NMR · 20 models (model 1 shown)');
    });

    it('omits the NMR badge for a single-model structure', () => {
        const tab = makeTab({
            selectedPDBs: ['4RLT'],
            pdbMetadata: {
                '4RLT': { chains: [{ id: 'A', residue_count: 100, gaps: [] }], is_nmr: false, num_models: 1 },
            },
        });
        tab.render();

        expect(tab.element.querySelector('.pdb-nmr-badge')).toBeNull();
    });

    it('shows a disordered-region badge when a chain has residue-numbering gaps', () => {
        const tab = makeTab({
            selectedPDBs: ['4RLT'],
            pdbMetadata: {
                '4RLT': {
                    chains: [
                        { id: 'A', residue_count: 100, gaps: [{ after: 20, before: 25 }] },
                    ],
                },
            },
        });
        tab.render();

        const row = tab.element.querySelector('#workspace-pdb-list-container > div');
        const badge = row.querySelector('.pdb-gaps-badge');
        expect(badge.textContent).toBe('1 disordered region');
        expect(badge.title).toContain('residues 21-24 missing');
    });

    it('omits the disordered-region badge when there are no gaps', () => {
        const tab = makeTab({
            selectedPDBs: ['4RLT'],
            pdbMetadata: {
                '4RLT': { chains: [{ id: 'A', residue_count: 100, gaps: [] }] },
            },
        });
        tab.render();

        expect(tab.element.querySelector('.pdb-gaps-badge')).toBeNull();
    });

    it('shows a PubMed link when the structure has a real primary citation with a PubMed ID', () => {
        const tab = makeTab({
            selectedPDBs: ['4HHB'],
            pdbMetadata: {
                '4HHB': {
                    chains: [{ id: 'A', residue_count: 141, gaps: [] }],
                    source: 'pdb',
                    citation: {
                        pubmed_id: 6726807,
                        doi: '10.1016/0022-2836(84)90472-8',
                        authors: ['Fermi, G.'],
                        title: 'The crystal structure of human deoxyhaemoglobin',
                    },
                },
            },
        });
        tab.render();

        const row = tab.element.querySelector('#workspace-pdb-list-container > div');
        const link = row.querySelector('.pdb-citation-link');
        expect(link.textContent).toBe('View publication (PubMed)');
        expect(link.href).toBe('https://pubmed.ncbi.nlm.nih.gov/6726807/');
        expect(link.title).toBe('The crystal structure of human deoxyhaemoglobin');
    });

    it('falls back to a DOI link when there is no PubMed ID', () => {
        const tab = makeTab({
            selectedPDBs: ['4HHB'],
            pdbMetadata: {
                '4HHB': {
                    chains: [{ id: 'A', residue_count: 141, gaps: [] }],
                    source: 'pdb',
                    citation: { pubmed_id: null, doi: '10.1016/0022-2836(84)90472-8', authors: [], title: null },
                },
            },
        });
        tab.render();

        const link = tab.element.querySelector('.pdb-citation-link');
        expect(link.textContent).toBe('View publication (DOI)');
        expect(link.href).toBe('https://doi.org/10.1016/0022-2836(84)90472-8');
    });

    it('omits the citation link when the structure has no primary citation', () => {
        const tab = makeTab({
            selectedPDBs: ['4RLT'],
            pdbMetadata: {
                '4RLT': { chains: [{ id: 'A', residue_count: 100, gaps: [] }], citation: null },
            },
        });
        tab.render();

        expect(tab.element.querySelector('.pdb-citation-link')).toBeNull();
    });

    it('defaults to a "PDB" badge and omits the metadata line while metadata has not loaded yet', () => {
        const tab = makeTab({ selectedPDBs: ['4RLT'] });
        tab.render();

        const row = tab.element.querySelector('#workspace-pdb-list-container > div');
        expect(row.querySelector('.source-badge').textContent).toBe('PDB');
        expect(row.querySelector('.pdb-meta-line')).toBeNull();
    });

    it('fires onChainSelection and onRemovePDB from row controls', () => {
        const onChainSelection = vi.fn();
        const onRemovePDB = vi.fn();
        const tab = makeTab({
            selectedPDBs: ['4RLT'],
            pdbMetadata: { '4RLT': { chains: [{ id: 'A', residue_count: 100 }, { id: 'B', residue_count: 90 }] } },
            onChainSelection,
            onRemovePDB,
        });
        tab.render();

        const select = tab.element.querySelector('.chain-select');
        select.value = 'B';
        select.dispatchEvent(new Event('change'));
        expect(onChainSelection).toHaveBeenCalledWith('4RLT', 'B');

        tab.element.querySelector('.remove-pdb-btn').click();
        expect(onRemovePDB).toHaveBeenCalledWith('4RLT');
    });

    it('shows a loading state instead of the PDB list while chains are loading', () => {
        const tab = makeTab({ selectedPDBs: ['4RLT'] });
        tab.render();
        tab.setLoadingChains(true);

        expect(tab.element.querySelector('#workspace-pdb-list-container').textContent)
            .toContain('Loading structure chains...');
    });

    it('getParameters reflects the checkbox states', () => {
        const tab = makeTab();
        tab.render();

        expect(tab.getParameters()).toEqual({ removeWater: true, removeHeteroatoms: true });

        tab.element.querySelector('#param-remove-water').checked = false;
        expect(tab.getParameters().removeWater).toBe(false);
    });

    it('setAligning toggles the run button label and disabled state', () => {
        const tab = makeTab({ selectedPDBs: ['4RLT', '3UG9'] });
        tab.render();
        const runBtn = tab.element.querySelector('#workspace-run-btn');

        tab.setAligning(true);
        expect(runBtn.disabled).toBe(true);
        expect(runBtn.textContent).toContain('Aligning Pipeline...');

        tab.setAligning(false);
        expect(runBtn.disabled).toBe(false);
        expect(runBtn.textContent).toContain('Run Structural Alignment');
    });

    it('calls onRunAlignment when the run button is clicked with 2+ structures', () => {
        const onRunAlignment = vi.fn();
        const tab = makeTab({ selectedPDBs: ['4RLT', '3UG9'], onRunAlignment });
        tab.render();

        tab.element.querySelector('#workspace-run-btn').click();
        expect(onRunAlignment).toHaveBeenCalled();
    });

    describe('Run Structural Alignment gating', () => {
        it('hides the run button with 0 or 1 structures', () => {
            const tab = makeTab();
            tab.render();
            expect(tab.element.querySelector('#workspace-run-btn').classList.contains('hidden')).toBe(true);

            tab.updateState(['4RLT'], {}, {});
            expect(tab.element.querySelector('#workspace-run-btn').classList.contains('hidden')).toBe(true);
        });

        it('shows the run button once there are 2+ structures', () => {
            const tab = makeTab();
            tab.render();

            tab.updateState(['4RLT', '3UG9'], {}, {});

            expect(tab.element.querySelector('#workspace-run-btn').classList.contains('hidden')).toBe(false);
        });

        it('does not call onRunAlignment if clicked while under 2 structures somehow', () => {
            const onRunAlignment = vi.fn();
            const tab = makeTab({ selectedPDBs: ['4RLT'], onRunAlignment });
            tab.render();

            tab.element.querySelector('#workspace-run-btn').click();
            expect(onRunAlignment).not.toHaveBeenCalled();
        });
    });

    describe('per-structure Discover action', () => {
        it('shows a "What is this?" button on every structure card, regardless of count', () => {
            const tab = makeTab({ selectedPDBs: ['4RLT', '3UG9', 'AF-P69905-F1'] });
            tab.render();

            const buttons = tab.element.querySelectorAll('.discover-structure-btn');
            expect(buttons).toHaveLength(3);
        });

        it('clicking it opens the DiscoveryPanel and runs a search for that structure', async () => {
            submitDiscoveryJob.mockResolvedValue({ job_id: 'job1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({
                status: 'completed',
                results: { id: 'd1', pdb_id: '4RLT', source: 'pdb', databases_searched: ['pdb100'], hit_count: 0, hits: [], annotations: null },
            });

            const tab = makeTab({ selectedPDBs: ['4RLT'] });
            tab.render();

            tab.element.querySelector('.discover-structure-btn[data-pdb="4RLT"]').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(submitDiscoveryJob).toHaveBeenCalledWith('4RLT', expect.any(Array));
            const slot = tab.element.querySelector('#workspace-discovery-panel-slot');
            expect(slot.classList.contains('hidden')).toBe(false);
            expect(slot.textContent).toContain('4RLT');
        });

        it('closing the panel via its close button hides the slot again', () => {
            const tab = makeTab({ selectedPDBs: ['4RLT'] });
            tab.render();

            tab.element.querySelector('.discover-structure-btn[data-pdb="4RLT"]').click();
            tab.discoveryPanel.element.querySelector('#discovery-panel-close-btn').click();

            expect(tab.element.querySelector('#workspace-discovery-panel-slot').classList.contains('hidden')).toBe(true);
        });

        it('closes the panel if its structure is removed from the workspace', () => {
            const tab = makeTab({ selectedPDBs: ['4RLT'] });
            tab.render();
            tab.element.querySelector('.discover-structure-btn[data-pdb="4RLT"]').click();

            tab.updateState([], {}, {});

            expect(tab.element.querySelector('#workspace-discovery-panel-slot').classList.contains('hidden')).toBe(true);
        });
    });

    describe('batch add', () => {
        it('is hidden until the "Paste multiple IDs" toggle is clicked', () => {
            const tab = makeTab();
            tab.render();

            expect(tab.element.querySelector('#workspace-batch-add-container').classList.contains('hidden')).toBe(true);
            tab.element.querySelector('#workspace-toggle-batch-add-btn').click();
            expect(tab.element.querySelector('#workspace-batch-add-container').classList.contains('hidden')).toBe(false);
        });

        it('parses a comma/newline/space-separated paste and calls onAddManyPDBs with valid, deduplicated, uppercased IDs', async () => {
            const onAddManyPDBs = vi.fn().mockResolvedValue({ added: ['4RLT', '3UG9', 'AF-P69905-F1'], overCap: 0 });
            const tab = makeTab({ onAddManyPDBs });
            tab.render();

            tab.element.querySelector('#workspace-batch-pdb-input').value = '4rlt, 3ug9\n4RLT af-p69905-f1';
            tab.element.querySelector('#workspace-batch-add-btn').click();

            expect(onAddManyPDBs).toHaveBeenCalledWith(['4RLT', '3UG9', 'AF-P69905-F1']);
        });

        it('reports invalid tokens and in-paste duplicates without calling onAddManyPDBs for them', async () => {
            const onAddManyPDBs = vi.fn().mockResolvedValue({ added: ['3UG9'], overCap: 0 });
            const tab = makeTab({ selectedPDBs: ['4RLT'], onAddManyPDBs });
            tab.render();

            tab.element.querySelector('#workspace-batch-pdb-input').value = '4RLT, 3ug9, notanid';
            tab.element.querySelector('#workspace-batch-add-btn').click();
            await onAddManyPDBs.mock.results[0].value;

            expect(onAddManyPDBs).toHaveBeenCalledWith(['3UG9']);
            const feedback = tab.element.querySelector('#workspace-batch-add-feedback').innerText;
            expect(feedback).toContain('Added 1');
            expect(feedback).toContain('Skipped 1 already in the workspace');
            expect(feedback).toContain("Couldn't recognize: NOTANID");
        });

        it('surfaces the workspace-limit count when the batch is capped', async () => {
            const onAddManyPDBs = vi.fn().mockResolvedValue({ added: ['4RLT'], overCap: 1 });
            const tab = makeTab({ onAddManyPDBs });
            tab.render();

            tab.element.querySelector('#workspace-batch-pdb-input').value = '4RLT, 3UG9';
            tab.element.querySelector('#workspace-batch-add-btn').click();
            await onAddManyPDBs.mock.results[0].value;

            expect(tab.element.querySelector('#workspace-batch-add-feedback').innerText)
                .toContain('Skipped 1 — workspace limit is 20 structures.');
        });

        it('disables the Add All button for the duration of the request, to prevent a double-submit', async () => {
            let resolveAdd;
            const onAddManyPDBs = vi.fn(() => new Promise(resolve => { resolveAdd = resolve; }));
            const tab = makeTab({ onAddManyPDBs });
            tab.render();

            const batchAddBtn = tab.element.querySelector('#workspace-batch-add-btn');
            tab.element.querySelector('#workspace-batch-pdb-input').value = '4RLT, 3UG9';
            batchAddBtn.click();

            expect(batchAddBtn.disabled).toBe(true);
            resolveAdd({ added: ['4RLT', '3UG9'], overCap: 0 });
            await onAddManyPDBs.mock.results[0].value;
            await Promise.resolve();

            expect(batchAddBtn.disabled).toBe(false);
        });

        it('clears the textarea only when something was actually added', async () => {
            const onAddManyPDBs = vi.fn();
            const tab = makeTab({ selectedPDBs: [], onAddManyPDBs });
            tab.render();

            const input = tab.element.querySelector('#workspace-batch-pdb-input');
            input.value = 'notanid';
            tab.element.querySelector('#workspace-batch-add-btn').click();

            expect(onAddManyPDBs).not.toHaveBeenCalled();
            expect(input.value).toBe('notanid');
        });
    });

    describe('upload structure', () => {
        function selectFile(tab, file) {
            const input = tab.element.querySelector('#workspace-upload-structure-input');
            Object.defineProperty(input, 'files', { value: [file], configurable: true });
            input.dispatchEvent(new Event('change'));
            return input;
        }

        it('clicking "Upload a structure file" opens the hidden file picker', () => {
            const tab = makeTab();
            tab.render();

            const input = tab.element.querySelector('#workspace-upload-structure-input');
            const clickSpy = vi.spyOn(input, 'click');
            tab.element.querySelector('#workspace-upload-structure-btn').click();

            expect(clickSpy).toHaveBeenCalled();
        });

        it('calls onUploadStructure with the selected file and reports success', async () => {
            const onUploadStructure = vi.fn().mockResolvedValue(undefined);
            const tab = makeTab({ onUploadStructure });
            tab.render();

            const file = new File(['ATOM ...'], 'my_structure.pdb', { type: 'chemical/x-pdb' });
            selectFile(tab, file);
            await onUploadStructure.mock.results[0].value;

            expect(onUploadStructure).toHaveBeenCalledWith(file);
            expect(tab.element.querySelector('#workspace-upload-structure-feedback').innerText)
                .toBe('Added my_structure.pdb.');
        });

        it('reports the error message when the upload fails', async () => {
            const onUploadStructure = vi.fn().mockRejectedValue(new Error("Couldn't parse 'bad.pdb' as a structure"));
            const tab = makeTab({ onUploadStructure });
            tab.render();

            const file = new File(['not a structure'], 'bad.pdb', { type: 'chemical/x-pdb' });
            selectFile(tab, file);
            await onUploadStructure.mock.results[0].value.catch(() => {});

            expect(tab.element.querySelector('#workspace-upload-structure-feedback').innerText)
                .toBe("Couldn't parse 'bad.pdb' as a structure");
        });

        it('resets the file input value so the same file can be re-selected', () => {
            const tab = makeTab();
            tab.render();

            const file = new File(['ATOM ...'], 'my_structure.pdb', { type: 'chemical/x-pdb' });
            const input = selectFile(tab, file);

            expect(input.value).toBe('');
        });

        it('shows an "Uploaded" source badge and the original filename, HTML-escaped', () => {
            const tab = makeTab({
                selectedPDBs: ['UPLOAD-ABCD1234'],
                pdbMetadata: {
                    'UPLOAD-ABCD1234': {
                        chains: [{ id: 'A', residue_count: 50 }],
                        source: 'upload',
                        original_filename: '<script>alert(1)</script>.pdb',
                    },
                },
            });
            tab.render();

            const row = tab.element.querySelector('#workspace-pdb-list-container > div');
            expect(row.querySelector('.source-badge').textContent).toBe('Uploaded');
            expect(row.querySelector('script')).toBeNull();
            expect(row.querySelector('.pdb-meta-line').textContent)
                .toContain('<script>alert(1)</script>.pdb');
        });
    });

    describe('predict from sequence', () => {
        it('clicking "Predict from sequence" reveals the sequence input', () => {
            const tab = makeTab();
            tab.render();

            const container = tab.element.querySelector('#workspace-predict-container');
            expect(container.classList.contains('hidden')).toBe(true);

            tab.element.querySelector('#workspace-toggle-predict-btn').click();

            expect(container.classList.contains('hidden')).toBe(false);
        });

        it('rejects a sequence shorter than 10 residues without calling the callback', async () => {
            const onPredictFromSequence = vi.fn();
            const tab = makeTab({ onPredictFromSequence });
            tab.render();

            tab.element.querySelector('#workspace-predict-sequence-input').value = 'MV';
            tab.element.querySelector('#workspace-predict-btn').click();
            await Promise.resolve();

            expect(onPredictFromSequence).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#workspace-predict-feedback').innerText)
                .toBe('A sequence of at least 10 residues is required.');
        });

        it('calls onPredictFromSequence with the normalized sequence and reports success', async () => {
            const onPredictFromSequence = vi.fn().mockResolvedValue(undefined);
            const tab = makeTab({ onPredictFromSequence });
            tab.render();

            tab.element.querySelector('#workspace-predict-sequence-input').value = ' mvhltpeek savtalwgkv nv ';
            tab.element.querySelector('#workspace-predict-btn').click();
            await onPredictFromSequence.mock.results[0].value;

            expect(onPredictFromSequence).toHaveBeenCalledWith('MVHLTPEEKSAVTALWGKVNV');
            expect(tab.element.querySelector('#workspace-predict-feedback').innerText)
                .toBe('Structure predicted for 21 residues.');
            expect(tab.element.querySelector('#workspace-predict-sequence-input').value).toBe('');
        });

        it('reports the error message when prediction fails', async () => {
            const onPredictFromSequence = vi.fn().mockRejectedValue(new Error('ESMFold returned status 504'));
            const tab = makeTab({ onPredictFromSequence });
            tab.render();

            tab.element.querySelector('#workspace-predict-sequence-input').value = 'MVHLTPEEKSAVTALWGKVNV';
            tab.element.querySelector('#workspace-predict-btn').click();
            await onPredictFromSequence.mock.results[0].value.catch(() => {});

            expect(tab.element.querySelector('#workspace-predict-feedback').innerText)
                .toBe('ESMFold returned status 504');
        });

        it('disables the predict button while a prediction is in flight', async () => {
            let resolvePredict;
            const onPredictFromSequence = vi.fn(() => new Promise(r => { resolvePredict = r; }));
            const tab = makeTab({ onPredictFromSequence });
            tab.render();

            tab.element.querySelector('#workspace-predict-sequence-input').value = 'MVHLTPEEKSAVTALWGKVNV';
            const btn = tab.element.querySelector('#workspace-predict-btn');
            btn.click();
            await Promise.resolve();

            expect(btn.disabled).toBe(true);
            resolvePredict();
            await onPredictFromSequence.mock.results[0].value;
            expect(btn.disabled).toBe(false);
        });
    });

    describe('Run QC on all', () => {
        it('fetches QC for every selected structure and renders a summary table', async () => {
            fetchQc.mockImplementation(async (pid) => ({
                pdb_id: pid,
                ramachandran_stats: { favored_percent: 92.5, outlier_count: 2 },
                secondary_structure_stats: { helix_percent: 80.3 },
                validation: { clashscore: { value: 1.2 } },
            }));

            const tab = makeTab({ selectedPDBs: ['4HHB', '2HHB'] });
            tab.render();

            tab.element.querySelector('#workspace-run-qc-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(fetchQc).toHaveBeenCalledWith('4HHB');
            expect(fetchQc).toHaveBeenCalledWith('2HHB');
            const rows = tab.element.querySelectorAll('#workspace-qc-summary tbody tr');
            expect(rows).toHaveLength(2);
            expect(rows[0].textContent).toContain('92.5');
            expect(rows[0].textContent).toContain('80.3');
            expect(rows[0].textContent).toContain('1.2');
        });

        it('shows a per-row failure message when QC fails for one structure', async () => {
            fetchQc.mockImplementation(async (pid) => {
                if (pid === '2HHB') throw new Error('boom');
                return {
                    pdb_id: pid,
                    ramachandran_stats: { favored_percent: 92.5, outlier_count: 0 },
                    secondary_structure_stats: { helix_percent: 80.3 },
                    validation: null,
                };
            });

            const tab = makeTab({ selectedPDBs: ['4HHB', '2HHB'] });
            tab.render();

            tab.element.querySelector('#workspace-run-qc-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            const rows = tab.element.querySelectorAll('#workspace-qc-summary tbody tr');
            expect(rows[1].textContent).toContain('2HHB');
            expect(rows[1].textContent).toContain('QC failed for this structure.');
        });

        it('shows -- for missing stats instead of crashing', async () => {
            fetchQc.mockResolvedValue({
                pdb_id: 'AF-P69905-F1',
                ramachandran_stats: null,
                secondary_structure_stats: null,
                validation: null,
            });

            const tab = makeTab({ selectedPDBs: ['AF-P69905-F1'] });
            tab.render();

            tab.element.querySelector('#workspace-run-qc-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            const row = tab.element.querySelector('#workspace-qc-summary tbody tr');
            expect(row.textContent).toContain('--');
        });

        it('does nothing when there are no structures in the workspace', async () => {
            fetchQc.mockClear();
            const tab = makeTab({ selectedPDBs: [] });
            tab.render();

            tab.element.querySelector('#workspace-run-qc-btn').click();
            await Promise.resolve();

            expect(fetchQc).not.toHaveBeenCalled();
        });
    });
});
