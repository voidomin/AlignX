import { fetchSuggestions, isValidPdbId, fetchValidation, fetchQc, fetchCathClassification } from '../api';
import { escapeHtml } from '../escapeHtml';
import { QUICK_START_EXAMPLES } from '../quickStartExamples';
import { DiscoveryPanel } from './DiscoveryPanel';

const SOURCE_LABELS = {
    pdb: 'PDB',
    alphafold: 'AlphaFold',
    swissmodel: 'SWISS-MODEL',
    esmfold: 'ESMFold',
    upload: 'Uploaded',
};

// The single merged "add structures, then see what you can do with them"
// tab - replaces the old Overview (2+, Mustang alignment) and Discover
// (exactly 1, Foldseek function inference) split. Add any number of
// structures from any source; each gets its own "What is this?" action
// (DiscoveryPanel, works at any N - Foldseek has no gating on workspace
// size), and Run Structural Alignment lights up once there are 2+ (the
// one genuinely N>=2-only backend requirement here).
export class WorkspaceTab {
    constructor(props) {
        this.selectedPDBs = props.selectedPDBs || [];
        this.chainSelections = props.chainSelections || {};
        this.pdbMetadata = props.pdbMetadata || {};
        this.onAddPDB = props.onAddPDB;
        this.onAddManyPDBs = props.onAddManyPDBs;
        this.onUploadStructure = props.onUploadStructure;
        this.onRemovePDB = props.onRemovePDB;
        this.onChainSelection = props.onChainSelection;
        this.onRunAlignment = props.onRunAlignment;
        this.onQuickStart = props.onQuickStart;
        this.element = null;
        this.isLoadingChains = false;
        this.isUploading = false;
        this.suggestTimeout = null;
        this.batchInputVisible = false;
        this.discoveryPanelVisible = false;
        this.discoveryPanel = new DiscoveryPanel({
            onClose: () => this.hideDiscoveryPanel(),
        });
        // wwPDB validation is only meaningful for real, experimentally-
        // solved PDB entries (AlphaFold/SWISS-MODEL/ESMFold have no
        // validation report) - fetched lazily per structure card, cached
        // so switching tabs and back doesn't re-fetch. undefined = not
        // yet fetched, null = fetched but no report available.
        this.validationCache = {};
        this._validationLoading = new Set();
        // CATH fold classification is only meaningful for real PDB entries
        // too - same lazy-per-card fetch/cache shape as validation above.
        this.cathCache = {};
        this._cathLoading = new Set();
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-workspace-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Workspace</span>
                    <h2 class="section-title">Structures &amp; parameters</h2>
                </div>
                <span id="workspace-pdb-count-badge" class="font-label-sm text-label-sm text-secondary">0 Proteins</span>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div class="flex flex-col gap-3">
                    <div class="flex gap-2 relative">
                        <input id="workspace-add-pdb-input" type="text" placeholder="PDB ID, or AF- / SM- / ESM- accession" class="flex-grow bg-surface-raised border border-border rounded-md px-3 py-1.5 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase" autocomplete="off"/>
                        <button id="workspace-add-pdb-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add</button>
                    </div>
                    <div id="workspace-add-pdb-suggestions" class="flex gap-2"></div>

                    <div class="flex items-center gap-4">
                        <button id="workspace-toggle-batch-add-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Paste multiple IDs</button>
                        <button id="workspace-upload-structure-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Upload a structure file</button>
                        <input id="workspace-upload-structure-input" type="file" accept=".pdb,.ent,.cif" class="hidden"/>
                    </div>
                    <span id="workspace-upload-structure-feedback" class="font-body-sm text-[11px] text-secondary"></span>

                    <div id="workspace-batch-add-container" class="flex flex-col gap-2 ${this.batchInputVisible ? '' : 'hidden'}">
                        <textarea id="workspace-batch-pdb-input" rows="3" placeholder="Paste PDB IDs or accessions, separated by commas, spaces, or new lines (e.g. 4RLT, 3UG9, AF-P69905-F1)" class="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase"></textarea>
                        <div class="flex items-center gap-3">
                            <button id="workspace-batch-add-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add All</button>
                            <span id="workspace-batch-add-feedback" class="font-body-sm text-[11px] text-secondary"></span>
                        </div>
                    </div>

                    <div id="workspace-pdb-list-container" class="flex flex-col gap-2 mt-1">
                        <!-- Dynamic list of PDBs with chain dropdowns -->
                    </div>

                    <div class="flex flex-col gap-2">
                        <button id="workspace-run-qc-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Run QC on all</button>
                        <div id="workspace-qc-summary" class="hidden flex-col gap-2"></div>
                    </div>

                    <div id="workspace-discovery-panel-slot" class="${this.discoveryPanelVisible ? '' : 'hidden'}"></div>
                </div>

                <div class="flex flex-col gap-3 border-t border-border pt-6">
                    <span class="eyebrow">Parameters</span>
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-water" type="checkbox" checked class="rounded border-border bg-surface-raised text-accent focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-secondary group-hover:text-primary transition-colors">Filter water molecules (HOH)</span>
                    </label>
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-heteroatoms" type="checkbox" checked class="rounded border-border bg-surface-raised text-accent focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-secondary group-hover:text-primary transition-colors">Exclude non-ligand heteroatoms</span>
                    </label>
                </div>

                <button id="workspace-run-btn" class="btn-primary-hard w-full py-3 rounded-sm font-label-md text-label-md flex justify-center items-center gap-2">
                    <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                    Run Structural Alignment
                </button>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        this.refreshPDBList();

        if (this.discoveryPanelVisible) {
            this.element.querySelector('#workspace-discovery-panel-slot').appendChild(this.discoveryPanel.render());
        }
        return div;
    }

