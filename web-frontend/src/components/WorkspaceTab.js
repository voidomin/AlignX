import { fetchSuggestions, isValidPdbId } from '../api';
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

        this.selectedPDBs.forEach(pid => {
            const meta = this.pdbMetadata[pid];
            const div = document.createElement('div');
            div.className = "flex flex-col gap-1.5 p-3 rounded-md bg-surface-raised border border-border-subtle";

            let chainsOptionsHTML = "";
            if (meta?.chains) {
                meta.chains.forEach(c => {
                    const selectedAttr = (this.chainSelections[pid] === c.id) ? "selected" : "";
                    chainsOptionsHTML += `<option value="${c.id}" ${selectedAttr}>Chain ${c.id} (${c.residue_count} residues)</option>`;
                });
            } else {
                chainsOptionsHTML = `<option value="A">Chain A</option>`;
            }

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
        });
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
