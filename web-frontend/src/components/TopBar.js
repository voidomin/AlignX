import { fetchMemoryStats, triggerClearMemory, fetchHealth } from '../api';
import { wireArrowKeyNavigation } from '../utils/tabKeyboardNav';
import { showDesktopModal } from './DesktopModal';

// Grouped into two sections so the nav communicates structure instead of
// 9 flat, equal-weight peers: Workspace (the one merged add-structures/
// analyze tab, replacing the old Overview+Discover split), Results (only
// meaningful once a structural alignment has actually run), Manage
// (history, settings, and the past-run diffing tool - this group used to
// be named "Workspace" too, before the merged tab took that name).
// "Compare" was renamed to "Diff Runs" here because it collided with a
// different meaning of "Compare" used elsewhere (the alignment workflow is
// informally called a "Compare run" in docs/guides/GETTING_STARTED.md) -
// this tab specifically diffs the current run against a past one. A flat
// array (group per entry) rather than nested {label, tabs: [...]} groups -
// the render loop below inserts a divider whenever `group` changes.
const TABS = [
    { key: 'workspace', label: 'Workspace', group: 'Workspace', stageLabel: '1. Setup' },
    { key: 'ligands', label: 'Ligands', group: 'Results', stageLabel: '2. Results' },
    { key: 'sequence', label: 'Sequence', group: 'Results' },
    { key: 'analytics', label: 'Analytics', group: 'Results' },
    { key: 'clusters', label: 'Clusters', group: 'Results' },
    { key: 'comparison', label: 'Diff Runs', group: 'Manage', stageLabel: '3. Manage' },
    { key: 'history', label: 'History', group: 'Manage' },
    { key: 'dashboard', label: 'Dashboard', group: 'Manage' },
    { key: 'settings', label: 'Settings', group: 'Manage' },
];

const RESULTS_TAB_KEYS = new Set(TABS.filter(t => t.group === 'Results').map(t => t.key));

export class TopBar {
    constructor(props) {
        this.onTabChange = props.onTabChange;
        this.onExportData = props.onExportData;
        this.onNewWorkspace = props.onNewWorkspace;
        this.activeTab = 'workspace';
        this.hasActiveRun = false;
        this.element = null;
        this.memoryInterval = null;
    }

