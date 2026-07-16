import { fetchInteractions, fetchLigands, fetchChains, fetchInterface, fetchLigandInfo, fetchPockets } from '../api';
import { buildContactRow } from '../utils/interactionRenderers';

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
        this.pocketSimilarity = null;
        this.availableChains = [];
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
                    <span id="ligand-sasa-badge" class="font-label-sm text-label-sm text-secondary hidden">SASA: -- Å²</span>
                </div>
                <div id="ligand-chemistry-info" class="font-body-sm text-[11px] text-secondary hidden"></div>

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

                <div id="pocket-similarity-section" class="hidden flex-col gap-2 mt-2 pt-4 border-t border-border">
                    <div class="flex items-baseline justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Binding pocket similarity</span>
                        <span class="font-body-sm text-body-sm text-secondary">Jaccard index of pocket residue composition</span>
                    </div>
                    <div id="pocket-similarity-heatmap" class="w-full h-[320px]"></div>
                </div>

                <div id="candidate-pockets-section" class="hidden flex-col gap-2 mt-2 pt-4 border-t border-border">
                    <div class="flex items-baseline justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Candidate binding pockets</span>
                        <span class="font-body-sm text-body-sm text-secondary">Heuristic - no bound ligand to analyze directly</span>
                    </div>
                    <table class="w-full text-left border-collapse">
                        <thead class="font-label-sm text-label-sm text-secondary">
                        <tr>
                            <th class="px-0 py-2 border-b border-border font-medium">Rank</th>
                            <th class="px-3 py-2 border-b border-border font-medium">Lining residues</th>
                            <th class="px-3 py-2 border-b border-border font-medium text-right">Score</th>
                            <th class="px-3 py-2 border-b border-border font-medium text-right">Est. volume (&Aring;&sup3;)</th>
                        </tr>
                        </thead>
                        <tbody id="candidate-pockets-table-body" class="font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle"></tbody>
                    </table>
                </div>

                <div id="interface-section" class="hidden flex-col gap-3 mt-2 pt-4 border-t border-border">
                    <div class="flex items-baseline justify-between">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Protein-protein interfaces</span>
                        <span class="font-body-sm text-body-sm text-secondary">Contact residues between two chains</span>
                    </div>
                    <div class="flex items-end gap-3">
                        <label class="flex flex-col gap-1">
                            <span class="font-label-sm text-label-sm text-secondary">Chain A</span>
                            <select id="interface-chain-a" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono"></select>
                        </label>
                        <label class="flex flex-col gap-1">
                            <span class="font-label-sm text-label-sm text-secondary">Chain B</span>
                            <select id="interface-chain-b" class="bg-surface-raised border border-border rounded-md text-body-sm text-primary py-1.5 px-3 focus:outline-none focus:border-accent font-mono"></select>
                        </label>
                        <button id="interface-analyze-btn" class="px-3 py-1.5 rounded-md bg-accent-muted text-accent font-label-md text-label-md hover:bg-accent hover:text-white transition-colors">Analyze Interface</button>
                    </div>
                    <div id="interface-results" class="flex flex-col gap-3"></div>
                </div>
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

        const analyzeBtn = this.element.querySelector('#interface-analyze-btn');
        analyzeBtn.addEventListener('click', () => this.analyzeInterface());
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

        // fetchLigands already treats runId as optional (resolves the raw
        // download directly when there's no run) - this used to bail out
        // here whenever there was no completed alignment, which is exactly
        // what blocked the Ligands tab from working for a lone, un-aligned
        // structure.
        const pdbId = this.selectedPDBs[index];
        try {
            const ligData = await fetchLigands(pdbId, this.currentRunId);
            this.ligandsList = ligData.ligands || [];
        } catch (err) {
            console.error("Failed to load ligands for structure:", err);
            this.ligandsList = [];
        }
        this.populateDropdown();
        await this.loadAvailableChains();
        await this.loadCandidatePockets();
    }

    updateLigands(ligands, runId, selectedPDBs, pocketSimilarity = null) {
        this.ligandsList = ligands || [];
        this.currentRunId = runId;
        if (selectedPDBs) this.selectedPDBs = selectedPDBs;
        this.currentStructureIndex = 0;
        this.selectedLigandId = "";
        this.pocketSimilarity = pocketSimilarity;
        this.populateStructurePicker();
        this.populateDropdown();
        this.clearTable();
        this.renderPocketSimilarity();
        this.loadAvailableChains();
        this.loadCandidatePockets();
    }

    async loadAvailableChains() {
        if (!this.element) return;
        const pdbId = this.selectedPDBs[this.currentStructureIndex];
        if (!pdbId) {
            this.availableChains = [];
            this.renderInterfaceSection();
            return;
        }
        try {
            const data = await fetchChains([pdbId]);
            const info = data.chains?.[pdbId];
            this.availableChains = (info?.chains || []).map(c => c.id);
        } catch (err) {
            console.error("Failed to load chain list for interface analysis:", err);
            this.availableChains = [];
        }
        this.renderInterfaceSection();
    }

    // Heuristic candidate-pocket detection (LigandAnalyzer.find_candidate_pockets)
    // only makes sense once a structure has confirmed NO real bound ligand -
    // otherwise the real interaction analysis above is strictly more useful.
    async loadCandidatePockets() {
        if (!this.element) return;
        const section = this.element.querySelector('#candidate-pockets-section');
        const pdbId = this.selectedPDBs[this.currentStructureIndex];

        if (!pdbId || this.ligandsList.length > 0) {
            section.classList.add('hidden');
            section.classList.remove('flex');
            return;
        }

        try {
            const data = await fetchPockets(pdbId, this.currentRunId);
            this.renderCandidatePockets(data.pockets || []);
        } catch (err) {
            console.error("Failed to load candidate pockets:", err);
            this.renderCandidatePockets([]);
        }
    }

    renderCandidatePockets(pockets) {
        if (!this.element) return;
        const section = this.element.querySelector('#candidate-pockets-section');
        const body = this.element.querySelector('#candidate-pockets-table-body');

        if (!pockets || pockets.length === 0) {
            section.classList.add('hidden');
            section.classList.remove('flex');
            return;
        }
        section.classList.remove('hidden');
        section.classList.add('flex');

        body.innerHTML = "";
        pockets.forEach(pocket => {
            const tr = document.createElement('tr');

            const rankCell = document.createElement('td');
            rankCell.className = "py-1.5";
            rankCell.textContent = pocket.rank;
            tr.appendChild(rankCell);

            const residuesCell = document.createElement('td');
            residuesCell.className = "px-3 py-1.5";
            residuesCell.textContent = (pocket.residues || [])
                .map(r => `${r.resn} ${r.chain}${r.resi}`)
                .join(', ');
            tr.appendChild(residuesCell);

            const scoreCell = document.createElement('td');
            scoreCell.className = "px-3 py-1.5 text-right";
            scoreCell.textContent = pocket.score;
            tr.appendChild(scoreCell);

            const volumeCell = document.createElement('td');
            volumeCell.className = "px-3 py-1.5 text-right";
            volumeCell.textContent = pocket.volume_estimate_a3 != null ? pocket.volume_estimate_a3 : '--';
            tr.appendChild(volumeCell);

            body.appendChild(tr);
        });
    }

    renderInterfaceSection() {
        if (!this.element) return;
        const section = this.element.querySelector('#interface-section');
        const chainASelect = this.element.querySelector('#interface-chain-a');
        const chainBSelect = this.element.querySelector('#interface-chain-b');
        const results = this.element.querySelector('#interface-results');
        results.innerHTML = "";

        if (this.availableChains.length < 2) {
            section.classList.add('hidden');
            section.classList.remove('flex');
            return;
        }
        section.classList.remove('hidden');
        section.classList.add('flex');

        const buildOptions = (select, defaultIndex) => {
            select.innerHTML = "";
            this.availableChains.forEach((chainId, i) => {
                const opt = document.createElement('option');
                opt.value = chainId;
                opt.textContent = chainId;
                if (i === defaultIndex) opt.selected = true;
                select.appendChild(opt);
            });
        };
        buildOptions(chainASelect, 0);
        buildOptions(chainBSelect, 1);
    }

    async analyzeInterface() {
        if (!this.element) return;
        const chainA = this.element.querySelector('#interface-chain-a').value;
        const chainB = this.element.querySelector('#interface-chain-b').value;
        const results = this.element.querySelector('#interface-results');

        if (!chainA || !chainB || chainA === chainB) {
            results.innerHTML = `<div class="font-body-sm text-body-sm text-secondary py-2">Select two different chains.</div>`;
            return;
        }

        results.innerHTML = `
            <div class="font-body-sm text-body-sm text-secondary py-2">
                <span class="animate-spin material-symbols-outlined text-[18px]">sync</span> Analyzing interface...
            </div>
        `;

        try {
            const pdbId = this.selectedPDBs[this.currentStructureIndex];
            const data = await fetchInterface(pdbId, chainA, chainB, this.currentRunId);
            this.renderInterfaceResults(data.interface);
        } catch (err) {
            console.error("Failed to analyze interface:", err);
            results.innerHTML = `<div class="font-body-sm text-body-sm text-secondary py-2">Failed to analyze interface.</div>`;
        }
    }

    renderInterfaceResults(interfaceData) {
        const results = this.element.querySelector('#interface-results');
        results.innerHTML = "";

        if (!interfaceData || interfaceData.error) {
            const msg = document.createElement('div');
            msg.className = "font-body-sm text-body-sm text-secondary py-2";
            msg.textContent = interfaceData?.error || "No interface data returned.";
            results.appendChild(msg);
            return;
        }

        const buriedBadge = document.createElement('span');
        buriedBadge.className = "font-label-sm text-label-sm text-secondary";
        buriedBadge.textContent = `Buried interface area: ${interfaceData.buried_area?.toFixed(1) ?? '--'} Å²`;
        results.appendChild(buriedBadge);

        const buildContactTable = (title, contacts) => {
            const wrapper = document.createElement('div');
            wrapper.className = "flex flex-col gap-1.5";

            const heading = document.createElement('span');
            heading.className = "font-label-sm text-label-sm text-secondary uppercase";
            heading.textContent = title;
            wrapper.appendChild(heading);

            if (!contacts || contacts.length === 0) {
                const empty = document.createElement('div');
                empty.className = "font-body-sm text-body-sm text-secondary py-1";
                empty.textContent = "No contact residues found.";
                wrapper.appendChild(empty);
                return wrapper;
            }

            const table = document.createElement('table');
            table.className = "w-full text-left border-collapse";
            table.innerHTML = `
                <thead class="font-label-sm text-label-sm text-secondary">
                    <tr>
                        <th class="px-0 py-1.5 border-b border-border font-medium">Residue</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium">Chain</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium text-right">Resi</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium text-right">Dist (Å)</th>
                        <th class="px-3 py-1.5 border-b border-border font-medium">Type</th>
                    </tr>
                </thead>
            `;
            const tbody = document.createElement('tbody');
            tbody.className = "font-body-sm text-body-sm text-primary font-mono divide-y divide-border-subtle";
            contacts.forEach(item => tbody.appendChild(buildContactRow(item)));
            table.appendChild(tbody);
            wrapper.appendChild(table);
            return wrapper;
        };

        results.appendChild(buildContactTable(`Chain ${interfaceData.chain_a} contacts`, interfaceData.chain_a_contacts));
        results.appendChild(buildContactTable(`Chain ${interfaceData.chain_b} contacts`, interfaceData.chain_b_contacts));
    }

    renderPocketSimilarity() {
        if (!this.element) return;
        const section = this.element.querySelector('#pocket-similarity-section');
        const heatmapDiv = this.element.querySelector('#pocket-similarity-heatmap');

        const sim = this.pocketSimilarity;
        if (!sim?.data?.length || sim.data.length < 2) {
            section.classList.add('hidden');
            return;
        }
        section.classList.remove('hidden');

        // Namespaced as "{pdb_id}:{ligand_id}" (coordinator.py's _analyze_ligands) -
        // split into a two-line label so the axis reads as structure + ligand
        // rather than one long opaque string.
        const splitLabel = (label) => {
            const idx = label.indexOf(':');
            return idx === -1 ? label : `${label.slice(0, idx)}<br>${label.slice(idx + 1)}`;
        };
        const labels = sim.columns.map(splitLabel);

        const trace = {
            z: sim.data,
            x: labels,
            y: labels,
            type: 'heatmap',
            colorscale: 'RdBu',
            reversescale: true,
            zmin: 0,
            zmax: 1,
        };
        const layout = {
            height: 320,
            margin: { l: 90, r: 20, t: 10, b: 90 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { family: "Inter, sans-serif", size: 10, color: "#A79E8E" }
        };
        Plotly.newPlot(heatmapDiv, [trace], layout, { responsive: true, displayModeBar: false });
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

        this.element.querySelector('#ligand-sasa-badge').classList.add('hidden');
        this.element.querySelector('#ligand-chemistry-info').classList.add('hidden');
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

            // Fire-and-forget - doesn't block interaction-table rendering,
            // and a slow/failed chemistry lookup shouldn't affect the rest
            // of this view.
            this.loadLigandChemistry(ligandId);

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
                contacts.forEach((item) => {
                    const tr = buildContactRow(item);
                    tr.className = "hover:bg-surface-raised transition-colors cursor-pointer group";

                    tr.addEventListener('click', () => {
                        // Highlight table row
                        this.element.querySelectorAll('#interactions-table-body tr').forEach(row => {
                            row.className = "hover:bg-surface-raised transition-colors cursor-pointer group";
                            for (const td of row.querySelectorAll('td')) {
                                td.classList.remove('text-tertiary', 'font-bold');
                            }
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

    // Resolves "what is this ligand?" via RCSB's Chemical Component
    // Dictionary - independent of the interaction analysis above (a slow
    // or failed lookup here never blocks it). ligandsList already carries
    // the bare 3-letter code as `.name` (the composite ligandId is
    // RESNAME_CHAIN_RESI, not directly usable for a chemistry lookup).
    async loadLigandChemistry(ligandId) {
        const info = this.element.querySelector('#ligand-chemistry-info');
        if (!info) return;

        const ligand = this.ligandsList.find(l => l.id === ligandId);
        const code = ligand ? ligand.name : ligandId.split('_')[0];

        info.textContent = 'Looking up ligand chemistry…';
        info.classList.remove('hidden');

        try {
            const data = await fetchLigandInfo(code);
            if (!data.chemistry) {
                info.textContent = `${code}: no chemistry data found.`;
                return;
            }
            const c = data.chemistry;
            const parts = [c.name, c.formula].filter(Boolean);
            info.textContent = parts.length > 0 ? parts.join(' · ') : `${code}: no chemistry data found.`;
            info.title = c.smiles ? `SMILES: ${c.smiles}` : '';
        } catch (err) {
            console.error("Failed to load ligand chemistry:", err);
            info.textContent = `${code}: chemistry lookup failed.`;
        }
    }
}
