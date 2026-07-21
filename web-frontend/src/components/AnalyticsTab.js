import { fetchAnnotations, fetchContactMap, fetchDifferenceDistance, fetchMutationImpact, fetchPae, fetchFlexibility, submitDdgStabilityJob, pollJobUntilDone } from '../api';
import { renderDomainList, renderGoTermList, renderFeatureList, renderCatalyticSiteList } from '../utils/annotationRenderers';
import { createInsightIconSvg } from '../utils/insightIcons';
import { wireArrowKeyNavigation } from '../utils/tabKeyboardNav';

// Renders one insight string's markdown-lite **bold** segments as real
// <strong> DOM nodes, built via createElement/createTextNode rather than
// any HTML-string sink (innerHTML/insertAdjacentHTML) - this is what
// makes it safe against injection regardless of what the string
// contains, not reliant on a string-escaping step a static analyzer
// can't verify survives a subsequent regex-based HTML reconstruction.
function appendMarkdownLiteBold(parent, text) {
    const parts = String(text ?? '').split(/\*\*(.+?)\*\*/g);
    parts.forEach((part, i) => {
        if (part === '') return;
        if (i % 2 === 1) {
            const strong = document.createElement('strong');
            strong.textContent = part;
            parent.appendChild(strong);
        } else {
            parent.appendChild(document.createTextNode(part));
        }
    });
}

// insights.py leads each insight with a "[[icon_name]] " marker (a real
// Material Symbols icon name, matching the icon font already used
// everywhere else in this app's UI) instead of an emoji character -
// this pulls that marker off and returns the icon name plus the
// remaining display text, or null for the icon if a string has no
// marker at all (so a malformed/legacy string still renders as plain
// text rather than breaking).
const INSIGHT_ICON_PATTERN = /^\[\[([a-z0-9_]+)\]\]\s*/;
function splitInsightIcon(text) {
    const match = INSIGHT_ICON_PATTERN.exec(String(text ?? ''));
    if (!match) return { icon: null, text: text ?? '' };
    return { icon: match[1], text: text.slice(match[0].length) };
}

const SUB_TABS = [
    { key: 'quality', label: 'Quality' },
    { key: 'rmsf', label: 'RMSF' },
    { key: 'rmsd', label: 'RMSD Matrix' },
    { key: 'phylo', label: 'Phylogeny' },
    { key: 'insights', label: 'Insights' },
    { key: 'annotations', label: 'Annotations' },
];

// Mirrors annotation_aggregator.py's PTM_FEATURE_TYPES exactly - which of
// the UniProt feature types this app already fetches specifically mean
// "a residue was chemically modified after translation," used to split
// one combined feature list into a distinct "PTM sites" section.
const PTM_FEATURE_TYPES = new Set(['Modified residue', 'Disulfide bond', 'Glycosylation', 'Lipidation', 'Cross-link']);

export class AnalyticsTab {
    element = null;
    currentRunId = null;
    heatmapFig = null;
    treeFig = null;
    ramachandranStats = null;
    secondaryStructureStats = null;
    tmScoreMatrix = null;
    rmsfValues = [];
    insights = [];
    qualityMetrics = null;
    activeSubTab = 'quality';
    // One entry per structure in the workspace: { pdbId, chain }. chain is
    // only needed for plain PDB IDs (a real SIFTS lookup); AlphaFold/SWISS-
    // MODEL IDs resolve their UniProt accession from the ID string alone.
    // Annotations work from this list alone (fetchAnnotations takes no
    // run_id at all) - unlike Quality/RMSF/RMSD/Phylogeny/Insights below,
    // which are genuinely N>=2-only and stay gated on a real currentRunId.
    structures = [];
    annotationsCache = {};
    // Keyed on the structure list's own identity (pdbIds joined), not
    // runId - two single-structure workspaces both have runId===null, so
    // keying on runId alone couldn't tell "already loaded for THIS
    // structure" apart from "already loaded for a different one".
    annotationsLoadedForKey = null;
    annotationsLoading = false;

    constructor(props = {}) {
        this.onHighlightResidues = props.onHighlightResidues || (() => {});
        this.onGoToWorkspace = props.onGoToWorkspace || (() => {});
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-analytics-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Structural Analytics</span>
                    <h2 class="section-title">Quality, fluctuation &amp; phylogeny</h2>
                </div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <!-- Sub-tab strip -->
                <div id="analytics-subtab-strip" role="tablist" class="flex gap-1 border border-border rounded-md p-1 shrink-0">
                    ${SUB_TABS.map(t => `
                        <button data-subtab="${t.key}" id="analytics-subtab-tab-${t.key}" role="tab" aria-controls="analytics-subtab-panel-${t.key}" class="analytics-subtab-btn flex-1 py-1.5 rounded-md font-label-md text-label-md transition-colors" aria-selected="${t.key === 'quality'}" tabindex="${t.key === 'quality' ? '0' : '-1'}">${t.label}</button>
                    `).join('')}
                </div>

                <!-- Ramachandran / Quality Report -->
                <div data-panel="quality" class="flex flex-col gap-4 shrink-0">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        <div class="stat-row stat-primary">
                            <span class="stat-key">Ramachandran score</span>
                            <span id="ramachandran-score" class="stat-value">--</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-key">Outlier residues</span>
                            <span id="ramachandran-outliers" class="stat-value">--</span>
                        </div>
                    </div>
                    <div id="ramachandran-outliers-list-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Top outliers</span>
                        <div id="ramachandran-outliers-list" class="flex flex-wrap gap-1.5">
                            <!-- Outlier chips -->
                        </div>
                    </div>
                    <div id="quality-metrics-table-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Alignment quality (TM-score / GDT-TS - fold-similarity scores from 0 to 1, higher is more similar)</span>
                        <table class="w-full font-body-sm text-body-sm">
                            <thead>
                                <tr class="text-secondary text-left border-b border-border-subtle">
                                    <th class="font-normal py-1">Structure</th>
                                    <th class="font-normal py-1">TM-score</th>
                                    <th class="font-normal py-1">GDT-TS</th>
                                </tr>
                            </thead>
                            <tbody id="quality-metrics-table-body"></tbody>
                        </table>
                    </div>
                    <div id="secondary-structure-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Secondary structure (backbone-torsion approximation, not DSSP)</span>
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div class="stat-row"><span class="stat-key">Helix</span><span id="ss-helix-percent" class="stat-value">--</span></div>
                            <div class="stat-row"><span class="stat-key">Sheet</span><span id="ss-sheet-percent" class="stat-value">--</span></div>
                            <div class="stat-row"><span class="stat-key">Coil</span><span id="ss-coil-percent" class="stat-value">--</span></div>
                        </div>
                    </div>
                    <div id="pairwise-tm-score-card" class="flex flex-col gap-2 hidden border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Pairwise TM-score (independent optimal superposition)</span>
                        <table class="w-full font-body-sm text-body-sm">
                            <thead>
                                <tr class="text-secondary text-left border-b border-border-subtle">
                                    <th class="font-normal py-1">Pair</th>
                                    <th class="font-normal py-1">TM-score</th>
                                </tr>
                            </thead>
                            <tbody id="pairwise-tm-score-table-body"></tbody>
                        </table>
                    </div>
                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Predicted aligned error (AlphaFold structures only - AlphaFold's own confidence in each residue pair's relative position, lower is better)</span>
                        <div class="flex gap-2 items-center">
                            <select id="pae-pdb-select" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="pae-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="pae-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select an AlphaFold structure and load to view its per-residue-pair confidence.
                            </div>
                        </div>
                    </div>
                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Predicted flexibility (Gaussian Network Model - a computational prediction from geometry alone, not a measurement)</span>
                        <div class="flex gap-2 items-center">
                            <select id="flexibility-pdb-select" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="flexibility-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="flexibility-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select a structure and load to view its predicted per-residue flexibility.
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Residue Fluctuation (Plotly Line Chart) -->
                <div data-panel="rmsf" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="rmsf-plotly-chart" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive RMSF chart.
                        </div>
                    </div>
                </div>

                <!-- Pairwise RMSD Matrix (Plotly Heatmap) -->
                <div data-panel="rmsd" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px] flex flex-col gap-4">
                    <div id="rmsd-plotly-heatmap" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive heatmap.
                        </div>
                    </div>

                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Contact map (CA-CA, 8&Aring; default)</span>
                        <div class="flex gap-2 items-center">
                            <select id="contact-map-pdb-select" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="contact-map-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="contact-map-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select a structure and load to view its contact map.
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Difference-distance matrix</span>
                        <div class="flex gap-2 items-center">
                            <select id="diff-distance-pdb-a-select" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <select id="diff-distance-pdb-b-select" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="diff-distance-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Load</button>
                        </div>
                        <div id="diff-distance-plotly" class="w-full h-[240px]">
                            <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                                Select two structures and load to view their difference-distance matrix.
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Phylogenetic Tree (Plotly Dendrogram) -->
                <div data-panel="phylo" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="phylo-plotly-tree" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive dendrogram.
                        </div>
                    </div>
                </div>

