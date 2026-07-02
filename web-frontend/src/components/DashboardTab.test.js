import { describe, it, expect, vi, afterEach } from 'vitest';
import { DashboardTab } from './DashboardTab.js';

vi.mock('../api.js', () => ({
    fetchStats: vi.fn(),
    fetchHistory: vi.fn(),
}));

import { fetchStats, fetchHistory } from '../api.js';

function makeRun(id) {
    return { id, timestamp: '2026-01-01', pdb_ids: ['4RLT', '3UG9'] };
}

describe('DashboardTab', () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('renders quick-start buttons immediately, without waiting on any fetch', () => {
        fetchStats.mockResolvedValue({ total_runs: 0, total_proteins_analyzed: 0, cache_size_mb: 0 });
        fetchHistory.mockResolvedValue({ runs: [] });

        const tab = new DashboardTab({ onReloadRun: vi.fn(), onQuickStart: vi.fn() });
        tab.render();

        const buttons = tab.element.querySelectorAll('.quick-start-btn');
        expect(buttons.length).toBeGreaterThan(0);
    });

    it('clicking a quick-start button calls onQuickStart with its PDB IDs', () => {
        fetchStats.mockResolvedValue({ total_runs: 0, total_proteins_analyzed: 0, cache_size_mb: 0 });
        fetchHistory.mockResolvedValue({ runs: [] });
        const onQuickStart = vi.fn();

        const tab = new DashboardTab({ onReloadRun: vi.fn(), onQuickStart });
        tab.render();
        tab.element.querySelector('.quick-start-btn').click();

        expect(onQuickStart).toHaveBeenCalledWith(expect.any(Array));
        expect(onQuickStart.mock.calls[0][0].length).toBeGreaterThan(0);
    });

    it('populates the stat cards from fetchStats', async () => {
        fetchStats.mockResolvedValue({ total_runs: 12, total_proteins_analyzed: 30, cache_size_mb: 4.5 });
        fetchHistory.mockResolvedValue({ runs: [] });

        const tab = new DashboardTab({ onReloadRun: vi.fn(), onQuickStart: vi.fn() });
        tab.render();
        await tab.loadDashboardData();

        expect(tab.element.querySelector('#stat-total-runs').textContent).toBe('12');
        expect(tab.element.querySelector('#stat-total-proteins').textContent).toBe('30');
        expect(tab.element.querySelector('#stat-cache-size').textContent).toBe('4.5 MB');
    });

    it('shows an empty state when there is no recent activity', async () => {
        fetchStats.mockResolvedValue({ total_runs: 0, total_proteins_analyzed: 0, cache_size_mb: 0 });
        fetchHistory.mockResolvedValue({ runs: [] });

        const tab = new DashboardTab({ onReloadRun: vi.fn(), onQuickStart: vi.fn() });
        tab.render();
        await tab.loadDashboardData();

        expect(tab.element.querySelector('#dashboard-recent-runs').textContent)
            .toContain('No past alignment sessions found.');
    });

    it('lists recent runs and calls onReloadRun when a row is clicked', async () => {
        fetchStats.mockResolvedValue({ total_runs: 1, total_proteins_analyzed: 2, cache_size_mb: 0.1 });
        fetchHistory.mockResolvedValue({ runs: [makeRun('run_1')] });
        const onReloadRun = vi.fn();

        const tab = new DashboardTab({ onReloadRun, onQuickStart: vi.fn() });
        tab.render();
        await tab.loadDashboardData();

        expect(fetchHistory).toHaveBeenCalledWith(5, 0);
        tab.element.querySelector('#dashboard-recent-runs > div').click();
        expect(onReloadRun).toHaveBeenCalledWith(expect.objectContaining({ id: 'run_1' }));
    });

    it('shows an error state when fetching recent activity fails', async () => {
        fetchStats.mockResolvedValue({ total_runs: 0, total_proteins_analyzed: 0, cache_size_mb: 0 });
        fetchHistory.mockRejectedValue(new Error('boom'));

        const tab = new DashboardTab({ onReloadRun: vi.fn(), onQuickStart: vi.fn() });
        tab.render();
        await tab.loadDashboardData();

        expect(tab.element.querySelector('#dashboard-recent-runs').textContent)
            .toContain('Failed to retrieve recent activity.');
    });
});
