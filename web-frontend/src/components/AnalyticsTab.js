export class AnalyticsTab {
    constructor() {
        this.element = null;
        this.currentRunId = null;
        this.heatmapFig = null;
        this.treeFig = null;
        this.ramachandranStats = null;
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col gap-4 overflow-y-auto pr-1";
        div.id = "tab-analytics-container";

        div.innerHTML = `
            <!-- Ramachandran / Quality Report -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">verified</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Structure Quality Report</h4>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Ramachandran Score</span>
                        <span id="ramachandran-score" class="font-headline-sm text-headline-sm font-semibold text-success font-mono">--</span>
                    </div>
                    <div class="bg-black/30 p-3 rounded-lg border border-white/5 flex flex-col">
                        <span class="font-label-sm text-label-sm text-text-secondary">Outlier Residues</span>
                        <span id="ramachandran-outliers" class="font-headline-sm text-headline-sm font-semibold text-error font-mono">--</span>
                    </div>
                </div>
                <div id="ramachandran-outliers-list-card" class="bg-black/20 border border-white/5 p-3 rounded-lg flex flex-col gap-1 hidden">
                    <span class="font-label-sm text-label-sm text-text-secondary uppercase">Top Outliers</span>
                    <div id="ramachandran-outliers-list" class="flex flex-wrap gap-1.5 mt-1">
                        <!-- Outlier badges -->
                    </div>
                </div>
            </div>

            <!-- Pairwise RMSD Matrix (Plotly Heatmap) -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0 min-h-[350px]">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-gradient-end">grid_on</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Pairwise RMSD Matrix</h4>
                </div>
                <div id="rmsd-plotly-heatmap" class="w-full h-[280px]">
                    <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                        Run alignment to display interactive heatmap.
                    </div>
                </div>
            </div>

            <!-- Phylogenetic Tree (Plotly Dendrogram) -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0 min-h-[350px]">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-tertiary">account_tree</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Phylogenetic Tree (UPGMA)</h4>
                </div>
                <div id="phylo-plotly-tree" class="w-full h-[280px]">
                    <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                        Run alignment to display interactive dendrogram.
                    </div>
                </div>
            </div>
        `;

        this.element = div;
        this.renderVisuals();
        return div;
    }

    updateResults(runId, heatmapFig, treeFig, ramachandranStats) {
        this.currentRunId = runId;
        this.heatmapFig = heatmapFig;
        this.treeFig = treeFig;
        this.ramachandranStats = ramachandranStats;
        this.renderVisuals();
    }

    renderVisuals() {
        if (!this.element) return;

        // 1. Update Torsion / Ramachandran metrics
        const score = this.element.querySelector('#ramachandran-score');
        const outliers = this.element.querySelector('#ramachandran-outliers');
        const listCard = this.element.querySelector('#ramachandran-outliers-list-card');
        const listContainer = this.element.querySelector('#ramachandran-outliers-list');

        if (this.ramachandranStats && this.ramachandranStats.favored_percent != null) {
            score.innerText = `${this.ramachandranStats.favored_percent.toFixed(1)}%`;
            outliers.innerText = this.ramachandranStats.outlier_count;

            if (this.ramachandranStats.outlier_count > 0 && this.ramachandranStats.outliers_list && this.ramachandranStats.outliers_list.length > 0) {
                listCard.classList.remove('hidden');
                listContainer.innerHTML = "";
                this.ramachandranStats.outliers_list.forEach(item => {
                    const badge = document.createElement('span');
                    badge.className = "px-2 py-0.5 rounded bg-error/10 border border-error/20 text-error font-mono text-[10px]";
                    badge.innerText = item;
                    listContainer.appendChild(badge);
                });
            } else {
                listCard.classList.add('hidden');
            }
        } else {
            score.innerText = "--";
            outliers.innerText = "--";
            listCard.classList.add('hidden');
        }

        // 2. Render Plotly Heatmap
        const heatmapDiv = this.element.querySelector('#rmsd-plotly-heatmap');
        if (this.heatmapFig && this.heatmapFig.data) {
            heatmapDiv.innerHTML = "";
            
            // Adjust layout for compact display in the sidebar panel
            const layout = {
                ...this.heatmapFig.layout,
                width: undefined, // Responsive
                height: 280,
                margin: { l: 50, r: 20, t: 30, b: 50 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { family: "Inter, sans-serif", size: 10, color: "#8F9CAE" }
            };

            Plotly.newPlot(heatmapDiv, this.heatmapFig.data, layout, { responsive: true, displayModeBar: false });
        } else if (this.currentRunId) {
            heatmapDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                    No pairwise heatmap figure available.
                </div>
            `;
        }

        // 3. Render Plotly Dendrogram
        const treeDiv = this.element.querySelector('#phylo-plotly-tree');
        if (this.treeFig && this.treeFig.data) {
            treeDiv.innerHTML = "";

            const layout = {
                ...this.treeFig.layout,
                width: undefined, // Responsive
                height: 280,
                margin: { l: 60, r: 20, t: 30, b: 40 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { family: "Inter, sans-serif", size: 10, color: "#8F9CAE" }
            };

            Plotly.newPlot(treeDiv, this.treeFig.data, layout, { responsive: true, displayModeBar: false });
        } else if (this.currentRunId) {
            treeDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                    No phylogenetic tree figure available.
                </div>
            `;
        }
    }
}
