import { fetchSuggestions, isValidPdbId } from '../api';

const SOURCE_LABELS = {
    pdb: 'PDB',
    alphafold: 'AlphaFold',
    swissmodel: 'SWISS-MODEL',
    esmfold: 'ESMFold',
};

export class OverviewTab {
    constructor(props) {
        this.selectedPDBs = props.selectedPDBs || [];
        this.chainSelections = props.chainSelections || {};
        this.pdbMetadata = props.pdbMetadata || {};
        this.onAddPDB = props.onAddPDB;
        this.onAddManyPDBs = props.onAddManyPDBs;
        this.onRemovePDB = props.onRemovePDB;
        this.onChainSelection = props.onChainSelection;
        this.onRunAlignment = props.onRunAlignment;
        this.element = null;
        this.isLoadingChains = false;
        this.suggestTimeout = null;
        this.batchInputVisible = false;
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-overview-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Alignment Workspace</span>
                    <h2 class="section-title">Structures &amp; parameters</h2>
                </div>
                <span id="pdb-count-badge" class="font-label-sm text-label-sm text-secondary">0 Proteins</span>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div class="flex flex-col gap-3">
                    <div class="flex gap-2 relative">
                        <input id="add-pdb-input" type="text" placeholder="PDB ID, or AF- / SM- / ESM- accession" class="flex-grow bg-surface-raised border border-border rounded-md px-3 py-1.5 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase" autocomplete="off"/>
                        <button id="add-pdb-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add</button>
                    </div>
                    <div id="add-pdb-suggestions" class="flex gap-2"></div>

                    <button id="toggle-batch-add-btn" type="button" class="self-start font-label-sm text-label-sm text-secondary hover:text-accent transition-colors underline decoration-dotted">Paste multiple IDs</button>

                    <div id="batch-add-container" class="flex flex-col gap-2 ${this.batchInputVisible ? '' : 'hidden'}">
                        <textarea id="batch-pdb-input" rows="3" placeholder="Paste PDB IDs or accessions, separated by commas, spaces, or new lines (e.g. 4RLT, 3UG9, AF-P69905-F1)" class="w-full bg-surface-raised border border-border rounded-md px-3 py-2 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase"></textarea>
                        <div class="flex items-center gap-3">
                            <button id="batch-add-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add All</button>
                            <span id="batch-add-feedback" class="font-body-sm text-[11px] text-secondary"></span>
                        </div>
                    </div>

                    <div id="pdb-list-container" class="flex flex-col gap-2 mt-1">
                        <!-- Dynamic list of PDBs with chain dropdowns -->
                    </div>
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

                <button id="overview-run-btn" class="btn-primary-hard w-full py-3 rounded-sm font-label-md text-label-md flex justify-center items-center gap-2">
                    <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                    Run Structural Alignment
                </button>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        this.refreshPDBList();
        return div;
    }

    setupEventListeners() {
        const addBtn = this.element.querySelector('#add-pdb-btn');
        const addInput = this.element.querySelector('#add-pdb-input');
        const runBtn = this.element.querySelector('#overview-run-btn');
        const suggestionsContainer = this.element.querySelector('#add-pdb-suggestions');

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
            this.onRunAlignment();
        });

        const toggleBatchBtn = this.element.querySelector('#toggle-batch-add-btn');
        const batchContainer = this.element.querySelector('#batch-add-container');
        const batchInput = this.element.querySelector('#batch-pdb-input');
        const batchAddBtn = this.element.querySelector('#batch-add-btn');
        const batchFeedback = this.element.querySelector('#batch-add-feedback');

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
                addedCount = (result && result.added) ? result.added.length : toAdd.length;
                overCap = (result && result.overCap) || 0;
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
    }

    updateState(selectedPDBs, chainSelections, pdbMetadata) {
        this.selectedPDBs = selectedPDBs;
        this.chainSelections = chainSelections;
        this.pdbMetadata = pdbMetadata;
        this.refreshPDBList();
    }

    setLoadingChains(isLoading) {
        this.isLoadingChains = isLoading;
        this.refreshPDBList();

        // Guard against submitting an alignment while a just-added structure's
        // chain selection hasn't resolved yet, which would silently persist
        // an incomplete chain_selection for that run.
        const runBtn = this.element && this.element.querySelector('#overview-run-btn');
        if (runBtn) runBtn.disabled = isLoading;
    }

    refreshPDBList() {
        if (!this.element) return;

        const badge = this.element.querySelector('#pdb-count-badge');
        badge.innerText = `${this.selectedPDBs.length} Protein${this.selectedPDBs.length !== 1 ? 's' : ''}`;

        const container = this.element.querySelector('#pdb-list-container');
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
                <div class="text-center py-4 text-secondary font-body-sm">
                    Add at least 2 PDB structures to align.
                </div>
            `;
            return;
        }

        this.selectedPDBs.forEach(pid => {
            const meta = this.pdbMetadata[pid];
            const div = document.createElement('div');
            div.className = "flex flex-col gap-1.5 p-3 rounded-md bg-surface-raised border border-border-subtle";

            let chainsOptionsHTML = "";
            if (meta && meta.chains) {
                meta.chains.forEach(c => {
                    const selectedAttr = (this.chainSelections[pid] === c.id) ? "selected" : "";
                    chainsOptionsHTML += `<option value="${c.id}" ${selectedAttr}>Chain ${c.id} (${c.residue_count} residues)</option>`;
                });
            } else {
                chainsOptionsHTML = `<option value="A">Chain A</option>`;
            }

            const sourceLabel = SOURCE_LABELS[meta && meta.source] || 'PDB';
            const metaParts = meta
                ? [meta.method, meta.resolution, meta.organism].filter(v => v && v !== 'N/A')
                : [];

            div.innerHTML = `
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="font-headline-sm text-body-md font-bold text-primary font-mono">${pid}</span>
                        <span class="px-1.5 py-0.5 rounded-md bg-surface border border-border-subtle font-mono text-[10px] text-secondary uppercase source-badge">${sourceLabel}</span>
                        <select class="bg-surface border border-border rounded-md px-2 py-1 text-body-sm text-secondary focus:outline-none focus:border-accent font-mono chain-select" data-pdb="${pid}">
                            ${chainsOptionsHTML}
                        </select>
                    </div>
                    <button class="text-error hover:text-red-400 p-1 rounded-md hover:bg-surface transition-colors remove-pdb-btn" data-pdb="${pid}">
                        <span class="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                </div>
                ${metaParts.length > 0 ? `<span class="pdb-meta-line font-body-sm text-[11px] text-secondary pl-0.5">${metaParts.join(' · ')}</span>` : ''}
            `;

            // Bind events
            div.querySelector('.chain-select').addEventListener('change', (e) => {
                this.onChainSelection(pid, e.target.value);
            });

            div.querySelector('.remove-pdb-btn').addEventListener('click', () => {
                this.onRemovePDB(pid);
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
        const runBtn = this.element.querySelector('#overview-run-btn');
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
