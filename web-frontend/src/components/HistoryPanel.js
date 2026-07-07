import { fetchHistory, getShareLink } from '../api';
import { escapeHtml } from '../escapeHtml';

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
        this.loadHistoryData();
        return div;
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
            } catch(e) {
                pids = [run.pdb_ids];
            }

            // Format timestamp
            let displayTime = run.timestamp;
            try {
                const dt = new Date(run.timestamp);
                if (!isNaN(dt.getTime())) {
                    displayTime = dt.toLocaleString();
                }
            } catch(e){}

            const runType = (run.metadata && run.metadata.run_type) || 'compare';
            const runTypeLabel = runType === 'discover' ? 'Discover' : 'Compare';

            div.innerHTML = `
                <div class="flex items-center gap-4">
                    <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase">${escapeHtml(runTypeLabel)}</span>
                    <span class="font-body-sm font-bold text-primary group-hover:text-accent font-mono">${escapeHtml(run.id)}</span>
                    <div class="flex gap-1">
                        ${pids.map(pid => `<span class="px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-mono text-[10px] text-secondary">${escapeHtml(pid)}</span>`).join("")}
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    <span class="text-[10px] font-medium capitalize text-success">${escapeHtml(run.status || "success")}</span>
                    <span class="font-label-sm text-[10px] text-secondary">${escapeHtml(displayTime)}</span>
                    <button class="share-run-btn font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Share</button>
                </div>
            `;

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
