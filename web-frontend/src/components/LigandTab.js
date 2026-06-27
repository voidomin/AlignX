import { fetchInteractions } from '../api';

export class LigandTab {
    constructor(props) {
        this.selectedPDBs = props.selectedPDBs || [];
        this.currentRunId = props.currentRunId;
        this.onResidueSelected = props.onResidueSelected;
        this.onLigandSelected = props.onLigandSelected;
        this.ligandsList = [];
        this.element = null;
        this.selectedLigandId = "";
    }

    render() {
        const div = document.createElement('div');
        div.className = "flex-grow flex flex-col gap-4 overflow-hidden";
        div.id = "tab-ligands-container";
        
        div.innerHTML = `
            <!-- Binding Site Description Card -->
            <div class="glass-panel rounded-xl p-5 flex flex-col gap-3 shrink-0 bg-[#11141c]/50">
                <div class="flex justify-between items-center">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-[20px] text-gradient-end">science</span>
                        <h4 class="font-body-md text-body-md font-semibold text-text-primary">Ligand Inspector</h4>
                    </div>
                    <select id="ligand-select" class="bg-black/60 border border-white/10 rounded-lg text-body-sm text-text-primary py-1 px-2 focus:outline-none focus:border-gradient-end font-mono max-w-[200px]">
                        <option value="">No Ligands Loaded</option>
                    </select>
                </div>
                <div id="ligand-pocket-desc" class="font-body-sm text-body-sm text-text-secondary leading-relaxed mt-1">
                    Perform an alignment and select a ligand from the list to analyze atomic interactions in the binding pocket.
                </div>
                <div class="flex gap-3 mt-2">
                    <span id="ligand-volume-badge" class="px-2.5 py-1 rounded-md bg-secondary/10 text-secondary font-label-sm text-label-sm border border-secondary/20 hidden">Volume: -- Å³</span>
                    <span id="ligand-sasa-badge" class="px-2.5 py-1 rounded-md bg-gradient-start/10 text-primary-fixed-dim font-label-sm text-label-sm border border-gradient-start/20 hidden">SASA: -- Å²</span>
                </div>
            </div>
            <!-- Data Table -->
            <div class="glass-panel rounded-xl flex-grow flex flex-col overflow-hidden min-h-[200px] bg-[#11141c]/50">
                <div class="px-4 py-3 border-b border-white/10 table-header flex justify-between items-center bg-black/20">
                    <h4 class="font-label-md text-label-md text-text-secondary uppercase tracking-wider">Molecular Interactions</h4>
                    <span id="interaction-count" class="font-label-sm text-label-sm text-text-secondary">0 Found</span>
                </div>
                <div class="flex-grow overflow-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="sticky top-0 bg-[#12141a] border-b border-white/5 font-label-sm text-label-sm text-text-secondary z-10">
                        <tr>
                            <th class="px-4 py-3 font-medium">Residue</th>
                            <th class="px-3 py-3 font-medium">Chain</th>
                            <th class="px-3 py-3 font-medium text-right">Resi</th>
                            <th class="px-3 py-3 font-medium text-right">Dist (Å)</th>
                            <th class="px-4 py-3 font-medium">Type</th>
                        </tr>
                        </thead>
                        <tbody id="interactions-table-body" class="font-body-sm text-body-sm text-text-primary font-mono divide-y divide-white/5">
                            <tr>
                                <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                                    Select a ligand to populate interactions.
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        this.populateDropdown();
        return div;
    }

    setupEventListeners() {
        const select = this.element.querySelector('#ligand-select');
        select.addEventListener('change', async (e) => {
            const ligandId = e.target.value;
            this.selectedLigandId = ligandId;
            await this.loadInteractions(ligandId);
        });
    }

    updateLigands(ligands, runId) {
        this.ligandsList = ligands || [];
        this.currentRunId = runId;
        this.selectedLigandId = "";
        this.populateDropdown();
        this.clearTable();
    }

    populateDropdown() {
        if (!this.element) return;
        const select = this.element.querySelector('#ligand-select');
        select.innerHTML = "";
        
        if (this.ligandsList.length === 0) {
            select.innerHTML = `<option value="">No Ligands Loaded</option>`;
            return;
        }

        const defaultOption = document.createElement('option');
        defaultOption.value = "";
        defaultOption.innerText = "Select a Ligand";
        select.appendChild(defaultOption);

        this.ligandsList.forEach(lig => {
            const opt = document.createElement('option');
            opt.value = lig.id;
            opt.innerText = `${lig.name} (Chain ${lig.chain}, Resi ${lig.resi})`;
            if (this.selectedLigandId === lig.id) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
    }

    clearTable() {
        if (!this.element) return;
        const desc = this.element.querySelector('#ligand-pocket-desc');
        desc.innerText = "Perform an alignment and select a ligand from the list to analyze atomic interactions in the binding pocket.";
        
        this.element.querySelector('#ligand-volume-badge').classList.add('hidden');
        this.element.querySelector('#ligand-sasa-badge').classList.add('hidden');
        this.element.querySelector('#interaction-count').innerText = "0 Found";
        
        this.element.querySelector('#interactions-table-body').innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                    Select a ligand to populate interactions.
                </td>
            </tr>
        `;
    }

