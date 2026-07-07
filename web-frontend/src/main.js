import './style.css';
import { TopBar } from './components/TopBar';
import { Viewer3D } from './components/Viewer3D';
import { OverviewTab } from './components/OverviewTab';
import { LigandTab } from './components/LigandTab';
import { SequenceTab } from './components/SequenceTab';
import { AnalyticsTab } from './components/AnalyticsTab';
import { ClustersTab } from './components/ClustersTab';
import { ComparisonTab } from './components/ComparisonTab';
import { HistoryPanel } from './components/HistoryPanel';
import { DashboardTab } from './components/DashboardTab';
import { DiscoverTab } from './components/DiscoverTab';
import { fetchChains, runAlignment, pollJobUntilDone, fetchLigands, getAlignmentReportUrl, isValidPdbId } from './api';

class App {
    static MAX_PROTEINS = 20; // matches config.yaml's core.max_proteins default

    constructor() {
        this.selectedPDBs = ["4RLT", "3UG9"];
        this.chainSelections = { "4RLT": "A", "3UG9": "A" };
        this.pdbMetadata = {};
        this.currentRunId = null;
        this.activeTab = 'overview'; // 'dashboard' | 'overview' | 'discover' | 'ligands' | 'sequence' | 'analytics' | 'clusters' | 'comparison' | 'history'
        this.currentLigands = [];
        this.isAligning = false;

        // Visual figs cached
        this.heatmapFig = null;
        this.treeFig = null;
        this.ramachandranStats = null;
        this.rmsdDf = null;

        // Instantiate components
        this.topBar = new TopBar({
            onTabChange: (tab) => this.switchTab(tab),
            onExportData: () => this.exportData(),
            onNewWorkspace: () => this.resetWorkspace()
        });

        this.viewer3D = new Viewer3D();

        this.overviewTab = new OverviewTab({
            selectedPDBs: this.selectedPDBs,
            chainSelections: this.chainSelections,
            pdbMetadata: this.pdbMetadata,
            onAddPDB: (pdbId) => this.addPDB(pdbId),
            onAddManyPDBs: (pdbIds) => this.addManyPDBs(pdbIds),
            onRemovePDB: (pdbId) => this.removePDB(pdbId),
            onChainSelection: (pdbId, chainId) => {
                this.chainSelections[pdbId] = chainId;
            },
            onRunAlignment: () => this.executeAlignment()
        });

        this.ligandTab = new LigandTab({
            selectedPDBs: this.selectedPDBs,
            currentRunId: this.currentRunId,
            onLigandSelected: (structureIndex, ligandId, contacts) => {
                if (ligandId) {
                    this.viewer3D.showLigandBindingSite(structureIndex, ligandId, contacts);
                } else {
                    this.viewer3D.resetCartoonStyles();
                }
            },
            onResidueSelected: (structureIndex, chain, resi, alignedResi) => {
                this.viewer3D.highlightResidue(structureIndex, chain, resi, alignedResi);
            }
        });

        this.sequenceTab = new SequenceTab();
        this.analyticsTab = new AnalyticsTab();
        this.clustersTab = new ClustersTab();
        this.comparisonTab = new ComparisonTab();

        this.historyPanel = new HistoryPanel({
            onReloadRun: (run) => this.reloadPastRun(run)
        });

        this.dashboardTab = new DashboardTab({
            onReloadRun: (run) => this.reloadPastRun(run),
            onQuickStart: (pdbIds) => this.loadQuickStart(pdbIds)
        });

        this.discoverTab = new DiscoverTab();
    }

    render(rootElement) {
        rootElement.innerHTML = "";

        // Main Layout Structure
        const container = document.createElement('div');
        container.className = "flex flex-col h-screen overflow-hidden bg-bg text-primary";

        // 1. Sticky top bar (brand + tabs + workspace actions + system status)
        container.appendChild(this.topBar.render());

        // 2. Two-column shell: tab content (left) + persistent 3D viewer (right).
        // Plain flexbox (not CSS grid) — this is the same box-model the app already
        // used reliably for the 3Dmol canvas before this redesign, just mirrored.
        const gridShell = document.createElement('div');
        gridShell.className = "flex-1 flex flex-col md:flex-row overflow-hidden max-w-[1280px] mx-auto w-full";

        const tabContentPane = document.createElement('div');
        tabContentPane.id = "tab-content-pane";
        tabContentPane.className = "flex-1 overflow-y-auto px-8";

        const viewerColumn = document.createElement('div');
        viewerColumn.id = "viewer-column";
        viewerColumn.className = "w-full md:w-[480px] shrink-0 flex flex-col h-full p-6 pl-0";
        viewerColumn.appendChild(this.viewer3D.render());

        gridShell.appendChild(tabContentPane);
        gridShell.appendChild(viewerColumn);
        container.appendChild(gridShell);
        rootElement.appendChild(container);

        // Initialize 3Dmol viewer — rendered once here, never re-rendered by tab switching
        this.viewer3D.init3Dmol();

        // Render initial tab content
        this.updateTabContentPane();

        // Load initial chains metadata
        this.loadChainsMetadata();
    }

