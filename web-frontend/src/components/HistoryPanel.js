import { fetchHistory } from '../api';

export class HistoryPanel {
    constructor(props) {
        this.onReloadRun = props.onReloadRun;
        this.onClose = props.onClose;
        this.element = null;
        this.runsList = [];
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col h-full overflow-hidden p-5";
        div.innerHTML = `
            <!-- Panel Header -->
            <div class="flex justify-between items-center border-b border-white/10 pb-3 mb-4 shrink-0">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[24px] text-secondary">history</span>
                    <h3 class="font-headline-sm text-headline-sm font-semibold text-text-primary">Session History</h3>
                </div>
                <button id="close-history-btn" class="p-1 rounded hover:bg-white/5 text-text-secondary hover:text-text-primary transition-colors">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <!-- Runs list container -->
            <div id="history-runs-list" class="flex-grow overflow-y-auto flex flex-col gap-3">
                <div class="text-center py-12 text-text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[24px] mb-2">sync</span>
                    Loading run logs...
                </div>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        this.loadHistoryData();
        return div;
    }

    setupEventListeners() {
        const closeBtn = this.element.querySelector('#close-history-btn');
        closeBtn.addEventListener('click', () => {
            if (this.onClose) this.onClose();
        });
    }

    async loadHistoryData() {
        const container = this.element.querySelector('#history-runs-list');
        try {
            const data = await fetchHistory();
            this.runsList = data.runs || [];
            
            container.innerHTML = "";
            if (this.runsList.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-12 text-text-secondary font-body-sm">
                        No past alignment sessions found.
                    </div>
                `;
                return;
            }

            this.runsList.forEach(run => {
                const div = document.createElement('div');
                div.className = "glass-panel p-4 rounded-lg bg-[#11141c]/50 hover:bg-[#11141c]/80 border border-white/5 hover:border-secondary/40 transition-all cursor-pointer flex flex-col gap-2 group";
                
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

                div.innerHTML = `
                    <div class="flex justify-between items-center">
                        <span class="font-body-sm font-bold text-text-primary group-hover:text-secondary font-mono">${run.id}</span>
                        <span class="font-label-sm text-[10px] text-text-secondary">${displayTime}</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <div class="flex gap-1">
                            ${pids.map(pid => `<span class="px-1.5 py-0.5 rounded bg-black/40 text-[#fff] border border-white/10 font-mono text-[10px]">${pid}</span>`).join("")}
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] bg-success/20 text-success border border-success/30 font-medium capitalize">${run.status || "success"}</span>
                    </div>
                `;

                div.addEventListener('click', () => {
                    this.onReloadRun(run);
                });

                container.appendChild(div);
            });
        } catch (err) {
            console.error("Failed to load history data:", err);
            container.innerHTML = `
                <div class="text-center py-12 text-error font-body-sm">
                    Failed to retrieve session history log.
                </div>
            `;
        }
    }
}
