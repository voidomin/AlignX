import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ComparisonTab } from './ComparisonTab.js';

vi.mock('../api.js', () => ({
    fetchComparisonRuns: vi.fn(),
    fetchComparison: vi.fn(),
}));

import { fetchComparisonRuns, fetchComparison } from '../api.js';

describe('ComparisonTab', () => {
    beforeEach(() => {
        global.Plotly = { newPlot: vi.fn() };
    });

    afterEach(() => {
        vi.clearAllMocks();
        delete global.Plotly;
    });

    it('shows a placeholder and skips fetching when there is no current run', async () => {
        const tab = new ComparisonTab();
        tab.render();

        await tab.updateResults(null);

        expect(fetchComparisonRuns).not.toHaveBeenCalled();
        expect(tab.element.querySelector('#comparison-controls').textContent)
            .toContain('Run an alignment to enable comparison.');
    });

    it('shows a message when there are no other past runs', async () => {
        fetchComparisonRuns.mockResolvedValue({ runs: [] });

        const tab = new ComparisonTab();
        tab.render();
        await tab.updateResults('run_current');

        expect(fetchComparisonRuns).toHaveBeenCalledWith('run_current');
        expect(tab.element.querySelector('#comparison-controls').textContent)
            .toContain('No other past runs found for comparison.');
    });

    it('populates the target-run dropdown and defaults to the first past run', async () => {
        fetchComparisonRuns.mockResolvedValue({
            runs: [
                { id: 'run_a', timestamp: '2026-01-01', proteins: ['4RLT', '3UG9'] },
                { id: 'run_b', timestamp: '2026-01-02', proteins: ['1L2Y'] },
            ],
        });

        const tab = new ComparisonTab();
        tab.render();
        await tab.updateResults('run_current');

        const select = tab.element.querySelector('#comparison-target-select');
        expect(select).not.toBeNull();
        expect(select.querySelectorAll('option')).toHaveLength(2);
        expect(tab.targetRunId).toBe('run_a');
    });

    it('runs comparison on button click and renders the diff heatmap + stats', async () => {
        fetchComparisonRuns.mockResolvedValue({
            runs: [{ id: 'run_a', timestamp: '2026-01-01', proteins: ['4RLT', '3UG9'] }],
        });
        fetchComparison.mockResolvedValue({
            current_run_id: 'run_current',
            target_run_id: 'run_a',
            diff: { index: ['4RLT', '3UG9'], columns: ['4RLT', '3UG9'], data: [[0, 0.5], [0.5, 0]] },
            current_mean_rmsd: 1.5,
            target_mean_rmsd: 1.0,
            mean_rmsd_shift: 0.5,
        });

        const tab = new ComparisonTab();
        tab.render();
        await tab.updateResults('run_current');

        tab.element.querySelector('#btn-run-comparison').click();
        await new Promise(resolve => setTimeout(resolve, 0));
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(fetchComparison).toHaveBeenCalledWith('run_current', 'run_a');
        expect(global.Plotly.newPlot).toHaveBeenCalled();
        const html = tab.element.querySelector('#comparison-results-container').innerHTML;
        expect(html).toContain('0.500');
        expect(html).toContain('1.500');
        expect(html).toContain('1.000');
    });

    it('shows an error message when the comparison fetch fails', async () => {
        fetchComparisonRuns.mockResolvedValue({
            runs: [{ id: 'run_a', timestamp: '2026-01-01', proteins: ['4RLT'] }],
        });
        fetchComparison.mockRejectedValue(new Error('No overlapping proteins found between these runs.'));

        const tab = new ComparisonTab();
        tab.render();
        await tab.updateResults('run_current');

        tab.element.querySelector('#btn-run-comparison').click();
        await new Promise(resolve => setTimeout(resolve, 0));
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(tab.element.querySelector('#comparison-results-container').textContent)
            .toContain('No overlapping proteins found between these runs.');
    });
});
