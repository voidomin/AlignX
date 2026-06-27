import './style.css';
import { TopNav } from './components/TopNav';
import { Sidebar } from './components/Sidebar';
import { Viewer3D } from './components/Viewer3D';
import { TabPanel } from './components/TabPanel';
import { OverviewTab } from './components/OverviewTab';
import { LigandTab } from './components/LigandTab';
import { SequenceTab } from './components/SequenceTab';
import { AnalyticsTab } from './components/AnalyticsTab';
import { HistoryPanel } from './components/HistoryPanel';
import { fetchChains, runAlignment, fetchLigands } from './api';

class App {
    constructor() {
        this.selectedPDBs = ["4RLT", "3UG9"];
        this.chainSelections = { "4RLT": "A", "3UG9": "A" };
        this.pdbMetadata = {};
        this.currentRunId = null;
        this.activeView = 'dashboard'; // 'dashboard' | 'history' | 'library' | 'parameters' | 'metrics' | 'analytics'
        this.activeTab = 'overview'; // 'overview' | 'ligands' | 'sequence' | 'analytics'
        this.currentLigands = [];
        this.isAligning = false;

        // Visual figs cached
        this.heatmapFig = null;
        this.treeFig = null;
        this.ramachandranStats = null;

        // Instantiate components
        this.topNav = new TopNav({
            onAddPDB: (pdbId) => this.addPDB(pdbId),
            onRunAlignment: () => this.executeAlignment(),
            onExportData: () => this.exportData()
        });

        this.sidebar = new Sidebar({
            onNavigate: (view) => this.navigateView(view),
            onNewWorkspace: () => this.resetWorkspace()
        });

        this.viewer3D = new Viewer3D();

        this.tabPanel = new TabPanel({
            onTabChange: (tab) => this.switchTab(tab)
        });

        this.overviewTab = new OverviewTab({
            selectedPDBs: this.selectedPDBs,
            chainSelections: this.chainSelections,
            pdbMetadata: this.pdbMetadata,
            onAddPDB: (pdbId) => this.addPDB(pdbId),
            onRemovePDB: (pdbId) => this.removePDB(pdbId),
            onChainSelection: (pdbId, chainId) => {
                this.chainSelections[pdbId] = chainId;
            },
            onRunAlignment: () => this.executeAlignment()
        });

        this.ligandTab = new LigandTab({
            selectedPDBs: this.selectedPDBs,
            currentRunId: this.currentRunId,
            onLigandSelected: (ligandId, contacts) => {
                if (ligandId) {
                    this.viewer3D.showLigandBindingSite(ligandId, contacts);
                } else {
                    this.viewer3D.resetCartoonStyles();
                }
            },
            onResidueSelected: (chain, resi) => {
                this.viewer3D.highlightResidue(chain, resi);
            }
        });

        this.sequenceTab = new SequenceTab();
        this.analyticsTab = new AnalyticsTab();

        this.historyPanel = new HistoryPanel({
            onReloadRun: (run) => this.reloadPastRun(run),
            onClose: () => this.navigateView('dashboard')
        });
    }

    render(rootElement) {
        rootElement.innerHTML = "";

        // Main Layout Structure
        const container = document.createElement('div');
        container.className = "flex flex-col h-screen overflow-hidden bg-[#08090C] text-[#e3e2e6]";
        
        // 1. Render TopNav
        container.appendChild(this.topNav.render());

        // 2. Render Body Workspace (Sidebar + Main Content Area Split)
        const bodyWrapper = document.createElement('div');
        bodyWrapper.className = "flex flex-1 overflow-hidden";
        
        bodyWrapper.appendChild(this.sidebar.render());

        // 3. Render Main Content (Viewer + Sidebar tab/history split)
        const mainContent = document.createElement('main');
        mainContent.className = "flex-grow flex flex-col md:flex-row h-full overflow-hidden p-6 gap-6 max-w-7xl mx-auto w-full";
        
        // Add 3D Viewer Panel
        mainContent.appendChild(this.viewer3D.render());

        // Add Right Control/Tab Panel wrapper
        const rightPane = document.createElement('div');
        rightPane.className = "w-full md:w-[400px] lg:w-[480px] flex flex-col gap-4 shrink-0 overflow-hidden";
        rightPane.id = "dashboard-right-pane";
        
        mainContent.appendChild(rightPane);
        bodyWrapper.appendChild(mainContent);
        container.appendChild(bodyWrapper);
        rootElement.appendChild(container);

        // Initialize 3Dmol viewer
        this.viewer3D.init3Dmol();

        // Render Right Pane contents based on current active view
        this.updateRightPaneDisplay();

        // Load initial chains metadata
        this.loadChainsMetadata();
    }

