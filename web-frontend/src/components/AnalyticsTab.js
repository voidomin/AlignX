import { fetchAnnotations } from '../api';
import { renderDomainList, renderGoTermList } from '../utils/annotationRenderers';

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

const SUB_TABS = [
    { key: 'quality', label: 'Quality' },
    { key: 'rmsf', label: 'RMSF' },
    { key: 'rmsd', label: 'RMSD Matrix' },
    { key: 'phylo', label: 'Phylogeny' },
    { key: 'insights', label: 'Insights' },
    { key: 'annotations', label: 'Annotations' },
];

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
                <div id="analytics-subtab-strip" class="flex gap-1 border border-border rounded-md p-1 shrink-0">
                    ${SUB_TABS.map(t => `
                        <button data-subtab="${t.key}" class="analytics-subtab-btn flex-1 py-1.5 rounded-md font-label-md text-label-md transition-colors">${t.label}</button>
                    `).join('')}
                </div>

                <!-- Ramachandran / Quality Report -->
                <div data-panel="quality" class="flex flex-col gap-4 shrink-0">
                    <div class="grid grid-cols-2 gap-6">
                        <div class="stat-row stat-primary">
                            <span class="stat-key">Ramachandran score</span>
                            <span id="ramachandran-score" class="stat-value">--</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-key">Outlier residues</span>
                            <span id="ramachandran-outliers" class="stat-value">--</span>
                        </div>
                    </div>
                    <div id="ramachandran-outliers-list-card" class="flex flex-col gap-2 hidden">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Top outliers</span>
                        <div id="ramachandran-outliers-list" class="flex flex-wrap gap-1.5">
                            <!-- Outlier chips -->
                        </div>
                    </div>
                    <div id="quality-metrics-table-card" class="flex flex-col gap-2 hidden">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Alignment quality (TM-score / GDT-TS)</span>
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
                    <div id="secondary-structure-card" class="flex flex-col gap-2 hidden">
                        <span class="font-label-sm text-label-sm text-secondary uppercase">Secondary structure (backbone-torsion approximation, not DSSP)</span>
                        <div class="grid grid-cols-3 gap-4">
                            <div class="stat-row"><span class="stat-key">Helix</span><span id="ss-helix-percent" class="stat-value">--</span></div>
                            <div class="stat-row"><span class="stat-key">Sheet</span><span id="ss-sheet-percent" class="stat-value">--</span></div>
                            <div class="stat-row"><span class="stat-key">Coil</span><span id="ss-coil-percent" class="stat-value">--</span></div>
                        </div>
                    </div>
                    <div id="pairwise-tm-score-card" class="flex flex-col gap-2 hidden">
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
                <div data-panel="rmsd" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <div id="rmsd-plotly-heatmap" class="w-full h-[280px]">
                        <div class="flex items-center justify-center h-full text-secondary font-body-sm">
                            Run alignment to display interactive heatmap.
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
                <div data-panel="insights" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px]">
                    <ul id="analytics-insights-list" class="flex flex-col gap-2"></ul>
                    <div id="analytics-insights-empty" class="flex items-center justify-center h-full text-secondary font-body-sm">
                        Run alignment to display automated insights.
                    </div>
                </div>

                <!-- Functional Annotation (InterPro domains / GO terms / Reactome pathways) -->
                <div data-panel="annotations" class="border border-border rounded-lg p-4 shrink-0 min-h-[320px] flex flex-col gap-4">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Functional annotation</span>
                        <select id="annotations-structure-select" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[160px]"></select>
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
                </div>
            </div>
        `;

        this.element = div;
        this.setupSubTabs();
        this.setupAnnotationsPicker();
        this.renderVisuals();
        return div;
    }

    setupSubTabs() {
        this.element.querySelectorAll('.analytics-subtab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchSubTab(btn.dataset.subtab));
        });
        this.updateSubTabView();
    }

    setupAnnotationsPicker() {
        const select = this.element.querySelector('#annotations-structure-select');
        select.addEventListener('change', () => this.renderAnnotationsPanel());
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
            content.innerHTML = `<div class="flex items-center justify-center h-full text-secondary font-body-sm">Add a structure to display functional annotation.</div>`;
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
        } else if (!annotation.domains?.length && !annotation.go_terms?.length && !annotation.reactome_pathways?.length) {
            content.innerHTML = `<div class="font-body-sm text-secondary py-4">Resolved to UniProt ${annotation.accession}, but no curated domains, GO terms, or pathways were found.</div>`;
        } else {
            content.innerHTML = `
                <div class="font-body-sm text-secondary">Resolved to UniProt <span class="font-mono text-primary">${annotation.accession}</span></div>
                ${renderDomainList(annotation.domains)}
                ${renderGoTermList(annotation.go_terms)}
                ${this.renderReactomePathways(annotation.reactome_pathways)}
            `;
            content.querySelectorAll('.domain-highlight-btn').forEach(btn => {
                const domain = annotation.domains[Number(btn.dataset.domainIndex)];
                if (domain?.highlight_chains) {
                    btn.addEventListener('click', () => this.onHighlightResidues(domain.highlight_chains));
                }
            });
        }

        this.renderSharedAnnotations(sharedSection, sharedContent);
    }

    renderReactomePathways(pathways) {
        if (!pathways?.length) return '';
        return `
            <div class="flex flex-col gap-2">
                <span class="eyebrow">Reactome pathways</span>
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
                <td class="py-1 font-mono">${r.a} &harr; ${r.b}</td>
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
            idCell.textContent = pdbId;

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
            this.insights.forEach(text => {
                const li = document.createElement('li');
                li.className = "font-body-sm text-primary border border-border-subtle rounded-md p-2";
                appendMarkdownLiteBold(li, text);
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
