import { fetchMemoryStats, triggerClearMemory, fetchHealth } from '../api';

const TABS = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'overview', label: 'Overview' },
    { key: 'discover', label: 'Discover' },
    { key: 'ligands', label: 'Ligands' },
    { key: 'sequence', label: 'Sequence' },
    { key: 'analytics', label: 'Analytics' },
    { key: 'clusters', label: 'Clusters' },
    { key: 'comparison', label: 'Compare' },
    { key: 'history', label: 'History' },
];

export class TopBar {
    constructor(props) {
        this.onTabChange = props.onTabChange;
        this.onExportData = props.onExportData;
        this.onNewWorkspace = props.onNewWorkspace;
        this.activeTab = 'overview';
        this.element = null;
        this.memoryInterval = null;
    }

    render() {
        const header = document.createElement('header');
        header.className = "sticky top-0 z-50 bg-surface border-b border-border shrink-0";
        header.innerHTML = `
            <div class="max-w-[1600px] mx-auto px-6 py-3 flex items-center justify-between gap-6">
                <div class="flex items-center gap-3 shrink-0">
                    <span class="material-symbols-outlined text-[20px] text-accent">science</span>
                    <span class="font-headline-md text-headline-md font-bold text-primary">StructScope</span>
                </div>

                <nav id="topbar-tabs" class="flex gap-1 flex-1 overflow-x-auto">
                    ${TABS.map(t => `
                        <button data-tab="${t.key}" class="tab-trigger px-4 py-2 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors">${t.label}</button>
                    `).join('')}
                </nav>

                <div class="flex items-center gap-4 shrink-0 font-mono text-label-sm">
                    <button id="topbar-new-ws-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">New Workspace</button>
                    <button id="topbar-export-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Export</button>
                    <div class="h-5 w-px bg-border"></div>
                    <span id="topbar-health-status" class="text-secondary truncate max-w-[200px]">Engine: checking...</span>
                    <span id="topbar-ram-text" class="text-muted">--</span>
                    <button id="topbar-free-ram-btn" class="text-accent hover:text-primary transition-colors">Free RAM</button>
                </div>
            </div>
        `;

        this.element = header;
        this.updateTabStyles();
        this.setupEventListeners();
        this.startMemoryTracking();
        return header;
    }

    setupEventListeners() {
        this.element.querySelectorAll('.tab-trigger').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.switchTab(tab);
                this.onTabChange(tab);
            });
        });

        this.element.querySelector('#topbar-export-btn').addEventListener('click', () => this.onExportData());
        this.element.querySelector('#topbar-new-ws-btn').addEventListener('click', () => this.onNewWorkspace());

        const freeBtn = this.element.querySelector('#topbar-free-ram-btn');
        freeBtn.addEventListener('click', async () => {
            freeBtn.innerText = "Clearing...";
            freeBtn.disabled = true;
            try {
                const data = await triggerClearMemory();
                this.updateMemoryDisplay(data.ram_mb);
            } catch (err) {
                console.error("Free memory failed:", err);
            } finally {
                freeBtn.innerText = "Free RAM";
                freeBtn.disabled = false;
            }
        });
    }

    switchTab(tab) {
        this.activeTab = tab;
        this.updateTabStyles();
    }

    updateTabStyles() {
        this.element.querySelectorAll('.tab-trigger').forEach(btn => {
            const isActive = btn.dataset.tab === this.activeTab;
            btn.className = `tab-trigger px-4 py-2 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors ${isActive ? 'bg-accent-muted text-accent' : 'text-secondary hover:text-primary'}`;
        });
    }

    startMemoryTracking() {
        const update = async () => {
            try {
                const data = await fetchMemoryStats();
                this.updateMemoryDisplay(data.ram_mb);
            } catch (err) {
                console.warn("Top bar memory update failed:", err);
            }

            try {
                const health = await fetchHealth();
                const healthEl = this.element.querySelector('#topbar-health-status');
                if (healthEl && health) {
                    if (health.mustang_installed) {
                        const mode = health.mustang_message?.toLowerCase().includes("wsl") ? "WSL" : "Native";
                        healthEl.innerText = `Mustang: Ready (${mode})`;
                        healthEl.className = "text-success truncate max-w-[200px]";
                    } else {
                        healthEl.innerText = "Mustang: Offline";
                        healthEl.className = "text-error truncate max-w-[200px]";
                    }
                }
            } catch (err) {
                console.warn("Top bar health update failed:", err);
                const healthEl = this.element.querySelector('#topbar-health-status');
                if (healthEl) {
                    healthEl.innerText = "Engine: Disconnected";
                    healthEl.className = "text-error truncate max-w-[200px]";
                }
            }
        };

        // Delay the first poll rather than firing immediately on page load,
        // so it doesn't compete with the initial chain-metadata fetch for
        // the default structures over the browser's limited per-host
        // connection pool. Poll less aggressively thereafter (20s, was 10s)
        // to reduce ongoing background request volume.
        this.initialPollTimeout = setTimeout(update, 3000);
        this.memoryInterval = setInterval(update, 20000);
    }

    updateMemoryDisplay(ramMb) {
        const text = this.element.querySelector('#topbar-ram-text');
        if (text) {
            text.innerText = `${ramMb} MB`;
        }
    }

    destroy() {
        clearTimeout(this.initialPollTimeout);
        clearInterval(this.memoryInterval);
    }
}