    render() {
        const header = document.createElement('header');
        header.className = "sticky top-0 z-50 bg-surface/90 backdrop-blur-md border-b border-border/80 shrink-0";
        header.innerHTML = `
            <div class="max-w-[1600px] mx-auto px-6 py-3 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2 lg:gap-4">
                <div class="flex items-center gap-2.5 shrink-0">
                    <span class="material-symbols-outlined text-[20px] text-accent">science</span>
                    <span class="font-headline-md text-headline-md font-bold text-primary">StructScope</span>
                </div>

                <div id="topbar-tabs-wrapper" class="flex items-center w-full lg:w-auto lg:flex-1 min-w-0">
                    <button id="topbar-scroll-left" class="hidden shrink-0 w-8 h-8 items-center justify-center rounded-md bg-surface border border-border-subtle text-secondary hover:text-primary transition-colors mr-1" title="Scroll tabs left" aria-label="Scroll tabs left">
                        <span class="material-symbols-outlined text-[16px]">chevron_left</span>
                    </button>
                    <nav id="topbar-tabs" role="tablist" class="flex items-center gap-1 min-w-0 overflow-x-auto scroll-smooth">
                        ${TABS.map((t, i) => `
                            ${i > 0 && t.group !== TABS[i - 1].group ? '<div class="w-px h-5 bg-border-subtle mx-1.5 shrink-0" aria-hidden="true"></div>' : ''}
                            ${t.stageLabel ? `<span data-group-label="${t.group}" class="hidden xl:inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider text-muted select-none whitespace-nowrap" aria-hidden="true">${t.stageLabel}</span>` : ''}
                            <button data-tab="${t.key}" role="tab" class="tab-trigger px-3 py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors" aria-selected="${t.key === 'workspace'}" tabindex="${t.key === 'workspace' ? '0' : '-1'}">${t.label}</button>
                        `).join('')}
                    </nav>
                    <button id="topbar-scroll-right" class="hidden shrink-0 w-8 h-8 items-center justify-center rounded-md bg-surface border border-border-subtle text-secondary hover:text-primary transition-colors ml-1" title="Scroll tabs right" aria-label="Scroll tabs right">
                        <span class="material-symbols-outlined text-[16px]">chevron_right</span>
                    </button>
                </div>

                <div class="flex items-center flex-wrap lg:flex-nowrap gap-2 shrink-0 font-mono text-label-sm">
                    <button id="topbar-new-ws-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">New Workspace</button>
                    <button id="topbar-export-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Export</button>
                    <details id="topbar-system-disclosure" class="relative group">
                        <summary class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-surface-raised border border-border-subtle text-[11px] text-secondary hover:text-primary cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden" title="Engine health, memory diagnostics &amp; desktop edition">
                            <span id="topbar-health-dot" class="w-2 h-2 rounded-full bg-secondary shrink-0" aria-hidden="true"></span>
                            <span>System</span>
                            <span class="material-symbols-outlined text-[14px] transition-transform group-open:rotate-180">expand_more</span>
                        </summary>
                        <div class="absolute right-0 mt-1.5 w-72 p-3 rounded-lg bg-surface border border-border shadow-xl z-50 flex flex-col gap-2.5 text-[11px]">
                            <div class="flex items-center justify-between gap-2 pb-2 border-b border-border-subtle">
                                <span id="topbar-health-status" class="text-secondary truncate">Alignment engine: Checking...</span>
                            </div>
                            <div class="flex items-center justify-between flex-wrap lg:flex-nowrap gap-2 pb-2 border-b border-border-subtle">
                                <span class="text-secondary">Server RAM: <strong id="topbar-ram-text" class="text-primary font-mono">--</strong></span>
                                <button id="topbar-free-ram-btn" class="text-accent hover:text-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:text-accent" title="Runs garbage collection on the shared server process">Free up memory</button>
                            </div>
                            <button id="topbar-download-desktop-btn" class="btn-secondary w-full px-2.5 py-1.5 rounded-md font-label-sm text-label-sm flex items-center justify-center gap-1.5" title="Download Desktop Edition for unlimited large files &amp; private local compute">
                                <span class="material-symbols-outlined text-[15px] text-accent">desktop_windows</span>
                                <span>Desktop App</span>
                            </button>
                        </div>
                    </details>
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

        wireArrowKeyNavigation(this.element.querySelector('#topbar-tabs'), '.tab-trigger', (btn) => {
            const tab = btn.dataset.tab;
            this.switchTab(tab);
            this.onTabChange(tab);
        });

        this.element.querySelector('#topbar-export-btn').addEventListener('click', () => this.onExportData());
        this.element.querySelector('#topbar-new-ws-btn').addEventListener('click', () => this.onNewWorkspace());
        const desktopBtn = this.element.querySelector('#topbar-download-desktop-btn');
        if (desktopBtn) {
            desktopBtn.addEventListener('click', () => showDesktopModal());
        }

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
                freeBtn.innerText = "Free up memory";
                freeBtn.disabled = false;
            }
        });
    }

    switchTab(tab) {
        this.activeTab = tab;
        this.updateTabStyles();
    }

    setRunActive(isActive) {
        this.hasActiveRun = Boolean(isActive);
        if (this.element) {
            this.updateTabStyles();
        }
    }

    updateTabStyles() {
        this.element.querySelectorAll('.tab-trigger').forEach(btn => {
            const isActive = btn.dataset.tab === this.activeTab;
            const isResultsPending = !this.hasActiveRun && RESULTS_TAB_KEYS.has(btn.dataset.tab);
            const stateClass = isActive
                ? 'bg-accent-muted text-accent'
                : `text-secondary hover:text-primary${isResultsPending ? ' opacity-75' : ''}`;
            btn.className = `tab-trigger px-3 py-1.5 rounded-md font-label-md text-label-md whitespace-nowrap transition-colors ${stateClass}`;
            btn.setAttribute('aria-selected', String(isActive));
            btn.tabIndex = isActive ? 0 : -1;
            if (isResultsPending && !isActive) {
                btn.title = 'Run an alignment in Workspace first to populate results';
            } else {
                btn.removeAttribute('title');
            }
            if (isActive) {
                btn.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' });
            }
        });

        const resultsLabel = this.element.querySelector('[data-group-label="Results"]');
        if (resultsLabel) {
            resultsLabel.innerHTML = this.hasActiveRun
                ? '2. Results <span class="w-1.5 h-1.5 rounded-full bg-accent inline-block" aria-hidden="true"></span>'
                : '2. Results';
        }

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
                const healthDot = this.element.querySelector('#topbar-health-dot');
                if (healthEl && health) {
                    if (health.mustang_installed) {
                        const msg = health.mustang_message || '';
                        const mode = msg.toLowerCase().includes("wsl") ? "WSL" : "Native";
                        healthEl.innerText = "Alignment engine: Ready";
                        healthEl.title = `Runs via Mustang, in ${mode} mode`;
                        healthEl.className = "text-success truncate max-w-[180px]";
                        if (healthDot) healthDot.className = "w-1.5 h-1.5 rounded-full bg-success shrink-0";
                    } else {
                        healthEl.innerText = "Alignment engine: Offline";
                        healthEl.title = "Mustang could not be found on the server";
                        healthEl.className = "text-error truncate max-w-[180px]";
                        if (healthDot) healthDot.className = "w-1.5 h-1.5 rounded-full bg-error shrink-0";
                    }
                }
            } catch (err) {
                console.warn("Top bar health update failed:", err);
                const healthEl = this.element.querySelector('#topbar-health-status');
                const healthDot = this.element.querySelector('#topbar-health-dot');
                if (healthEl) {
                    healthEl.innerText = "Alignment engine: Disconnected";
                    healthEl.title = "Could not reach the backend server";
                    healthEl.className = "text-error truncate max-w-[180px]";
                }
                if (healthDot) healthDot.className = "w-1.5 h-1.5 rounded-full bg-error shrink-0";
            }
        };

        // Delay the first poll rather than firing immediately on page load,
        // so it doesn't compete with the initial chain-metadata fetch for
        // the default structures over the browser's limited per-host
        // connection pool. Poll less aggressively thereafter (20s, was 10s)
        // to reduce ongoing background request volume.
        this.initialPollTimeout = setTimeout(() => { void update(); }, 3000);
        this.memoryInterval = setInterval(() => { void update(); }, 20000);
    }

    updateMemoryDisplay(ramMb) {
        const text = this.element.querySelector('#topbar-ram-text');
        if (text) {
            text.innerText = `${ramMb} MB`;
        }
    }

    destroy() {
        if (this._updateScrollArrows) {
            window.removeEventListener('resize', this._updateScrollArrows);
        }
        clearTimeout(this.initialPollTimeout);
        clearInterval(this.memoryInterval);
    }
}
