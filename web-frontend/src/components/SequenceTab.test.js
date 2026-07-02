import { describe, it, expect, vi, afterEach } from 'vitest';
import { SequenceTab } from './SequenceTab.js';

vi.mock('../api.js', () => ({
    fetchSequence: vi.fn(),
    getAlignmentPdbUrl: vi.fn((runId) => `http://api/results/${runId}/alignment.pdb`),
    getAlignmentFastaUrl: vi.fn((runId) => `http://api/results/${runId}/alignment.fasta`),
    getAlignmentReportUrl: vi.fn((runId, sections) => `http://api/api/report?run_id=${runId}${sections ? `&sections=${sections.join(',')}` : ''}`),
    getLabNotebookUrl: vi.fn((runId) => `http://api/api/notebook?run_id=${runId}`),
}));

import { fetchSequence } from '../api.js';

describe('SequenceTab', () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('renders placeholder stats and disabled download links with no run loaded', () => {
        const tab = new SequenceTab();
        tab.render();

        expect(tab.element.querySelector('#stat-rmsd').innerText).toBe('--');
        const pdbLink = tab.element.querySelector('#download-pdb-link');
        expect(pdbLink.classList.contains('pointer-events-none')).toBe(true);
    });

    it('updates stats and enables download links once a run is set', () => {
        fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
        const tab = new SequenceTab();
        tab.render();

        tab.updateResults('run_123', {
            rmsd: 1.234, aligned_length: 150, seq_identity: 87.5, seq_similarity: 92.1,
        });

        expect(tab.element.querySelector('#stat-rmsd').innerText).toBe('1.23 Å');
        expect(String(tab.element.querySelector('#stat-length').innerText)).toBe('150');
        expect(tab.element.querySelector('#stat-identity').innerText).toBe('87.5%');
        expect(tab.element.querySelector('#stat-similarity').innerText).toBe('92.1%');

        const pdbLink = tab.element.querySelector('#download-pdb-link');
        expect(pdbLink.classList.contains('pointer-events-none')).toBe(false);
        expect(pdbLink.href).toContain('run_123');
    });

    it('renders the sequence alignment grid with conservation-based coloring', async () => {
        fetchSequence.mockResolvedValue({
            sequences: { '4RLT_A': 'MVL-A', '3UG9_A': 'MVHLA' },
            conservation: [1.0, 1.0, 0.8, 0.0, 1.0],
        });

        const tab = new SequenceTab();
        tab.render();
        tab.updateResults('run_123', { rmsd: 1.0 });
        await Promise.resolve();
        await Promise.resolve();

        expect(fetchSequence).toHaveBeenCalledWith('run_123');
        const wrapper = tab.element.querySelector('#sequence-alignment-grid-wrapper');
        expect(wrapper.textContent).toContain('4RLT_A');
        expect(wrapper.textContent).toContain('Consensus');
        expect(wrapper.querySelectorAll('table tbody tr').length).toBe(3); // 2 sequences + consensus row
    });

    it('shows an error message when sequence parsing fails', async () => {
        fetchSequence.mockRejectedValue(new Error('parse failed'));

        const tab = new SequenceTab();
        tab.render();
        tab.updateResults('run_123', { rmsd: 1.0 });
        await Promise.resolve();
        await Promise.resolve();

        expect(tab.element.querySelector('#sequence-alignment-grid-wrapper').textContent)
            .toContain('Failed to parse alignment FASTA data.');
    });

    it('enables the lab notebook link once a run is set', () => {
        fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
        const tab = new SequenceTab();
        tab.render();

        tab.updateResults('run_123', { rmsd: 1.0 });

        const notebookLink = tab.element.querySelector('#download-notebook-link');
        expect(notebookLink.classList.contains('pointer-events-none')).toBe(false);
        expect(notebookLink.href).toContain('run_123');
    });

    it('report checklist defaults to all 5 sections checked with no sections param in the URL', () => {
        fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
        const tab = new SequenceTab();
        tab.render();
        tab.updateResults('run_123', { rmsd: 1.0 });

        const checkboxes = tab.element.querySelectorAll('.report-section-checkbox');
        expect(checkboxes.length).toBe(5);
        expect(Array.from(checkboxes).every(cb => cb.checked)).toBe(true);

        const reportLink = tab.element.querySelector('#download-report-link');
        expect(reportLink.href).not.toContain('sections=');
    });

    it('unchecking a report section updates the download link to a subset', () => {
        fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
        const tab = new SequenceTab();
        tab.render();
        tab.updateResults('run_123', { rmsd: 1.0 });

        const checkboxes = tab.element.querySelectorAll('.report-section-checkbox');
        checkboxes[0].checked = false;
        checkboxes[0].dispatchEvent(new Event('change'));

        const reportLink = tab.element.querySelector('#download-report-link');
        expect(reportLink.href).toContain('sections=insights,heatmap,tree,matrix');
    });

    it('unchecking every report section disables the download link', () => {
        fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
        const tab = new SequenceTab();
        tab.render();
        tab.updateResults('run_123', { rmsd: 1.0 });

        const checkboxes = tab.element.querySelectorAll('.report-section-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = false;
            cb.dispatchEvent(new Event('change'));
        });

        const reportLink = tab.element.querySelector('#download-report-link');
        expect(reportLink.classList.contains('pointer-events-none')).toBe(true);
    });
});
