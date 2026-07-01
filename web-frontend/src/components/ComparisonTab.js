import { fetchComparisonRuns, fetchComparison } from '../api';

export class ComparisonTab {
    constructor() {
        this.currentRunId = null;
        this.pastRuns = [];
        this.targetRunId = null;
        this.element = null;
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col gap-4 overflow-y-auto pr-1";
        div.id = "tab-comparison-container";

        div.innerHTML = `
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">compare_arrows</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Batch Comparison</h4>
                </div>
                <span class="font-body-sm text-body-sm text-text-secondary">
                    Compare this run's RMSD matrix against a past run to see how structural relationships shifted.
                </span>
                <div id="comparison-controls" class="flex flex-col gap-2">
                    <div class="text-center py-4 text-text-secondary font-body-sm">
                        Run an alignment to enable comparison.
                    </div>
                </div>
            </div>

            <div id="comparison-results-container" class="flex flex-col gap-4"></div>
        `;
        this.element = div;
        return div;
    }

    async updateResults(runId) {
        this.currentRunId = runId;
        this.targetRunId = null;
        if (this.element) {
            this.element.querySelector('#comparison-results-container').innerHTML = "";
        }

        if (!runId) {
            this.renderControls();
            return;
        }

        try {
            const data = await fetchComparisonRuns(runId);
            this.pastRuns = data.runs || [];
        } catch (err) {
            console.error("Failed to load comparison run list:", err);
            this.pastRuns = [];
        }
        this.renderControls();
    }

    renderControls() {
        if (!this.element) return;
        const controls = this.element.querySelector('#comparison-controls');

        if (!this.currentRunId) {
            controls.innerHTML = `
                <div class="text-center py-4 text-text-secondary font-body-sm">
                    Run an alignment to enable comparison.
                </div>
            `;
            return;
        }

        if (this.pastRuns.length === 0) {
            controls.innerHTML = `
                <div class="text-center py-4 text-text-secondary font-body-sm">
                    No other past runs found for comparison.
                </div>
            `;
            return;
        }

        controls.innerHTML = `
            <select id="comparison-target-select" class="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 font-body-sm text-text-primary">
                ${this.pastRuns.map(r => `
                    <option value="${r.id}">${r.timestamp} - ${r.id.slice(0, 8)}... (${r.proteins.length} p)</option>
                `).join("")}
            </select>
            <button id="btn-run-comparison" class="w-full py-2 px-3 rounded-lg bg-primary/20 border border-primary/40 text-primary font-label-md text-label-md hover:bg-primary/30 transition-colors">
                🚀 Run Comparative Analysis
            </button>
        `;

        this.targetRunId = this.pastRuns[0].id;
        controls.querySelector('#comparison-target-select').addEventListener('change', (e) => {
            this.targetRunId = e.target.value;
        });
        controls.querySelector('#btn-run-comparison').addEventListener('click', () => this.runComparison());
    }

    async runComparison() {
        if (!this.currentRunId || !this.targetRunId) return;
        const resultsContainer = this.element.querySelector('#comparison-results-container');
        resultsContainer.innerHTML = `
            <div class="text-center py-8 text-text-secondary font-body-sm">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                Calculating differences...
            </div>
        `;

        try {
            const data = await fetchComparison(this.currentRunId, this.targetRunId);
            this.renderComparisonResults(data);
        } catch (err) {
            console.error("Batch comparison failed:", err);
            resultsContainer.innerHTML = `
                <div class="text-center py-8 text-error font-body-sm">
                    ${err.message || "No overlapping proteins found between these runs."}
                </div>
            `;
        }
    }

    renderComparisonResults(data) {
        const resultsContainer = this.element.querySelector('#comparison-results-container');

        resultsContainer.innerHTML = `
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-3 bg-[#11141c]/50">
                <h4 class="font-body-md text-body-md font-semibold text-text-primary">RMSD Difference Matrix (ΔRMSD)</h4>
                <span class="font-body-sm text-body-sm text-text-secondary">
                    Positive values indicate increased divergence in the current run compared to the target.
                </span>
                <div id="comparison-diff-heatmap" class="w-full h-[280px]"></div>
            </div>
            <div class="glass-panel rounded-xl p-5 grid grid-cols-3 gap-4 bg-[#11141c]/50">
                <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                    <span class="font-label-sm text-label-sm text-text-secondary">Mean RMSD Shift</span>
                    <span class="font-headline-sm text-headline-sm font-semibold ${data.mean_rmsd_shift >= 0 ? 'text-error' : 'text-success'} font-mono">${data.mean_rmsd_shift.toFixed(3)} Å</span>
                </div>
                <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                    <span class="font-label-sm text-label-sm text-text-secondary">Current Mean</span>
                    <span class="font-headline-sm text-headline-sm font-semibold text-text-primary font-mono">${data.current_mean_rmsd.toFixed(3)} Å</span>
                </div>
                <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                    <span class="font-label-sm text-label-sm text-text-secondary">Target Mean</span>
                    <span class="font-headline-sm text-headline-sm font-semibold text-text-primary font-mono">${data.target_mean_rmsd.toFixed(3)} Å</span>
                </div>
            </div>
        `;

        const heatmapDiv = resultsContainer.querySelector('#comparison-diff-heatmap');
        const diff = data.diff;
        const trace = {
            z: diff.data,
            x: diff.columns,
            y: diff.index,
            type: 'heatmap',
            colorscale: 'RdBu',
            zmid: 0,
        };
        const layout = {
            margin: { l: 60, r: 20, t: 10, b: 40 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#8F9CAE" }
        };
        Plotly.newPlot(heatmapDiv, [trace], layout, { responsive: true, displayModeBar: false });

        if (diff.data.every(row => row.every(v => v === 0))) {
            const notice = document.createElement('div');
            notice.className = "text-center py-2 text-success font-body-sm";
            notice.innerText = "✨ Perfect Consensus: overlapping proteins are structurally identical in both runs.";
            resultsContainer.appendChild(notice);
        }
    }
}