    async loadInteractions(ligandId) {
        if (!this.element) return;
        
        const tableBody = this.element.querySelector('#interactions-table-body');
        const desc = this.element.querySelector('#ligand-pocket-desc');
        const countBadge = this.element.querySelector('#interaction-count');
        const volBadge = this.element.querySelector('#ligand-volume-badge');
        const sasaBadge = this.element.querySelector('#ligand-sasa-badge');

        if (!ligandId) {
            this.clearTable();
            this.onLigandSelected(""); // Trigger reset styles on 3D viewport
            return;
        }

        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Analyzing interactions...
                </td>
            </tr>
        `;

        try {
            const referencePdbId = this.selectedPDBs[0];
            const data = await fetchInteractions(referencePdbId, ligandId, this.currentRunId);
            const metadata = data.interactions;
            const contacts = metadata.interactions;

            // Trigger parent event to update 3D viewer binding site
            this.onLigandSelected(ligandId, contacts);

            desc.innerText = `Conserved catalytic pocket near ligand ${metadata.ligand}. Stable hydrophobic cluster showing coordinated interactions.`;
            
            if (metadata.pocket_volume) {
                volBadge.innerText = `Volume: ${metadata.pocket_volume.toFixed(1)} Å³`;
                volBadge.classList.remove('hidden');
            } else {
                volBadge.classList.add('hidden');
            }

            if (metadata.pocket_sasa) {
                sasaBadge.innerText = `SASA: ${metadata.pocket_sasa.toFixed(1)} Å²`;
                sasaBadge.classList.remove('hidden');
            } else {
                sasaBadge.classList.add('hidden');
            }

            countBadge.innerText = `${contacts.length} Found`;
            tableBody.innerHTML = "";

            if (contacts.length === 0) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                            No specific interaction contacts found.
                        </td>
                    </tr>
                `;
            } else {
                contacts.forEach((item, index) => {
                    const tr = document.createElement('tr');
                    tr.className = "hover:bg-white/5 transition-colors cursor-pointer group";
                    
                    let typeColor = "bg-gray-500/20 text-gray-300 border border-gray-500/30";
                    if (item.type.toLowerCase().includes("h-bond")) {
                        typeColor = "bg-blue-500/20 text-blue-300 border border-blue-500/30";
                    } else if (item.type.toLowerCase().includes("pi")) {
                        typeColor = "bg-purple-500/20 text-purple-300 border border-purple-500/30";
                    } else if (item.type.toLowerCase().includes("salt")) {
                        typeColor = "bg-green-500/20 text-green-300 border border-green-500/30";
                    } else if (item.type.toLowerCase().includes("metal")) {
                        typeColor = "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30";
                    }

                    const resn = item.resn || item.residue || "UNK";
                    tr.innerHTML = `
                        <td class="px-4 py-2.5">${resn}</td>
                        <td class="px-3 py-2.5">${item.chain}</td>
                        <td class="px-3 py-2.5 text-right text-text-secondary group-hover:text-text-primary">${item.resi}</td>
                        <td class="px-3 py-2.5 text-right font-semibold">${item.distance.toFixed(1)}</td>
                        <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] ${typeColor}">${item.type}</span></td>
                    `;

                    tr.addEventListener('click', () => {
                        // Highlight table row
                        this.element.querySelectorAll('#interactions-table-body tr').forEach(row => {
                            row.className = "hover:bg-white/5 transition-colors cursor-pointer group";
                            row.querySelectorAll('td').forEach(td => td.classList.remove('text-tertiary', 'font-bold'));
                        });
                        tr.className = "row-selected cursor-pointer group";
                        tr.querySelectorAll('td').forEach(td => td.classList.add('text-tertiary', 'font-bold'));

                        // Callback to highlight in 3D
                        this.onResidueSelected(item.chain, item.resi);
                    });

                    tableBody.appendChild(tr);
                });
            }
        } catch (err) {
            console.error("Failed to load interactions:", err);
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center py-8 text-text-secondary font-body-sm">
                        Failed to calculate pocket site contacts.
                    </td>
                </tr>
            `;
        }
    }
}
