import { describe, it, expect, vi, afterEach } from 'vitest';
import { SequenceTab } from './SequenceTab.js';

vi.mock('../api.js', () => ({
    fetchSequence: vi.fn(),
    getAlignmentPdbUrl: vi.fn((runId) => `http://api/results/${runId}/alignment.pdb`),
    getAlignmentFastaUrl: vi.fn((runId) => `http://api/results/${runId}/alignment.fasta`),
    getAlignmentReportUrl: vi.fn((runId, sections) => `http://api/api/report?run_id=${runId}${sections ? `&sections=${sections.join(',')}` : ''}`),
    getLabNotebookUrl: vi.fn((runId) => `http://api/api/notebook?run_id=${runId}`),
    getLabNotebookIpynbUrl: vi.fn((runId) => `http://api/api/notebook/ipynb?run_id=${runId}`),
    getCitationsUrl: vi.fn((runId) => `http://api/api/report/citations?run_id=${runId}`),
    getRmsdCsvUrl: vi.fn((runId) => `http://api/api/report/rmsd-csv?run_id=${runId}`),
    getHeatmapPngUrl: vi.fn((runId) => `http://api/api/report/heatmap-png?run_id=${runId}`),
    getReportZipUrl: vi.fn((runId) => `http://api/api/report/zip?run_id=${runId}`),
    getNewickUrl: vi.fn((runId) => `http://api/api/report/newick?run_id=${runId}`),
    submitClustalOmegaJob: vi.fn(),
    submitConservationJob: vi.fn(),
    pollJobUntilDone: vi.fn(),
}));

