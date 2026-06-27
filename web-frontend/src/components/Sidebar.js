import { fetchMemoryStats, triggerClearMemory, fetchHealth } from '../api';

export class Sidebar {
    constructor(props) {
        this.onNavigate = props.onNavigate;
        this.onNewWorkspace = props.onNewWorkspace;
        this.element = null;
        this.activeView = 'dashboard';
        this.memoryInterval = null;
    }

    render() {
        const nav = document.createElement('nav');
        nav.className = "w-[280px] h-full bg-surface/70 backdrop-blur-xl border-r border-white/10 shadow-lg flex flex-col py-6 shrink-0 z-40 hidden md:flex glass-panel";
        nav.innerHTML = `
            <!-- Header Area (System Health) -->
            <div class="px-6 mb-8 flex flex-col gap-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-surface-variant flex items-center justify-center border border-white/10">
                        <span class="material-symbols-outlined text-gradient-start text-[24px]">memory</span>
                    </div>
                    <div>
                        <h2 class="font-body-md text-body-md font-semibold text-text-primary">System Health</h2>
                        <p id="sidebar-health-status" class="font-label-sm text-label-sm text-text-secondary font-mono">Engine: checking...</p>
                    </div>
                </div>
                <!-- Expanded Panel Content -->
                <div class="mt-2 glass-panel p-3 rounded-lg flex flex-col gap-2 bg-black/20">
                    <div class="flex justify-between items-center">
                        <span class="font-label-sm text-label-sm text-text-secondary">Live RAM</span>
                        <span id="sidebar-ram-text" class="font-label-sm text-label-sm text-text-primary font-mono">Loading...</span>
                    </div>
                    <div class="w-full bg-black/40 rounded-full h-1.5 overflow-hidden">
                        <div id="sidebar-ram-bar" class="bg-secondary-container h-full rounded-full transition-all duration-500" style="width: 30%"></div>
                    </div>
                    <button id="sidebar-free-ram-btn" class="mt-2 text-center text-secondary font-label-sm text-label-sm hover:text-secondary-fixed transition-colors border border-secondary/20 rounded py-1 hover:bg-secondary/10">
                        Free RAM
                    </button>
                </div>
                <button id="sidebar-new-ws-btn" class="mt-2 btn-secondary w-full py-2 rounded-lg font-label-md text-label-md flex justify-center items-center gap-2">
                    <span class="material-symbols-outlined text-[16px]">add</span>
                    New Workspace
                </button>
            </div>
            <!-- Navigation Links -->
            <div class="flex-1 overflow-y-auto px-4 flex flex-col gap-1" id="sidebar-links-container">
                <!-- Links rendered dynamically -->
            </div>
            <!-- Footer Links -->
            <div class="px-4 mt-auto pt-4 border-t border-white/10 flex flex-col gap-1">
                <a class="text-text-secondary font-label-md text-label-md flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 hover:text-text-primary transition-all duration-200" href="#">
                    <span class="material-symbols-outlined text-[18px]">help</span>
                    Docs
                </a>
                <a class="text-text-secondary font-label-md text-label-md flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 hover:text-text-primary transition-all duration-200" href="#">
                    <span class="material-symbols-outlined text-[18px]">contact_support</span>
                    Support
                </a>
            </div>
        `;

        this.element = nav;
        this.renderLinks();
        this.setupEventListeners();
        this.startMemoryTracking();
        return nav;
    }

