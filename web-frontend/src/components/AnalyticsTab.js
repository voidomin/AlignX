const SUB_TABS = [
    { key: 'quality', label: 'Quality' },
    { key: 'rmsf', label: 'RMSF' },
    { key: 'rmsd', label: 'RMSD Matrix' },
    { key: 'phylo', label: 'Phylogeny' },
];

export class AnalyticsTab {
    constructor() {
        this.element = null;
        this.currentRunId = null;
        this.heatmapFig = null;
        this.treeFig = null;
        this.ramachandranStats = null;
        this.rmsfValues = [];
        this.activeSubTab = 'quality';
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-analytics-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Structural Analytics</span>
                    <h2 class="section-title">Quality, fluctuation &amp; phylogeny</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <!-- Sub-tab strip -->
                <div id="analytics-subtab-strip" class="flex gap-1 border border-border rounded-md p-1 shrink-0">
                    ${SUB_TABS.map(t => `
                        <button data-subtab="${t.key}" class="analytics-subtab-btn flex-1 py-1.5 rounded-md font-label-md text-label-md transition-colors">${t.label}</button>
                    `).join('')}
                </div>

                <!-- Ramachandran / Quality Report -->
                <div data-panel="quality" class="flex flex-col gap-4 shrink-0">
                    <div class="grid grid-cols-2 gap-6">
                        <div class="stat-row stat-primary">
                            <span class="stat-key">Ramachandran score</span>
                            <span id="ramachandran-score" class="stat-value">--</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-key">Outlier residues</span>
                            <span id="ramachandran-outliers" class="stat-value">--</span>
                        </div>
                    </div>
                    <div id="ramachandran-outliers-list-card" class="flex flex-col gap-2 hidden">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Top outliers</span>
                        <div id="ramachandran-outliers-list" class="flex flex-wrap gap-1.5">
                            <!-- Outlier chips -->
                        </div>
                    </div>
                </div>

                <!-- Residue Fluctuation (Plotly Line Chart) -->
                <div data-panel="rmsf" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="rmsf-plotly-chart" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive RMSF chart.
                        </div>
                    </div>
                </div>

                <!-- Pairwise RMSD Matrix (Plotly Heatmap) -->
                <div data-panel="rmsd" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="rmsd-plotly-heatmap" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive heatmap.
                        </div>
                    </div>
                </div>

                <!-- Phylogenetic Tree (Plotly Dendrogram) -->
                <div data-panel="phylo" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="phylo-plotly-tree" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive dendrogram.
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.element = div;
        this.setupSubTabs();
        this.renderVisuals();
        return div;
    }

    setupSubTabs() {
        this.element.querySelectorAll('.analytics-subtab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchSubTab(btn.getAttribute('data-subtab')));
        });
        this.updateSubTabView();
    }

    switchSubTab(key) {
        this.activeSubTab = key;
        this.updateSubTabView();

        // Plotly may not auto-detect a container going from hidden -> visible;
        // resize defensively so the chart in the panel just shown renders correctly.
        const chartIdByPanel = { rmsf: 'rmsf-plotly-chart', rmsd: 'rmsd-plotly-heatmap', phylo: 'phylo-plotly-tree' };
        const chartId = chartIdByPanel[key];
        if (chartId && typeof Plotly !== 'undefined') {
            const chartDiv = this.element.querySelector(`#${chartId}`);
            if (chartDiv && chartDiv.data) {
                Plotly.Plots.resize(chartDiv);
            }
        }
    }

    updateSubTabView() {
        this.element.querySelectorAll('.analytics-subtab-btn').forEach(btn => {
            const isActive = btn.getAttribute('data-subtab') === this.activeSubTab;
            btn.className = `analytics-subtab-btn flex-1 py-1.5 rounded-md font-label-md text-label-md transition-colors ${isActive ? 'bg-accent-muted text-accent' : 'text-secondary hover:text-primary'}`;
        });
        this.element.querySelectorAll('[data-panel]').forEach(panel => {
            panel.classList.toggle('hidden', panel.getAttribute('data-panel') !== this.activeSubTab);
        });
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
                    const chip = document.createElement('span');
                    chip.className = "px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle text-error font-mono text-[10px]";
                    chip.innerText = item;
                    listContainer.appendChild(chip);
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
                    color: '#E2846A',
                    width: 2.5,
                    shape: 'spline'
                },
                fill: 'tozeroy',
                fillcolor: 'rgba(226, 132, 106, 0.1)',
                hoverinfo: 'x+y',
                name: 'RMSF'
            };

            const layout = {
                xaxis: {
                    title: 'Alignment Position',
                    gridcolor: '#2C2620',
                    zeroline: false
                },
                yaxis: {
                    title: 'RMSF (Å)',
                    gridcolor: '#2C2620',
                    zeroline: false
                },
                margin: { l: 50, r: 20, t: 20, b: 40 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                height: 280,
                font: { family: "Segoe UI, sans-serif", size: 10, color: "#A79E8E" }
            };

            Plotly.newPlot(rmsfDiv, [trace], layout, { responsive: true, displayModeBar: false });
        } else if (this.currentRunId) {
            rmsfDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-secondary font-body-sm">
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
                font: { family: "Segoe UI, sans-serif", size: 10, color: "#A79E8E" }
            };

            Plotly.newPlot(heatmapDiv, this.heatmapFig.data, layout, { responsive: true, displayModeBar: false });
        } else if (this.currentRunId) {
            heatmapDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-secondary font-body-sm">
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
                font: { family: "Segoe UI, sans-serif", size: 10, color: "#A79E8E" }
            };

            Plotly.newPlot(treeDiv, this.treeFig.data, layout, { responsive: true, displayModeBar: false });
        } else if (this.currentRunId) {
            treeDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                    No phylogenetic tree figure available.
                </div>
            `;
        }
    }
}
