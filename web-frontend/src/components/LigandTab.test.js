import { describe, it, expect, vi, afterEach } from 'vitest';
import { LigandTab } from './LigandTab.js';

vi.mock('../api.js', () => ({
    fetchInteractions: vi.fn(),
    fetchLigands: vi.fn(),
}));

import { fetchInteractions, fetchLigands } from '../api.js';

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
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('shows "No Ligands Loaded" when there are no ligands', () => {
        const tab = makeTab();
        tab.render();

        const select = tab.element.querySelector('#ligand-select');
        expect(select.options.length).toBe(1);
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
        expect(select.options.length).toBe(3);
        expect(select.options[1].value).toBe('RET_A_296');
        expect(select.options[2].value).toBe('ZN_A_301');
    });

    it('loads interactions and renders table rows when a ligand is selected', async () => {
        fetchInteractions.mockResolvedValue({
            interactions: {
                ligand: 'RET_A_296',
                pocket_volume: 123.4,
                pocket_sasa: 56.7,
                interactions: [
                    { resn: 'TYR', chain: 'A', resi: 191, distance: 3.2, type: 'H-Bond' },
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
            { resn: 'TYR', chain: 'A', resi: 191, distance: 3.2, type: 'H-Bond' },
        ]);
        expect(tab.element.querySelector('#interaction-count').innerText).toBe('1 Found');
        expect(tab.element.querySelector('#ligand-volume-badge').classList.contains('hidden')).toBe(false);
        const rows = tab.element.querySelectorAll('#interactions-table-body tr');
        expect(rows.length).toBe(1);
        expect(rows[0].textContent).toContain('TYR');
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
        expect(select.options.length).toBe(3);
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
});
