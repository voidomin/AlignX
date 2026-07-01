import { fetchClusters } from '../api';

export class ClustersTab {
    constructor() {
        this.rmsdDf = null;
        this.pdbMetadata = {};
        this.threshold = 3.0;
        this.element = null;
        this.debounceTimer = null;
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col gap-4 overflow-y-auto pr-1";
        div.id = "tab-clusters-container";

        div.innerHTML = `
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-primary">workspaces</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Structural Clusters</h4>
                </div>
                <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-sm text-label-sm text-text-secondary">RMSD Threshold</span>
                        <span id="cluster-threshold-value" class="font-label-sm text-label-sm text-text-primary font-mono">3.00 Å</span>
                    </div>
                    <input id="cluster-threshold-slider" type="range" min="0.1" max="10.0" step="0.1" value="3.0"
                        class="w-full h-1.5 rounded-lg appearance-none bg-white/10 accent-primary cursor-pointer" />
                    <span class="font-body-sm text-body-sm text-text-secondary">
                        Structures with RMSD lower than this cutoff are grouped into the same family.
                    </span>
                </div>
            </div>

            <div id="clusters-list-container" class="flex flex-col gap-3">
                <div class="text-center py-8 text-text-secondary font-body-sm">
                    Run alignment to identify structural clusters.
                </div>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        return div;
    }

    setupEventListeners() {
        const slider = this.element.querySelector('#cluster-threshold-slider');
        slider.addEventListener('input', (e) => {
            this.threshold = parseFloat(e.target.value);
            this.element.querySelector('#cluster-threshold-value').innerText = `${this.threshold.toFixed(2)} Å`;

            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => this.loadClusters(), 250);
        });
    }

    updateResults(rmsdDf, pdbMetadata) {
        this.rmsdDf = rmsdDf;
        this.pdbMetadata = pdbMetadata || {};
        this.loadClusters();
    }

    async loadClusters() {
        if (!this.element) return;
        const container = this.element.querySelector('#clusters-list-container');

        if (!this.rmsdDf) {
            container.innerHTML = `
                <div class="text-center py-8 text-text-secondary font-body-sm">
                    Run alignment to identify structural clusters.
                </div>
            `;
            return;
        }

        try {
            const data = await fetchClusters(this.rmsdDf, this.threshold);
            this.renderClusters(data.clusters);
        } catch (err) {
            console.error("Failed to compute structural clusters:", err);
            container.innerHTML = `
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to compute structural clusters.
                </div>
            `;
        }
    }

    renderClusters(clusters) {
        const container = this.element.querySelector('#clusters-list-container');

        if (!clusters || clusters.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-text-secondary font-body-sm">
                    No clusters identified with current settings.
                </div>
            `;
            return;
        }

        container.innerHTML = clusters.map(cluster => {
            const memberRows = cluster.members.map(pid => {
                const title = (this.pdbMetadata[pid] && this.pdbMetadata[pid].title) || "Unknown Title";
                return `
                    <div class="flex items-center justify-between px-3 py-1.5 rounded bg-black/20 border border-white/5">
                        <span class="font-mono text-body-sm text-text-primary">${pid}</span>
                        <span class="text-body-sm text-text-secondary truncate ml-2">${title}</span>
                    </div>
                `;
            }).join("");

            return `
                <div class="glass-panel rounded-xl p-4 flex flex-col gap-2 bg-[#11141c]/50">
                    <div class="flex items-center justify-between">
                        <span class="font-body-md text-body-md font-semibold text-text-primary">
                            📁 Cluster ${cluster.cluster_id} (${cluster.members.length} members)
                        </span>
                        <span class="font-label-sm text-label-sm text-text-secondary font-mono">
                            Avg RMSD: ${cluster.avg_rmsd.toFixed(2)} Å
                        </span>
                    </div>
                    <div class="flex flex-col gap-1">
                        ${memberRows}
                    </div>
                </div>
            `;
        }).join("");
    }
}