    updateRightPaneDisplay() {
        const pane = document.getElementById('dashboard-right-pane');
        if (!pane) return;
        
        pane.innerHTML = "";

        if (this.activeView === 'history') {
            pane.appendChild(this.historyPanel.render());
        } else if (this.activeView === 'dashboard' || this.activeView === 'alignment' || this.activeView === 'parameters') {
            pane.appendChild(this.tabPanel.render());
            
            const tabContentContainer = document.createElement('div');
            tabContentContainer.className = "flex-grow flex flex-col gap-4 overflow-hidden";
            tabContentContainer.id = "tab-content-container";
            
            pane.appendChild(tabContentContainer);

            if (this.activeTab === 'overview') {
                tabContentContainer.appendChild(this.overviewTab.render());
            } else if (this.activeTab === 'ligands') {
                tabContentContainer.appendChild(this.ligandTab.render());
            } else if (this.activeTab === 'sequence') {
                tabContentContainer.appendChild(this.sequenceTab.render());
            } else if (this.activeTab === 'analytics') {
                tabContentContainer.appendChild(this.analyticsTab.render());
            }
        } else {
            const div = document.createElement('div');
            div.className = "glass-panel rounded-xl p-6 flex flex-col items-center justify-center h-full text-center bg-[#11141c]/50";
            
            let icon = "folder_open";
            let title = "Protein Library";
            let desc = "Browse, organize, and inspect all downloaded structure coordinates.";
            
            if (this.activeView === 'metrics') {
                icon = "monitoring";
                title = "System Metrics";
                desc = "Monitor pipeline engine CPU workloads and disk storage quotas.";
            } else if (this.activeView === 'analytics') {
                icon = "query_stats";
                title = "Analytics Report";
                desc = "Detailed statistical distribution of structural residues and alignments.";
            }

            div.innerHTML = `
                <span class="material-symbols-outlined text-[48px] text-gradient-start mb-3">${icon}</span>
                <h3 class="font-headline-sm text-headline-sm font-semibold text-text-primary mb-2">${title}</h3>
                <p class="font-body-sm text-body-sm text-text-secondary max-w-xs leading-relaxed">${desc}</p>
            `;
            pane.appendChild(div);
        }
    }

    navigateView(viewName) {
        this.activeView = viewName;
        this.updateRightPaneDisplay();
    }

    switchTab(tabName) {
        this.activeTab = tabName;
        this.tabPanel.switchTab(tabName);
        this.updateRightPaneDisplay();
    }

    async loadChainsMetadata() {
        if (this.selectedPDBs.length === 0) return;
        this.overviewTab.setLoadingChains(true);
        try {
            const data = await fetchChains(this.selectedPDBs);
            Object.keys(data.chains).forEach(pid => {
                this.pdbMetadata[pid] = data.chains[pid];
                if (data.chains[pid].chains && data.chains[pid].chains.length > 0) {
                    if (!this.chainSelections[pid]) {
                        this.chainSelections[pid] = data.chains[pid].chains[0].id;
                    }
                }
            });
            this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
        } catch (err) {
            console.error("Failed to load chain selection data:", err);
        } finally {
            this.overviewTab.setLoadingChains(false);
        }
    }

    async addPDB(pdbId) {
        pdbId = pdbId.toUpperCase().trim();
        if (pdbId.length !== 4) return;
        if (this.selectedPDBs.includes(pdbId)) return;
        
        this.selectedPDBs.push(pdbId);
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
        await this.loadChainsMetadata();
    }

    removePDB(pdbId) {
        this.selectedPDBs = this.selectedPDBs.filter(pid => pid !== pdbId);
        delete this.chainSelections[pdbId];
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
    }

