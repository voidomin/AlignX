import { fetchStats, fetchHistory } from '../api';
import { QUICK_START_EXAMPLES } from '../quickStartExamples';

const RECENT_RUNS_LIMIT = 5;

export class DashboardTab {
    constructor(props) {
        this.onReloadRun = props.onReloadRun;
        this.onQuickStart = props.onQuickStart;
        this.element = null;
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-dashboard-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Mission Control</span>
                    <h2 class="section-title">Dashboard</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div id="dashboard-stats" class="grid grid-cols-3 gap-6">
                    <div class="stat-row stat-primary">
                        <span class="stat-key">Total runs</span>
                        <span id="stat-total-runs" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Proteins analyzed</span>
                        <span id="stat-total-proteins" class="stat-value">--</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-key">Cache size</span>
                        <span id="stat-cache-size" class="stat-value">--</span>
                    </div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Recent activity</span>
                    <div id="dashboard-recent-runs" class="flex flex-col">
                        <div class="text-center py-8 text-secondary font-body-sm">
                            <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                            Loading recent activity...
                        </div>
                    </div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Quick start</span>
                    <div id="dashboard-quick-start" class="flex flex-wrap gap-2"></div>
                </div>
            </div>
        `;
        this.element = div;
        this.renderQuickStart();
        this.loadDashboardData();
        return div;
    }

    renderQuickStart() {
        const container = this.element.querySelector('#dashboard-quick-start');
        container.innerHTML = "";
        QUICK_START_EXAMPLES.forEach(ex => {
            const btn = document.createElement('button');
            btn.className = "quick-start-btn px-3 py-1.5 rounded-md bg-surface-raised border border-border-subtle font-label-sm text-label-sm text-secondary hover:text-primary transition-colors";
            btn.textContent = `${ex.label} (${ex.pdbIds.join(' + ')})`;
            btn.addEventListener('click', () => this.onQuickStart(ex.pdbIds));
            container.appendChild(btn);
        });
    }

    async loadDashboardData() {
        if (!this.element) return;

        try {
            const stats = await fetchStats();
            this.element.querySelector('#stat-total-runs').textContent = stats.total_runs;
            this.element.querySelector('#stat-total-proteins').textContent = stats.total_proteins_analyzed;
            this.element.querySelector('#stat-cache-size').textContent = `${stats.cache_size_mb} MB`;
        } catch (err) {
            console.error("Failed to load dashboard stats:", err);
        }

        const recentContainer = this.element.querySelector('#dashboard-recent-runs');
        try {
            const data = await fetchHistory(RECENT_RUNS_LIMIT, 0);
            const runs = data.runs || [];

            if (runs.length === 0) {
                recentContainer.innerHTML = `
                    <div class="text-center py-8 text-secondary font-body-sm">
                        No past alignment sessions found.
                    </div>
                `;
                return;
            }

            recentContainer.innerHTML = "";
            runs.forEach(run => {
                let pids;
                try {
                    pids = typeof run.pdb_ids === 'string' ? JSON.parse(run.pdb_ids) : run.pdb_ids;
                } catch {
                    pids = [run.pdb_ids];
                }

                const runType = run.metadata?.run_type || 'compare';
                const runTypeLabel = runType === 'discover' ? 'Discover' : 'Compare';

                const row = document.createElement('div');
                row.className = "flex justify-between items-center py-3 border-b border-border-subtle hover:bg-surface-raised transition-colors cursor-pointer group px-2 -mx-2 rounded-md";
                // Static shell only (no interpolated values) - every actual
                // dynamic value is assigned via textContent below, which
                // can't be parsed as markup regardless of its content, so
                // there's no injection sink here at all (stronger than
                // escaping into an innerHTML template).
                row.innerHTML = `
                    <div class="flex items-center gap-4">
                        <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase" data-field="type"></span>
                        <span class="font-body-sm font-bold text-primary group-hover:text-accent font-mono" data-field="id"></span>
                        <div class="flex gap-1" data-field="pids"></div>
                    </div>
                    <span class="font-label-sm text-[10px] text-secondary" data-field="timestamp"></span>
                `;
                row.querySelector('[data-field="type"]').textContent = runTypeLabel;
                row.querySelector('[data-field="id"]').textContent = run.id;
                row.querySelector('[data-field="timestamp"]').textContent = run.timestamp;

                const pidsContainer = row.querySelector('[data-field="pids"]');
                pids.forEach(pid => {
                    const badge = document.createElement('span');
                    badge.className = "px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-mono text-[10px] text-secondary";
                    badge.textContent = pid;
                    pidsContainer.appendChild(badge);
                });

                row.addEventListener('click', () => this.onReloadRun(run));
                recentContainer.appendChild(row);
            });
        } catch (err) {
            console.error("Failed to load recent activity:", err);
            recentContainer.innerHTML = `
                <div class="text-center py-8 text-error font-body-sm">
                    Failed to retrieve recent activity.
                </div>
            `;
        }
    }
}
