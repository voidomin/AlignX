import { fetchSequence, getAlignmentPdbUrl, getAlignmentFastaUrl, getAlignmentReportUrl, getLabNotebookUrl, getLabNotebookIpynbUrl, getCitationsUrl, getRmsdCsvUrl, getHeatmapPngUrl, getReportZipUrl, getNewickUrl, submitClustalOmegaJob, submitConservationJob, pollJobUntilDone } from '../api';
import { escapeHtml } from '../escapeHtml';

const REPORT_SECTIONS = [
    { key: 'summary', label: 'Summary' },
    { key: 'insights', label: 'Insights' },
    { key: 'heatmap', label: 'RMSD Heatmap' },
    { key: 'tree', label: 'Phylogenetic Tree' },
    { key: 'matrix', label: 'RMSD Matrix' },
];

export class SequenceTab {
    currentRunId = null;
    element = null;
    stats = { rmsd: null, aligned_length: null, seq_identity: null, seq_similarity: null };
    motifMatches = null;
    highlightChains = null;

    constructor(props = {}) {
        this.onHighlightResidues = props.onHighlightResidues || (() => {});
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col gap-4 overflow-y-auto pr-1";
        div.id = "tab-sequence-container";
        
        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Alignment Report</span>
                    <h2 class="section-title">Sequence &amp; identity</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-10">
                <div id="alignment-stats-container" class="grid grid-cols-4 gap-6">
                    <div class="stat-row stat-primary">
                        <span class="stat-key">RMSD</span>
                        <span id="stat-rmsd" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Aligned length</span>
                        <span id="stat-length" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Seq identity</span>
                        <span id="stat-identity" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Seq similarity</span>
                        <span id="stat-similarity" class="stat-value">--</span>
                    </div>
                </div>

                <div class="flex flex-col gap-3">
                    <span class="eyebrow">Sequence alignment view</span>
                    <div class="section-caption">
                        Coloring shows identity across the structures loaded in this run, not true evolutionary conservation - see "True sequence-only MSA" below for a real homolog-based conservation profile.
                    </div>
                    <div id="sequence-alignment-grid-wrapper" class="overflow-x-auto rounded-md max-h-[350px]">
                        <div class="text-center py-8 text-secondary font-body-sm">
                            Run alignment to generate sequence view.
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <div class="flex items-center justify-between">
                        <span class="eyebrow">True sequence-only MSA (Clustal Omega)</span>
                        <button id="clustalo-run-btn" class="btn-secondary py-1.5 px-3 rounded-md font-label-md text-label-md" disabled>Run true sequence alignment</button>
                    </div>
                    <div class="section-caption">
                        Independent of Mustang's structural alignment above - a real multiple sequence alignment computed purely from each structure's own sequence, via EBI's public Clustal Omega service. Can disagree with the structural alignment for divergent sequences with similar folds.
                    </div>
                    <label class="flex flex-col gap-1">
                        <span class="font-label-sm text-label-sm text-secondary">Notify me when done - we'll POST to this URL when the job finishes (optional)</span>
                        <input id="clustalo-webhook-url" type="url" placeholder="https://..." class="max-w-[320px] bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent font-mono" />
                    </label>
                    <div id="clustalo-result-wrapper" class="overflow-x-auto rounded-md max-h-[350px]"></div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <div class="flex items-center justify-between">
                        <span class="eyebrow">Real evolutionary conservation (NCBI BLAST)</span>
                        <div class="flex items-center gap-2">
                            <select id="conservation-structure-select" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[160px]"></select>
                            <button id="conservation-run-btn" class="btn-secondary py-1.5 px-3 rounded-md font-label-md text-label-md" disabled>Find real homologs</button>
                        </div>
                    </div>
                    <div class="section-caption">
                        Searches NCBI BLAST for real homologs of the selected structure's sequence, then scores real per-position conservation from their alignments (Shannon entropy) - genuinely different from the identity-based coloring above. Real BLAST searches commonly take several minutes.
                    </div>
                    <label class="flex flex-col gap-1">
                        <span class="font-label-sm text-label-sm text-secondary">Notify me when done - we'll POST to this URL when the job finishes (optional)</span>
                        <input id="conservation-webhook-url" type="url" placeholder="https://..." class="max-w-[320px] bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent font-mono" />
                    </label>
                    <div id="conservation-result-wrapper" class="overflow-x-auto rounded-md max-h-[350px]"></div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="eyebrow">Sequence motif search</span>
                    <div class="section-caption">
                        Search for a residue motif (e.g. <code>RYY</code>, <code>G.G</code>, <code>G-X-P</code> — <code>X</code>/<code>.</code>/<code>-</code> act as single-residue wildcards) and highlight every match in the 3D viewer.
                    </div>
                    <div class="flex gap-2">
                        <input id="motif-search-input" type="text" placeholder="e.g. RYY or G.G" class="flex-1 bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary uppercase" />
                        <button id="motif-search-btn" class="btn-primary py-2 px-4 rounded-md font-label-md text-label-md" disabled>Search</button>
                    </div>
                    <div id="motif-results-container"></div>
                </div>

                <div class="flex flex-col gap-2 border-t border-border pt-6">
                    <span class="eyebrow mb-2">Generated outputs</span>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">alignment.pdb</span>
                        <a id="download-pdb-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View PDB</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">alignment.fasta</span>
                        <a id="download-fasta-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View FASTA</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">lab_notebook.html</span>
                        <a id="download-notebook-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">View Notebook</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">lab_notebook.ipynb</span>
                        <a id="download-notebook-ipynb-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download Jupyter Notebook</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">mustang_report.pdf</span>
                        <a id="download-report-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download PDF</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">citations.txt</span>
                        <a id="download-citations-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Export Citations</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">rmsd_matrix.csv</span>
                        <a id="download-rmsd-csv-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download CSV</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">rmsd_heatmap.png</span>
                        <a id="download-heatmap-png-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download PNG</a>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle">
                        <span class="font-body-sm text-body-sm text-primary font-mono">tree.newick</span>
                        <a id="download-newick-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download Tree</a>
                    </div>
                    <div class="flex items-center justify-between py-2">
                        <span class="font-body-sm text-body-sm text-primary font-mono">everything.zip</span>
                        <a id="download-zip-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download Everything</a>
                    </div>
                    <div id="report-section-checklist" class="flex flex-wrap gap-x-4 gap-y-1.5 pt-2">
                        ${REPORT_SECTIONS.map(s => `
                            <label class="flex items-center gap-1.5 font-label-sm text-label-sm text-secondary cursor-pointer">
                                <input type="checkbox" class="report-section-checkbox rounded border-border bg-surface-raised text-accent focus:ring-0 focus:ring-offset-0" value="${s.key}" checked/>
                                ${s.label}
                            </label>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        this.refreshStats();
        return div;
    }

    setupEventListeners() {
        this.element.querySelectorAll('.report-section-checkbox').forEach(cb => {
            cb.addEventListener('change', () => this.updateReportLink());
        });

        const motifInput = this.element.querySelector('#motif-search-input');
        const motifBtn = this.element.querySelector('#motif-search-btn');
        motifBtn.addEventListener('click', () => this.searchMotif(motifInput.value));
        motifInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.searchMotif(motifInput.value);
        });

        this.element.querySelector('#clustalo-run-btn').addEventListener('click', () => this.runClustalOmegaAlignment());
        this.element.querySelector('#conservation-run-btn').addEventListener('click', () => this.runConservationSearch());
    }

    async searchMotif(query) {
        if (!this.currentRunId || !query?.trim()) return;

        const resultsContainer = this.element.querySelector('#motif-results-container');
        resultsContainer.innerHTML = `
            <div class="text-center py-4 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Searching...
            </div>
        `;

        try {
            const data = await fetchSequence(this.currentRunId, query.trim());
            this.motifMatches = data.motif_matches || {};
            this.highlightChains = data.highlight_chains || {};
            this.renderMotifResults();
        } catch (err) {
            console.error("Motif search failed:", err);
            resultsContainer.innerHTML = `
                <div class="text-center py-4 text-error font-body-sm">
                    Motif search failed.
                </div>
            `;
        }
    }

    renderMotifResults() {
        const resultsContainer = this.element.querySelector('#motif-results-container');
        const matches = this.motifMatches || {};
        const names = Object.keys(matches);

        if (names.length === 0) {
            resultsContainer.innerHTML = `
                <div class="text-center py-4 text-secondary font-body-sm">
                    No matches found for this motif pattern.
                </div>
            `;
            return;
        }

        const totalHits = names.reduce((sum, name) => sum + matches[name].length, 0);

        resultsContainer.innerHTML = "";

        const summary = document.createElement('div');
        summary.className = "text-success font-body-sm";
        summary.textContent = `Found ${totalHits} matching residue position${totalHits === 1 ? '' : 's'} across ${names.length} structure${names.length === 1 ? '' : 's'}.`;
        resultsContainer.appendChild(summary);

        const table = document.createElement('table');
        table.className = "w-full text-left border-collapse mt-2";
        const tbody = document.createElement('tbody');
        names.forEach(name => {
            const tr = document.createElement('tr');
            tr.className = "border-b border-border-subtle";
            const nameCell = document.createElement('td');
            nameCell.className = "py-1.5 pr-4 font-body-sm font-mono text-primary";
            nameCell.textContent = name;
            const colsCell = document.createElement('td');
            colsCell.className = "py-1.5 font-body-sm font-mono text-secondary";
            colsCell.textContent = matches[name].join(', ');
            tr.appendChild(nameCell);
            tr.appendChild(colsCell);
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        resultsContainer.appendChild(table);

        const highlightBtn = document.createElement('button');
        highlightBtn.className = "btn-primary py-2 px-4 rounded-md font-label-md text-label-md mt-3";
        highlightBtn.textContent = "Highlight Motif in 3D Viewer";
        highlightBtn.addEventListener('click', () => this.onHighlightResidues(this.highlightChains));
        resultsContainer.appendChild(highlightBtn);
    }

    updateReportLink() {
        if (!this.element) return;
        const reportLink = this.element.querySelector('#download-report-link');
        if (!this.currentRunId) return;

        const checkboxes = Array.from(this.element.querySelectorAll('.report-section-checkbox'));
        const selected = checkboxes.filter(cb => cb.checked).map(cb => cb.value);

        if (selected.length === 0) {
            reportLink.classList.add('opacity-55', 'pointer-events-none');
            return;
        }

        reportLink.classList.remove('opacity-55', 'pointer-events-none');
        const allChecked = selected.length === checkboxes.length;
        reportLink.href = getAlignmentReportUrl(this.currentRunId, allChecked ? null : selected);
    }

    updateResults(runId, stats) {
        this.currentRunId = runId;
        this.stats = stats || {};
        this.motifMatches = null;
        this.highlightChains = null;
        this.refreshStats();
        this.loadSequenceGrid();
        if (this.element) {
            this.element.querySelector('#motif-search-input').value = "";
            this.element.querySelector('#motif-results-container').innerHTML = "";
            this.element.querySelector('#clustalo-result-wrapper').innerHTML = "";
            this.element.querySelector('#conservation-result-wrapper').innerHTML = "";
            this.element.querySelector('#conservation-structure-select').innerHTML = "";
        }
    }

    refreshStats() {
        if (!this.element) return;
        
        const rmsdText = this.stats.rmsd != null ? `${Number.parseFloat(this.stats.rmsd).toFixed(2)} Å` : '--';
        const lengthText = this.stats.aligned_length != null ? this.stats.aligned_length : '--';
        const identityText = this.stats.seq_identity != null ? `${Number.parseFloat(this.stats.seq_identity).toFixed(1)}%` : '--';
        const similarityText = this.stats.seq_similarity != null ? `${Number.parseFloat(this.stats.seq_similarity).toFixed(1)}%` : '--';

        this.element.querySelector('#stat-rmsd').innerText = rmsdText;
        this.element.querySelector('#stat-length').innerText = lengthText;
        this.element.querySelector('#stat-identity').innerText = identityText;
        this.element.querySelector('#stat-similarity').innerText = similarityText;

        const pdbLink = this.element.querySelector('#download-pdb-link');
        const fastaLink = this.element.querySelector('#download-fasta-link');
        const notebookLink = this.element.querySelector('#download-notebook-link');
        const notebookIpynbLink = this.element.querySelector('#download-notebook-ipynb-link');
        const reportLink = this.element.querySelector('#download-report-link');
        const citationsLink = this.element.querySelector('#download-citations-link');
        const rmsdCsvLink = this.element.querySelector('#download-rmsd-csv-link');
        const heatmapPngLink = this.element.querySelector('#download-heatmap-png-link');
        const newickLink = this.element.querySelector('#download-newick-link');
        const zipLink = this.element.querySelector('#download-zip-link');
        const motifBtn = this.element.querySelector('#motif-search-btn');
        motifBtn.disabled = !this.currentRunId;

        const clustaloBtn = this.element.querySelector('#clustalo-run-btn');
        clustaloBtn.disabled = !this.currentRunId;

        const conservationBtn = this.element.querySelector('#conservation-run-btn');
        conservationBtn.disabled = !this.currentRunId;

        if (this.currentRunId) {
            pdbLink.href = getAlignmentPdbUrl(this.currentRunId);
            pdbLink.classList.remove('opacity-55', 'pointer-events-none');

            fastaLink.href = getAlignmentFastaUrl(this.currentRunId);
            fastaLink.classList.remove('opacity-55', 'pointer-events-none');

            notebookLink.href = getLabNotebookUrl(this.currentRunId);
            notebookLink.classList.remove('opacity-55', 'pointer-events-none');

            notebookIpynbLink.href = getLabNotebookIpynbUrl(this.currentRunId);
            notebookIpynbLink.classList.remove('opacity-55', 'pointer-events-none');

            citationsLink.href = getCitationsUrl(this.currentRunId);
            citationsLink.classList.remove('opacity-55', 'pointer-events-none');

            rmsdCsvLink.href = getRmsdCsvUrl(this.currentRunId);
            rmsdCsvLink.classList.remove('opacity-55', 'pointer-events-none');

            heatmapPngLink.href = getHeatmapPngUrl(this.currentRunId);
            heatmapPngLink.classList.remove('opacity-55', 'pointer-events-none');

            newickLink.href = getNewickUrl(this.currentRunId);
            newickLink.classList.remove('opacity-55', 'pointer-events-none');

            zipLink.href = getReportZipUrl(this.currentRunId);
            zipLink.classList.remove('opacity-55', 'pointer-events-none');

            this.element.querySelectorAll('.report-section-checkbox').forEach(cb => { cb.checked = true; });
            this.updateReportLink();
        } else {
            pdbLink.href = "#";
            pdbLink.classList.add('opacity-55', 'pointer-events-none');

            fastaLink.href = "#";
            fastaLink.classList.add('opacity-55', 'pointer-events-none');

            notebookLink.href = "#";
            notebookLink.classList.add('opacity-55', 'pointer-events-none');

            notebookIpynbLink.href = "#";
            notebookIpynbLink.classList.add('opacity-55', 'pointer-events-none');

            citationsLink.href = "#";
            citationsLink.classList.add('opacity-55', 'pointer-events-none');

            rmsdCsvLink.href = "#";
            rmsdCsvLink.classList.add('opacity-55', 'pointer-events-none');

            heatmapPngLink.href = "#";
            heatmapPngLink.classList.add('opacity-55', 'pointer-events-none');

            newickLink.href = "#";
            newickLink.classList.add('opacity-55', 'pointer-events-none');

            zipLink.href = "#";
            zipLink.classList.add('opacity-55', 'pointer-events-none');

            reportLink.href = "#";
            reportLink.classList.add('opacity-55', 'pointer-events-none');
        }
    }

    async loadSequenceGrid() {
        if (!this.element || !this.currentRunId) return;

        const wrapper = this.element.querySelector('#sequence-alignment-grid-wrapper');
        wrapper.innerHTML = `
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Parsing sequence alignment...
            </div>
        `;

        try {
            const data = await fetchSequence(this.currentRunId);
            const { sequences, conservation } = data;

            this._populateConservationStructureSelect(Object.keys(sequences));

            // Render colored scrollable grid
            let rowsHtml = "";

            const colors = {
                identity: "#ff4757",       // Red for conserved
                high_similarity: "#ffa502", // Amber
                gap: "#2f3542",             // Muted dark for gaps
                default: "transparent"
            };

            // Sequence rows
            Object.keys(sequences).forEach(header => {
                const seq = sequences[header];
                let residuesHtml = "";
                
                for (let i = 0; i < seq.length; i++) {
                    const char = seq[i];
                    const score = conservation[i];
                    let bgColor = colors.default;

                    if (char === '-') {
                        bgColor = colors.gap;
                    } else if (score === 1.0) {
                        bgColor = colors.identity;
                    } else if (score > 0.7) {
                        bgColor = colors.high_similarity;
                    }

                    const resClass = (score > 0.5 || char === '-') ? "res-val" : "";
                    residuesHtml += `<td class="${resClass} text-center font-mono border border-border-subtle" style="background-color: ${bgColor}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;">${char}</td>`;
                }

                rowsHtml += `
                    <tr class="border-b border-border-subtle">
                        <td class="sticky left-0 bg-surface-raised text-primary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">${header}</td>
                        ${residuesHtml}
                    </tr>
                `;
            });

            // Consensus row
            let consensusHtml = "";
            conservation.forEach(score => {
                let symbol = "&nbsp;";
                if (score === 1.0) symbol = "*";
                else if (score > 0.7) symbol = ":";
                else if (score > 0.5) symbol = ".";

                consensusHtml += `<td class="text-center font-mono font-bold text-secondary" style="min-width: 22px; height: 20px;">${symbol}</td>`;
            });

            rowsHtml += `
                <tr class="bg-surface">
                    <td class="sticky left-0 bg-surface text-secondary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">Consensus</td>
                    ${consensusHtml}
                </tr>
            `;

            wrapper.innerHTML = `
                <table class="text-left border-collapse">
                    <tbody>
                        ${rowsHtml}
                    </tbody>
                </table>
            `;
        } catch (err) {
            console.error("Failed to render sequence alignment viewer:", err);
            wrapper.innerHTML = `
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to parse alignment FASTA data.
                </div>
            `;
        }
    }

    static _parseFasta(text) {
        const result = {};
        let current = null;
        (text || '').split(/\r?\n/).forEach(line => {
            if (line.startsWith('>')) {
                current = line.slice(1).trim();
                result[current] = '';
            } else if (current) {
                result[current] += line.trim();
            }
        });
        return result;
    }

    // Independent of loadSequenceGrid() above - reuses the same run's raw
    // sequences (gaps stripped, since Mustang's structural correspondence
    // is exactly what this alignment must NOT depend on) but submits them
    // fresh to EBI's Clustal Omega service for a real sequence-only MSA,
    // rather than reading anything Mustang already computed.
    async runClustalOmegaAlignment() {
        if (!this.currentRunId) return;
        const btn = this.element.querySelector('#clustalo-run-btn');
        const wrapper = this.element.querySelector('#clustalo-result-wrapper');

        btn.disabled = true;
        wrapper.innerHTML = `
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Submitting sequences to EBI Clustal Omega…
            </div>
        `;

        try {
            const data = await fetchSequence(this.currentRunId);
            const ungapped = Object.fromEntries(
                Object.entries(data.sequences || {}).map(([id, seq]) => [id, seq.replaceAll('-', '')])
            );

            if (Object.keys(ungapped).length < 2) {
                wrapper.innerHTML = `<div class="text-center py-8 text-secondary font-body-sm">Need at least 2 structures for a sequence alignment.</div>`;
                return;
            }

            const webhookUrl = this.element.querySelector('#clustalo-webhook-url')?.value.trim();
            const submission = webhookUrl
                ? await submitClustalOmegaJob(ungapped, webhookUrl)
                : await submitClustalOmegaJob(ungapped);
            wrapper.innerHTML = `
                <div class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Waiting on EBI Clustal Omega (this can take a couple of minutes)…
                </div>
            `;

            const job = await pollJobUntilDone(submission.job_id, { intervalMs: 5000 });
            if (job.status === 'failed') {
                wrapper.innerHTML = `<div class="text-center py-8 text-error font-body-sm">Clustal Omega alignment failed: ${escapeHtml(job.error || 'unknown error')}</div>`;
                return;
            }

            this.renderClustalOmegaResult(job.aligned_fasta);
        } catch (err) {
            console.error("Clustal Omega alignment failed:", err);
            wrapper.innerHTML = `<div class="text-center py-8 text-error font-body-sm">Failed to run sequence-only alignment.</div>`;
        } finally {
            btn.disabled = !this.currentRunId;
        }
    }

    renderClustalOmegaResult(alignedFastaText) {
        const wrapper = this.element.querySelector('#clustalo-result-wrapper');
        const sequences = SequenceTab._parseFasta(alignedFastaText);
        const headers = Object.keys(sequences);

        if (headers.length === 0) {
            wrapper.innerHTML = `<div class="text-center py-8 text-error font-body-sm">Could not parse the returned alignment.</div>`;
            return;
        }

        const seqLen = Math.max(...headers.map(h => sequences[h].length));
        let rowsHtml = "";
        headers.forEach(header => {
            const seq = sequences[header];
            let residuesHtml = "";
            for (let i = 0; i < seqLen; i++) {
                const char = seq[i] || '-';
                const isConservedColumn = char !== '-' && headers.every(h => (sequences[h][i] || '-') === char);
                let bgColor;
                if (isConservedColumn) {
                    bgColor = "#ff4757";
                } else if (char === '-') {
                    bgColor = "#2f3542";
                } else {
                    bgColor = "transparent";
                }
                residuesHtml += `<td class="text-center font-mono border border-border-subtle" style="background-color: ${bgColor}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;">${escapeHtml(char)}</td>`;
            }
            rowsHtml += `
                <tr class="border-b border-border-subtle">
                    <td class="sticky left-0 bg-surface-raised text-primary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">${escapeHtml(header)}</td>
                    ${residuesHtml}
                </tr>
            `;
        });

        wrapper.innerHTML = `
            <table class="text-left border-collapse">
                <tbody>
                    ${rowsHtml}
                </tbody>
            </table>
        `;
    }

    _populateConservationStructureSelect(headers) {
        const select = this.element.querySelector('#conservation-structure-select');
        const previousValue = select.value;
        select.innerHTML = "";
        headers.forEach(header => {
            const opt = document.createElement('option');
            opt.value = header;
            opt.textContent = header;
            select.appendChild(opt);
        });
        if (headers.includes(previousValue)) {
            select.value = previousValue;
        }
    }

    // Independent of both loadSequenceGrid() and runClustalOmegaAlignment()
    // above - searches a real external homolog database (NCBI BLAST) for
    // just the one selected structure's sequence, rather than comparing
    // sequences already loaded in this workspace against each other.
    async runConservationSearch() {
        if (!this.currentRunId) return;
        const select = this.element.querySelector('#conservation-structure-select');
        const header = select.value;
        const btn = this.element.querySelector('#conservation-run-btn');
        const wrapper = this.element.querySelector('#conservation-result-wrapper');

        if (!header) {
            wrapper.innerHTML = `<div class="text-center py-8 text-secondary font-body-sm">No structure available to search.</div>`;
            return;
        }

        btn.disabled = true;
        wrapper.innerHTML = `
            <div class="text-center py-8 text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Submitting ${escapeHtml(header)}'s sequence to NCBI BLAST…
            </div>
        `;

        try {
            const data = await fetchSequence(this.currentRunId);
            const sequence = (data.sequences?.[header] || '').replaceAll('-', '');

            if (sequence.length < 10) {
                wrapper.innerHTML = `<div class="text-center py-8 text-secondary font-body-sm">Sequence too short for a BLAST search.</div>`;
                return;
            }

            const webhookUrl = this.element.querySelector('#conservation-webhook-url')?.value.trim();
            const submission = webhookUrl
                ? await submitConservationJob(sequence, webhookUrl)
                : await submitConservationJob(sequence);
            wrapper.innerHTML = `
                <div class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Waiting on NCBI BLAST (real searches commonly take several minutes)…
                </div>
            `;

            const job = await pollJobUntilDone(submission.job_id, { intervalMs: 15000 });
            if (job.status === 'failed') {
                wrapper.innerHTML = `<div class="text-center py-8 text-error font-body-sm">BLAST conservation search failed: ${escapeHtml(job.error || 'unknown error')}</div>`;
                return;
            }

            this.renderConservationResult(header, job.conservation_profile, job.num_hits);
        } catch (err) {
            console.error("Conservation search failed:", err);
            wrapper.innerHTML = `<div class="text-center py-8 text-error font-body-sm">Failed to run conservation search.</div>`;
        } finally {
            btn.disabled = !this.currentRunId;
        }
    }

    renderConservationResult(header, profile, numHits) {
        const wrapper = this.element.querySelector('#conservation-result-wrapper');
        if (!profile || profile.length === 0) {
            wrapper.innerHTML = `<div class="text-center py-8 text-error font-body-sm">No conservation profile returned.</div>`;
            return;
        }

        let residuesHtml = "";
        profile.forEach(p => {
            const score = p.conservation;
            const char = p.most_common || '-';
            const bgColor = score == null ? "#2f3542" : `rgba(255, 71, 87, ${score.toFixed(2)})`;
            const title = score == null
                ? 'No homolog coverage at this position'
                : `Conservation: ${(score * 100).toFixed(1)}% (${p.num_homologs} homologs)`;
            residuesHtml += `<td class="text-center font-mono border border-border-subtle" style="background-color: ${bgColor}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;" title="${escapeHtml(title)}">${escapeHtml(char)}</td>`;
        });

        wrapper.innerHTML = `
            <div class="font-body-sm text-[11px] text-secondary pb-2">${numHits} real homolog(s) found via NCBI BLAST</div>
            <table class="text-left border-collapse">
                <tbody>
                    <tr class="border-b border-border-subtle">
                        <td class="sticky left-0 bg-surface-raised text-primary pr-4 pl-2 font-bold font-mono border-r border-border whitespace-nowrap min-w-[120px] text-body-sm">${escapeHtml(header)}</td>
                        ${residuesHtml}
                    </tr>
                </tbody>
            </table>
        `;
    }
}
