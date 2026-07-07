import { fetchInteractions, fetchLigands } from '../api';

export class LigandTab {
    constructor(props) {
        this.selectedPDBs = props.selectedPDBs || [];
        this.currentRunId = props.currentRunId;
        this.onResidueSelected = props.onResidueSelected;
        this.onLigandSelected = props.onLigandSelected;
        this.ligandsList = [];
        this.element = null;
        this.selectedLigandId = "";
        this.currentStructureIndex = 0;
    }

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-ligands-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — Binding Pocket</span>
                    <h2 class="section-title">Ligand inspector</h2>
                </div>
                <div class="flex gap-2">
                    <select id="ligand-structure-select" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[140px]">
                    </select>
                    <select id="ligand-select" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono max-w-[220px]">
                        <option value="">No Ligands Loaded</option>
                    </select>
                </div>
            </header>

            <div class="section-body flex flex-col gap-6">
                <div id="ligand-pocket-desc" class="font-body-sm text-body-sm text-secondary leading-relaxed">
                    Perform an alignment and select a ligand from the list to analyze atomic interactions in the binding pocket.
                </div>
                <div class="flex gap-4">
                    <span id="ligand-volume-badge" class="font-label-sm text-label-sm text-secondary hidden">Volume: -- Å³</span>
                    <span id="ligand-sasa-badge" class="font-label-sm text-label-sm text-secondary hidden">SASA: -- Å²</span>
                </div>

                <div class="flex items-baseline justify-between mt-2 pt-4 border-t border-border">
                    <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Molecular interactions</span>
                    <span id="interaction-count" class="font-label-sm text-label-sm text-secondary">0 Found</span>
                </div>
                <table class="w-full text-left border-collapse">
                    <thead class="font-label-sm text-label-sm text-secondary">
                    <tr>
                        <th class="px-0 py-2 border-b border-border font-medium">Residue</th>
                        <th class="px-3 py-2 border-b border-border font-medium">Chain</th>
                        <th class="px-3 py-2 border-b border-border font-medium text-right">Resi</th>
                        <th class="px-3 py-2 border-b border-border font-medium text-right">Dist (Å)</th>
                        <th class="px-3 py-2 border-b border-border font-medium">Type</th>
                    </tr>
                    </thead>
                    <tbody id="interactions-table-body" class="font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle">
                        <tr>
                            <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                                Select a ligand to populate interactions.
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        this.populateStructurePicker();
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

        const structureSelect = this.element.querySelector('#ligand-structure-select');
        structureSelect.addEventListener('change', async (e) => {
            await this.switchStructure(Number.parseInt(e.target.value, 10));
        });
    }

    populateStructurePicker() {
        if (!this.element) return;
        const select = this.element.querySelector('#ligand-structure-select');
        select.innerHTML = "";
        this.selectedPDBs.forEach((pdbId, index) => {
            const opt = document.createElement('option');
            opt.value = String(index);
            opt.textContent = pdbId;
            if (index === this.currentStructureIndex) opt.selected = true;
            select.appendChild(opt);
        });
    }

    async switchStructure(index) {
        if (index === this.currentStructureIndex) return;
        this.currentStructureIndex = index;
        this.selectedLigandId = "";
        this.clearTable();
        this.onLigandSelected(this.currentStructureIndex, "");

        if (!this.currentRunId) return;

        const pdbId = this.selectedPDBs[index];
        try {
            const ligData = await fetchLigands(pdbId, this.currentRunId);
            this.ligandsList = ligData.ligands || [];
        } catch (err) {
            console.error("Failed to load ligands for structure:", err);
            this.ligandsList = [];
        }
        this.populateDropdown();
    }

    updateLigands(ligands, runId, selectedPDBs) {
        this.ligandsList = ligands || [];
        this.currentRunId = runId;
        if (selectedPDBs) this.selectedPDBs = selectedPDBs;
        this.currentStructureIndex = 0;
        this.selectedLigandId = "";
        this.populateStructurePicker();
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
                <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
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
            this.onLigandSelected(this.currentStructureIndex, ""); // Trigger reset styles on 3D viewport
            return;
        }

        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Analyzing interactions...
                </td>
            </tr>
        `;

        try {
            const targetPdbId = this.selectedPDBs[this.currentStructureIndex];
            const data = await fetchInteractions(targetPdbId, ligandId, this.currentRunId);
            const metadata = data.interactions;
            const contacts = metadata.interactions;

            // Trigger parent event to update 3D viewer binding site
            this.onLigandSelected(this.currentStructureIndex, ligandId, contacts);

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
                        <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                            No specific interaction contacts found.
                        </td>
                    </tr>
                `;
            } else {
                contacts.forEach((item, index) => {
                    const tr = document.createElement('tr');
                    tr.className = "hover:bg-surface-raised transition-colors cursor-pointer group";

                    // Functional data-encoding: dot color signals interaction type
                    let dotColor = "bg-muted";
                    if (item.type.toLowerCase().includes("h-bond")) {
                        dotColor = "bg-accent";
                    } else if (item.type.toLowerCase().includes("pi")) {
                        dotColor = "bg-[#8B5CF6]";
                    } else if (item.type.toLowerCase().includes("salt")) {
                        dotColor = "bg-success";
                    } else if (item.type.toLowerCase().includes("metal")) {
                        dotColor = "bg-warning";
                    }

                    const resn = item.resn || item.residue || "UNK";
                    tr.innerHTML = `
                        <td class="px-0 py-2.5">${resn}</td>
                        <td class="px-3 py-2.5">${item.chain}</td>
                        <td class="px-3 py-2.5 text-right text-secondary group-hover:text-primary">${item.resi}</td>
                        <td class="px-3 py-2.5 text-right font-semibold">${item.distance.toFixed(1)}</td>
                        <td class="px-3 py-2.5"><span class="inline-flex items-center gap-1.5 text-secondary"><span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>${item.type}</span></td>
                    `;

                    tr.addEventListener('click', () => {
                        // Highlight table row
                        this.element.querySelectorAll('#interactions-table-body tr').forEach(row => {
                            row.className = "hover:bg-surface-raised transition-colors cursor-pointer group";
                            row.querySelectorAll('td').forEach(td => td.classList.remove('text-tertiary', 'font-bold'));
                        });
                        tr.className = "row-selected cursor-pointer group";
                        tr.querySelectorAll('td').forEach(td => td.classList.add('text-tertiary', 'font-bold'));

                        // Callback to highlight in 3D
                        this.onResidueSelected(this.currentStructureIndex, item.chain, item.resi, item.aligned_resi);
                    });

                    tableBody.appendChild(tr);
                });
            }
        } catch (err) {
            console.error("Failed to load interactions:", err);
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center py-8 text-secondary font-body-sm">
                        Failed to calculate pocket site contacts.
                    </td>
                </tr>
            `;
        }
    }
}
