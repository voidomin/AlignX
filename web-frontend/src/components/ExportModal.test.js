import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { showExportModal, REPORT_SECTIONS, PRESETS } from './ExportModal';

describe('ExportModal', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        vi.spyOn(window, 'open').mockImplementation(() => null);
    });

    afterEach(() => {
        vi.restoreAllMocks();
        const existing = document.getElementById('export-studio-modal');
        if (existing) existing.remove();
    });

    it('renders empty-state modal when runId is not provided', () => {
        const modal = showExportModal({ runId: null });

        expect(document.getElementById('export-studio-modal')).not.toBeNull();
        expect(modal.textContent).toContain('No active alignment results to export');

        const closeBtn = modal.querySelector('#close-export-modal-btn');
        closeBtn.click();
        expect(document.getElementById('export-studio-modal')).toBeNull();
    });

    it('closes empty-state modal via dismiss button and overlay click', () => {
        const modal1 = showExportModal({ runId: null });
        modal1.querySelector('#dismiss-export-modal-btn').click();
        expect(document.getElementById('export-studio-modal')).toBeNull();

        const modal2 = showExportModal({ runId: null });
        modal2.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(document.getElementById('export-studio-modal')).toBeNull();
    });

    it('renders active run export studio when runId is provided', () => {
        const modal = showExportModal({
            runId: 'run_abc123',
            selectedPDBs: ['4HHB', '1A3N'],
        });

        expect(modal.textContent).toContain('Custom Report & Export Studio');
        expect(modal.textContent).toContain('run_abc123');
        expect(modal.textContent).toContain('4HHB, 1A3N');

        const checkboxes = modal.querySelectorAll('.export-section-checkbox');
        expect(checkboxes.length).toBe(REPORT_SECTIONS.length);
        checkboxes.forEach(cb => expect(cb.checked).toBe(true));

        const zipLink = modal.querySelector('#export-zip-btn');
        expect(zipLink.getAttribute('href')).toContain('run_id=run_abc123');

        const ipynbLink = modal.querySelector('#export-ipynb-btn');
        expect(ipynbLink.getAttribute('href')).toContain('run_id=run_abc123');

        const csvLink = modal.querySelector('#export-csv-btn');
        expect(csvLink.getAttribute('href')).toContain('run_id=run_abc123');

        const pymolLink = modal.querySelector('#export-pymol-btn');
        expect(pymolLink.getAttribute('href')).toContain('run_id=run_abc123');

        const chimeraxLink = modal.querySelector('#export-chimerax-btn');
        expect(chimeraxLink.getAttribute('href')).toContain('run_id=run_abc123');

        const citationsLink = modal.querySelector('#export-citations-btn');
        expect(citationsLink.getAttribute('href')).toContain('run_id=run_abc123');
    });

    it('removes existing modal when showExportModal is called multiple times', () => {
        showExportModal({ runId: 'run_1' });
        expect(document.querySelectorAll('#export-studio-modal').length).toBe(1);

        showExportModal({ runId: 'run_2' });
        expect(document.querySelectorAll('#export-studio-modal').length).toBe(1);
        expect(document.body.textContent).toContain('run_2');
    });

    it('clicking preset buttons updates checkboxes correctly', () => {
        const modal = showExportModal({ runId: 'run_1' });

        // Click Executive Summary preset
        const execBtn = modal.querySelector('.preset-btn[data-preset="executive"]');
        execBtn.click();

        const checkedKeys = Array.from(modal.querySelectorAll('.export-section-checkbox:checked'))
            .map(cb => cb.dataset.section);
        expect(checkedKeys).toEqual(PRESETS.executive.sections);

        // Click Drug Discovery Brief preset
        const ddBtn = modal.querySelector('.preset-btn[data-preset="drugDiscovery"]');
        ddBtn.click();

        const ddKeys = Array.from(modal.querySelectorAll('.export-section-checkbox:checked'))
            .map(cb => cb.dataset.section);
        expect(ddKeys).toEqual(PRESETS.drugDiscovery.sections);

        // Click Full Publication Appendix preset
        const appendixBtn = modal.querySelector('.preset-btn[data-preset="appendix"]');
        appendixBtn.click();

        const appendixKeys = Array.from(modal.querySelectorAll('.export-section-checkbox:checked'))
            .map(cb => cb.dataset.section);
        expect(appendixKeys).toEqual(PRESETS.appendix.sections);
    });

    it('toggle-all button toggles all section checkboxes', () => {
        const modal = showExportModal({ runId: 'run_1' });
        const toggleBtn = modal.querySelector('#toggle-all-sections-btn');

        expect(toggleBtn.textContent).toBe('Deselect All');

        // All are initially checked -> toggling unchecks all
        toggleBtn.click();
        modal.querySelectorAll('.export-section-checkbox').forEach(cb => {
            expect(cb.checked).toBe(false);
        });
        expect(toggleBtn.textContent).toBe('Select All');

        // Toggling again checks all
        toggleBtn.click();
        modal.querySelectorAll('.export-section-checkbox').forEach(cb => {
            expect(cb.checked).toBe(true);
        });
        expect(toggleBtn.textContent).toBe('Deselect All');
    });

    it('clicking Custom Report button opens window with selected sections', () => {
        const modal = showExportModal({ runId: 'run_test_sections' });

        // Uncheck all except summary
        modal.querySelectorAll('.export-section-checkbox').forEach(cb => {
            cb.checked = cb.dataset.section === 'summary';
        });

        const printBtn = modal.querySelector('#export-html-report-btn');
        printBtn.click();

        expect(window.open).toHaveBeenCalledWith(
            expect.stringContaining('sections=summary'),
            '_blank'
        );
    });

    it('closes modal when close, dismiss, or overlay is clicked', () => {
        const modal1 = showExportModal({ runId: 'run_1' });
        modal1.querySelector('#close-export-modal-btn').click();
        expect(document.getElementById('export-studio-modal')).toBeNull();

        const modal2 = showExportModal({ runId: 'run_2' });
        modal2.querySelector('#dismiss-export-modal-btn').click();
        expect(document.getElementById('export-studio-modal')).toBeNull();

        const modal3 = showExportModal({ runId: 'run_3' });
        modal3.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(document.getElementById('export-studio-modal')).toBeNull();
    });
});
