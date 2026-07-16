import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { HistoryPanel } from './HistoryPanel.js';

vi.mock('../api.js', () => ({
    fetchHistory: vi.fn(),
    getShareLink: vi.fn((runId) => `http://localhost/?shared_run=${runId}`),
    deleteRun: vi.fn(),
    clearAllHistory: vi.fn(),
    updateRunNotes: vi.fn(),
    fetchRunsTrend: vi.fn(),
}));

import { fetchHistory, getShareLink, deleteRun, clearAllHistory, updateRunNotes, fetchRunsTrend } from '../api.js';

function makeRun(id) {
    return { id, timestamp: '2026-01-01', pdb_ids: ['4RLT', '3UG9'], status: 'success' };
}

describe('HistoryPanel', () => {
    afterEach(() => {
        vi.clearAllMocks();
        vi.unstubAllGlobals();
        delete global.Plotly;
    });

    beforeEach(() => {
        Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
        vi.stubGlobal('confirm', vi.fn(() => true));
        vi.stubGlobal('alert', vi.fn());
        global.Plotly = { newPlot: vi.fn() };
    });

    it('shows an empty state when there are no runs', async () => {
        fetchHistory.mockResolvedValue({ runs: [], total: 0 });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        expect(panel.element.querySelector('#history-runs-list').textContent)
            .toContain('No past alignment sessions found.');
    });

    it('renders a "Load More" button when more runs exist beyond the first page', async () => {
        fetchHistory.mockResolvedValue({
            runs: [makeRun('run_1'), makeRun('run_2')],
            total: 5,
        });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        expect(fetchHistory).toHaveBeenCalledWith(20, 0);
        const loadMoreBtn = panel.element.querySelector('#history-load-more-btn');
        expect(loadMoreBtn).not.toBeNull();
        expect(loadMoreBtn.innerText).toContain('2/5');
    });

    it('does not render "Load More" once all runs are loaded', async () => {
        fetchHistory.mockResolvedValue({
            runs: [makeRun('run_1'), makeRun('run_2')],
            total: 2,
        });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        expect(panel.element.querySelector('#history-load-more-btn')).toBeNull();
    });

    it('appends the next page of runs and updates the Load More button on click', async () => {
        fetchHistory.mockResolvedValueOnce({
            runs: [makeRun('run_1'), makeRun('run_2')],
            total: 3,
        });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        fetchHistory.mockResolvedValueOnce({ runs: [makeRun('run_3')], total: 3 });
        panel.element.querySelector('#history-load-more-btn').click();
        await Promise.resolve();
        await Promise.resolve();

        expect(fetchHistory).toHaveBeenLastCalledWith(20, 2);
        expect(panel.runsList).toHaveLength(3);
        expect(panel.element.querySelector('#history-load-more-btn')).toBeNull();
    });

    it('calls onReloadRun when a run card is clicked', async () => {
        const onReloadRun = vi.fn();
        fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

        const panel = new HistoryPanel({ onReloadRun, onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        panel.element.querySelector('#history-runs-list > div').click();
        expect(onReloadRun).toHaveBeenCalledWith(expect.objectContaining({ id: 'run_1' }));
    });

    it('escapes HTML in a run id / pdb_id instead of injecting it into the DOM', async () => {
        // pdb_ids trace back to user input at job-submission time - this
        // must not assume that upstream validation always holds by the
        // time a run reaches history.
        fetchHistory.mockResolvedValue({
            runs: [
                {
                    id: '<img src=x onerror=alert(1)>',
                    timestamp: '2026-01-01',
                    pdb_ids: ['<script>alert(2)</script>'],
                    status: 'success',
                },
            ],
            total: 1,
        });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        const container = panel.element.querySelector('#history-runs-list');
        expect(container.querySelector('img')).toBeNull();
        expect(container.querySelector('script')).toBeNull();
        expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
        expect(container.textContent).toContain('<script>alert(2)</script>');
    });

    it('copies the share link and does not trigger onReloadRun when "Share" is clicked', async () => {
        const onReloadRun = vi.fn();
        fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

        const panel = new HistoryPanel({ onReloadRun, onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        panel.element.querySelector('.share-run-btn').click();

        expect(getShareLink).toHaveBeenCalledWith('run_1');
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost/?shared_run=run_1');
        expect(onReloadRun).not.toHaveBeenCalled();
    });

    it('shows "Copied!" feedback on the Share button after clicking', async () => {
        fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        const shareBtn = panel.element.querySelector('.share-run-btn');
        shareBtn.click();

        expect(shareBtn.innerText).toBe('Copied!');
    });

    it('deletes a run when Delete is clicked and confirmed, without triggering onReloadRun', async () => {
        const onReloadRun = vi.fn();
        deleteRun.mockResolvedValue({ deleted: 'run_1' });
        fetchHistory.mockResolvedValue({
            runs: [makeRun('run_1'), makeRun('run_2')],
            total: 2,
        });

        const panel = new HistoryPanel({ onReloadRun, onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        panel.element.querySelector('.delete-run-btn').click();
        await Promise.resolve();
        await Promise.resolve();

        expect(deleteRun).toHaveBeenCalledWith('run_1');
        expect(onReloadRun).not.toHaveBeenCalled();
        expect(panel.runsList.map(r => r.id)).toEqual(['run_2']);
        expect(panel.element.querySelectorAll('#history-runs-list > div')).toHaveLength(1);
    });

    it('does not delete when the confirm dialog is cancelled', async () => {
        vi.stubGlobal('confirm', vi.fn(() => false));
        fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        panel.element.querySelector('.delete-run-btn').click();
        await Promise.resolve();

        expect(deleteRun).not.toHaveBeenCalled();
        expect(panel.runsList).toHaveLength(1);
    });

    it('shows the empty state after deleting the last remaining run', async () => {
        deleteRun.mockResolvedValue({ deleted: 'run_1' });
        fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        panel.element.querySelector('.delete-run-btn').click();
        await Promise.resolve();
        await Promise.resolve();

        expect(panel.element.querySelector('#history-runs-list').textContent)
            .toContain('No past alignment sessions found.');
    });

    it('clears all history when "Clear All History" is clicked and confirmed', async () => {
        clearAllHistory.mockResolvedValue({ cleared: 'all' });
        fetchHistory.mockResolvedValue({
            runs: [makeRun('run_1'), makeRun('run_2')],
            total: 2,
        });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        panel.element.querySelector('#history-clear-all-btn').click();
        await Promise.resolve();
        await Promise.resolve();

        expect(clearAllHistory).toHaveBeenCalled();
        expect(panel.runsList).toHaveLength(0);
        expect(panel.element.querySelector('#history-runs-list').textContent)
            .toContain('No past alignment sessions found.');
    });

    it('does not clear history when there are no runs to clear', async () => {
        fetchHistory.mockResolvedValue({ runs: [], total: 0 });

        const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
        panel.render();
        await Promise.resolve();
        await Promise.resolve();

        panel.element.querySelector('#history-clear-all-btn').click();
        await Promise.resolve();

        expect(clearAllHistory).not.toHaveBeenCalled();
    });

    describe('notes & tags', () => {
        it('shows existing tags and a note preview under the run row', async () => {
            fetchHistory.mockResolvedValue({
                runs: [{ ...makeRun('run_1'), metadata: { notes: 'Interesting fold', tags: ['kinase', 'review'] } }],
                total: 1,
            });

            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            const row = panel.element.querySelector('#history-runs-list > div');
            const tagsDisplay = row.querySelector('[data-field="tags-display"]');
            expect(tagsDisplay.textContent).toContain('kinase');
            expect(tagsDisplay.textContent).toContain('review');
            expect(tagsDisplay.textContent).toContain('Interesting fold');
        });

        it('opens the notes editor pre-filled with existing values, without triggering onReloadRun', async () => {
            const onReloadRun = vi.fn();
            fetchHistory.mockResolvedValue({
                runs: [{ ...makeRun('run_1'), metadata: { notes: 'Existing note', tags: ['a', 'b'] } }],
                total: 1,
            });

            const panel = new HistoryPanel({ onReloadRun, onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            const row = panel.element.querySelector('#history-runs-list > div');
            row.querySelector('.notes-toggle-btn').click();

            const editor = row.querySelector('[data-field="notes-editor"]');
            expect(editor.classList.contains('hidden')).toBe(false);
            expect(row.querySelector('.notes-input').value).toBe('Existing note');
            expect(row.querySelector('.tags-input').value).toBe('a, b');
            expect(onReloadRun).not.toHaveBeenCalled();
        });

        it('saves notes and tags, then re-renders the display and hides the editor', async () => {
            updateRunNotes.mockResolvedValue({ run_id: 'run_1', notes: 'New note', tags: ['x', 'y'] });
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            const row = panel.element.querySelector('#history-runs-list > div');
            row.querySelector('.notes-toggle-btn').click();
            row.querySelector('.notes-input').value = 'New note';
            row.querySelector('.tags-input').value = 'x, y';
            row.querySelector('.notes-save-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(updateRunNotes).toHaveBeenCalledWith('run_1', { notes: 'New note', tags: ['x', 'y'] });
            const editor = row.querySelector('[data-field="notes-editor"]');
            expect(editor.classList.contains('hidden')).toBe(true);
            expect(row.querySelector('[data-field="tags-display"]').textContent).toContain('New note');
        });

        it('cancels the editor without saving', async () => {
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            const row = panel.element.querySelector('#history-runs-list > div');
            row.querySelector('.notes-toggle-btn').click();
            row.querySelector('.notes-cancel-btn').click();

            expect(updateRunNotes).not.toHaveBeenCalled();
            expect(row.querySelector('[data-field="notes-editor"]').classList.contains('hidden')).toBe(true);
        });

        it('shows an alert and keeps the editor open when saving fails', async () => {
            updateRunNotes.mockRejectedValue(new Error('boom'));
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')], total: 1 });

            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            const row = panel.element.querySelector('#history-runs-list > div');
            row.querySelector('.notes-toggle-btn').click();
            row.querySelector('.notes-save-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(alert).toHaveBeenCalledWith('boom');
            expect(row.querySelector('[data-field="notes-editor"]').classList.contains('hidden')).toBe(false);
        });
    });

    describe('RMSD trend across runs', () => {
        function selectOptions(select, values) {
            [...select.options].forEach(o => { o.selected = values.includes(o.value); });
        }

        it('populates the trend selector from the loaded runs list', async () => {
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1'), makeRun('run_2')], total: 2 });

            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            const select = panel.element.querySelector('#trend-run-select');
            expect([...select.options].map(o => o.value)).toEqual(['run_1', 'run_2']);
        });

        it('shows a message instead of fetching when fewer than 2 runs are selected', async () => {
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1'), makeRun('run_2')], total: 2 });
            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            selectOptions(panel.element.querySelector('#trend-run-select'), ['run_1']);
            panel.element.querySelector('#trend-load-btn').click();
            await Promise.resolve();

            expect(fetchRunsTrend).not.toHaveBeenCalled();
            expect(panel.element.querySelector('#trend-plotly').textContent)
                .toContain('Select at least 2 runs');
        });

        it('loads and renders a trend chart for the selected runs', async () => {
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1'), makeRun('run_2')], total: 2 });
            fetchRunsTrend.mockResolvedValue({
                trend: [
                    { run_id: 'run_1', timestamp: '2026-01-01', proteins: ['4RLT'], mean_rmsd: 1.0, max_rmsd: 1.5 },
                    { run_id: 'run_2', timestamp: '2026-02-01', proteins: ['4RLT'], mean_rmsd: 2.0, max_rmsd: 2.5 },
                ],
            });
            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            selectOptions(panel.element.querySelector('#trend-run-select'), ['run_1', 'run_2']);
            panel.element.querySelector('#trend-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(fetchRunsTrend).toHaveBeenCalledWith(['run_1', 'run_2']);
            expect(global.Plotly.newPlot).toHaveBeenCalled();
        });

        it('shows a message when none of the selected runs resolve to a usable trend', async () => {
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1'), makeRun('run_2')], total: 2 });
            fetchRunsTrend.mockResolvedValue({ trend: [] });
            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            selectOptions(panel.element.querySelector('#trend-run-select'), ['run_1', 'run_2']);
            panel.element.querySelector('#trend-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(global.Plotly.newPlot).not.toHaveBeenCalled();
            expect(panel.element.querySelector('#trend-plotly').textContent)
                .toContain('usable RMSD matrix');
        });

        it('shows a graceful message when the trend fetch fails', async () => {
            fetchHistory.mockResolvedValue({ runs: [makeRun('run_1'), makeRun('run_2')], total: 2 });
            fetchRunsTrend.mockRejectedValue(new Error('boom'));
            const panel = new HistoryPanel({ onReloadRun: vi.fn(), onClose: vi.fn() });
            panel.render();
            await Promise.resolve();
            await Promise.resolve();

            selectOptions(panel.element.querySelector('#trend-run-select'), ['run_1', 'run_2']);
            panel.element.querySelector('#trend-load-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(panel.element.querySelector('#trend-plotly').textContent)
                .toContain('Failed to load run trend.');
        });
    });
});
