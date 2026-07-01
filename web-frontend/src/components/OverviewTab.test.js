import { describe, it, expect, vi } from 'vitest';
import { OverviewTab } from './OverviewTab.js';

function makeTab(overrides = {}) {
    return new OverviewTab({
        selectedPDBs: [],
        chainSelections: {},
        pdbMetadata: {},
        onAddPDB: vi.fn(),
        onRemovePDB: vi.fn(),
        onChainSelection: vi.fn(),
        onRunAlignment: vi.fn(),
        ...overrides,
    });
}

describe('OverviewTab', () => {
    it('shows the empty-state message and a "0 Proteins" badge with no structures selected', () => {
        const tab = makeTab();
        tab.render();

        expect(tab.element.querySelector('#pdb-count-badge').innerText).toBe('0 Proteins');
        expect(tab.element.querySelector('#pdb-list-container').textContent)
            .toContain('Add at least 2 PDB structures to align.');
    });

    it('calls onAddPDB with the uppercased 4-char input on Add click, and clears the input', () => {
        const onAddPDB = vi.fn();
        const tab = makeTab({ onAddPDB });
        tab.render();

        const input = tab.element.querySelector('#add-pdb-input');
        input.value = '4rlt';
        tab.element.querySelector('#add-pdb-btn').click();

        expect(onAddPDB).toHaveBeenCalledWith('4RLT');
        expect(input.value).toBe('');
    });

    it('does not call onAddPDB for input that is not exactly 4 characters', () => {
        const onAddPDB = vi.fn();
        const tab = makeTab({ onAddPDB });
        tab.render();

        tab.element.querySelector('#add-pdb-input').value = '4rl';
        tab.element.querySelector('#add-pdb-btn').click();

        expect(onAddPDB).not.toHaveBeenCalled();
    });

    it('adds a PDB on Enter keypress in the input field', () => {
        const onAddPDB = vi.fn();
        const tab = makeTab({ onAddPDB });
        tab.render();

        const input = tab.element.querySelector('#add-pdb-input');
        input.value = '3ug9';
        input.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter' }));

        expect(onAddPDB).toHaveBeenCalledWith('3UG9');
    });

    it('renders one row per selected PDB with chain options from metadata', () => {
        const tab = makeTab({
            selectedPDBs: ['4RLT', '3UG9'],
            chainSelections: { '4RLT': 'B' },
            pdbMetadata: {
                '4RLT': { chains: [{ id: 'A', residues_count: 100 }, { id: 'B', residues_count: 90 }] },
            },
        });
        tab.render();

        expect(tab.element.querySelector('#pdb-count-badge').innerText).toBe('2 Proteins');
        const rows = tab.element.querySelectorAll('#pdb-list-container > div');
        expect(rows.length).toBe(2);

        const select4RLT = rows[0].querySelector('select');
        expect(select4RLT.querySelectorAll('option').length).toBe(2);
        expect(select4RLT.querySelector('option[value="B"]').selected).toBe(true);

        // 3UG9 has no metadata -> falls back to a single Chain A option
        const select3UG9 = rows[1].querySelector('select');
        expect(select3UG9.querySelectorAll('option').length).toBe(1);
    });

    it('fires onChainSelection and onRemovePDB from row controls', () => {
        const onChainSelection = vi.fn();
        const onRemovePDB = vi.fn();
        const tab = makeTab({
            selectedPDBs: ['4RLT'],
            pdbMetadata: { '4RLT': { chains: [{ id: 'A', residues_count: 100 }, { id: 'B', residues_count: 90 }] } },
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

        expect(tab.element.querySelector('#pdb-list-container').textContent)
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
        const tab = makeTab();
        tab.render();
        const runBtn = tab.element.querySelector('#overview-run-btn');

        tab.setAligning(true);
        expect(runBtn.disabled).toBe(true);
        expect(runBtn.textContent).toContain('Aligning Pipeline...');

        tab.setAligning(false);
        expect(runBtn.disabled).toBe(false);
        expect(runBtn.textContent).toContain('Run Structural Alignment');
    });

    it('calls onRunAlignment when the run button is clicked', () => {
        const onRunAlignment = vi.fn();
        const tab = makeTab({ onRunAlignment });
        tab.render();

        tab.element.querySelector('#overview-run-btn').click();
        expect(onRunAlignment).toHaveBeenCalled();
    });
});
