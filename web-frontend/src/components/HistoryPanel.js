import { fetchHistory, getShareLink, deleteRun, clearAllHistory, updateRunNotes, fetchRunsTrend } from '../api';

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
                <div class="flex flex-col gap-2 border border-border rounded-lg p-4 mb-4">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">RMSD trend across runs</span>
                    <span class="font-body-sm text-body-sm text-secondary">Pick 2 or more past runs (Ctrl/Cmd-click for multiple) to see how their structural similarity has shifted over time.</span>
                    <div class="flex gap-2 items-center">
                        <select id="trend-run-select" multiple size="4" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm"></select>
                        <button id="trend-load-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md self-start">Show trend</button>
                    </div>
                    <div id="trend-plotly" class="w-full h-[220px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Select runs above and click "Show trend".
                        </div>
                    </div>
                </div>

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
        this.element.querySelector('#trend-load-btn').addEventListener('click', () => this.loadTrend());
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
            this.populateTrendSelect();
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
            div.className = "flex flex-col gap-2 py-3 border-b border-border-subtle hover:bg-surface-raised transition-colors cursor-pointer group px-2 -mx-2 rounded-md";

            let pids;
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
                <div class="flex justify-between items-center">
                    <div class="flex items-center gap-4">
                        <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase" data-field="type"></span>
                        <span class="font-body-sm font-bold text-primary group-hover:text-accent font-mono" data-field="id"></span>
                        <div class="flex gap-1" data-field="pids"></div>
                    </div>
                    <div class="flex items-center gap-4">
                        <span class="text-[10px] font-medium capitalize text-success" data-field="status"></span>
                        <span class="font-label-sm text-[10px] text-secondary" data-field="time"></span>
                        <button class="notes-toggle-btn font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Notes &amp; tags</button>
                        <button class="share-run-btn font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Share</button>
                        <button class="delete-run-btn font-label-sm text-label-sm text-secondary hover:text-error transition-colors underline decoration-dotted">Delete</button>
                    </div>
                </div>
                <div class="flex flex-wrap items-center gap-1.5" data-field="tags-display"></div>
                <div class="hidden flex-col gap-2 pt-1" data-field="notes-editor">
                    <textarea class="notes-input w-full bg-surface border border-border rounded-md px-2 py-1.5 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent" rows="2" placeholder="Add a note about this run..."></textarea>
                    <input type="text" class="tags-input w-full bg-surface border border-border rounded-md px-2 py-1.5 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent font-mono" placeholder="Comma-separated tags, e.g. kinase, review" />
                    <div class="flex gap-2">
                        <button class="notes-save-btn btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm">Save</button>
                        <button class="notes-cancel-btn px-3 py-1 rounded-md font-label-sm text-label-sm text-secondary hover:text-primary">Cancel</button>
                    </div>
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

            this.renderTagsDisplay(div, run);

            div.addEventListener('click', () => {
                this.onReloadRun(run);
            });

            const notesToggleBtn = div.querySelector('.notes-toggle-btn');
            const notesEditor = div.querySelector('[data-field="notes-editor"]');
            const notesInput = div.querySelector('.notes-input');
            const tagsInput = div.querySelector('.tags-input');
            notesToggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                notesInput.value = run.metadata?.notes || '';
                tagsInput.value = (run.metadata?.tags || []).join(', ');
                notesEditor.classList.remove('hidden');
                notesEditor.classList.add('flex');
            });

            div.querySelector('.notes-cancel-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                notesEditor.classList.add('hidden');
                notesEditor.classList.remove('flex');
            });

            div.querySelector('.notes-save-btn').addEventListener('click', async (e) => {
                e.stopPropagation();
                const notes = notesInput.value.trim();
                const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);
                try {
                    await updateRunNotes(run.id, { notes, tags });
                    run.metadata = { ...run.metadata, notes, tags };
                    this.renderTagsDisplay(div, run);
                    notesEditor.classList.add('hidden');
                    notesEditor.classList.remove('flex');
                } catch (err) {
                    console.error("Failed to save run notes:", err);
                    alert(err.message || "Failed to save notes.");
                }
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

    // Renders the tag badges + note preview under one run's row - called
    // both on initial render and after a successful notes-editor save, so
    // the display reflects the just-saved values without a full reload.
    renderTagsDisplay(div, run) {
        const container = div.querySelector('[data-field="tags-display"]');
        container.innerHTML = "";

        const tags = run.metadata?.tags || [];
        tags.forEach(tag => {
            const badge = document.createElement('span');
            badge.className = "px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle text-secondary font-mono text-[10px]";
            badge.textContent = tag;
            container.appendChild(badge);
        });

        if (run.metadata?.notes) {
            const note = document.createElement('span');
            note.className = "font-body-sm text-[11px] text-secondary italic";
            note.textContent = run.metadata.notes;
            container.appendChild(note);
        }
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
            this.populateTrendSelect();
        } catch (err) {
            console.error("Failed to load more history:", err);
        }
    }

    // Independent of the main runs list's click-to-reload row behavior -
    // a separate multi-select avoids overloading each row's click handler
    // with a second, conflicting meaning ("select for trend" vs "reload
    // this run").
    populateTrendSelect() {
        const select = this.element.querySelector('#trend-run-select');
        if (!select) return;
        const previouslySelected = new Set(
            [...select.selectedOptions].map(o => o.value)
        );
        select.innerHTML = "";
        this.runsList.forEach(run => {
            const opt = document.createElement('option');
            opt.value = run.id;
            opt.textContent = `${run.id} — ${run.timestamp}`;
            opt.selected = previouslySelected.has(run.id);
            select.appendChild(opt);
        });
    }

    async loadTrend() {
        const select = this.element.querySelector('#trend-run-select');
        const div = this.element.querySelector('#trend-plotly');
        const runIds = [...select.selectedOptions].map(o => o.value);

        if (runIds.length < 2) {
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Select at least 2 runs to compare a trend.</div>`;
            return;
        }

        div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading trend&hellip;</div>`;
        try {
            const data = await fetchRunsTrend(runIds);
            this.renderTrendChart(data.trend || []);
        } catch (err) {
            console.error("Failed to load run trend:", err);
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Failed to load run trend.</div>`;
        }
    }

    renderTrendChart(trend) {
        const div = this.element.querySelector('#trend-plotly');
        if (!div) return;

        if (trend.length === 0) {
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">None of the selected runs have a usable RMSD matrix.</div>`;
            return;
        }

        div.innerHTML = "";
        const x = trend.map(t => t.timestamp);
        const traces = [
            {
                x, y: trend.map(t => t.mean_rmsd), name: 'Mean RMSD',
                type: 'scatter', mode: 'lines+markers', line: { color: '#C9A063' },
            },
            {
                x, y: trend.map(t => t.max_rmsd), name: 'Max RMSD',
                type: 'scatter', mode: 'lines+markers', line: { color: '#8B5CF6' },
            },
        ];
        const layout = {
            height: 220,
            margin: { l: 40, r: 10, t: 10, b: 60 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" },
            legend: { orientation: 'h', y: -0.3 },
            xaxis: { tickangle: -30 },
        };
        Plotly.newPlot(div, traces, layout, { responsive: true, displayModeBar: false });
    }
}