    setupEventListeners() {
        const addBtn = this.element.querySelector('#workspace-add-pdb-btn');
        const addInput = this.element.querySelector('#workspace-add-pdb-input');
        const runBtn = this.element.querySelector('#workspace-run-btn');
        const suggestionsContainer = this.element.querySelector('#workspace-add-pdb-suggestions');

        const renderSuggestions = (list) => {
            suggestionsContainer.innerHTML = "";
            const items = (list && list.length > 0) ? list.slice(0, 4) : [];
            items.forEach(item => {
                const span = document.createElement('span');
                span.className = "px-1.5 py-0.5 rounded-md bg-surface-raised border border-border-subtle font-label-sm text-label-sm text-secondary cursor-pointer hover:text-primary transition-colors";
                span.innerText = item;
                span.addEventListener('click', () => {
                    this.onAddPDB(item);
                    addInput.value = "";
                    renderSuggestions([]);
                });
                suggestionsContainer.appendChild(span);
            });
        };

        addInput.addEventListener('input', () => {
            clearTimeout(this.suggestTimeout);
            const q = addInput.value.trim();
            if (q.length < 1) {
                renderSuggestions([]);
                return;
            }
            this.suggestTimeout = setTimeout(async () => {
                try {
                    const data = await fetchSuggestions(q);
                    renderSuggestions(data.suggestions);
                } catch (err) {
                    console.error("Autocomplete suggestions failed:", err);
                }
            }, 300);
        });

        addBtn.addEventListener('click', () => {
            const val = addInput.value.trim().toUpperCase();
            if (isValidPdbId(val)) {
                this.onAddPDB(val);
                addInput.value = "";
                renderSuggestions([]);
            }
        });

        addInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const val = addInput.value.trim().toUpperCase();
                if (isValidPdbId(val)) {
                    this.onAddPDB(val);
                    addInput.value = "";
                    renderSuggestions([]);
                }
            }
        });

        runBtn.addEventListener('click', () => {
            if (this.selectedPDBs.length < 2) return;
            this.onRunAlignment();
        });

        this.element.querySelector('#workspace-run-qc-btn').addEventListener('click', () => this.runQcOnAll());

        const toggleBatchBtn = this.element.querySelector('#workspace-toggle-batch-add-btn');
        const batchContainer = this.element.querySelector('#workspace-batch-add-container');
        const batchInput = this.element.querySelector('#workspace-batch-pdb-input');
        const batchAddBtn = this.element.querySelector('#workspace-batch-add-btn');
        const batchFeedback = this.element.querySelector('#workspace-batch-add-feedback');

        toggleBatchBtn.addEventListener('click', () => {
            this.batchInputVisible = !this.batchInputVisible;
            batchContainer.classList.toggle('hidden', !this.batchInputVisible);
            if (this.batchInputVisible) batchInput.focus();
        });

        batchAddBtn.addEventListener('click', async () => {
            const raw = batchInput.value;
            const tokens = raw.split(/[\s,]+/).map(t => t.trim().toUpperCase()).filter(Boolean);

            const toAdd = [];
            const invalid = [];
            let duplicates = 0;
            const seen = new Set(this.selectedPDBs);

            tokens.forEach(token => {
                if (!isValidPdbId(token)) {
                    invalid.push(token);
                    return;
                }
                if (seen.has(token)) {
                    duplicates += 1;
                    return;
                }
                seen.add(token);
                toAdd.push(token);
            });

            let overCap = 0;
            let addedCount = 0;
            if (toAdd.length > 0) {
                const result = await this.onAddManyPDBs(toAdd);
                addedCount = result?.added ? result.added.length : toAdd.length;
                overCap = result?.overCap || 0;
            }

            const parts = [];
            if (addedCount > 0) parts.push(`Added ${addedCount}.`);
            if (duplicates > 0) parts.push(`Skipped ${duplicates} already in the workspace.`);
            if (invalid.length > 0) parts.push(`Couldn't recognize: ${invalid.join(', ')}.`);
            if (overCap > 0) parts.push(`Skipped ${overCap} — workspace limit is 20 structures.`);
            if (parts.length === 0) parts.push('Nothing to add — paste at least one ID.');
            batchFeedback.innerText = parts.join(' ');

            if (addedCount > 0) batchInput.value = "";
        });

        const uploadBtn = this.element.querySelector('#workspace-upload-structure-btn');
        const uploadInput = this.element.querySelector('#workspace-upload-structure-input');
        const uploadFeedback = this.element.querySelector('#workspace-upload-structure-feedback');

        uploadBtn.addEventListener('click', () => uploadInput.click());

        uploadInput.addEventListener('change', async () => {
            const file = uploadInput.files?.[0];
            uploadInput.value = ""; // allow re-selecting the same file later
            if (!file) return;

            this.isUploading = true;
            uploadFeedback.innerText = `Uploading ${file.name}...`;
            try {
                await this.onUploadStructure(file);
                uploadFeedback.innerText = `Added ${file.name}.`;
            } catch (err) {
                uploadFeedback.innerText = err.message || `Upload of ${file.name} failed.`;
            } finally {
                this.isUploading = false;
            }
        });
    }

    updateState(selectedPDBs, chainSelections, pdbMetadata) {
        this.selectedPDBs = selectedPDBs;
        this.chainSelections = chainSelections;
        this.pdbMetadata = pdbMetadata;
        // A removed/replaced structure invalidates whatever the Discovery
        // panel is showing - rather than leave it displaying results for a
        // structure no longer in the workspace, close it.
        if (this.discoveryPanelVisible && !this.selectedPDBs.includes(this.discoveryPanel.pdbId)) {
            this.hideDiscoveryPanel();
        }
        this.refreshPDBList();
    }

    setLoadingChains(isLoading) {
        this.isLoadingChains = isLoading;
        this.refreshPDBList();

        // Guard against submitting an alignment while a just-added structure's
        // chain selection hasn't resolved yet, which would silently persist
        // an incomplete chain_selection for that run.
        const runBtn = this.element?.querySelector('#workspace-run-btn');
        if (runBtn) runBtn.disabled = isLoading;
    }

    showDiscoveryPanel(pdbId) {
        this.discoveryPanelVisible = true;
        const slot = this.element.querySelector('#workspace-discovery-panel-slot');
        slot.classList.remove('hidden');
        slot.innerHTML = '';
        slot.appendChild(this.discoveryPanel.render());
        this.discoveryPanel.runFor(pdbId);
    }

    // Reopens a Discover run loaded from the Dashboard/History tab - hands
    // the saved result straight to the panel instead of re-running Foldseek.
    showSavedDiscoveryResults(results) {
        this.discoveryPanelVisible = true;
        if (!this.element) return;
        const slot = this.element.querySelector('#workspace-discovery-panel-slot');
        slot.classList.remove('hidden');
        slot.innerHTML = '';
        slot.appendChild(this.discoveryPanel.render());
        this.discoveryPanel.loadSavedResults(results);
    }

    hideDiscoveryPanel() {
        this.discoveryPanelVisible = false;
        const slot = this.element?.querySelector('#workspace-discovery-panel-slot');
        if (slot) {
            slot.classList.add('hidden');
            slot.innerHTML = '';
        }
    }

    refreshPDBList() {
        if (!this.element) return;

        const badge = this.element.querySelector('#workspace-pdb-count-badge');
        badge.innerText = `${this.selectedPDBs.length} Protein${this.selectedPDBs.length !== 1 ? 's' : ''}`;

        const runBtn = this.element.querySelector('#workspace-run-btn');
        if (runBtn) runBtn.classList.toggle('hidden', this.selectedPDBs.length < 2);

        const container = this.element.querySelector('#workspace-pdb-list-container');
        if (this.isLoadingChains) {
            container.innerHTML = `
                <div class="flex items-center justify-center py-4 gap-2 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Loading structure chains...
                </div>
            `;
            return;
        }

        container.innerHTML = "";
        if (this.selectedPDBs.length === 0) {
            container.innerHTML = `
                <div class="flex flex-col items-center gap-3 py-4 text-center">
                    <span class="text-secondary font-body-sm">Add a structure to analyze it on its own, or 2+ to align them - or try an example:</span>
                    <div id="workspace-quick-start" class="flex flex-wrap justify-center gap-2"></div>
                </div>
            `;
            const quickStartContainer = container.querySelector('#workspace-quick-start');
            if (quickStartContainer && this.onQuickStart) {
                QUICK_START_EXAMPLES.forEach(ex => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = "quick-start-btn px-3 py-1.5 rounded-md bg-surface-raised border border-border-subtle font-label-sm text-label-sm text-secondary hover:text-primary transition-colors";
                    btn.textContent = `${ex.label} (${ex.pdbIds.join(' + ')})`;
                    btn.addEventListener('click', () => this.onQuickStart(ex.pdbIds));
                    quickStartContainer.appendChild(btn);
                });
            }
            return;
        }

        this.selectedPDBs.forEach(pid => this._renderPDBCard(pid, container));
    }

    _chainsOptionsHTML(pid, meta) {
        if (!meta?.chains) return `<option value="A">Chain A</option>`;
        return meta.chains
            .map(c => {
                const selectedAttr = (this.chainSelections[pid] === c.id) ? "selected" : "";
                return `<option value="${c.id}" ${selectedAttr}>Chain ${c.id} (${c.residue_count} residues)</option>`;
            })
            .join('');
    }

    // RCSB's primary-citation lookup - prefer a PubMed link when an ID is
    // present (more reliably resolvable than every DOI), fall back to the
    // DOI resolver otherwise. AlphaFold/SWISS-MODEL/ESMFold structures have
    // no citation concept, so meta has no `citation` field for those at all.
    _citationLinkHTML(meta) {
        if (!meta?.citation?.pubmed_id && !meta?.citation?.doi) return '';
        const citation = meta.citation;
        const href = citation.pubmed_id
            ? `https://pubmed.ncbi.nlm.nih.gov/${citation.pubmed_id}/`
            : `https://doi.org/${citation.doi}`;
        const label = citation.pubmed_id ? 'PubMed' : 'DOI';
        return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" class="pdb-citation-link font-body-sm text-[11px] text-accent hover:underline pl-0.5" title="${escapeHtml(citation.title || '')}">View publication (${label})</a>`;
    }

    _renderPDBCard(pid, container) {
        const meta = this.pdbMetadata[pid];
        const div = document.createElement('div');
        div.className = "flex flex-col gap-1.5 p-3 rounded-md bg-surface-raised border border-border-subtle";

        const chainsOptionsHTML = this._chainsOptionsHTML(pid, meta);

        const sourceLabel = SOURCE_LABELS[meta?.source] || 'PDB';
        const metaParts = meta
            ? [meta.method, meta.resolution, meta.organism].filter(v => v && v !== 'N/A')
            : [];
        if (meta?.source === 'upload' && meta.original_filename) {
            metaParts.push(escapeHtml(meta.original_filename));
        }

        // NMR ensembles only ever have model 1 analyzed (Mustang/RMSD/
        // ligand analysis all need one consistent conformer, not a
        // silently-arbitrary mix of several) - surfacing that plainly
        // beats leaving it invisible, which is what happened before.
        const gapChains = (meta?.chains || []).filter(c => c.gaps?.length > 0);
        const gapCount = gapChains.reduce((sum, c) => sum + c.gaps.length, 0);
        const gapTooltip = gapChains
            .flatMap(c => c.gaps.map(g => `Chain ${c.id}: residues ${g.after + 1}-${g.before - 1} missing`))
            .join('; ');
        const gapLabel = gapCount === 1 ? 'region' : 'regions';

        const citationLinkHTML = this._citationLinkHTML(meta);

        div.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="font-headline-sm text-body-md font-bold text-primary font-mono">${pid}</span>
                    <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase source-badge">${sourceLabel}</span>
                    <select class="bg-surface border border-border rounded-md px-2 py-1 text-body-sm text-secondary focus:outline-none focus:border-accent font-mono chain-select" data-pdb="${pid}">
                        ${chainsOptionsHTML}
                    </select>
                </div>
                <div class="flex items-center gap-1">
                    <button class="discover-structure-btn font-label-sm text-label-sm text-secondary hover:text-accent px-2 py-1 rounded-md hover:bg-surface transition-colors whitespace-nowrap" data-pdb="${pid}">What is this?</button>
                    <button class="text-error hover:text-red-400 p-1 rounded-md hover:bg-surface transition-colors remove-pdb-btn" data-pdb="${pid}">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                </div>
            </div>
            ${metaParts.length > 0 ? `<span class="pdb-meta-line font-body-sm text-[11px] text-secondary pl-0.5">${metaParts.join(' · ')}</span>` : ''}
            ${meta?.is_nmr ? `<span class="pdb-nmr-badge font-body-sm text-[11px] text-tertiary pl-0.5" title="Showing model 1 of ${meta.num_models} - other conformers in this NMR ensemble aren't analyzed.">NMR · ${meta.num_models} models (model 1 shown)</span>` : ''}
            ${gapCount > 0 ? `<span class="pdb-gaps-badge font-body-sm text-[11px] text-tertiary pl-0.5" title="${escapeHtml(gapTooltip)}">${gapCount} disordered ${gapLabel}</span>` : ''}
            ${meta?.source === 'pdb' ? `<span id="validation-badge-${pid}" class="pdb-validation-badge font-body-sm text-[11px] text-tertiary pl-0.5">${this._validationBadgeContent(pid)}</span>` : ''}
            ${meta?.source === 'pdb' ? `<span id="cath-badge-${pid}" class="pdb-cath-badge font-body-sm text-[11px] text-tertiary pl-0.5">${this._cathBadgeContent(pid)}</span>` : ''}
            ${citationLinkHTML}
        `;

        // Bind events
        div.querySelector('.chain-select').addEventListener('change', (e) => {
            this.onChainSelection(pid, e.target.value);
        });

        div.querySelector('.remove-pdb-btn').addEventListener('click', () => {
            this.onRemovePDB(pid);
        });

        div.querySelector('.discover-structure-btn').addEventListener('click', () => {
            this.showDiscoveryPanel(pid);
        });

        container.appendChild(div);

        if (meta?.source === 'pdb') {
            this._loadValidation(pid);
            this._loadCath(pid);
        }
    }

    _validationBadgeContent(pid) {
        const cached = this.validationCache[pid];
        if (cached === undefined) return 'Checking wwPDB validation…';
        if (!cached) return 'No wwPDB validation report available';

        const parts = [];
        if (cached.clashscore) {
            parts.push(`Clashscore ${cached.clashscore.value.toFixed(1)} (archive percentile ${Math.round(cached.clashscore.percentile_archive)})`);
        }
        if (cached.percent_rama_outliers) {
            parts.push(`Rama outliers ${cached.percent_rama_outliers.value.toFixed(1)}% (archive percentile ${Math.round(cached.percent_rama_outliers.percentile_archive)})`);
        }
        return parts.length > 0 ? parts.join(' · ') : 'No wwPDB validation report available';
    }

    // Fetched lazily per structure card (not part of the chain-metadata
    // round trip) and only for real PDB entries - re-rendering just this
    // one badge span in place once the fetch settles, not the whole list,
    // so an in-flight fetch for one card doesn't disturb the others.
    async _loadValidation(pid) {
        if (this.validationCache[pid] !== undefined || this._validationLoading.has(pid)) return;
        this._validationLoading.add(pid);
        try {
            const data = await fetchValidation(pid);
            this.validationCache[pid] = data.validation;
        } catch (err) {
            console.error('Failed to load wwPDB validation for', pid, err);
            this.validationCache[pid] = null;
        } finally {
            this._validationLoading.delete(pid);
        }
        const badge = this.element?.querySelector(`#validation-badge-${pid}`);
        if (badge) badge.textContent = this._validationBadgeContent(pid);
    }

    _cathBadgeContent(pid) {
        const cached = this.cathCache[pid];
        if (cached === undefined) return 'Checking CATH classification…';
        if (!cached || cached.length === 0) return 'No CATH classification available';

        const codes = [...new Set(cached.map(d => d.classification))];
        return codes.length > 1
            ? `CATH ${codes[0]} (+${codes.length - 1} more)`
            : `CATH ${codes[0]}`;
    }

    // Same lazy-per-card fetch/cache shape as _loadValidation - real CATH
    // fold classification only exists for real PDB entries.
    async _loadCath(pid) {
        if (this.cathCache[pid] !== undefined || this._cathLoading.has(pid)) return;
        this._cathLoading.add(pid);
        try {
            const data = await fetchCathClassification(pid);
            this.cathCache[pid] = data.domains;
        } catch (err) {
            console.error('Failed to load CATH classification for', pid, err);
            this.cathCache[pid] = null;
        } finally {
            this._cathLoading.delete(pid);
        }
        const badge = this.element?.querySelector(`#cath-badge-${pid}`);
        if (badge) badge.textContent = this._cathBadgeContent(pid);
    }

    // Generalizes the per-card wwPDB validation badge above (and the
    // Ramachandran/secondary-structure QC that's otherwise only ever
    // computed inside a completed alignment run) into a one-shot sweep
    // across every structure currently in the workspace, no alignment
    // required - see GET /api/qc.
    async runQcOnAll() {
        if (!this.element || this.selectedPDBs.length === 0) return;
        const btn = this.element.querySelector('#workspace-run-qc-btn');
        const summary = this.element.querySelector('#workspace-qc-summary');

        btn.disabled = true;
        summary.classList.remove('hidden');
        summary.classList.add('flex');
        summary.innerHTML = `<div class="font-body-sm text-[11px] text-secondary"><span class="animate-spin material-symbols-outlined text-[14px]">sync</span> Running QC on ${this.selectedPDBs.length} structure(s)…</div>`;

        const results = await Promise.all(
            this.selectedPDBs.map(async pid => {
                try {
                    return await fetchQc(pid);
                } catch (err) {
                    console.error('QC failed for', pid, err);
                    return { pdb_id: pid, error: true };
                }
            })
        );

        btn.disabled = false;
        this.renderQcSummary(results);
    }

    renderQcSummary(results) {
        const summary = this.element.querySelector('#workspace-qc-summary');
        summary.innerHTML = "";

        const table = document.createElement('table');
        table.className = "w-full text-left border-collapse";
        table.innerHTML = `
            <thead class="font-label-sm text-label-sm text-secondary">
                <tr>
                    <th class="px-0 py-1.5 border-b border-border font-medium">Structure</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Favored %</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Outliers</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Helix %</th>
                    <th class="px-3 py-1.5 border-b border-border font-medium text-right">Clashscore</th>
                </tr>
            </thead>
        `;
        const tbody = document.createElement('tbody');
        tbody.className = "font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle";

        results.forEach(r => {
            const tr = document.createElement('tr');
            if (r.error) {
                tr.innerHTML = `<td class="py-1.5">${escapeHtml(r.pdb_id)}</td><td class="px-3 py-1.5 text-secondary" colspan="4">QC failed for this structure.</td>`;
                tbody.appendChild(tr);
                return;
            }

            const rama = r.ramachandran_stats;
            const ss = r.secondary_structure_stats;
            const clash = r.validation?.clashscore?.value;

            const idCell = document.createElement('td');
            idCell.className = "py-1.5";
            idCell.textContent = r.pdb_id;
            tr.appendChild(idCell);

            [
                rama?.favored_percent != null ? rama.favored_percent.toFixed(1) : '--',
                rama?.outlier_count ?? '--',
                ss?.helix_percent != null ? ss.helix_percent.toFixed(1) : '--',
                clash != null ? clash.toFixed(1) : '--',
            ].forEach(value => {
                const td = document.createElement('td');
                td.className = "px-3 py-1.5 text-right";
                td.textContent = value;
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        summary.appendChild(table);
    }

    getParameters() {
        return {
            removeWater: this.element.querySelector('#param-remove-water').checked,
            removeHeteroatoms: this.element.querySelector('#param-remove-heteroatoms').checked
        };
    }

    setAligning(isAligning) {
        const runBtn = this.element.querySelector('#workspace-run-btn');
        if (!runBtn) return;
        if (isAligning) {
            runBtn.disabled = true;
            runBtn.innerHTML = `
                <span class="animate-spin material-symbols-outlined text-[16px]">sync</span>
                Aligning Pipeline...
            `;
        } else {
            runBtn.disabled = false;
            runBtn.innerHTML = `
                <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Structural Alignment
            `;
        }
    }
}