    updateTabContentPane() {
        const pane = document.getElementById('tab-content-pane');
        if (!pane) return;

        pane.innerHTML = "";

        if (this.activeTab === 'dashboard') {
            pane.appendChild(this.dashboardTab.render());
        } else if (this.activeTab === 'overview') {
            pane.appendChild(this.overviewTab.render());
        } else if (this.activeTab === 'discover') {
            pane.appendChild(this.discoverTab.render());
        } else if (this.activeTab === 'ligands') {
            pane.appendChild(this.ligandTab.render());
            this.ligandTab.updateLigands(this.currentLigands, this.currentRunId, this.selectedPDBs);
        } else if (this.activeTab === 'sequence') {
            pane.appendChild(this.sequenceTab.render());
            this.sequenceTab.updateResults(this.currentRunId, this.sequenceTab.stats);
        } else if (this.activeTab === 'analytics') {
            pane.appendChild(this.analyticsTab.render());
            this.analyticsTab.updateResults(
                this.currentRunId,
                this.heatmapFig,
                this.treeFig,
                this.ramachandranStats,
                this.analyticsTab.rmsfValues
            );
        } else if (this.activeTab === 'clusters') {
            pane.appendChild(this.clustersTab.render());
            this.clustersTab.updateResults(this.rmsdDf, this.pdbMetadata);
        } else if (this.activeTab === 'comparison') {
            pane.appendChild(this.comparisonTab.render());
            this.comparisonTab.updateResults(this.currentRunId);
        } else if (this.activeTab === 'history') {
            pane.appendChild(this.historyPanel.render());
        }
    }

    switchTab(tabName) {
        this.activeTab = tabName;
        this.topBar.switchTab(tabName);
        this.updateTabContentPane();
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
        if (!isValidPdbId(pdbId)) return;
        if (this.selectedPDBs.includes(pdbId)) return;

        this.selectedPDBs.push(pdbId);
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
        await this.loadChainsMetadata();
    }

    // Same cap config.yaml's core.max_proteins enforces server-side - a batch
    // paste is the one path that can realistically blow past it in one go,
    // where one-at-a-time adding never practically did.
    async addManyPDBs(pdbIds) {
        const room = App.MAX_PROTEINS - this.selectedPDBs.length;
        const accepted = pdbIds.slice(0, Math.max(room, 0));
        const overCap = pdbIds.length - accepted.length;

        this.selectedPDBs.push(...accepted);
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
        if (accepted.length > 0) await this.loadChainsMetadata();

        return { added: accepted, overCap };
    }

    removePDB(pdbId) {
        this.selectedPDBs = this.selectedPDBs.filter(pid => pid !== pdbId);
        delete this.chainSelections[pdbId];
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
    }

    loadQuickStart(pdbIds) {
        this.selectedPDBs = [...pdbIds];
        this.chainSelections = {};
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
        this.loadChainsMetadata();
        this.switchTab('overview');
    }

