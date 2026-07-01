import { describe, it, expect, vi, afterEach } from 'vitest';
import { HistoryPanel } from './HistoryPanel.js';

vi.mock('../api.js', () => ({
    fetchHistory: vi.fn(),
}));

import { fetchHistory } from '../api.js';

function makeRun(id) {
    return { id, timestamp: '2026-01-01', pdb_ids: ['4RLT', '3UG9'], status: 'success' };
}

describe('HistoryPanel', () => {
    afterEach(() => {
        vi.clearAllMocks();
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
        expect(panel.runsList.length).toBe(3);
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
});
