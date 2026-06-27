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
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col gap-4 overflow-y-auto pr-1";
        div.id = "tab-overview-container";
        
        div.innerHTML = `
            <!-- Selected Proteins Card -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-[20px] text-primary">layers</span>
                        <h4 class="font-body-md text-body-md font-semibold text-text-primary">Alignment Structures</h4>
                    </div>
                    <span id="pdb-count-badge" class="px-2 py-0.5 rounded-full bg-white/10 text-text-secondary font-label-sm text-label-sm">0 Proteins</span>
                </div>
                
                <div id="pdb-list-container" class="flex flex-col gap-3">
                    <!-- Dynamic list of PDBs with chain dropdowns -->
                </div>
                
                <!-- Quick Add Section -->
                <div class="flex gap-2 mt-2">
                    <input id="add-pdb-input" type="text" placeholder="Enter PDB ID (e.g. 1L2Y)" class="flex-grow bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-body-sm text-text-primary focus:outline-none focus:border-primary font-mono uppercase" maxlength="4"/>
                    <button id="add-pdb-btn" class="btn-secondary px-4 py-1.5 rounded-lg font-label-md text-label-md flex items-center gap-1">
                        <span class="material-symbols-outlined text-[16px]">add</span>
                        Add
                    </button>
                </div>
            </div>
            
            <!-- Alignment Parameters -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-4 bg-[#11141c]/50">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px] text-gradient-end">tune</span>
                    <h4 class="font-body-md text-body-md font-semibold text-text-primary">Pipeline Parameters</h4>
                </div>
                <div class="flex flex-col gap-3">
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-water" type="checkbox" checked class="rounded border-white/10 bg-black/40 text-primary focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-text-secondary group-hover:text-text-primary transition-colors">Filter Water Molecules (HOH)</span>
                    </label>
                    <label class="flex items-center gap-3 cursor-pointer group">
                        <input id="param-remove-heteroatoms" type="checkbox" checked class="rounded border-white/10 bg-black/40 text-primary focus:ring-0 focus:ring-offset-0"/>
                        <span class="font-body-sm text-body-sm text-text-secondary group-hover:text-text-primary transition-colors">Exclude Non-Ligand Heteroatoms</span>
                    </label>
                </div>
            </div>
            
            <!-- Quick Run Action -->
            <button id="overview-run-btn" class="btn-primary w-full py-3 rounded-xl font-label-md text-label-md flex justify-center items-center gap-2 shadow-lg shadow-gradient-start/20 hover:shadow-gradient-start/40">
                <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">play_arrow</span>
                Run Structural Alignment
            </button>
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

        addBtn.addEventListener('click', () => {
            const val = addInput.value.trim().toUpperCase();
            if (val.length === 4) {
                this.onAddPDB(val);
                addInput.value = "";
            }
        });

        addInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const val = addInput.value.trim().toUpperCase();
                if (val.length === 4) {
                    this.onAddPDB(val);
                    addInput.value = "";
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
    }

    refreshPDBList() {
        if (!this.element) return;

        const badge = this.element.querySelector('#pdb-count-badge');
        badge.innerText = `${this.selectedPDBs.length} Protein${this.selectedPDBs.length !== 1 ? 's' : ''}`;

        const container = this.element.querySelector('#pdb-list-container');
        if (this.isLoadingChains) {
            container.innerHTML = `
                <div class="flex items-center justify-center py-4 gap-2 text-text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Loading structure chains...
                </div>
            `;
            return;
        }

        container.innerHTML = "";
        if (this.selectedPDBs.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-text-secondary font-body-sm">
                    Add at least 2 PDB structures to align.
                </div>
            `;
            return;
        }

        this.selectedPDBs.forEach(pid => {
            const meta = this.pdbMetadata[pid];
            const div = document.createElement('div');
            div.className = "flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 transition-all";
            
            let chainsOptionsHTML = "";
            if (meta && meta.chains) {
                meta.chains.forEach(c => {
                    const selectedAttr = (this.chainSelections[pid] === c.id) ? "selected" : "";
                    chainsOptionsHTML += `<option value="${c.id}" ${selectedAttr}>Chain ${c.id} (${c.residues_count} residues)</option>`;
                });
            } else {
                chainsOptionsHTML = `<option value="A">Chain A</option>`;
            }

            div.innerHTML = `
                <div class="flex items-center gap-3">
                    <span class="font-headline-sm text-body-md font-bold text-text-primary font-mono">${pid}</span>
                    <select class="bg-black/60 border border-white/10 rounded px-2 py-1 text-body-sm text-text-secondary focus:outline-none focus:border-primary font-mono chain-select" data-pdb="${pid}">
                        ${chainsOptionsHTML}
                    </select>
                </div>
                <button class="text-error hover:text-red-400 p-1 rounded hover:bg-white/5 transition-colors remove-pdb-btn" data-pdb="${pid}">
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
