import { fetchSequence, getAlignmentPdbUrl, getAlignmentFastaUrl, getAlignmentReportUrl } from '../api';

export class SequenceTab {
    constructor() {
        this.currentRunId = null;
        this.element = null;
        this.stats = { rmsd: null, aligned_length: null, seq_identity: null, seq_similarity: null };
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
                    <div id="sequence-alignment-grid-wrapper" class="overflow-x-auto rounded-md max-h-[350px]">
                        <div class="text-center py-8 text-secondary font-body-sm">
                            Run alignment to generate sequence view.
                        </div>
                    </div>
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
                    <div class="flex items-center justify-between py-2">
                        <span class="font-body-sm text-body-sm text-primary font-mono">mustang_report.pdf</span>
                        <a id="download-report-link" href="#" target="_blank" class="text-accent text-body-sm hover:underline opacity-55 pointer-events-none">Download PDF</a>
                    </div>
                </div>
            </div>
        `;
        this.element = div;
        this.refreshStats();
        return div;
    }

    updateResults(runId, stats) {
        this.currentRunId = runId;
        this.stats = stats || {};
        this.refreshStats();
        this.loadSequenceGrid();
    }

    refreshStats() {
        if (!this.element) return;
        
        const rmsdText = this.stats.rmsd != null ? `${parseFloat(this.stats.rmsd).toFixed(2)} Å` : '--';
        const lengthText = this.stats.aligned_length != null ? this.stats.aligned_length : '--';
        const identityText = this.stats.seq_identity != null ? `${parseFloat(this.stats.seq_identity).toFixed(1)}%` : '--';
        const similarityText = this.stats.seq_similarity != null ? `${parseFloat(this.stats.seq_similarity).toFixed(1)}%` : '--';

        this.element.querySelector('#stat-rmsd').innerText = rmsdText;
        this.element.querySelector('#stat-length').innerText = lengthText;
        this.element.querySelector('#stat-identity').innerText = identityText;
        this.element.querySelector('#stat-similarity').innerText = similarityText;

        const pdbLink = this.element.querySelector('#download-pdb-link');
        const fastaLink = this.element.querySelector('#download-fasta-link');
        const reportLink = this.element.querySelector('#download-report-link');
        
        if (this.currentRunId) {
            pdbLink.href = getAlignmentPdbUrl(this.currentRunId);
            pdbLink.classList.remove('opacity-55', 'pointer-events-none');
            
            fastaLink.href = getAlignmentFastaUrl(this.currentRunId);
            fastaLink.classList.remove('opacity-55', 'pointer-events-none');

            reportLink.href = getAlignmentReportUrl(this.currentRunId);
            reportLink.classList.remove('opacity-55', 'pointer-events-none');
        } else {
            pdbLink.href = "#";
            pdbLink.classList.add('opacity-55', 'pointer-events-none');
            
            fastaLink.href = "#";
            fastaLink.classList.add('opacity-55', 'pointer-events-none');

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
                <table class="w-full text-left border-collapse table-fixed">
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
}
