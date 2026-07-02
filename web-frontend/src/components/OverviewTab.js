import { fetchSuggestions } from '../api';

export class OverviewTab {
    constructor(props) {
        this.selectedPDBs = props.selectedPDBs || [];
        this.chainSelections = props.chainSelections || {};
        this.pdbMetadata = props.pdbMetadata || {};
        this.onAddPDB = props.onAddPDB;
        this.onRemovePDB = props.onRemovePDB;
        this.onChainSelection = props.onChainSelection;
        this.onRunAlignment = props.onRunAlignment;
        this.element = null;
        this.isLoadingChains = false;
        this.suggestTimeout = null;
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
                        <input id="add-pdb-input" type="text" placeholder="Enter PDB ID (e.g. 1L2Y)" class="flex-grow bg-surface-raised border border-border rounded-md px-3 py-1.5 text-body-sm text-primary focus:outline-none focus:border-accent font-mono uppercase" maxlength="4" autocomplete="off"/>
                        <button id="add-pdb-btn" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Add</button>
                    </div>
                    <div id="add-pdb-suggestions" class="flex gap-2"></div>

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
            if (val.length === 4) {
                this.onAddPDB(val);
                addInput.value = "";
                renderSuggestions([]);
            }
        });

        addInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const val = addInput.value.trim().toUpperCase();
                if (val.length === 4) {
                    this.onAddPDB(val);
                    addInput.value = "";
                    renderSuggestions([]);
                }
            }
        });

        runBtn.addEventListener('click', () => {
            this.onRunAlignment();
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
            div.className = "flex items-center justify-between p-3 rounded-md bg-surface-raised border border-border-subtle";

            let chainsOptionsHTML = "";
            if (meta && meta.chains) {
                meta.chains.forEach(c => {
                    const selectedAttr = (this.chainSelections[pid] === c.id) ? "selected" : "";
                    chainsOptionsHTML += `<option value="${c.id}" ${selectedAttr}>Chain ${c.id} (${c.residue_count} residues)</option>`;
                });
            } else {
                chainsOptionsHTML = `<option value="A">Chain A</option>`;
            }

            div.innerHTML = `
                <div class="flex items-center gap-3">
                    <span class="font-headline-sm text-body-md font-bold text-primary font-mono">${pid}</span>
                    <select class="bg-surface border border-border rounded-md px-2 py-1 text-body-sm text-secondary focus:outline-none focus:border-accent font-mono chain-select" data-pdb="${pid}">
                        ${chainsOptionsHTML}
                    </select>
                </div>
                <button class="text-error hover:text-red-400 p-1 rounded-md hover:bg-surface transition-colors remove-pdb-btn" data-pdb="${pid}">
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                </button>
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
