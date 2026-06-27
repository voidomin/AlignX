export class AnalyticsTab {
    constructor() {
        this.element = null;
        this.currentRunId = null;
        this.heatmapFig = null;
        this.treeFig = null;
        this.ramachandranStats = null;
        this.rmsfValues = [];
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

            <!-- Residue Fluctuation (Plotly Line Chart) -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0 min-h-[350px]">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">show_chart</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Residue Fluctuation (RMSF)</h4>
                </div>
                <div id="rmsf-plotly-chart" class="w-full h-[280px]">
                    <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                        Run alignment to display interactive RMSF chart.
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

    updateResults(runId, heatmapFig, treeFig, ramachandranStats, rmsfValues) {
        this.currentRunId = runId;
        this.heatmapFig = heatmapFig;
        this.treeFig = treeFig;
        this.ramachandranStats = ramachandranStats;
        this.rmsfValues = rmsfValues || [];
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

        // 2. Render Plotly RMSF Line Chart
        const rmsfDiv = this.element.querySelector('#rmsf-plotly-chart');
        if (this.rmsfValues && this.rmsfValues.length > 0) {
            rmsfDiv.innerHTML = "";
            
            // X-axis: 1-indexed positions
            const xData = Array.from({ length: this.rmsfValues.length }, (_, i) => i + 1);
            
            const trace = {
                x: xData,
                y: this.rmsfValues,
                type: 'scatter',
                mode: 'lines',
                line: {
                    color: '#8B5CF6',
                    width: 2.5,
                    shape: 'spline'
                },
                fill: 'tozeroy',
                fillcolor: 'rgba(139, 92, 246, 0.1)',
                hoverinfo: 'x+y',
                name: 'RMSF'
            };

            const layout = {
                xaxis: {
                    title: 'Alignment Position',
                    gridcolor: 'rgba(255,255,255,0.05)',
                    zeroline: false
                },
                yaxis: {
                    title: 'RMSF (Å)',
                    gridcolor: 'rgba(255,255,255,0.05)',
                    zeroline: false
                },
                margin: { l: 50, r: 20, t: 20, b: 40 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                height: 280,
                font: { family: "Inter, sans-serif", size: 10, color: "#8F9CAE" }
            };

            Plotly.newPlot(rmsfDiv, [trace], layout, { responsive: true, displayModeBar: false });
        } else if (this.currentRunId) {
            rmsfDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-text-secondary font-body-sm">
                    No residue fluctuation data available.
                </div>
            `;
        }

        // 3. Render Plotly Heatmap
        const heatmapDiv = this.element.querySelector('#rmsd-plotly-heatmap');
        if (this.heatmapFig && this.heatmapFig.data) {
            heatmapDiv.innerHTML = "";
            
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

        // 4. Render Plotly Dendrogram
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
