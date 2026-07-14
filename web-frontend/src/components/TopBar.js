import { fetchMemoryStats, triggerClearMemory, fetchHealth } from '../api';

// Grouped into three sections so the nav communicates structure instead of
// 10 flat, equal-weight peers: Explore (pick a mode), Results (only
// meaningful once a Compare/Overview alignment has actually run), Workspace
// (meta - history, settings, and the past-run diffing tool). "Compare" was
// renamed to "Diff Runs" here because it collided with a different meaning
// of "Compare" used elsewhere (the Overview tab's alignment workflow is
// informally called a "Compare run" in docs/guides/GETTING_STARTED.md) -
// this tab specifically diffs the current run against a past one. A flat
// array (group per entry) rather than nested {label, tabs: [...]} groups -
// the render loop below inserts a divider whenever `group` changes.
const TABS = [
    { key: 'overview', label: 'Overview', group: 'Explore' },
    { key: 'discover', label: 'Discover', group: 'Explore' },
    { key: 'ligands', label: 'Ligands', group: 'Results' },
    { key: 'sequence', label: 'Sequence', group: 'Results' },
    { key: 'analytics', label: 'Analytics', group: 'Results' },
    { key: 'clusters', label: 'Clusters', group: 'Results' },
    { key: 'comparison', label: 'Diff Runs', group: 'Workspace' },
    { key: 'history', label: 'History', group: 'Workspace' },
    { key: 'dashboard', label: 'Dashboard', group: 'Workspace' },
    { key: 'settings', label: 'Settings', group: 'Workspace' },
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

                <div id="topbar-tabs-wrapper" class="flex items-center flex-1 min-w-0">
                    <button id="topbar-scroll-left" class="hidden shrink-0 w-5 h-7 items-center justify-center rounded-md bg-surface border border-border-subtle text-secondary hover:text-primary transition-colors mr-1" title="Scroll tabs left">
                        <span class="material-symbols-outlined text-[16px]">chevron_left</span>
                    </button>
                    <nav id="topbar-tabs" class="flex items-center gap-1 min-w-0 overflow-x-auto scroll-smooth">
                        ${TABS.map((t, i) => `
                            ${i > 0 && t.group !== TABS[i - 1].group ? '<div class="w-px h-5 bg-border-subtle mx-1.5 shrink-0" aria-hidden="true"></div>' : ''}
                            <button data-tab="${t.key}" class="tab-trigger px-3 py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors">${t.label}</button>
                        `).join('')}
                    </nav>
                    <button id="topbar-scroll-right" class="hidden shrink-0 w-5 h-7 items-center justify-center rounded-md bg-surface border border-border-subtle text-secondary hover:text-primary transition-colors ml-1" title="Scroll tabs right">
                        <span class="material-symbols-outlined text-[16px]">chevron_right</span>
                    </button>
                </div>

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
        this.setupTabScrollAffordance();
        this.startMemoryTracking();
        return header;
    }

    // The tab strip has always scrolled horizontally when it doesn't fit
    // (overflow-x-auto), but with no visible affordance - at 10 tabs a
    // real content width can clip the last few with nothing telling the
    // user there's more to see. These two buttons only appear when there's
    // actually somewhere to scroll (checked via scrollLeft/scrollWidth),
    // and the active tab auto-scrolls into view on every switch so
    // switching to an off-screen tab never leaves the active state hidden.
    setupTabScrollAffordance() {
        const nav = this.element.querySelector('#topbar-tabs');
        const leftBtn = this.element.querySelector('#topbar-scroll-left');
        const rightBtn = this.element.querySelector('#topbar-scroll-right');
        const SCROLL_STEP = 150;

        const updateArrows = () => {
            const canScrollLeft = nav.scrollLeft > 2;
            const canScrollRight = nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 2;
            leftBtn.classList.toggle('hidden', !canScrollLeft);
            leftBtn.classList.toggle('flex', canScrollLeft);
            rightBtn.classList.toggle('hidden', !canScrollRight);
            rightBtn.classList.toggle('flex', canScrollRight);
        };

        leftBtn.addEventListener('click', () => nav.scrollBy({ left: -SCROLL_STEP, behavior: 'smooth' }));
        rightBtn.addEventListener('click', () => nav.scrollBy({ left: SCROLL_STEP, behavior: 'smooth' }));
        nav.addEventListener('scroll', updateArrows);
        window.addEventListener('resize', updateArrows);

        this._updateScrollArrows = updateArrows;
        requestAnimationFrame(updateArrows);
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
            btn.className = `tab-trigger px-3 py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors ${isActive ? 'bg-accent-muted text-accent' : 'text-secondary hover:text-primary'}`;
            if (isActive) {
                btn.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' });
            }
        });
        // Scrolling into view may change what's scrollable in either
        // direction - refresh the arrow affordance once the scroll settles.
        if (this._updateScrollArrows) {
            requestAnimationFrame(this._updateScrollArrows);
        }
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
