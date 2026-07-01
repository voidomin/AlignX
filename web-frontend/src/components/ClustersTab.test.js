import { describe, it, expect, vi, afterEach } from 'vitest';
import { ClustersTab } from './ClustersTab.js';

vi.mock('../api.js', () => ({
    fetchClusters: vi.fn(),
}));

import { fetchClusters } from '../api.js';

describe('ClustersTab', () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('renders a threshold slider defaulting to 3.0', () => {
        const tab = new ClustersTab();
        const el = tab.render();

        const slider = el.querySelector('#cluster-threshold-slider');
        expect(slider.value).toBe('3.0');
        expect(el.querySelector('#cluster-threshold-value').textContent).toBe('3.00 Å');
    });

    it('shows a placeholder when no rmsd matrix is available', async () => {
        const tab = new ClustersTab();
        tab.render();

        await tab.updateResults(null, {});

        expect(fetchClusters).not.toHaveBeenCalled();
        expect(tab.element.querySelector('#clusters-list-container').textContent)
            .toContain('Run alignment to identify structural clusters.');
    });

    it('fetches and renders clusters when an rmsd matrix is provided', async () => {
        fetchClusters.mockResolvedValue({
            threshold: 3.0,
            clusters: [
                { cluster_id: 1, members: ['4RLT', '3UG9'], avg_rmsd: 1.2 },
            ],
        });

        const tab = new ClustersTab();
        tab.render();
        const rmsdDf = { index: ['4RLT', '3UG9'], columns: ['4RLT', '3UG9'], data: [[0, 1.2], [1.2, 0]] };

        await tab.updateResults(rmsdDf, { '4RLT': { title: 'Test Protein' } });

        expect(fetchClusters).toHaveBeenCalledWith(rmsdDf, 3.0);
        const html = tab.element.querySelector('#clusters-list-container').innerHTML;
        expect(html).toContain('Cluster 1');
        expect(html).toContain('4RLT');
        expect(html).toContain('Test Protein');
        expect(html).toContain('1.20');
    });

    it('shows an error message when the clusters fetch fails', async () => {
        fetchClusters.mockRejectedValue(new Error('network down'));

        const tab = new ClustersTab();
        tab.render();
        await tab.updateResults({ index: ['A'], columns: ['A'], data: [[0]] }, {});

        expect(tab.element.querySelector('#clusters-list-container').textContent)
            .toContain('Failed to compute structural clusters.');
    });

    it('re-fetches clusters with the new threshold when the slider changes', async () => {
        fetchClusters.mockResolvedValue({ threshold: 5.0, clusters: [] });

        const tab = new ClustersTab();
        tab.render();
        await tab.updateResults({ index: ['A', 'B'], columns: ['A', 'B'], data: [[0, 1], [1, 0]] }, {});
        fetchClusters.mockClear();

        const slider = tab.element.querySelector('#cluster-threshold-slider');
        slider.value = '5.0';
        slider.dispatchEvent(new Event('input'));

        await new Promise(resolve => setTimeout(resolve, 300));

        expect(fetchClusters).toHaveBeenCalledWith(expect.anything(), 5.0);
    });
});
