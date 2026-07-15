import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { LigandTab } from './LigandTab.js';

vi.mock('../api.js', () => ({
    fetchInteractions: vi.fn(),
    fetchLigands: vi.fn(),
    fetchChains: vi.fn().mockResolvedValue({ chains: {} }),
    fetchInterface: vi.fn(),
}));

import { fetchInteractions, fetchLigands, fetchChains, fetchInterface } from '../api.js';

function makeTab(overrides = {}) {
    return new LigandTab({
        selectedPDBs: ['4RLT', '3UG9'],
        currentRunId: 'run_1',
        onLigandSelected: vi.fn(),
        onResidueSelected: vi.fn(),
        ...overrides,
    });
}

describe('LigandTab', () => {
    beforeEach(() => {
        global.Plotly = { newPlot: vi.fn() };
    });

    afterEach(() => {
        vi.clearAllMocks();
        delete global.Plotly;
    });

    it('shows "No Ligands Loaded" when there are no ligands', () => {
        const tab = makeTab();
        tab.render();

        const select = tab.element.querySelector('#ligand-select');
        expect(select.options).toHaveLength(1);
        expect(select.options[0].textContent).toBe('No Ligands Loaded');
    });

    it('populates the dropdown with ligand options after updateLigands', () => {
        const tab = makeTab();
        tab.render();

        tab.updateLigands([
            { id: 'RET_A_296', name: 'RET', chain: 'A', resi: 296 },
            { id: 'ZN_A_301', name: 'ZN', chain: 'A', resi: 301 },
        ], 'run_2');

        const select = tab.element.querySelector('#ligand-select');
        // 1 "Select a Ligand" placeholder + 2 real ligands
        expect(select.options).toHaveLength(3);
        expect(select.options[1].value).toBe('RET_A_296');
        expect(select.options[2].value).toBe('ZN_A_301');
    });

    it('loads interactions and renders table rows when a ligand is selected', async () => {
        fetchInteractions.mockResolvedValue({
            interactions: {
                ligand: 'RET_A_296',
                pocket_sasa: 56.7,
                interactions: [
                    { resn: 'TYR', chain: 'A', resi: 191, distance: 3.2, type: 'Hydrogen Bond' },
                ],
            },
        });

        const onLigandSelected = vi.fn();
        const tab = makeTab({ onLigandSelected });
        tab.render();
        tab.updateLigands([{ id: 'RET_A_296', name: 'RET', chain: 'A', resi: 296 }], 'run_1');

        await tab.loadInteractions('RET_A_296');

        expect(fetchInteractions).toHaveBeenCalledWith('4RLT', 'RET_A_296', 'run_1');
        expect(onLigandSelected).toHaveBeenCalledWith(0, 'RET_A_296', [
            { resn: 'TYR', chain: 'A', resi: 191, distance: 3.2, type: 'Hydrogen Bond' },
        ]);
        expect(tab.element.querySelector('#interaction-count').innerText).toBe('1 Found');
        expect(tab.element.querySelector('#ligand-sasa-badge').classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('#ligand-sasa-badge').innerText).toBe('SASA: 56.7 Å²');
        const rows = tab.element.querySelectorAll('#interactions-table-body tr');
        expect(rows).toHaveLength(1);
        expect(rows[0].textContent).toContain('TYR');
    });

    it('does not render a Volume badge (removed - no pocket-volume computation exists)', () => {
        const tab = makeTab();
        tab.render();

        expect(tab.element.querySelector('#ligand-volume-badge')).toBeNull();
    });

    it('clicking a contact row passes aligned_resi (the raw->aligned residue remap) to onResidueSelected', async () => {
        fetchInteractions.mockResolvedValue({
            interactions: {
                ligand: 'RET_A_296',
                interactions: [
                    { resn: 'TYR', chain: 'A', resi: 191, aligned_resi: 42, distance: 3.2, type: 'Hydrogen Bond' },
                ],
            },
        });

        const onResidueSelected = vi.fn();
        const tab = makeTab({ onResidueSelected });
        tab.render();
        tab.updateLigands([{ id: 'RET_A_296', name: 'RET', chain: 'A', resi: 296 }], 'run_1');

        await tab.loadInteractions('RET_A_296');
        tab.element.querySelector('#interactions-table-body tr').click();

        expect(onResidueSelected).toHaveBeenCalledWith(0, 'A', 191, 42);
    });

    it('resets to the empty state and notifies the parent when ligand is deselected', async () => {
        const onLigandSelected = vi.fn();
        const tab = makeTab({ onLigandSelected });
        tab.render();

        await tab.loadInteractions('');

        expect(onLigandSelected).toHaveBeenCalledWith(0, '');
        expect(tab.element.querySelector('#interactions-table-body').textContent)
            .toContain('Select a ligand to populate interactions.');
    });

    it('shows an error row when the interactions fetch fails', async () => {
        fetchInteractions.mockRejectedValue(new Error('boom'));

        const tab = makeTab();
        tab.render();
        tab.updateLigands([{ id: 'RET_A_296', name: 'RET', chain: 'A', resi: 296 }], 'run_1');

        await tab.loadInteractions('RET_A_296');

        expect(tab.element.querySelector('#interactions-table-body').textContent)
            .toContain('Failed to calculate pocket site contacts.');
    });

    it('populates the structure picker with one option per selected PDB', () => {
        const tab = makeTab({ selectedPDBs: ['4RLT', '3UG9', '1L2Y'] });
        tab.render();

        const select = tab.element.querySelector('#ligand-structure-select');
        expect(select.options).toHaveLength(3);
        expect(Array.from(select.options).map(o => o.value)).toEqual(['0', '1', '2']);
        expect(select.options[1].textContent).toBe('3UG9');
    });

    it('switching structure refetches ligands for that PDB and notifies the viewer', async () => {
        fetchLigands.mockResolvedValue({
            ligands: [{ id: 'ZN_B_50', name: 'ZN', chain: 'B', resi: 50 }],
        });

        const onLigandSelected = vi.fn();
        const tab = makeTab({ selectedPDBs: ['4RLT', '3UG9'], onLigandSelected });
        tab.render();
        tab.updateLigands([{ id: 'RET_A_296', name: 'RET', chain: 'A', resi: 296 }], 'run_1', ['4RLT', '3UG9']);

        await tab.switchStructure(1);

        expect(fetchLigands).toHaveBeenCalledWith('3UG9', 'run_1');
        expect(onLigandSelected).toHaveBeenCalledWith(1, '');
        expect(tab.currentStructureIndex).toBe(1);
        const select = tab.element.querySelector('#ligand-select');
        expect(select.options[1].value).toBe('ZN_B_50');
    });

    it('switching structure still fetches ligands with no completed run (a lone, un-aligned structure)', async () => {
        // Regression: this used to bail out with `if (!this.currentRunId)
        // return;` - the only thing blocking the Ligands tab from working
        // for a single structure that's never been through a Compare
        // alignment. fetchLigands already treats runId as optional.
        fetchLigands.mockResolvedValue({
            ligands: [{ id: 'ZN_A_50', name: 'ZN', chain: 'A', resi: 50 }],
        });
        const tab = makeTab({ selectedPDBs: ['4RLT'], currentRunId: null });
        tab.render();
        tab.updateLigands([], null, ['4RLT']);
        tab.currentStructureIndex = -1; // force switchStructure(0) to not short-circuit as a no-op

        await tab.switchStructure(0);

        expect(fetchLigands).toHaveBeenCalledWith('4RLT', null);
        const select = tab.element.querySelector('#ligand-select');
        expect(select.options[1].value).toBe('ZN_A_50');
    });

    it('loadInteractions targets the currently selected structure, not always the first', async () => {
        fetchInteractions.mockResolvedValue({
            interactions: { ligand: 'ZN_B_50', interactions: [] },
        });

        const tab = makeTab({ selectedPDBs: ['4RLT', '3UG9'] });
        tab.render();
        tab.currentStructureIndex = 1;

        await tab.loadInteractions('ZN_B_50');

        expect(fetchInteractions).toHaveBeenCalledWith('3UG9', 'ZN_B_50', 'run_1');
    });

    describe('binding pocket similarity matrix', () => {
        it('renders a heatmap with split "pdb_id / ligand_id" axis labels when >=2 ligands were compared', () => {
            const tab = makeTab();
            tab.render();

            tab.updateLigands([], 'run_1', undefined, {
                index: ['4HHB:HEM_A_142', '2HHB:HEM_A_142'],
                columns: ['4HHB:HEM_A_142', '2HHB:HEM_A_142'],
                data: [[1.0, 0.75], [0.75, 1.0]],
            });

            const section = tab.element.querySelector('#pocket-similarity-section');
            expect(section.classList.contains('hidden')).toBe(false);
            expect(global.Plotly.newPlot).toHaveBeenCalled();
            const [, traces] = global.Plotly.newPlot.mock.calls[0];
            expect(traces[0].x).toEqual(['4HHB<br>HEM_A_142', '2HHB<br>HEM_A_142']);
            expect(traces[0].z).toEqual([[1.0, 0.75], [0.75, 1.0]]);
        });

        it('stays hidden when there is no similarity data', () => {
            const tab = makeTab();
            tab.render();

            tab.updateLigands([], 'run_1', undefined, null);

            expect(tab.element.querySelector('#pocket-similarity-section').classList.contains('hidden')).toBe(true);
            expect(global.Plotly.newPlot).not.toHaveBeenCalled();
        });

        it('stays hidden when only a single ligand was found (nothing to compare)', () => {
            const tab = makeTab();
            tab.render();

            tab.updateLigands([], 'run_1', undefined, {
                index: ['4HHB:HEM_A_142'],
                columns: ['4HHB:HEM_A_142'],
                data: [[1.0]],
            });

            expect(tab.element.querySelector('#pocket-similarity-section').classList.contains('hidden')).toBe(true);
            expect(global.Plotly.newPlot).not.toHaveBeenCalled();
        });

        it('re-renders the matrix against a fresh DOM element after a tab switch (render() called again)', () => {
            const tab = makeTab();
            tab.render();
            tab.updateLigands([], 'run_1', undefined, {
                index: ['4HHB:HEM_A_142', '2HHB:HEM_A_142'],
                columns: ['4HHB:HEM_A_142', '2HHB:HEM_A_142'],
                data: [[1.0, 0.75], [0.75, 1.0]],
            });

            tab.render(); // simulates main.js re-rendering the pane on tab switch
            tab.updateLigands(tab.ligandsList, tab.currentRunId, tab.selectedPDBs, tab.pocketSimilarity);

            expect(tab.element.querySelector('#pocket-similarity-section').classList.contains('hidden')).toBe(false);
        });
    });

    describe('protein-protein interface analysis', () => {
        it('stays hidden when the structure has fewer than 2 chains', async () => {
            fetchChains.mockResolvedValue({ chains: { '4RLT': { chains: [{ id: 'A', residue_count: 100 }] } } });
            const tab = makeTab();
            tab.render();

            tab.updateLigands([], 'run_1', ['4RLT']);
            await tab.loadAvailableChains();

            expect(tab.element.querySelector('#interface-section').classList.contains('hidden')).toBe(true);
        });

        it('shows the section and populates chain dropdowns when the structure has 2+ chains', async () => {
            fetchChains.mockResolvedValue({
                chains: { '4HHB': { chains: [{ id: 'A' }, { id: 'B' }, { id: 'C' }, { id: 'D' }] } },
            });
            const tab = makeTab({ selectedPDBs: ['4HHB'] });
            tab.render();

            tab.updateLigands([], 'run_1', ['4HHB']);
            await tab.loadAvailableChains();

            const section = tab.element.querySelector('#interface-section');
            expect(section.classList.contains('hidden')).toBe(false);
            const chainAOptions = Array.from(tab.element.querySelector('#interface-chain-a').options).map(o => o.value);
            const chainBOptions = Array.from(tab.element.querySelector('#interface-chain-b').options).map(o => o.value);
            expect(chainAOptions).toEqual(['A', 'B', 'C', 'D']);
            expect(chainBOptions).toEqual(['A', 'B', 'C', 'D']);
        });

        it('rejects analyzing when the same chain is selected twice', async () => {
            fetchChains.mockResolvedValue({ chains: { '4HHB': { chains: [{ id: 'A' }, { id: 'B' }] } } });
            const tab = makeTab({ selectedPDBs: ['4HHB'] });
            tab.render();
            tab.updateLigands([], 'run_1', ['4HHB']);
            await tab.loadAvailableChains();

            tab.element.querySelector('#interface-chain-a').value = 'A';
            tab.element.querySelector('#interface-chain-b').value = 'A';
            await tab.analyzeInterface();

            expect(fetchInterface).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#interface-results').textContent).toContain('Select two different chains');
        });

        it('renders contact tables and buried area for a successful analysis', async () => {
            fetchChains.mockResolvedValue({ chains: { '4HHB': { chains: [{ id: 'A' }, { id: 'B' }] } } });
            fetchInterface.mockResolvedValue({
                interface: {
                    chain_a: 'A',
                    chain_b: 'B',
                    chain_a_contacts: [{ resn: 'HIS', chain: 'A', resi: 10, distance: 3.1, type: 'Salt Bridge' }],
                    chain_b_contacts: [{ resn: 'ASP', chain: 'B', resi: 20, distance: 3.4, type: 'Hydrogen Bond' }],
                    buried_area: 842.6,
                },
            });
            const tab = makeTab({ selectedPDBs: ['4HHB'] });
            tab.render();
            tab.updateLigands([], 'run_1', ['4HHB']);
            await tab.loadAvailableChains();

            tab.element.querySelector('#interface-chain-a').value = 'A';
            tab.element.querySelector('#interface-chain-b').value = 'B';
            await tab.analyzeInterface();

            expect(fetchInterface).toHaveBeenCalledWith('4HHB', 'A', 'B', 'run_1');
            const results = tab.element.querySelector('#interface-results');
            expect(results.textContent).toContain('842.6');
            expect(results.textContent).toContain('HIS');
            expect(results.textContent).toContain('ASP');
        });

        it('shows the backend error message when interface analysis fails server-side', async () => {
            fetchChains.mockResolvedValue({ chains: { '4HHB': { chains: [{ id: 'A' }, { id: 'B' }] } } });
            fetchInterface.mockResolvedValue({ interface: { error: 'Chain Z not found in structure' } });
            const tab = makeTab({ selectedPDBs: ['4HHB'] });
            tab.render();
            tab.updateLigands([], 'run_1', ['4HHB']);
            await tab.loadAvailableChains();

            tab.element.querySelector('#interface-chain-a').value = 'A';
            tab.element.querySelector('#interface-chain-b').value = 'B';
            await tab.analyzeInterface();

            expect(tab.element.querySelector('#interface-results').textContent).toContain('Chain Z not found in structure');
        });
    });
});