    renderLinks() {
        const container = this.element.querySelector('#sidebar-links-container');
        container.innerHTML = `
            <!-- Dashboard (Active) -->
            <button data-view="dashboard" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView === 'dashboard' ? 'bg-secondary/10 text-secondary border-secondary' : 'text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent'}">
                <span class="material-symbols-outlined text-[20px]">dashboard</span>
                Dashboard
            </button>
            <!-- Protein Library -->
            <button data-view="library" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView === 'library' ? 'bg-secondary/10 text-secondary border-secondary' : 'text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent'}">
                <span class="material-symbols-outlined text-[20px]">folder_open</span>
                Protein Library
            </button>
            <!-- Session Controls -->
            <div class="mt-4 mb-1 px-3">
                <span class="font-label-sm text-label-sm text-text-secondary uppercase tracking-wider">Session</span>
            </div>
            <button data-view="alignment" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView === 'alignment' ? 'bg-secondary/10 text-secondary border-secondary' : 'text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent'}">
                <span class="material-symbols-outlined text-[18px]">play_circle</span>
                Active Alignment
            </button>
            <button data-view="parameters" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView === 'parameters' ? 'bg-secondary/10 text-secondary border-secondary' : 'text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent'}">
                <span class="material-symbols-outlined text-[18px]">tune</span>
                Parameters
            </button>
            <!-- History Section -->
            <div class="mt-4 mb-1 px-3">
                <span class="font-label-sm text-label-sm text-text-secondary uppercase tracking-wider">History</span>
            </div>
            <button data-view="history" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView === 'history' ? 'bg-secondary/10 text-secondary border-secondary' : 'text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent'}">
                <span class="material-symbols-outlined text-[20px]">history</span>
                Session History
            </button>
            <!-- System Metrics -->
            <button data-view="metrics" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView === 'metrics' ? 'bg-secondary/10 text-secondary border-secondary' : 'text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent'}">
                <span class="material-symbols-outlined text-[20px]">monitoring</span>
                System Metrics
            </button>
            <!-- Analytics -->
            <button data-view="analytics" class="nav-btn w-full text-left font-label-md text-label-md flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 active:translate-x-1 border-r-2 ${this.activeView === 'analytics' ? 'bg-secondary/10 text-secondary border-secondary' : 'text-on-surface-variant hover:bg-white/5 hover:text-text-primary border-transparent'}">
                <span class="material-symbols-outlined text-[20px]">query_stats</span>
                Analytics
            </button>
        `;

        // Bind clicks
        container.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetView = btn.getAttribute('data-view');
                this.setView(targetView);
                this.onNavigate(targetView);
            });
        });
    }

    setView(viewName) {
        this.activeView = viewName;
        this.renderLinks();
    }

    setupEventListeners() {
        const freeBtn = this.element.querySelector('#sidebar-free-ram-btn');
        const newWsBtn = this.element.querySelector('#sidebar-new-ws-btn');

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

        newWsBtn.addEventListener('click', () => {
            if (this.onNewWorkspace) this.onNewWorkspace();
        });
    }

    startMemoryTracking() {
        const update = async () => {
            try {
                const data = await fetchMemoryStats();
                this.updateMemoryDisplay(data.ram_mb);
            } catch (err) {
                console.warn("Sidebar memory update failed:", err);
            }

            try {
                const health = await fetchHealth();
                const healthEl = this.element.querySelector('#sidebar-health-status');
                if (healthEl && health) {
                    if (health.mustang_installed) {
                        const mode = health.mustang_message && health.mustang_message.toLowerCase().includes("wsl") ? "WSL" : "Native";
                        healthEl.innerText = `Mustang: Ready (${mode})`;
                        healthEl.className = "font-label-sm text-label-sm text-success font-mono";
                    } else {
                        healthEl.innerText = "Mustang: Offline";
                        healthEl.className = "font-label-sm text-label-sm text-error font-mono";
                    }
                }
            } catch (err) {
                console.warn("Sidebar health update failed:", err);
                const healthEl = this.element.querySelector('#sidebar-health-status');
                if (healthEl) {
                    healthEl.innerText = "Engine: Disconnected";
                    healthEl.className = "font-label-sm text-label-sm text-error font-mono";
                }
            }
        };

        update();
        this.memoryInterval = setInterval(update, 10000);
    }

    updateMemoryDisplay(ramMb) {
        const text = this.element.querySelector('#sidebar-ram-text');
        const bar = this.element.querySelector('#sidebar-ram-bar');
        if (text && bar) {
            text.innerText = `${ramMb} MB`;
            const percent = Math.min(100, Math.max(10, (ramMb / 500) * 100));
            bar.style.width = `${percent}%`;
        }
    }

    destroy() {
        clearInterval(this.memoryInterval);
    }
}
