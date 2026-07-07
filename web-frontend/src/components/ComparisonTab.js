import { fetchComparisonRuns, fetchComparison } from '../api';

export class ComparisonTab {
    currentRunId = null;
    pastRuns = [];
    targetRunId = null;
    element = null;

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col gap-4 overflow-y-auto pr-1";
        div.id = "tab-comparison-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Batch Comparison</span>
                    <h2 class="section-title">Compare against a past run</h2>
                </div>
                <div class="section-caption">See how structural relationships shifted between this run and a prior one.</div>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div id="comparison-controls" class="flex flex-col gap-2">
                    <div class="text-center py-4 text-secondary font-body-sm">
                        Run an alignment to enable comparison.
                    </div>
                </div>

                <div id="comparison-results-container" class="flex flex-col gap-8"></div>
            </div>
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
                <div class="text-center py-4 text-secondary font-body-sm">
                    Run an alignment to enable comparison.
                </div>
            `;
            return;
        }

        if (this.pastRuns.length === 0) {
            controls.innerHTML = `
                <div class="text-center py-4 text-secondary font-body-sm">
                    No other past runs found for comparison.
                </div>
            `;
            return;
        }

        controls.innerHTML = `
            <select id="comparison-target-select" class="w-full bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                ${this.pastRuns.map(r => `
                    <option value="${r.id}">${r.timestamp} - ${r.id.slice(0, 8)}... (${r.proteins.length} p)</option>
                `).join("")}
            </select>
            <button id="btn-run-comparison" class="btn-primary w-full py-2 px-3 rounded-md font-label-md text-label-md">
                Run Comparative Analysis
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
            <div class="text-center py-8 text-secondary font-body-sm">
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
            <div>
                <div class="flex items-baseline justify-between mb-3">
                    <span class="font-body-md text-body-md font-semibold text-primary">RMSD difference matrix (ΔRMSD)</span>
                    <span class="font-body-sm text-body-sm text-secondary">Positive = current run diverges more than the target.</span>
                </div>
                <div id="comparison-diff-heatmap" class="w-full h-[280px]"></div>
            </div>
            <div class="grid grid-cols-3 gap-6">
                <div class="stat-row stat-primary">
                    <span class="stat-key">Mean RMSD shift</span>
                    <span class="stat-value ${data.mean_rmsd_shift >= 0 ? 'text-error' : 'text-success'}">${data.mean_rmsd_shift.toFixed(3)} Å</span>
                </div>
                <div class="stat-row">
                    <span class="stat-key">Current mean</span>
                    <span class="stat-value">${data.current_mean_rmsd.toFixed(3)} Å</span>
                </div>
                <div class="stat-row">
                    <span class="stat-key">Target mean</span>
                    <span class="stat-value">${data.target_mean_rmsd.toFixed(3)} Å</span>
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
            height: 280,
            margin: { l: 60, r: 20, t: 10, b: 40 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Segoe UI, sans-serif", size: 10, color: "#A79E8E" }
        };
        Plotly.newPlot(heatmapDiv, [trace], layout, { responsive: true, displayModeBar: false });

        if (diff.data.every(row => row.every(v => v === 0))) {
            const notice = document.createElement('div');
            notice.className = "text-center py-2 text-success font-body-sm";
            notice.innerText = "Perfect Consensus: overlapping proteins are structurally identical in both runs.";
            resultsContainer.appendChild(notice);
        }
    }
}
