import { fetchSequence, getAlignmentPdbUrl, getAlignmentFastaUrl } from '../api';

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
            <!-- Alignment Statistics Card -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-tertiary">analytics</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Alignment Report</h4>
                </div>
                <div id="alignment-stats-container" class="grid grid-cols-2 gap-4">
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">RMSD</span>
                        <span id="stat-rmsd" class="font-headline-sm text-headline-sm font-semibold text-success font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Aligned Length</span>
                        <span id="stat-length" class="font-headline-sm text-headline-sm font-semibold text-primary font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Seq Identity</span>
                        <span id="stat-identity" class="font-headline-sm text-headline-sm font-semibold text-secondary font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Seq Similarity</span>
                        <span id="stat-similarity" class="font-headline-sm text-headline-sm font-semibold text-tertiary font-mono">--</span>
                    </div>
                </div>
            </div>
            
            <!-- Dynamic Sequence Alignment Table -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 overflow-hidden">
                <div class="flex items-center gap-2 border-b border-white/10 pb-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">format_align_justify</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Sequence Alignment View</h4>
                </div>
                <div id="sequence-alignment-grid-wrapper" class="overflow-x-auto rounded-lg max-h-[350px]">
                    <div class="text-center py-8 text-text-secondary font-body-sm">
                        Run alignment to generate sequence view.
                    </div>
                </div>
            </div>

            <!-- Output Files -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-3 bg-[#11141c]/50">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-text-secondary">folder_zip</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Generated Outputs</h4>
                </div>
                <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between p-2.5 rounded bg-white/5 hover:bg-white/10 transition-colors">
                        <span class="font-body-sm text-body-sm text-text-primary font-mono">alignment.pdb</span>
                        <a id="download-pdb-link" href="#" target="_blank" class="text-secondary text-body-sm hover:underline flex items-center gap-1 opacity-55 pointer-events-none">
                            <span class="material-symbols-outlined text-[16px]">open_in_new</span> View PDB
                        </a>
                    </div>
                    <div class="flex items-center justify-between p-2.5 rounded bg-white/5 hover:bg-white/10 transition-colors">
                        <span class="font-body-sm text-body-sm text-text-primary font-mono">alignment.fasta</span>
                        <a id="download-fasta-link" href="#" target="_blank" class="text-secondary text-body-sm hover:underline flex items-center gap-1 opacity-55 pointer-events-none">
                            <span class="material-symbols-outlined text-[16px]">open_in_new</span> View FASTA
                        </a>
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
        const identityText = this.stats.seq_identity != null ? `${(this.stats.seq_identity * 100).toFixed(1)}%` : '--';
        const similarityText = this.stats.seq_similarity != null ? `${(this.stats.seq_similarity * 100).toFixed(1)}%` : '--';

        this.element.querySelector('#stat-rmsd').innerText = rmsdText;
        this.element.querySelector('#stat-length').innerText = lengthText;
        this.element.querySelector('#stat-identity').innerText = identityText;
        this.element.querySelector('#stat-similarity').innerText = similarityText;

        const pdbLink = this.element.querySelector('#download-pdb-link');
        const fastaLink = this.element.querySelector('#download-fasta-link');
        
        if (this.currentRunId) {
            pdbLink.href = getAlignmentPdbUrl(this.currentRunId);
            pdbLink.classList.remove('opacity-55', 'pointer-events-none');
            
            fastaLink.href = getAlignmentFastaUrl(this.currentRunId);
            fastaLink.classList.remove('opacity-55', 'pointer-events-none');
        } else {
            pdbLink.href = "#";
            pdbLink.classList.add('opacity-55', 'pointer-events-none');
            
            fastaLink.href = "#";
            fastaLink.classList.add('opacity-55', 'pointer-events-none');
        }
    }

    async loadSequenceGrid() {
        if (!this.element || !this.currentRunId) return;

        const wrapper = this.element.querySelector('#sequence-alignment-grid-wrapper');
        wrapper.innerHTML = `
            <div class="text-center py-8 text-text-secondary font-body-sm">
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
                    residuesHtml += `<td class="${resClass} text-center font-mono border border-white/5" style="background-color: ${bgColor}; min-width: 22px; height: 24px; font-size: 12px; color: #fff;">${char}</td>`;
                }

                rowsHtml += `
                    <tr class="border-b border-white/5">
                        <td class="sticky left-0 bg-[#161a24] text-text-primary pr-4 pl-2 font-bold font-mono border-r border-white/10 whitespace-nowrap min-w-[120px] text-body-sm">${header}</td>
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

                consensusHtml += `<td class="text-center font-mono font-bold text-text-secondary" style="min-width: 22px; height: 20px;">${symbol}</td>`;
            });

            rowsHtml += `
                <tr class="bg-[#121316]/50">
                    <td class="sticky left-0 bg-[#121316] text-text-secondary pr-4 pl-2 font-bold font-mono border-r border-white/10 whitespace-nowrap min-w-[120px] text-body-sm">Consensus</td>
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