                <!-- Automated Insights (plain-language summary bullets) -->
                <div data-panel="insights" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px] flex flex-col gap-4">
                    <ul id="analytics-insights-list" class="flex flex-col gap-2"></ul>
                    <div id="analytics-insights-empty" class="flex items-center justify-center h-full text-secondary font-body-sm">
                        Run alignment to display automated insights.
                    </div>

                    <div class="flex flex-col gap-2 border-t border-border-subtle pt-4">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Describe the difference between two structures</span>
                        <div class="flex gap-2 items-center">
                            <select id="diff-narrative-pdb-a-select" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <select id="diff-narrative-pdb-b-select" class="flex-1 bg-surface-raised border border-border-subtle rounded-md px-2 py-1 font-body-sm text-body-sm">
                                <option value="">Select a structure</option>
                            </select>
                            <button id="diff-narrative-load-btn" class="btn-secondary px-3 py-1 rounded-md font-label-sm text-label-sm" disabled>Describe</button>
                        </div>
                        <p id="diff-narrative-text" class="font-body-sm text-body-sm text-secondary">
                            Select two structures above to get a plain-English summary of how they differ.
                        </p>
                    </div>
                </div>

                <!-- Functional Annotation (InterPro domains / GO terms / Reactome pathways) -->
                <div data-panel="annotations" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px] flex flex-col gap-4">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Functional annotation</span>
                        <select id="annotations-structure-select" aria-label="Structure to show functional annotation for" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[160px]"></select>
                    </div>
                    <div id="annotations-content" class="flex flex-col gap-3">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display functional annotation.
                        </div>
                    </div>
                    <div id="annotations-shared-section" class="hidden flex-col gap-3 pt-3 border-t border-border-subtle">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Shared across all structures</span>
                        <div id="annotations-shared-content"></div>
                    </div>

                    <div class="flex flex-col gap-2 pt-3 border-t border-border-subtle">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Map a mutation</span>
                        <span class="font-body-sm text-body-sm text-secondary">Maps the selected structure's residue to UniProt, then checks ClinVar for a known clinical record and AlphaMissense for a predicted pathogenicity score</span>
                        <div class="flex items-end gap-2">
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary">Residue #</span>
                                <input id="mutation-resi-input" type="number" min="1" class="w-24 bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono" />
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary">Mutant residue</span>
                                <input id="mutation-mutant-input" type="text" maxlength="1" class="w-16 bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono uppercase" />
                            </label>
                            <button id="mutation-map-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Map</button>
                            <button id="mutation-ddg-btn" class="btn-secondary px-3 py-1.5 rounded-md font-label-md text-label-md">Predict stability impact</button>
                        </div>
                        <div id="mutation-impact-result" class="font-body-sm text-body-sm text-secondary flex flex-col gap-1"></div>
                        <div id="mutation-ddg-result" class="font-body-sm text-body-sm text-secondary flex flex-col gap-1"></div>
                    </div>
                </div>
            </div>
        `;

        this.element = div;
        this.setupSubTabs();
        this.setupAnnotationsPicker();
        this.setupContactMapControls();
        this.setupPaeControls();
        this.setupFlexibilityControls();
        this.setupDiffNarrativeControls();
        this.renderVisuals();
        return div;
    }

    setupDiffNarrativeControls() {
        this.element.querySelector('#diff-narrative-load-btn').addEventListener('click', () => this.describeStructureDiff());
        ['#diff-narrative-pdb-a-select', '#diff-narrative-pdb-b-select'].forEach(sel => {
            this.element.querySelector(sel).addEventListener('change', () => {
                const a = this.element.querySelector('#diff-narrative-pdb-a-select').value;
                const b = this.element.querySelector('#diff-narrative-pdb-b-select').value;
                this.element.querySelector('#diff-narrative-load-btn').disabled = !a || !b;
            });
        });
    }

    setupContactMapControls() {
        this.element.querySelector('#contact-map-load-btn').addEventListener('click', () => this.loadContactMap());
        this.element.querySelector('#diff-distance-load-btn').addEventListener('click', () => this.loadDifferenceDistance());
        ['#contact-map-pdb-select', '#diff-distance-pdb-a-select', '#diff-distance-pdb-b-select'].forEach(sel => {
            this.element.querySelector(sel).addEventListener('change', () => this.updateContactMapButtonStates());
        });
    }

    setupPaeControls() {
        this.element.querySelector('#pae-load-btn').addEventListener('click', () => this.loadPae());
        this.element.querySelector('#pae-pdb-select').addEventListener('change', (e) => {
            this.element.querySelector('#pae-load-btn').disabled = !e.target.value;
        });
    }

    setupFlexibilityControls() {
        this.element.querySelector('#flexibility-load-btn').addEventListener('click', () => this.loadFlexibility());
        this.element.querySelector('#flexibility-pdb-select').addEventListener('change', (e) => {
            this.element.querySelector('#flexibility-load-btn').disabled = !e.target.value;
        });
    }

    setupSubTabs() {
        this.element.querySelectorAll('.analytics-subtab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchSubTab(btn.dataset.subtab));
        });
        // Panels are co-located with their tabs in this component (unlike
        // TopBar's tabs, which swap in entirely different components
        // elsewhere in the DOM), so a real role="tabpanel"/aria-labelledby
        // pairing is possible here.
        SUB_TABS.forEach(t => {
            const panel = this.element.querySelector(`[data-panel="${t.key}"]`);
            if (panel) {
                panel.id = `analytics-subtab-panel-${t.key}`;
                panel.setAttribute('role', 'tabpanel');
                panel.setAttribute('aria-labelledby', `analytics-subtab-tab-${t.key}`);
            }
        });
        wireArrowKeyNavigation(this.element.querySelector('#analytics-subtab-strip'), '.analytics-subtab-btn', (btn) => this.switchSubTab(btn.dataset.subtab));
        this.updateSubTabView();
    }

    setupAnnotationsPicker() {
        const select = this.element.querySelector('#annotations-structure-select');
        select.addEventListener('change', () => this.renderAnnotationsPanel());
        this.element.querySelector('#mutation-map-btn').addEventListener('click', () => this.loadMutationImpact());
        this.element.querySelector('#mutation-ddg-btn').addEventListener('click', () => this.loadDdgStability());
    }

    switchSubTab(key) {
        this.activeSubTab = key;
        this.updateSubTabView();

        // Plotly may not auto-detect a container going from hidden -> visible;
        // resize defensively so the chart in the panel just shown renders correctly.
        const chartIdByPanel = { rmsf: 'rmsf-plotly-chart', rmsd: 'rmsd-plotly-heatmap', phylo: 'phylo-plotly-tree' };
        const chartId = chartIdByPanel[key];
        if (chartId && typeof Plotly !== 'undefined') {
            const chartDiv = this.element.querySelector(`#${chartId}`);
            if (chartDiv?.data) {
                Plotly.Plots.resize(chartDiv);
            }
        }

        // Annotation lookups are real network calls (InterPro/QuickGO/
        // Reactome/SIFTS) - fetched lazily on first visit to this sub-tab,
        // not for every run whether or not anyone looks, and only once per
        // structure set (annotationsLoadedForKey guards a re-fetch on every
        // click). Available whenever there's at least one structure, not
        // just after a completed alignment - fetchAnnotations needs no run.
        if (key === 'annotations' && this.structures.length > 0 && this.annotationsLoadedForKey !== this._structuresKey()) {
            this.loadAllAnnotations();
        }
    }

    updateSubTabView() {
        this.element.querySelectorAll('.analytics-subtab-btn').forEach(btn => {
            const isActive = btn.dataset.subtab === this.activeSubTab;
            btn.className = `analytics-subtab-btn flex-1 py-1.5 rounded-md font-label-md text-label-md transition-colors ${isActive ? 'bg-accent-muted text-accent' : 'text-secondary hover:text-primary'}`;
            btn.setAttribute('aria-selected', String(isActive));
            btn.tabIndex = isActive ? 0 : -1;
        });
        this.element.querySelectorAll('[data-panel]').forEach(panel => {
            panel.classList.toggle('hidden', panel.dataset.panel !== this.activeSubTab);
        });
    }

    // `figures` bundles { heatmap, tree } (previously two positional params)
    // and `structures` is an array of { pdbId, chain } pairs the caller
    // builds from its own selectedPDBs/chainSelections state (previously
    // two more positional params) - both consolidations exist purely to
    // keep this under SonarCloud's max-7-parameter threshold (S107), not
    // for any behavioral reason.
    _structuresKey() {
        return this.structures.map(s => s.pdbId).join('|');
    }

    // structuralStats bundles ramachandran + secondaryStructure (both
    // per-run structural-QC summaries) into one object instead of adding a
    // new positional parameter, same rationale as the `structures` param -
    // keeps this under SonarCloud's max-parameter threshold.
    updateResults(runId, figures, structuralStats, rmsfValues, insights, qualityMetrics, structures) {
        const newStructures = structures || [];
        const newKey = newStructures.map(s => s.pdbId).join('|');
        if (newKey !== this._structuresKey()) {
            // A different structure set (a different run, a reset, or a
            // different single un-aligned structure) - any cached
            // annotations belong to a set that's no longer showing, so
            // they'd be wrong to reuse; the next Annotations-tab visit
            // re-fetches for real.
            this.annotationsCache = {};
            this.annotationsLoadedForKey = null;
        }
        this.currentRunId = runId;
        this.heatmapFig = figures?.heatmap ?? null;
        this.treeFig = figures?.tree ?? null;
        this.ramachandranStats = structuralStats?.ramachandran ?? null;
        this.secondaryStructureStats = structuralStats?.secondaryStructure ?? null;
        this.tmScoreMatrix = structuralStats?.tmScoreMatrix ?? null;
        this.rmsfValues = rmsfValues || [];
        this.insights = insights || [];
        this.qualityMetrics = qualityMetrics || null;
        this.structures = newStructures;
        this.renderVisuals();
    }

    async loadAllAnnotations() {
        if (!this.element || this.structures.length === 0) return;
        this.annotationsLoading = true;
        this.renderAnnotationsPanel();

        const keyAtStart = this._structuresKey();
        const results = await Promise.all(
            this.structures.map(async ({ pdbId, chain }) => {
                try {
                    const data = await fetchAnnotations(pdbId, chain);
                    return [pdbId, data.annotation];
                } catch (err) {
                    console.error(`Failed to load annotation for ${pdbId}:`, err);
                    return [pdbId, null];
                }
            })
        );

        // The structure set may have changed while these were in flight -
        // don't clobber newer state with a stale response.
        if (keyAtStart !== this._structuresKey()) return;

        this.annotationsCache = Object.fromEntries(results);
        this.annotationsLoadedForKey = keyAtStart;
        this.annotationsLoading = false;
        this.populateAnnotationsPicker();
        this.renderAnnotationsPanel();
    }

    populateAnnotationsPicker() {
        const select = this.element.querySelector('#annotations-structure-select');
        const previousValue = select.value;
        select.innerHTML = "";
        this.structures.forEach(({ pdbId }) => {
            const opt = document.createElement('option');
            opt.value = pdbId;
            opt.textContent = pdbId;
            select.appendChild(opt);
        });
        if (this.structures.some(s => s.pdbId === previousValue)) {
            select.value = previousValue;
        }
    }

    renderAnnotationsPanel() {
        if (!this.element) return;
        const content = this.element.querySelector('#annotations-content');
        const sharedSection = this.element.querySelector('#annotations-shared-section');
        const sharedContent = this.element.querySelector('#annotations-shared-content');

        if (this.structures.length === 0) {
            content.innerHTML = "";
            const empty = document.createElement('div');
            empty.className = "flex flex-col items-center justify-center gap-2 h-full text-secondary font-body-sm";
            const text = document.createElement('span');
            text.textContent = "Add a structure in the Workspace tab to display functional annotation.";
            empty.appendChild(text);
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = "font-label-sm text-label-sm text-accent hover:underline";
            btn.textContent = 'Go to Workspace';
            btn.addEventListener('click', () => this.onGoToWorkspace());
            empty.appendChild(btn);
            content.appendChild(empty);
            sharedSection.classList.add('hidden');
            sharedSection.classList.remove('flex');
            return;
        }
        if (this.annotationsLoading) {
            content.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm"><span class="animate-spin material-symbols-outlined text-[18px]">sync</span> Resolving functional annotation…</div>`;
            sharedSection.classList.add('hidden');
            sharedSection.classList.remove('flex');
            return;
        }

        const select = this.element.querySelector('#annotations-structure-select');
        const selectedPdbId = select.value || this.structures[0]?.pdbId;
        const annotation = this.annotationsCache[selectedPdbId];

        if (!annotation) {
            content.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Switch to this tab to load functional annotation.</div>`;
        } else if (!annotation.accession) {
            content.innerHTML = `<div class="font-body-sm text-secondary py-4">No UniProt accession could be resolved for ${selectedPdbId} - no functional annotation available.</div>`;
        } else if (!annotation.domains?.length && !annotation.go_terms?.length && !annotation.reactome_pathways?.length && !annotation.uniprot_features?.length && !annotation.catalytic_sites?.length) {
            content.innerHTML = `<div class="font-body-sm text-secondary py-4">Resolved to UniProt ${annotation.accession}, but no curated domains, GO terms, pathways, or sequence features were found.</div>`;
        } else {
            // Split the single fetch_uniprot_features() result into a
            // distinct "PTM sites" list (chemical modifications after
            // translation - phosphorylation, glycosylation, lipidation,
            // disulfides, cross-links) and everything else (active/binding
            // sites, natural variants) - real data this app already
            // fetches, just surfaced as two clearly-labeled groups instead
            // of one mixed list.
            const allFeatures = annotation.uniprot_features || [];
            const ptmFeatures = allFeatures.filter(f => PTM_FEATURE_TYPES.has(f.type));
            const otherFeatures = allFeatures.filter(f => !PTM_FEATURE_TYPES.has(f.type));

            content.innerHTML = `
                <div class="font-body-sm text-secondary">Resolved to UniProt <span class="font-mono text-primary">${annotation.accession}</span></div>
                ${renderDomainList(annotation.domains)}
                ${renderGoTermList(annotation.go_terms)}
                ${renderFeatureList(ptmFeatures, 'PTM sites', 'ptm-highlight-btn')}
                ${renderFeatureList(otherFeatures, 'UniProt features', 'feature-highlight-btn')}
                ${renderCatalyticSiteList(annotation.catalytic_sites)}
                ${this.renderReactomePathways(annotation.reactome_pathways)}
            `;
            content.querySelectorAll('.domain-highlight-btn').forEach(btn => {
                const domain = annotation.domains[Number(btn.dataset.domainIndex)];
                if (domain?.highlight_chains) {
                    btn.addEventListener('click', () => this.onHighlightResidues(domain.highlight_chains));
                }
            });
            content.querySelectorAll('.ptm-highlight-btn').forEach(btn => {
                const feature = ptmFeatures[Number(btn.dataset.featureIndex)];
                if (feature?.highlight_chains) {
                    btn.addEventListener('click', () => this.onHighlightResidues(feature.highlight_chains));
                }
            });
            content.querySelectorAll('.feature-highlight-btn').forEach(btn => {
                const feature = otherFeatures[Number(btn.dataset.featureIndex)];
                if (feature?.highlight_chains) {
                    btn.addEventListener('click', () => this.onHighlightResidues(feature.highlight_chains));
                }
            });
        }

        this.renderSharedAnnotations(sharedSection, sharedContent);
    }

    // Maps the currently-selected structure's own author-numbered residue
    // to UniProt/ClinVar - independent of the cached annotation list above
    // (a fresh network call per click, not something to prefetch for every
    // structure the way the domain/GO/pathway lists are).
    async loadMutationImpact() {
        const resultDiv = this.element.querySelector('#mutation-impact-result');
        const select = this.element.querySelector('#annotations-structure-select');
        const pdbId = select.value || this.structures[0]?.pdbId;
        const structure = this.structures.find(s => s.pdbId === pdbId);
        const chain = structure?.chain;
        const resi = Number.parseInt(this.element.querySelector('#mutation-resi-input').value, 10);
        const mutant = this.element.querySelector('#mutation-mutant-input').value.trim();

        if (!pdbId || !chain) {
            resultDiv.textContent = 'Select a structure with a resolved chain first.';
            return;
        }
        if (!Number.isInteger(resi) || !mutant) {
            resultDiv.textContent = 'Enter a residue number and a mutant residue.';
            return;
        }

        resultDiv.textContent = 'Mapping mutation…';
        try {
            const data = await fetchMutationImpact(pdbId, chain, resi, mutant);
            this.renderMutationImpact(data);
        } catch (err) {
            console.error("Failed to map mutation:", err);
            resultDiv.textContent = 'Failed to map this mutation.';
        }
    }

    renderMutationImpact(data) {
        const resultDiv = this.element.querySelector('#mutation-impact-result');
        resultDiv.innerHTML = "";

        const summary = document.createElement('div');
        summary.className = "text-primary";
        summary.textContent = `UniProt ${data.accession ?? '--'} position ${data.uniprot_position ?? '--'}: ${data.wildtype_residue ?? '?'} → ${data.mutant_residue}`;
        resultDiv.appendChild(summary);

        const clinvarLine = document.createElement('div');
        if (data.clinvar) {
            clinvarLine.textContent = `ClinVar: ${data.clinvar.clinical_significance} (${data.clinvar.review_status})`;
        } else {
            clinvarLine.textContent = 'No matching ClinVar record found.';
        }
        resultDiv.appendChild(clinvarLine);

        const alphamissenseLine = document.createElement('div');
        if (data.alphamissense) {
            alphamissenseLine.textContent = `AlphaMissense: ${data.alphamissense.pathogenicity.toFixed(3)} (${data.alphamissense.class})`;
        } else {
            alphamissenseLine.textContent = 'No AlphaMissense score available for this substitution.';
        }
        resultDiv.appendChild(alphamissenseLine);

        const gnomadLine = document.createElement('div');
        if (data.gnomad && (data.gnomad.af_exome != null || data.gnomad.af_genome != null)) {
            const parts = [];
            if (data.gnomad.af_exome != null) parts.push(`exome ${(data.gnomad.af_exome * 100).toPrecision(3)}%`);
            if (data.gnomad.af_genome != null) parts.push(`genome ${(data.gnomad.af_genome * 100).toPrecision(3)}%`);
            gnomadLine.textContent = `gnomAD population frequency: ${parts.join(', ')}`;
        } else {
            gnomadLine.textContent = 'No gnomAD population frequency data found for this substitution.';
        }
        resultDiv.appendChild(gnomadLine);

        if (data.known_uniprot_variant) {
            const variantLine = document.createElement('div');
            variantLine.textContent = `Known UniProt variant at this position: ${data.known_uniprot_variant.description || '(no description)'}`;
            resultDiv.appendChild(variantLine);
        }

        if (data.highlight_chains) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = "font-label-sm text-label-sm text-accent hover:underline text-left";
            btn.textContent = 'Highlight in 3D';
            btn.addEventListener('click', () => this.onHighlightResidues(data.highlight_chains));
            resultDiv.appendChild(btn);
        }
    }

    // Separate from loadMutationImpact() above - DDMut's own submit-then-
    // poll workflow against an external server is itself slow (a real job,
    // not an instant lookup), so this goes through the same job-submit +
    // pollJobUntilDone pattern already used for Clustal Omega/BLAST rather
    // than a synchronous fetch. Resolves pdbId/chain/resi/mutant the same
    // way loadMutationImpact() does, for the same selected structure.
    async loadDdgStability() {
        const resultDiv = this.element.querySelector('#mutation-ddg-result');
        const select = this.element.querySelector('#annotations-structure-select');
        const pdbId = select.value || this.structures[0]?.pdbId;
        const structure = this.structures.find(s => s.pdbId === pdbId);
        const chain = structure?.chain;
        const resi = Number.parseInt(this.element.querySelector('#mutation-resi-input').value, 10);
        const mutant = this.element.querySelector('#mutation-mutant-input').value.trim();

        if (!pdbId || !chain) {
            resultDiv.textContent = 'Select a structure with a resolved chain first.';
            return;
        }
        if (!Number.isInteger(resi) || !mutant) {
            resultDiv.textContent = 'Enter a residue number and a mutant residue.';
            return;
        }

        resultDiv.textContent = 'Predicting stability impact (this can take a minute)…';
        try {
            const submitted = await submitDdgStabilityJob(pdbId, chain, resi, mutant);
            const job = await pollJobUntilDone(submitted.job_id, { intervalMs: 10000 });
            if (job.status === 'failed') {
                resultDiv.textContent = job.error || 'Failed to predict stability impact.';
                return;
            }
            this.renderDdgStability(job.prediction);
        } catch (err) {
            console.error("Failed to predict stability impact:", err);
            resultDiv.textContent = 'Failed to predict stability impact.';
        }
    }

    renderDdgStability(prediction) {
        const resultDiv = this.element.querySelector('#mutation-ddg-result');
        const ddg = prediction?.prediction;
        if (typeof ddg !== 'number') {
            resultDiv.textContent = 'DDMut did not return a usable prediction.';
            return;
        }
        const direction = ddg >= 0 ? 'stabilizing' : 'destabilizing';
        resultDiv.textContent = `Predicted stability change (DDMut): ${ddg >= 0 ? '+' : ''}${ddg.toFixed(2)} kcal/mol (${direction})`;
    }

    renderReactomePathways(pathways) {
        if (!pathways?.length) return '';
        return `
            <div class="flex flex-col gap-2">
                <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Reactome pathways</span>
                ${pathways.map(p => `
                    <div class="flex items-center py-1.5 border-b border-border-subtle">
                        <span class="font-body-sm">${p.name}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // A domain/GO term counts as "shared" when every structure that
    // resolved an accession also carries it - a plain name intersection,
    // computed client-side since each structure's annotation is already in
    // hand once loadAllAnnotations() settles (no new backend call needed).
    renderSharedAnnotations(sharedSection, sharedContent) {
        const annotated = Object.values(this.annotationsCache).filter(a => a?.accession);
        if (annotated.length < 2) {
            sharedSection.classList.add('hidden');
            sharedSection.classList.remove('flex');
            return;
        }

        const domainNameSets = annotated.map(a => new Set((a.domains || []).map(d => d.name)));
        const sharedDomainNames = [...domainNameSets[0]].filter(name => domainNameSets.every(s => s.has(name)));

        const goNameSets = annotated.map(a => new Set((a.go_terms || []).map(g => g.name || g.id)));
        const sharedGoNames = [...goNameSets[0]].filter(name => goNameSets.every(s => s.has(name)));

        if (sharedDomainNames.length === 0 && sharedGoNames.length === 0) {
            sharedSection.classList.add('hidden');
            sharedSection.classList.remove('flex');
            sharedContent.innerHTML = '';
            return;
        }

        sharedSection.classList.remove('hidden');
        sharedSection.classList.add('flex');
        sharedContent.innerHTML = `
            ${renderDomainList(sharedDomainNames.map(name => ({ name, type: 'domain' })))}
            ${renderGoTermList(sharedGoNames.map(name => ({ name })))}
        `;
    }

    renderVisuals() {
        if (!this.element) return;

        this.renderRamachandranSection();
        this.renderQualityMetricsTable();
        this.renderSecondaryStructureSection();
        this.renderPairwiseTmScoreTable();
        this.renderRmsfChart();
        this.renderRmsdHeatmap();
        this.populateContactMapSelectors();
        this.populatePaeSelector();
        this.populateFlexibilitySelector();
        this.populateDiffNarrativeSelectors();
        this.renderPhyloTree();
        this.renderInsightsList();

        // Annotations sub-tab - repopulate the structure picker for this
        // run and re-render from whatever's already cached (a fresh
        // network fetch only happens on first visit to this sub-tab, see
        // switchSubTab()).
        this.populateAnnotationsPicker();
        this.renderAnnotationsPanel();
    }

    renderRamachandranSection() {
        const score = this.element.querySelector('#ramachandran-score');
        const outliers = this.element.querySelector('#ramachandran-outliers');
        const listCard = this.element.querySelector('#ramachandran-outliers-list-card');
        const listContainer = this.element.querySelector('#ramachandran-outliers-list');

        if (this.ramachandranStats?.favored_percent == null) {
            score.innerText = "--";
            outliers.innerText = "--";
            listCard.classList.add('hidden');
            return;
        }

        score.innerText = `${this.ramachandranStats.favored_percent.toFixed(1)}%`;
        outliers.innerText = this.ramachandranStats.outlier_count;

        if (this.ramachandranStats.outlier_count > 0 && this.ramachandranStats.outliers_list?.length > 0) {
            listCard.classList.remove('hidden');
            listContainer.innerHTML = "";
            this.ramachandranStats.outliers_list.forEach(item => {
                const chip = document.createElement('span');
                chip.className = "px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle text-error font-mono text-[10px]";
                chip.innerText = item;
                listContainer.appendChild(chip);
            });
        } else {
            listCard.classList.add('hidden');
        }
    }

    renderSecondaryStructureSection() {
        const card = this.element.querySelector('#secondary-structure-card');
        if (this.secondaryStructureStats?.total_residues == null || this.secondaryStructureStats.total_residues === 0) {
            card.classList.add('hidden');
            return;
        }

        card.classList.remove('hidden');
        this.element.querySelector('#ss-helix-percent').innerText = `${this.secondaryStructureStats.helix_percent.toFixed(1)}%`;
        this.element.querySelector('#ss-sheet-percent').innerText = `${this.secondaryStructureStats.sheet_percent.toFixed(1)}%`;
        this.element.querySelector('#ss-coil-percent').innerText = `${this.secondaryStructureStats.coil_percent.toFixed(1)}%`;
    }

    // tmScoreMatrix mirrors rmsd_df's { index, columns, data } shape
    // (both are pandas DataFrames sanitized the same way server-side) - a
    // symmetric pdb_id x pdb_id matrix, self-comparisons excluded here
    // since they're always 1.0 and not informative.
    renderPairwiseTmScoreTable() {
        const card = this.element.querySelector('#pairwise-tm-score-card');
        const body = this.element.querySelector('#pairwise-tm-score-table-body');
        const index = this.tmScoreMatrix?.index;
        const data = this.tmScoreMatrix?.data;

        if (!index || !data || index.length < 2) {
            card.classList.add('hidden');
            return;
        }

        card.classList.remove('hidden');
        const rows = [];
        for (let i = 0; i < index.length; i++) {
            for (let j = i + 1; j < index.length; j++) {
                rows.push({ a: index[i], b: index[j], value: data[i][j] });
            }
        }
        body.innerHTML = rows.map(r => `
            <tr>
                <td class="py-1 font-mono"><span class="block max-w-[220px] truncate" title="${r.a} &harr; ${r.b}">${r.a} &harr; ${r.b}</span></td>
                <td class="py-1 font-mono">${r.value.toFixed(3)}</td>
            </tr>
        `).join('');
    }

    renderQualityMetricsTable() {
        const qualityCard = this.element.querySelector('#quality-metrics-table-card');
        const qualityBody = this.element.querySelector('#quality-metrics-table-body');
        const qualityEntries = this.qualityMetrics ? Object.entries(this.qualityMetrics) : [];

        if (qualityEntries.length === 0) {
            qualityCard.classList.add('hidden');
            return;
        }

        qualityCard.classList.remove('hidden');
        qualityBody.innerHTML = "";
        qualityEntries.forEach(([pdbId, metrics]) => {
            const row = document.createElement('tr');
            row.className = "border-b border-border-subtle last:border-0";

            const idCell = document.createElement('td');
            idCell.className = "py-1 font-mono text-primary";
            const idSpan = document.createElement('span');
            idSpan.className = "block max-w-[180px] truncate";
            idSpan.title = pdbId;
            idSpan.textContent = pdbId;
            idCell.appendChild(idSpan);

            const tmCell = document.createElement('td');
            tmCell.className = "py-1 text-primary";
            tmCell.textContent = metrics?.tm_score != null ? metrics.tm_score.toFixed(3) : '--';

            const gdtCell = document.createElement('td');
            gdtCell.className = "py-1 text-primary";
            gdtCell.textContent = metrics?.gdt_ts != null ? metrics.gdt_ts.toFixed(3) : '--';

            row.appendChild(idCell);
            row.appendChild(tmCell);
            row.appendChild(gdtCell);
            qualityBody.appendChild(row);
        });
    }

    renderRmsfChart() {
        const rmsfDiv = this.element.querySelector('#rmsf-plotly-chart');
        if (!this.rmsfValues?.length) {
            if (this.currentRunId) {
                rmsfDiv.innerHTML = `
                    <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                        No residue fluctuation data available.
                    </div>
                `;
            }
            return;
        }

        rmsfDiv.innerHTML = "";

        // X-axis: 1-indexed positions
        const xData = Array.from({ length: this.rmsfValues.length }, (_, i) => i + 1);

        const trace = {
            x: xData,
            y: this.rmsfValues,
            type: 'scatter',
            mode: 'lines',
            line: {
                color: '#E2846A',
                width: 2.5,
                shape: 'spline'
            },
            fill: 'tozeroy',
            fillcolor: 'rgba(226, 132, 106, 0.1)',
            hoverinfo: 'x+y',
            name: 'RMSF'
        };

        const layout = {
            xaxis: {
                title: 'Alignment Position',
                gridcolor: '#2C2620',
                zeroline: false
            },
            yaxis: {
                title: 'RMSF (Å)',
                gridcolor: '#2C2620',
                zeroline: false
            },
            margin: { l: 50, r: 20, t: 20, b: 40 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            height: 280,
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" }
        };

        Plotly.newPlot(rmsfDiv, [trace], layout, { responsive: true, displayModeBar: false });
    }

    renderRmsdHeatmap() {
        const heatmapDiv = this.element.querySelector('#rmsd-plotly-heatmap');
        if (!this.heatmapFig?.data) {
            if (this.currentRunId) {
                heatmapDiv.innerHTML = `
                    <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                        No pairwise heatmap figure available.
                    </div>
                `;
            }
            return;
        }

        heatmapDiv.innerHTML = "";
        const layout = {
            ...this.heatmapFig.layout,
            width: undefined, // Responsive
            height: 280,
            margin: { l: 50, r: 20, t: 30, b: 50 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" }
        };
        Plotly.newPlot(heatmapDiv, this.heatmapFig.data, layout, { responsive: true, displayModeBar: false });
    }

    // Contact map / difference-distance controls are only meaningful once
    // there's a real completed run (>=2 structures) to fetch them from -
    // repopulated on every renderVisuals() call, preserving the previously
    // selected structure(s) where they're still valid, same pattern as
    // populateAnnotationsPicker().
    // Shared option-population logic for the app's several "pick a
    // workspace structure" selects: preserves the previously selected
    // value when it's still valid, and falls back to an explicit
    // "Select a structure" placeholder only when the given candidate
    // list is genuinely empty - otherwise behaves exactly like the old
    // per-caller duplicated version (auto-defaults to the first real
    // option via normal <select> behavior).
    _populateStructureOptions(select, structures) {
        const previousValue = select.value;
        select.innerHTML = "";
        if (structures.length === 0) {
            const placeholder = document.createElement('option');
            placeholder.value = "";
            placeholder.textContent = "Select a structure";
            select.appendChild(placeholder);
        }
        structures.forEach(({ pdbId }) => {
            const opt = document.createElement('option');
            opt.value = pdbId;
            opt.textContent = pdbId;
            select.appendChild(opt);
        });
        if (structures.some(s => s.pdbId === previousValue)) {
            select.value = previousValue;
        }
    }

    populateContactMapSelectors() {
        const singleSelects = [this.element.querySelector('#contact-map-pdb-select')];
        const pairSelects = [
            this.element.querySelector('#diff-distance-pdb-a-select'),
            this.element.querySelector('#diff-distance-pdb-b-select'),
        ];

        [...singleSelects, ...pairSelects].forEach(select => this._populateStructureOptions(select, this.structures));
        if (pairSelects[1] && this.structures.length > 1 && pairSelects[0].value === pairSelects[1].value) {
            pairSelects[1].value = this.structures[1].pdbId;
        }
        this.updateContactMapButtonStates();
    }

    // Keeps the Load/Compare buttons disabled while their paired select(s)
    // are still on the "Select a structure" placeholder, rather than
    // letting a click silently no-op against an empty pdbId.
    updateContactMapButtonStates() {
        const contactSelect = this.element.querySelector('#contact-map-pdb-select');
        const contactBtn = this.element.querySelector('#contact-map-load-btn');
        if (contactBtn) contactBtn.disabled = !contactSelect.value;

        const diffA = this.element.querySelector('#diff-distance-pdb-a-select').value;
        const diffB = this.element.querySelector('#diff-distance-pdb-b-select').value;
        const diffBtn = this.element.querySelector('#diff-distance-load-btn');
        if (diffBtn) diffBtn.disabled = !diffA || !diffB;
    }

    // PAE only exists for AlphaFold-sourced structures (see
    // AnnotationAggregator.fetch_predicted_aligned_error) - the workspace
    // ID format ("AF-{UniProt}-F{fragment}") is enough to tell without
    // needing each structure's source database passed down separately.
    populatePaeSelector() {
        const select = this.element.querySelector('#pae-pdb-select');
        const afStructures = this.structures.filter(({ pdbId }) => pdbId.toUpperCase().startsWith('AF-'));
        this._populateStructureOptions(select, afStructures);
        const btn = this.element.querySelector('#pae-load-btn');
        if (btn) btn.disabled = !select.value;
    }

    async loadPae() {
        const pdbId = this.element.querySelector('#pae-pdb-select').value;
        const div = this.element.querySelector('#pae-plotly');
        if (!pdbId) return;

        div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading PAE&hellip;</div>`;
        try {
            const data = await fetchPae(pdbId);
            this.renderPaeHeatmap(data);
        } catch (err) {
            console.error("Failed to load PAE:", err);
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">No PAE data available for this structure.</div>`;
        }
    }

    renderPaeHeatmap(data) {
        const div = this.element.querySelector('#pae-plotly');
        if (!div) return;

        div.innerHTML = "";
        const trace = {
            z: data.pae,
            type: 'heatmap',
            // PAE is an error metric in Angstroms - low (blue) is
            // confident, high (red) is not, the reverse sense of a
            // similarity/contact heatmap's colorscale.
            colorscale: [[0, '#3E5C9A'], [0.5, '#C9A063'], [1, '#B23A3A']],
            showscale: true,
        };
        const layout = {
            height: 240,
            margin: { l: 40, r: 10, t: 10, b: 30 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" },
            yaxis: { autorange: 'reversed' },
        };
        Plotly.newPlot(div, [trace], layout, { responsive: true, displayModeBar: false });
    }

    // Unlike PAE (AlphaFold-only), GNM flexibility works for any structure
    // source - no external API, just this structure's own coordinates
    // (see flexibility_calculator.calculate_gnm_flexibility) - so every
    // loaded structure is selectable here.
    populateFlexibilitySelector() {
        const select = this.element.querySelector('#flexibility-pdb-select');
        this._populateStructureOptions(select, this.structures);
        const btn = this.element.querySelector('#flexibility-load-btn');
        if (btn) btn.disabled = !select.value;
    }

    async loadFlexibility() {
        const pdbId = this.element.querySelector('#flexibility-pdb-select').value;
        const div = this.element.querySelector('#flexibility-plotly');
        if (!pdbId) return;

        div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading flexibility prediction&hellip;</div>`;
        try {
            const data = await fetchFlexibility(pdbId, this.currentRunId);
            this.renderFlexibilityChart(data.flexibility);
        } catch (err) {
            console.error("Failed to load flexibility prediction:", err);
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">${err.message || 'No flexibility prediction available for this structure.'}</div>`;
        }
    }

    renderFlexibilityChart(flexibility) {
        const div = this.element.querySelector('#flexibility-plotly');
        if (!div) return;

        div.innerHTML = "";
        const traces = [{
            x: flexibility.residue_numbers,
            y: flexibility.flexibility,
            type: 'scatter',
            mode: 'lines',
            name: 'Predicted flexibility (GNM)',
            line: { color: '#8B5CF6' },
        }];
        // A real crystallographic B-factor, when present, is plotted
        // alongside the prediction as a free sanity comparison - not
        // claimed to be the same measurement, just a real-world reference
        // point on the same chart.
        if (flexibility.b_factor) {
            traces.push({
                x: flexibility.residue_numbers,
                y: flexibility.b_factor,
                type: 'scatter',
                mode: 'lines',
                name: 'Real B-factor',
                yaxis: 'y2',
                line: { color: '#F59E0B', dash: 'dot' },
            });
        }
        const layout = {
            height: 240,
            margin: { l: 40, r: flexibility.b_factor ? 40 : 10, t: 10, b: 30 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" },
            xaxis: { title: 'Residue' },
            yaxis: { title: 'Predicted flexibility (0-1)' },
            yaxis2: flexibility.b_factor ? { title: 'B-factor', overlaying: 'y', side: 'right' } : undefined,
            showlegend: !!flexibility.b_factor,
            legend: { orientation: 'h', y: -0.3 },
        };
        Plotly.newPlot(div, traces, layout, { responsive: true, displayModeBar: false });
    }

    // Same picker-population pattern as populateContactMapSelectors, for
    // the "describe the difference between two structures" narrative
    // below - reuses data already loaded into this tab (heatmapFig,
    // tmScoreMatrix), no new fetch needed.
    populateDiffNarrativeSelectors() {
        const selects = [
            this.element.querySelector('#diff-narrative-pdb-a-select'),
            this.element.querySelector('#diff-narrative-pdb-b-select'),
        ];
        selects.forEach(select => this._populateStructureOptions(select, this.structures));
        if (this.structures.length > 1 && selects[0].value === selects[1].value) {
            selects[1].value = this.structures[1].pdbId;
        }
        const btn = this.element.querySelector('#diff-narrative-load-btn');
        if (btn) btn.disabled = !selects[0].value || !selects[1].value;
    }

    // Looks up the real RMSD value for a structure pair out of the same
    // Plotly heatmap trace already rendered above (server-built via
    // rmsd_analyzer.generate_plotly_heatmap - z/x/y arrays, not a
    // separate fetch).
    _rmsdFor(pdbIdA, pdbIdB) {
        const trace = this.heatmapFig?.data?.[0];
        if (!trace?.z || !trace?.x || !trace?.y) return null;
        const rowIdx = trace.y.indexOf(pdbIdA);
        const colIdx = trace.x.indexOf(pdbIdB);
        if (rowIdx === -1 || colIdx === -1) return null;
        const value = trace.z[rowIdx]?.[colIdx];
        return typeof value === 'number' ? value : null;
    }

    // Independent tmtools-computed pairwise TM-score (tmScoreMatrix), not
    // the Mustang-column-based per-structure score in qualityMetrics.
    _tmScoreFor(pdbIdA, pdbIdB) {
        const matrix = this.tmScoreMatrix;
        if (!matrix?.data || !matrix?.index || !matrix?.columns) return null;
        const rowIdx = matrix.index.indexOf(pdbIdA);
        const colIdx = matrix.columns.indexOf(pdbIdB);
        if (rowIdx === -1 || colIdx === -1) return null;
        const value = matrix.data[rowIdx]?.[colIdx];
        return typeof value === 'number' ? value : null;
    }

    describeStructureDiff() {
        const pdbIdA = this.element.querySelector('#diff-narrative-pdb-a-select').value;
        const pdbIdB = this.element.querySelector('#diff-narrative-pdb-b-select').value;
        const textEl = this.element.querySelector('#diff-narrative-text');
        if (!textEl) return;

        if (!pdbIdA || !pdbIdB || pdbIdA === pdbIdB) {
            textEl.textContent = "Select two different structures to compare.";
            return;
        }

        const rmsd = this._rmsdFor(pdbIdA, pdbIdB);
        if (rmsd === null) {
            textEl.textContent = "No RMSD data available for this pair yet - run alignment first.";
            return;
        }

        let rmsdSentence;
        if (rmsd < 2.0) {
            rmsdSentence = `${pdbIdA} and ${pdbIdB} are structurally very similar (${rmsd.toFixed(2)} Å RMSD).`;
        } else if (rmsd <= 5.0) {
            rmsdSentence = `${pdbIdA} and ${pdbIdB} show moderate structural divergence (${rmsd.toFixed(2)} Å RMSD).`;
        } else {
            rmsdSentence = `${pdbIdA} and ${pdbIdB} are substantially different in shape (${rmsd.toFixed(2)} Å RMSD).`;
        }

        const tmScore = this._tmScoreFor(pdbIdA, pdbIdB);
        let tmSentence = "";
        if (tmScore !== null) {
            // Standard TM-score interpretation cutoffs (Zhang & Skolnick):
            // >0.5 indicates the same fold; below that, likely different folds.
            if (tmScore > 0.9) {
                tmSentence = ` Their independent TM-score of ${tmScore.toFixed(3)} confirms the same fold with high confidence.`;
            } else if (tmScore >= 0.5) {
                tmSentence = ` Their independent TM-score of ${tmScore.toFixed(3)} still indicates the same overall fold.`;
            } else {
                tmSentence = ` Their independent TM-score of ${tmScore.toFixed(3)} suggests these may not share the same fold at all, despite the RMSD above.`;
            }
        }

        textEl.textContent = rmsdSentence + tmSentence;
    }

    async loadContactMap() {
        const pdbId = this.element.querySelector('#contact-map-pdb-select').value;
        const div = this.element.querySelector('#contact-map-plotly');
        if (!this.currentRunId || !pdbId) return;

        div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading contact map&hellip;</div>`;
        try {
            const data = await fetchContactMap(this.currentRunId, pdbId);
            this.renderContactMapHeatmap(data);
        } catch (err) {
            console.error("Failed to load contact map:", err);
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Failed to load contact map.</div>`;
        }
    }

    renderContactMapHeatmap(data) {
        const div = this.element.querySelector('#contact-map-plotly');
        if (!div) return;

        if (data.capped) {
            div.innerHTML = `
                <div class="flex items-center justify-center h-full text-secondary font-body-sm text-center px-4">
                    ${data.residue_count} residues exceeds the dense-matrix cap - ${data.contacts.length} contacts found, too sparse to render as a heatmap here.
                </div>
            `;
            return;
        }

        div.innerHTML = "";
        const trace = {
            z: data.matrix,
            type: 'heatmap',
            colorscale: [[0, 'rgba(0,0,0,0)'], [1, '#C9A063']],
            showscale: false,
        };
        const layout = {
            height: 240,
            margin: { l: 40, r: 10, t: 10, b: 30 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" },
            yaxis: { autorange: 'reversed' },
        };
        Plotly.newPlot(div, [trace], layout, { responsive: true, displayModeBar: false });
    }

    async loadDifferenceDistance() {
        const pdbIdA = this.element.querySelector('#diff-distance-pdb-a-select').value;
        const pdbIdB = this.element.querySelector('#diff-distance-pdb-b-select').value;
        const div = this.element.querySelector('#diff-distance-plotly');
        if (!this.currentRunId || !pdbIdA || !pdbIdB) return;

        if (pdbIdA === pdbIdB) {
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Select two different structures.</div>`;
            return;
        }

        div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Loading difference-distance matrix&hellip;</div>`;
        try {
            const data = await fetchDifferenceDistance(this.currentRunId, pdbIdA, pdbIdB);
            this.renderDifferenceDistanceHeatmap(data);
        } catch (err) {
            console.error("Failed to load difference-distance matrix:", err);
            div.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Failed to load difference-distance matrix.</div>`;
        }
    }

    renderDifferenceDistanceHeatmap(data) {
        const div = this.element.querySelector('#diff-distance-plotly');
        if (!div) return;

        if (data.capped) {
            div.innerHTML = `
                <div class="flex items-center justify-center h-full text-secondary font-body-sm text-center px-4">
                    ${data.column_count} aligned columns exceeds the dense-matrix cap - ${data.differences.length} notable shifts (&gt;3&Aring;) found, too sparse to render as a heatmap here.
                </div>
            `;
            return;
        }

        div.innerHTML = "";
        const trace = {
            z: data.matrix,
            type: 'heatmap',
            colorscale: 'YlOrRd',
        };
        const layout = {
            height: 240,
            margin: { l: 40, r: 10, t: 10, b: 30 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" },
            yaxis: { autorange: 'reversed' },
        };
        Plotly.newPlot(div, [trace], layout, { responsive: true, displayModeBar: false });
    }

    renderPhyloTree() {
        const treeDiv = this.element.querySelector('#phylo-plotly-tree');
        if (!this.treeFig?.data) {
            if (this.currentRunId) {
                treeDiv.innerHTML = `
                    <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                        No phylogenetic tree figure available.
                    </div>
                `;
            }
            return;
        }

        treeDiv.innerHTML = "";
        const layout = {
            ...this.treeFig.layout,
            width: undefined, // Responsive
            height: 280,
            margin: { l: 60, r: 20, t: 30, b: 40 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" }
        };
        Plotly.newPlot(treeDiv, this.treeFig.data, layout, { responsive: true, displayModeBar: false });
    }

    renderInsightsList() {
        const insightsList = this.element.querySelector('#analytics-insights-list');
        const insightsEmpty = this.element.querySelector('#analytics-insights-empty');
        insightsList.innerHTML = "";

        if (this.insights?.length > 0) {
            insightsEmpty.classList.add('hidden');
            this.insights.forEach(rawText => {
                const { icon, text } = splitInsightIcon(rawText);
                const li = document.createElement('li');
                li.className = "font-body-sm text-primary border border-border-subtle rounded-md p-2 flex items-start gap-2";
                const iconSvg = icon ? createInsightIconSvg(icon) : null;
                if (iconSvg) {
                    iconSvg.classList.add('text-accent', 'shrink-0', 'mt-0.5');
                    li.appendChild(iconSvg);
                }
                const textSpan = document.createElement('span');
                appendMarkdownLiteBold(textSpan, text);
                li.appendChild(textSpan);
                insightsList.appendChild(li);
            });
        } else if (this.currentRunId) {
            insightsEmpty.textContent = "No automated insights available for this run.";
            insightsEmpty.classList.remove('hidden');
        } else {
            insightsEmpty.textContent = "Run alignment to display automated insights.";
            insightsEmpty.classList.remove('hidden');
        }
    }
}