import { fetchSequence, submitClustalOmegaJob, submitConservationJob, pollJobUntilDone } from '../api.js';

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

        const rmsdCsvLink = tab.element.querySelector('#download-rmsd-csv-link');
        expect(rmsdCsvLink.classList.contains('pointer-events-none')).toBe(false);
        expect(rmsdCsvLink.href).toContain('run_123');

        const heatmapPngLink = tab.element.querySelector('#download-heatmap-png-link');
        expect(heatmapPngLink.classList.contains('pointer-events-none')).toBe(false);
        expect(heatmapPngLink.href).toContain('run_123');

        const zipLink = tab.element.querySelector('#download-zip-link');
        expect(zipLink.classList.contains('pointer-events-none')).toBe(false);
        expect(zipLink.href).toContain('run_123');

        const newickLink = tab.element.querySelector('#download-newick-link');
        expect(newickLink.classList.contains('pointer-events-none')).toBe(false);
        expect(newickLink.href).toContain('run_123');
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
        expect(wrapper.querySelectorAll('table tbody tr')).toHaveLength(3); // 2 sequences + consensus row
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

    it('enables the Jupyter notebook link once a run is set, and disables it again on reset', () => {
        fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
        const tab = new SequenceTab();
        tab.render();

        tab.updateResults('run_123', { rmsd: 1.0 });

        const notebookIpynbLink = tab.element.querySelector('#download-notebook-ipynb-link');
        expect(notebookIpynbLink.classList.contains('pointer-events-none')).toBe(false);
        expect(notebookIpynbLink.href).toContain('run_123');

        tab.updateResults(null, null);

        expect(notebookIpynbLink.classList.contains('pointer-events-none')).toBe(true);
    });

    it('report checklist defaults to all 5 sections checked with no sections param in the URL', () => {
        fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
        const tab = new SequenceTab();
        tab.render();
        tab.updateResults('run_123', { rmsd: 1.0 });

        const checkboxes = tab.element.querySelectorAll('.report-section-checkbox');
        expect(checkboxes).toHaveLength(5);
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

    describe('sequence motif search', () => {
        it('disables the search button until a run is loaded', () => {
            const tab = new SequenceTab();
            tab.render();

            expect(tab.element.querySelector('#motif-search-btn').disabled).toBe(true);
        });

        it('enables the search button once a run is set', () => {
            fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });

            expect(tab.element.querySelector('#motif-search-btn').disabled).toBe(false);
        });

        it('searches with the query and renders the match summary + table', async () => {
            fetchSequence.mockResolvedValueOnce({ sequences: {}, conservation: [] });
            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();
            await Promise.resolve();

            fetchSequence.mockResolvedValueOnce({
                sequences: {},
                conservation: [],
                motif_matches: { '4RLT': [4, 5, 6], '3UG9': [4, 5, 6] },
                highlight_chains: { A: [3, 4, 5], B: [3, 4, 5] },
            });
            tab.element.querySelector('#motif-search-input').value = 'G.K';
            tab.element.querySelector('#motif-search-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(fetchSequence).toHaveBeenLastCalledWith('run_123', 'G.K');
            const container = tab.element.querySelector('#motif-results-container');
            expect(container.textContent).toContain('Found 6 matching residue positions across 2 structures');
            expect(container.textContent).toContain('4RLT');
            expect(container.textContent).toContain('4, 5, 6');
            expect(container.querySelector('button')).not.toBeNull();
        });

        it('shows a no-matches message when the motif search finds nothing', async () => {
            fetchSequence.mockResolvedValueOnce({ sequences: {}, conservation: [] });
            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();
            await Promise.resolve();

            fetchSequence.mockResolvedValueOnce({
                sequences: {},
                conservation: [],
                motif_matches: {},
                highlight_chains: {},
            });
            tab.element.querySelector('#motif-search-input').value = 'ZZZZ';
            tab.element.querySelector('#motif-search-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#motif-results-container').textContent)
                .toContain('No matches found for this motif pattern.');
        });

        it('clicking "Highlight Motif in 3D Viewer" calls onHighlightResidues with the chain mapping', async () => {
            fetchSequence.mockResolvedValueOnce({ sequences: {}, conservation: [] });
            const onHighlightResidues = vi.fn();
            const tab = new SequenceTab({ onHighlightResidues });
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();
            await Promise.resolve();

            fetchSequence.mockResolvedValueOnce({
                sequences: {},
                conservation: [],
                motif_matches: { '4RLT': [4, 5, 6] },
                highlight_chains: { A: [3, 4, 5] },
            });
            tab.element.querySelector('#motif-search-input').value = 'G.K';
            tab.element.querySelector('#motif-search-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            tab.element.querySelector('#motif-results-container button').click();

            expect(onHighlightResidues).toHaveBeenCalledWith({ A: [3, 4, 5] });
        });

        it('clears the motif input and results when a new run is loaded', async () => {
            fetchSequence.mockResolvedValue({ sequences: {}, conservation: [] });
            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();

            tab.motifMatches = { '4RLT': [1] };
            tab.renderMotifResults();
            tab.element.querySelector('#motif-search-input').value = 'RYY';

            tab.updateResults('run_456', { rmsd: 2.0 });

            expect(tab.element.querySelector('#motif-search-input').value).toBe('');
            expect(tab.element.querySelector('#motif-results-container').innerHTML).toBe('');
        });
    });

    describe('Clustal Omega true sequence-only MSA', () => {
        it('strips gaps before submitting, then renders the real aligned result', async () => {
            fetchSequence.mockResolvedValue({
                sequences: { '4RLT': 'MV--HL', '3UG9': '-MVLSH' },
                conservation: [],
            });
            submitClustalOmegaJob.mockResolvedValue({ job_id: 'job-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({
                status: 'completed',
                aligned_fasta: '>4RLT\nMVHL--\n>3UG9\nMVLSH-',
            });

            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();

            tab.element.querySelector('#clustalo-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(submitClustalOmegaJob).toHaveBeenCalledWith({ '4RLT': 'MVHL', '3UG9': 'MVLSH' });
            expect(pollJobUntilDone).toHaveBeenCalledWith('job-1', expect.objectContaining({ intervalMs: 5000 }));

            const wrapper = tab.element.querySelector('#clustalo-result-wrapper');
            expect(wrapper.textContent).toContain('4RLT');
            expect(wrapper.textContent).toContain('3UG9');
            expect(wrapper.querySelectorAll('tbody tr')).toHaveLength(2);
        });

        it('passes the webhook URL through when one is entered', async () => {
            fetchSequence.mockResolvedValue({
                sequences: { '4RLT': 'MVHL', '3UG9': 'MVLSH' },
                conservation: [],
            });
            submitClustalOmegaJob.mockResolvedValue({ job_id: 'job-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({ status: 'completed', aligned_fasta: '>4RLT\nMVHL\n>3UG9\nMVLSH' });

            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();
            tab.element.querySelector('#clustalo-webhook-url').value = 'https://example.com/hook';

            tab.element.querySelector('#clustalo-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(submitClustalOmegaJob).toHaveBeenCalledWith(
                { '4RLT': 'MVHL', '3UG9': 'MVLSH' },
                'https://example.com/hook'
            );
        });

        it('shows the real failure reason when the job fails', async () => {
            fetchSequence.mockResolvedValue({
                sequences: { '4RLT': 'MVHL', '3UG9': 'MVLS' },
                conservation: [],
            });
            submitClustalOmegaJob.mockResolvedValue({ job_id: 'job-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({
                status: 'failed',
                error: 'Clustal Omega job job-1 did not complete within 600s',
            });

            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();

            tab.element.querySelector('#clustalo-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#clustalo-result-wrapper').textContent)
                .toContain('did not complete within 600s');
        });

        it('shows a graceful message when fewer than 2 real sequences resolve', async () => {
            fetchSequence.mockResolvedValue({ sequences: { '4RLT': 'MVHL' }, conservation: [] });

            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();

            tab.element.querySelector('#clustalo-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(submitClustalOmegaJob).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#clustalo-result-wrapper').textContent)
                .toContain('Need at least 2 structures');
        });

        it('shows a graceful message when the submission itself throws', async () => {
            fetchSequence.mockResolvedValue({
                sequences: { '4RLT': 'MVHL', '3UG9': 'MVLS' },
                conservation: [],
            });
            submitClustalOmegaJob.mockRejectedValue(new Error('boom'));

            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();

            tab.element.querySelector('#clustalo-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#clustalo-result-wrapper').textContent)
                .toContain('Failed to run sequence-only alignment.');
        });

        it('disables the button with no run loaded and re-enables it once one is set', () => {
            const tab = new SequenceTab();
            tab.render();

            expect(tab.element.querySelector('#clustalo-run-btn').disabled).toBe(true);

            tab.updateResults('run_123', { rmsd: 1.0 });

            expect(tab.element.querySelector('#clustalo-run-btn').disabled).toBe(false);
        });
    });

    describe('real evolutionary conservation (BLAST)', () => {
        async function setUpWithSequences(tab) {
            fetchSequence.mockResolvedValue({
                sequences: { '4RLT': 'MVHLTPEE--KSAVTAL', '3UG9': '-MVLSPADKTNVKAAWGK' },
                conservation: [],
            });
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();
        }

        it('populates the structure selector from the run sequences', async () => {
            const tab = new SequenceTab();
            await setUpWithSequences(tab);

            const options = Array.from(tab.element.querySelector('#conservation-structure-select').options).map(o => o.value);
            expect(options).toEqual(['4RLT', '3UG9']);
        });

        it('strips gaps before submitting, then renders the real conservation profile', async () => {
            submitConservationJob.mockResolvedValue({ job_id: 'blast-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({
                status: 'completed',
                num_hits: 10,
                conservation_profile: [
                    { position: 1, conservation: 1.0, num_homologs: 10, most_common: 'M' },
                    { position: 2, conservation: 0.5, num_homologs: 10, most_common: 'V' },
                ],
            });

            const tab = new SequenceTab();
            await setUpWithSequences(tab);

            tab.element.querySelector('#conservation-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(submitConservationJob).toHaveBeenCalledWith('MVHLTPEEKSAVTAL');
            expect(pollJobUntilDone).toHaveBeenCalledWith('blast-1', expect.objectContaining({ intervalMs: 15000 }));

            const wrapper = tab.element.querySelector('#conservation-result-wrapper');
            expect(wrapper.textContent).toContain('10 real homolog');
            expect(wrapper.querySelectorAll('td[title]')).toHaveLength(2);
        });

        it('renders a sequence logo from the per-position residue distribution', async () => {
            global.Plotly = { newPlot: vi.fn() };
            submitConservationJob.mockResolvedValue({ job_id: 'blast-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({
                status: 'completed',
                num_hits: 10,
                conservation_profile: [
                    { position: 1, conservation: 1.0, num_homologs: 10, most_common: 'M', residue_counts: { M: 10 } },
                    { position: 2, conservation: 0.5, num_homologs: 10, most_common: 'V', residue_counts: { V: 5, L: 5 } },
                ],
            });

            const tab = new SequenceTab();
            await setUpWithSequences(tab);

            tab.element.querySelector('#conservation-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(global.Plotly.newPlot).toHaveBeenCalled();
            const logoContainer = tab.element.querySelector('#conservation-logo-plotly');
            expect(logoContainer.classList.contains('hidden')).toBe(false);

            delete global.Plotly;
        });

        it('keeps the sequence logo hidden when no position has any residue distribution', async () => {
            submitConservationJob.mockResolvedValue({ job_id: 'blast-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({
                status: 'completed',
                num_hits: 0,
                conservation_profile: [
                    { position: 1, conservation: null, num_homologs: 0, most_common: null, residue_counts: {} },
                ],
            });

            const tab = new SequenceTab();
            await setUpWithSequences(tab);

            tab.element.querySelector('#conservation-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#conservation-logo-plotly').classList.contains('hidden')).toBe(true);
        });

        it('passes the webhook URL through when one is entered', async () => {
            submitConservationJob.mockResolvedValue({ job_id: 'blast-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({ status: 'completed', num_hits: 1, conservation_profile: [] });

            const tab = new SequenceTab();
            await setUpWithSequences(tab);
            tab.element.querySelector('#conservation-webhook-url').value = 'https://example.com/hook';

            tab.element.querySelector('#conservation-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(submitConservationJob).toHaveBeenCalledWith('MVHLTPEEKSAVTAL', 'https://example.com/hook');
        });

        it('shows the real failure reason when the BLAST job fails', async () => {
            submitConservationJob.mockResolvedValue({ job_id: 'blast-1', status: 'queued' });
            pollJobUntilDone.mockResolvedValue({
                status: 'failed',
                error: 'BLAST job blast-1 did not complete within 1200s',
            });

            const tab = new SequenceTab();
            await setUpWithSequences(tab);

            tab.element.querySelector('#conservation-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(tab.element.querySelector('#conservation-result-wrapper').textContent)
                .toContain('did not complete within 1200s');
        });

        it('shows a graceful message when the selected sequence is too short', async () => {
            fetchSequence.mockResolvedValue({ sequences: { '4RLT': 'MV' }, conservation: [] });

            const tab = new SequenceTab();
            tab.render();
            tab.updateResults('run_123', { rmsd: 1.0 });
            await Promise.resolve();

            tab.element.querySelector('#conservation-run-btn').click();
            await Promise.resolve();
            await Promise.resolve();

            expect(submitConservationJob).not.toHaveBeenCalled();
            expect(tab.element.querySelector('#conservation-result-wrapper').textContent)
                .toContain('too short');
        });

        it('disables the button with no run loaded and re-enables it once one is set', () => {
            const tab = new SequenceTab();
            tab.render();

            expect(tab.element.querySelector('#conservation-run-btn').disabled).toBe(true);

            tab.updateResults('run_123', { rmsd: 1.0 });

            expect(tab.element.querySelector('#conservation-run-btn').disabled).toBe(false);
        });
    });
});