    async executeAlignment() {
        if (this.selectedPDBs.length < 2) {
            alert("At least 2 PDB structures are required for structural alignment.");
            return;
        }
        if (this.overviewTab.isLoadingChains) {
            // A just-added structure's chain selection hasn't resolved yet;
            // running now would persist an incomplete chain_selection.
            return;
        }

        this.setAligningState(true);
        const params = this.overviewTab.getParameters();

        try {
            const submission = await runAlignment(
                this.selectedPDBs,
                this.chainSelections,
                params.removeWater,
                params.removeHeteroatoms
            );

            const job = await pollJobUntilDone(submission.job_id);
            if (job.status === 'failed') {
                throw new Error(job.error || "Alignment pipeline failed.");
            }

            const results = job.results;
            this.currentRunId = results.id;

            // Cache figures
            this.heatmapFig = results.heatmap_fig;
            this.treeFig = results.tree_fig;
            this.ramachandranStats = results.ramachandran_stats;
            this.rmsdDf = results.rmsd_df;

            // Load 3D Superposition (all N structures)
            await this.viewer3D.loadSuperposition(
                results.id,
                this.selectedPDBs,
                this.chainSelections,
                results.rmsd_df
            );

            // Fetch Ligands for the first structure by default; LigandTab can
            // switch to any of the other N structures on demand.
            const refId = this.selectedPDBs[0];
            this.currentLigands = [];
            const ligData = await fetchLigands(refId, results.id);
            this.currentLigands = ligData.ligands || [];

            // Update tabs
            this.ligandTab.updateLigands(this.currentLigands, results.id, this.selectedPDBs);
            this.sequenceTab.updateResults(results.id, results.stats);
            this.analyticsTab.updateResults(results.id, this.heatmapFig, this.treeFig, this.ramachandranStats, results.rmsf_values);
            this.clustersTab.updateResults(this.rmsdDf, this.pdbMetadata);

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
        this.overviewTab.setAligning(isAligning);
    }

    async reloadPastRun(run) {
        let metadata = {};
        try {
            metadata = typeof run.metadata === 'string' ? JSON.parse(run.metadata) : run.metadata;
        } catch(e){}

        // Discover runs have no result directory/RMSD matrix to reload -
        // the full result is stashed in metadata.results at save time, so
        // reopening one just means handing that back to DiscoverTab.
        if (metadata && metadata.run_type === 'discover') {
            this.discoverTab.loadSavedResults(metadata.results);
            this.switchTab('discover');
            return;
        }

        this.activeTab = 'sequence';

        this.currentRunId = run.id;

        let pids = [];
        try {
            pids = typeof run.pdb_ids === 'string' ? JSON.parse(run.pdb_ids) : run.pdb_ids;
        } catch(e) {
            pids = [run.pdb_ids];
        }

        this.selectedPDBs = pids;

        this.chainSelections = metadata.chain_selection || {};
        
        // Cache figures and quality stats from past run
        let stats = {};
        if (metadata.results) {
            stats = metadata.results.stats || {};
            this.heatmapFig = metadata.results.heatmap_fig || null;
            this.treeFig = metadata.results.tree_fig || null;
            this.ramachandranStats = metadata.results.ramachandran_stats || null;
            this.rmsdDf = metadata.results.rmsd_df || null;
        } else {
            stats = metadata.stats || {};
            this.heatmapFig = null;
            this.treeFig = null;
            this.ramachandranStats = null;
            this.rmsdDf = null;
        }

        // Update tabs state
        this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
        this.updateTabContentPane();
        
        // Render 3D Superposition (all N structures)
        await this.viewer3D.loadSuperposition(
            run.id,
            this.selectedPDBs,
            this.chainSelections,
            this.rmsdDf
        );

        // Load metadata chains asynchronously
        this.loadChainsMetadata();

        // Fetch Ligands for the first structure by default
        const refId = this.selectedPDBs[0];
        this.currentLigands = [];
        try {
            const ligData = await fetchLigands(refId, run.id);
            this.currentLigands = ligData.ligands || [];
        } catch(err) {
            console.error("Failed to load ligands for past run:", err);
        }

        // Update tabs
        this.ligandTab.updateLigands(this.currentLigands, run.id, this.selectedPDBs);
        this.sequenceTab.updateResults(run.id, stats);
        this.analyticsTab.updateResults(
            run.id,
            this.heatmapFig,
            this.treeFig,
            this.ramachandranStats,
            metadata.results ? metadata.results.rmsf_values : null
        );
        this.clustersTab.updateResults(this.rmsdDf, this.pdbMetadata);

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
            this.rmsdDf = null;

            // Reload defaults
            this.overviewTab.updateState(this.selectedPDBs, this.chainSelections, this.pdbMetadata);
            this.ligandTab.updateLigands([], null, this.selectedPDBs);
            this.sequenceTab.updateResults(null, null);
            this.analyticsTab.updateResults(null, null, null, null);
            this.clustersTab.updateResults(null, null);
            this.comparisonTab.updateResults(null);
            this.viewer3D.reset();

            this.switchTab('overview');
        }
    }

    exportData() {
        if (!this.currentRunId) {
            alert("No active alignment result to export.");
            return;
        }
        window.open(getAlignmentReportUrl(this.currentRunId), '_blank');
    }
}

// Bootstrap Application
const app = new App();
app.render(document.getElementById('app'));
