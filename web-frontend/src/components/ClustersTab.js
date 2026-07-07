import { fetchClusters } from '../api';

export class ClustersTab {
    rmsdDf = null;
    pdbMetadata = {};
    threshold = 3.0;
    element = null;
    debounceTimer = null;

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-clusters-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Structural Families</span>
                    <h2 class="section-title">Structural clusters</h2>
                </div>
                <div class="section-caption">Structures with RMSD lower than this cutoff are grouped into the same family.</div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-sm text-label-sm text-secondary">RMSD threshold</span>
                        <span id="cluster-threshold-value" class="font-mono text-body-sm text-primary">3.00 Å</span>
                    </div>
                    <input id="cluster-threshold-slider" type="range" min="0.1" max="10.0" step="0.1" value="3.0"
                        class="w-full h-1.5 rounded-md appearance-none bg-surface-raised accent-accent cursor-pointer" />
                </div>

                <div id="clusters-list-container" class="flex flex-col">
                    <div class="text-center py-8 text-secondary font-body-sm">
                        Run alignment to identify structural clusters.
                    </div>
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
            this.threshold = Number.parseFloat(e.target.value);
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
                <div class="text-center py-8 text-secondary font-body-sm">
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
                <div class="text-center py-8 text-secondary font-body-sm">
                    No clusters identified with current settings.
                </div>
            `;
            return;
        }

        container.innerHTML = clusters.map(cluster => {
            const memberRows = cluster.members.map(pid => {
                const title = this.pdbMetadata[pid]?.title || "Unknown Title";
                return `
                    <div class="flex items-center justify-between py-2 border-b border-border-subtle last:border-b-0">
                        <span class="font-mono text-body-sm text-primary">${pid}</span>
                        <span class="text-body-sm text-secondary truncate ml-2">${title}</span>
                    </div>
                `;
            }).join("");

            return `
                <div class="border-t border-border pt-4 pb-2">
                    <div class="flex items-center justify-between mb-2">
                        <span class="font-body-md text-body-md font-semibold text-primary">
                            Cluster ${cluster.cluster_id} <span class="text-secondary font-normal">(${cluster.members.length} members)</span>
                        </span>
                        <span class="font-label-sm text-label-sm text-secondary font-mono">
                            Avg RMSD: ${cluster.avg_rmsd.toFixed(2)} Å
                        </span>
                    </div>
                    <div class="flex flex-col">
                        ${memberRows}
                    </div>
                </div>
            `;
        }).join("");
    }
}