    async executeAlignment() {
        if (this.selectedPDBs.length < 2) {
            alert("At least 2 PDB structures are required for structural alignment.");
            return;
        }

        this.setAligningState(true);
        const params = this.overviewTab.getParameters();

        try {
            const data = await runAlignment(
                this.selectedPDBs,
                this.chainSelections,
                params.removeWater,
                params.removeHeteroatoms
            );

            const results = data.results;
            this.currentRunId = results.id;

            // Cache figures
            this.heatmapFig = results.heatmap_fig;
            this.treeFig = results.tree_fig;
            this.ramachandranStats = results.ramachandran_stats;

            // Load 3D Superposition
            const refId = this.selectedPDBs[0];
            const targetId = this.selectedPDBs[1];
            await this.viewer3D.loadSuperposition(
                results.id,
                refId,
                targetId,
                this.chainSelections[refId],
                this.chainSelections[targetId],
                results.stats.rmsd
            );

            // Fetch Ligands for Reference PDB
            this.currentLigands = [];
            const ligData = await fetchLigands(refId, results.id);
            this.currentLigands = ligData.ligands || [];

            // Update tabs
            this.ligandTab.updateLigands(this.currentLigands, results.id);
            this.sequenceTab.updateResults(results.id, results.stats);
            this.analyticsTab.updateResults(results.id, this.heatmapFig, this.treeFig, this.ramachandranStats);

            // Switch to Sequence tab
            this.switchTab('sequence');

        } catch (err) {
            console.error("Alignment run failed:", err);
            alert(`Alignment pipeline failed: ${err.message}`);
        } finally {
            this.setAligningState(false);
        }
    }

    setAligningState(isAligning) {
        this.isAligning = isAligning;
        this.topNav.setAligning(isAligning);
        this.overviewTab.setAligning(isAligning);
    }

    async reloadPastRun(run) {
        this.activeView = 'dashboard';
        this.activeTab = 'sequence';

        this.currentRunId = run.id;
        
        let pids = [];
        try {
            pids = typeof run.pdb_ids === 'string' ? JSON.parse(run.pdb_ids) : run.pdb_ids;
        } catch(e) {
            pids = [run.pdb_ids];
        }

        this.selectedPDBs = pids;
        
        let metadata = {};
        try {
            metadata = typeof run.metadata === 'string' ? JSON.parse(run.metadata) : run.metadata;
        } catch(e){}

        this.chainSelections = metadata.chain_selection || {};
        
        // Cache figures and quality stats from past run
        let stats = {};
        if (metadata.results) {
            stats = metadata.results.stats || {};
            this.heatmapFig = metadata.results.heatmap_fig || null;
            this.treeFig = metadata.results.tree_fig || null;
            this.ramachandranStats = metadata.results.ramachandran_stats || null;
        } else {
            stats = metadata.stats || {};
            this.heatmapFig = null;
            this.treeFig = null;
            this.ramachandranStats = null;
        }

        const rmsdValue = stats.rmsd || 0.0;

        // Update tabs state
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
        this.updateRightPaneDisplay();
        
        // Render 3D Superposition
        const refId = this.selectedPDBs[0];
        const targetId = this.selectedPDBs[1];
        
        await this.viewer3D.loadSuperposition(
            run.id,
            refId,
            targetId,
            this.chainSelections[refId] || 'A',
            this.chainSelections[targetId] || 'A',
            rmsdValue
        );

        // Load metadata chains asynchronously
        this.loadChainsMetadata();

        // Fetch Ligands
        this.currentLigands = [];
        try {
            const ligData = await fetchLigands(refId, run.id);
            this.currentLigands = ligData.ligands || [];
        } catch(err) {
            console.error("Failed to load ligands for past run:", err);
        }

        // Update tabs
        this.ligandTab.updateLigands(this.currentLigands, run.id);
        this.sequenceTab.updateResults(run.id, stats);
        this.analyticsTab.updateResults(run.id, this.heatmapFig, this.treeFig, this.ramachandranStats);

        // Switch to Sequence tab
        this.switchTab('sequence');
    }

    resetWorkspace() {
        if (confirm("Reset current workspace and clear selected structures?")) {
            this.selectedPDBs = ["4RLT", "3UG9"];
            this.chainSelections = { "4RLT": "A", "3UG9": "A" };
            this.currentRunId = null;
            this.currentLigands = [];
            this.activeTab = 'overview';
            this.heatmapFig = null;
            this.treeFig = null;
            this.ramachandranStats = null;
            
            // Reload defaults
            this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
            this.ligandTab.updateLigands([], null);
            this.sequenceTab.updateResults(null, null);
            this.analyticsTab.updateResults(null, null, null, null);
            this.viewer3D.resetCartoonStyles();
            
            document.getElementById("ambient-placeholder").style.display = "flex";
            document.getElementById("hud-reference-label").innerText = `Reference: --`;
            document.getElementById("hud-target-label").innerText = `Target: --`;
            document.getElementById("rmsd-value-hud").innerText = `-- Å`;

            this.switchTab('overview');
        }
    }

    exportData() {
        if (!this.currentRunId) {
            alert("No active alignment result to export.");
            return;
        }
        window.open(getAlignmentPdbUrl(this.currentRunId), '_blank');
    }
}

// Bootstrap Application
const app = new App();
app.render(document.getElementById('app'));
