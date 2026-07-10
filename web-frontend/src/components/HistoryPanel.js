import { fetchHistory, getShareLink, deleteRun, clearAllHistory } from '../api';

const PAGE_SIZE = 20;

export class HistoryPanel {
    constructor(props) {
        this.onReloadRun = props.onReloadRun;
        this.element = null;
        this.runsList = [];
        this.total = 0;
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-history-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Table — Session History</span>
                    <h2 class="section-title">Past runs</h2>
                </div>
                <button id="history-clear-all-btn" class="font-label-sm text-label-sm text-secondary hover:text-error transition-colors underline decoration-dotted">Clear All History</button>
            </header>

            <div class="section-body">
                <div id="history-runs-list" class="flex flex-col">
                    <div class="text-center py-12 text-secondary font-body-sm">
                        <span class="animate-spin material-symbols-outlined text-[24px] mb-2">sync</span>
                        Loading run logs...
                    </div>
                </div>
            </div>
        `;
        this.element = div;
        this.element.querySelector('#history-clear-all-btn').addEventListener('click', () => this.clearAll());
        this.loadHistoryData();
        return div;
    }

    async clearAll() {
        if (this.runsList.length === 0) return;
        if (!confirm("Clear all run history? This cannot be undone.")) return;

        try {
            await clearAllHistory();
            this.runsList = [];
            this.total = 0;
            const container = this.element.querySelector('#history-runs-list');
            container.innerHTML = `
                <div class="text-center py-12 text-secondary font-body-sm">
                    No past alignment sessions found.
                </div>
            `;
        } catch (err) {
            console.error("Failed to clear history:", err);
            alert(err.message || "Failed to clear history.");
        }
    }

    async loadHistoryData() {
        const container = this.element.querySelector('#history-runs-list');
        try {
            const data = await fetchHistory(PAGE_SIZE, 0);
            this.runsList = data.runs || [];
            this.total = data.total || this.runsList.length;

            container.innerHTML = "";
            if (this.runsList.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-12 text-secondary font-body-sm">
                        No past alignment sessions found.
                    </div>
                `;
                return;
            }

            this.renderRuns(this.runsList);
            this.renderLoadMoreControl();
        } catch (err) {
            console.error("Failed to load history data:", err);
            container.innerHTML = `
                <div class="text-center py-12 text-error font-body-sm">
                    Failed to retrieve session history log.
                </div>
            `;
        }
    }

    renderRuns(runs) {
        const container = this.element.querySelector('#history-runs-list');
        runs.forEach(run => {
            const div = document.createElement('div');
            div.className = "flex justify-between items-center py-3 border-b border-border-subtle hover:bg-surface-raised transition-colors cursor-pointer group px-2 -mx-2 rounded-md";

            let pids = [];
            try {
                pids = typeof run.pdb_ids === 'string' ? JSON.parse(run.pdb_ids) : run.pdb_ids;
            } catch {
                pids = [run.pdb_ids];
            }

            // Format timestamp
            let displayTime = run.timestamp;
            try {
                const dt = new Date(run.timestamp);
                if (!Number.isNaN(dt.getTime())) {
                    displayTime = dt.toLocaleString();
                }
            } catch {
                // Malformed timestamp - keep the raw value already assigned above.
            }

            const runType = run.metadata?.run_type || 'compare';
            const runTypeLabel = runType === 'discover' ? 'Discover' : 'Compare';

            // Static shell only (no interpolated values) - every dynamic
            // value is assigned via textContent below, which can't be
            // parsed as markup regardless of content, so there's no
            // injection sink here at all (stronger than escaping into an
            // innerHTML template).
            div.innerHTML = `
                <div class="flex items-center gap-4">
                    <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase" data-field="type"></span>
                    <span class="font-body-sm font-bold text-primary group-hover:text-accent font-mono" data-field="id"></span>
                    <div class="flex gap-1" data-field="pids"></div>
                </div>
                <div class="flex items-center gap-4">
                    <span class="text-[10px] font-medium capitalize text-success" data-field="status"></span>
                    <span class="font-label-sm text-[10px] text-secondary" data-field="time"></span>
                    <button class="share-run-btn font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Share</button>
                    <button class="delete-run-btn font-label-sm text-label-sm text-secondary hover:text-error transition-colors underline decoration-dotted">Delete</button>
                </div>
            `;

            div.querySelector('[data-field="type"]').textContent = runTypeLabel;
            div.querySelector('[data-field="id"]').textContent = run.id;
            div.querySelector('[data-field="status"]').textContent = run.status || "success";
            div.querySelector('[data-field="time"]').textContent = displayTime;

            const pidsContainer = div.querySelector('[data-field="pids"]');
            pids.forEach(pid => {
                const badge = document.createElement('span');
                badge.className = "px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-mono text-[10px] text-secondary";
                badge.textContent = pid;
                pidsContainer.appendChild(badge);
            });

            div.addEventListener('click', () => {
                this.onReloadRun(run);
            });

            const shareBtn = div.querySelector('.share-run-btn');
            shareBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(getShareLink(run.id));
                const original = shareBtn.innerText;
                shareBtn.innerText = 'Copied!';
                setTimeout(() => { shareBtn.innerText = original; }, 1500);
            });

            const deleteBtn = div.querySelector('.delete-run-btn');
            deleteBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                if (!confirm(`Delete run ${run.id}? This cannot be undone.`)) return;

                try {
                    await deleteRun(run.id);
                    this.runsList = this.runsList.filter(r => r.id !== run.id);
                    this.total = Math.max(0, this.total - 1);
                    div.remove();
                    if (this.runsList.length === 0) {
                        container.innerHTML = `
                            <div class="text-center py-12 text-secondary font-body-sm">
                                No past alignment sessions found.
                            </div>
                        `;
                    } else {
                        this.renderLoadMoreControl();
                    }
                } catch (err) {
                    console.error("Failed to delete run:", err);
                    alert(err.message || "Failed to delete run.");
                }
            });

            container.appendChild(div);
        });
    }

    renderLoadMoreControl() {
        const container = this.element.querySelector('#history-runs-list');
        const existing = this.element.querySelector('#history-load-more-btn');
        if (existing) existing.remove();

        if (this.runsList.length >= this.total) return;

        const btn = document.createElement('button');
        btn.id = 'history-load-more-btn';
        btn.className = "w-full py-3 text-secondary hover:text-primary font-label-md text-label-md transition-colors shrink-0";
        btn.innerText = `Load More (${this.runsList.length}/${this.total})`;
        btn.addEventListener('click', () => this.loadMore());
        container.appendChild(btn);
    }

    async loadMore() {
        try {
            const data = await fetchHistory(PAGE_SIZE, this.runsList.length);
            const newRuns = data.runs || [];
            this.total = data.total || this.total;
            this.runsList = this.runsList.concat(newRuns);
            this.renderRuns(newRuns);
            this.renderLoadMoreControl();
        } catch (err) {
            console.error("Failed to load more history:", err);
        }
    }
}
