import { getAlignmentPdbUrl } from '../api';

// Qualitative palette for N-structure identity coloring. Deliberately avoids
// amber/#F59E0B (reserved for the residue-selection highlight) and the
// coral brand accent (reserved for UI chrome), so chain-identity color never
// collides with those other two semantic uses of color in the app.
const CHAIN_COLORS = ['#8B5CF6', '#06B6D4', '#EC4899', '#A3E635', '#FB923C', '#2DD4BF'];

function colorForIndex(i) {
    return CHAIN_COLORS[i % CHAIN_COLORS.length];
}

export class Viewer3D {
    element = null;
    viewer = null;
    currentRunId = null;
    isSurfaceVisible = false;
    // One entry per aligned input structure, in submission order.
    // mustangChain is always chr(65+i) — the sequential chain letter
    // Mustang assigns in alignment.pdb regardless of the structure's
    // original source chain. sourceChain is only for HUD display text.
    structures = [];
    rmsdDf = null;

    render() {
        const div = document.createElement('div');
        div.className = "flex-1 card rounded-lg flex flex-col overflow-hidden relative";
        div.innerHTML = `
            <!-- Viewport Header -->
            <div class="px-4 py-3 border-b border-border flex justify-between items-center">
                <h3 class="font-body-md text-body-md font-semibold text-primary">Superposition Viewer</h3>
                <div class="flex gap-2">
                    <button id="btn-toggle-surface" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Surface">
                        <span class="material-symbols-outlined text-[18px]">blur_on</span>
                    </button>
                    <button id="btn-reset-view" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Reset View">
                        <span class="material-symbols-outlined text-[18px]">center_focus_strong</span>
                    </button>
                </div>
            </div>

            <!-- 3D Canvas Area -->
            <div id="3d-canvas-container" class="flex-grow relative bg-bg overflow-hidden min-h-[300px]">
                <!-- 3Dmol viewer div (positioned absolutely to fill the container) -->
                <div id="viewer-canvas-3dmol" class="w-full h-full absolute inset-0 z-0"></div>

                <!-- Placeholder shown only before an alignment has been run -->
                <div id="ambient-placeholder" class="absolute inset-0 flex items-center justify-center pointer-events-none z-5 px-8 text-center">
                    <span class="font-body-sm text-body-sm text-muted">Add 2+ structures and run alignment to view superposition</span>
                </div>

                <!-- HUD: dynamic per-structure legend -->
                <div id="hud-structure-legend" class="absolute top-4 left-4 bg-surface border border-border px-3 py-1.5 rounded-md flex flex-col gap-1.5 z-10 max-w-[240px]"></div>

                <!-- HUD: RMSD (single value for N=2, pairwise list for N>2) -->
                <div id="hud-rmsd-container" class="absolute top-4 right-4 bg-surface border border-border p-3 rounded-md flex flex-col items-end z-10 font-mono max-h-[220px] overflow-y-auto"></div>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        this._renderEmptyHUD();
        return div;
    }

    init3Dmol() {
        const container = this.element.querySelector('#viewer-canvas-3dmol');
        if (!container) return;

        container.innerHTML = "";
        this.viewer = $3Dmol.createViewer(container, {
            defaultcolors: $3Dmol.rasmolElementColors
        });
        this.viewer.setBackgroundColor("#050608");

        window.addEventListener('resize', () => {
            if (this.viewer) this.viewer.resize();
        });
    }

    setupEventListeners() {
        const toggleSurfaceBtn = this.element.querySelector('#btn-toggle-surface');
        const resetViewBtn = this.element.querySelector('#btn-reset-view');

        toggleSurfaceBtn.addEventListener('click', () => {
            if (!this.viewer) return;
            if (this.isSurfaceVisible) {
                this.viewer.removeAllSurfaces();
                this.isSurfaceVisible = false;
            } else {
                this.viewer.addSurface($3Dmol.SurfaceType.SAS, {
                    opacity: 0.45,
                    colorscheme: 'whiteCarbon'
                });
                this.isSurfaceVisible = true;
            }
            this.viewer.render();
        });

        resetViewBtn.addEventListener('click', () => {
            if (this.viewer) {
                this.viewer.zoomTo();
                this.viewer.render();
            }
        });
    }

    _buildStructures(pdbIds, chainSelections) {
        return pdbIds.map((pdbId, i) => ({
            pdbId,
            mustangChain: String.fromCodePoint(65 + i),
            sourceChain: chainSelections?.[pdbId] || '?',
            color: colorForIndex(i)
        }));
    }

    _renderEmptyHUD() {
        const legend = this.element.querySelector('#hud-structure-legend');
        const rmsdBox = this.element.querySelector('#hud-rmsd-container');
        if (legend) legend.innerHTML = `<span class="font-label-sm text-label-sm text-muted font-mono">No structures loaded</span>`;
        if (rmsdBox) rmsdBox.innerHTML = `
            <span class="font-label-sm text-label-sm text-secondary uppercase">Global RMSD</span>
            <span class="font-headline-md text-headline-md text-success font-semibold">-- Å</span>
        `;
    }

    _renderHUD() {
        const legend = this.element.querySelector('#hud-structure-legend');
        const rmsdBox = this.element.querySelector('#hud-rmsd-container');

        legend.innerHTML = this.structures.map(s => `
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full shrink-0" style="background-color: ${s.color};"></div>
                <span class="font-label-sm text-label-sm text-primary font-mono truncate">${s.pdbId} (Chain ${s.sourceChain})</span>
            </div>
        `).join('');

        if (this.structures.length <= 2 || !this.rmsdDf) {
            const rmsdValue = this._meanRmsd();
            rmsdBox.innerHTML = `
                <span class="font-label-sm text-label-sm text-secondary uppercase">Global RMSD</span>
                <span class="font-headline-md text-headline-md text-success font-semibold">${rmsdValue}</span>
            `;
            return;
        }

        // N>2: show every pairwise value from the full RMSD matrix rather
        // than collapsing to one number.
        const pairs = this._pairwiseRmsdRows();
        rmsdBox.innerHTML = `
            <span class="font-label-sm text-label-sm text-secondary uppercase mb-1">Pairwise RMSD</span>
            <div class="flex flex-col gap-1 items-end">
                ${pairs.map(p => `
                    <div class="flex items-center gap-2 text-body-sm">
                        <span class="text-secondary">${p.a} &harr; ${p.b}</span>
                        <span class="text-success font-semibold">${p.value.toFixed(2)} Å</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    _pairwiseRmsdRows() {
        if (!this.rmsdDf?.index || !this.rmsdDf?.data) return [];
        const { index, data } = this.rmsdDf;
        const rows = [];
        for (let i = 0; i < index.length; i++) {
            for (let j = i + 1; j < index.length; j++) {
                rows.push({ a: index[i], b: index[j], value: data[i][j] });
            }
        }
        return rows;
    }

    _meanRmsd() {
        const pairs = this._pairwiseRmsdRows();
        if (pairs.length === 0) return '-- Å';
        const mean = pairs.reduce((sum, p) => sum + p.value, 0) / pairs.length;
        return `${mean.toFixed(2)} Å`;
    }

    async loadSuperposition(runId, pdbIds, chainSelections, rmsdDf) {
        if (!this.viewer) {
            this.init3Dmol();
        }

        this.currentRunId = runId;
        this.structures = this._buildStructures(pdbIds, chainSelections);
        this.rmsdDf = rmsdDf || null;

        this.element.querySelector("#ambient-placeholder").style.display = "none";
        this._renderHUD();

        try {
            const response = await fetch(getAlignmentPdbUrl(runId));
            if (!response.ok) {
                throw new Error(`Failed to fetch alignment PDB: ${response.statusText}`);
            }
            const pdbData = await response.text();

            this.viewer.clear();
            this.viewer.addModel(pdbData, "pdb");

            this.structures.forEach(s => {
                this.viewer.setStyle({chain: s.mustangChain}, {cartoon: {color: s.color, opacity: 0.85}});
            });

            this.viewer.zoomTo();
            this.viewer.render();
            this.isSurfaceVisible = false;
        } catch (err) {
            console.error("Error loading superposition coordinate data:", err);
        }
    }

    // Ligand atoms are never present in the aligned structure (Mustang only
    // aligns protein backbones — HETATM/ligand records are stripped during
    // cleaning), so there is nothing to select/style for the ligand itself.
    // Each contact's `aligned_resi` (a raw->aligned residue-number remap
    // computed server-side, since the aligned structure's chains are
    // renumbered from 1) is used instead of its raw PDB `resi` so the
    // highlighted atoms actually exist in the loaded model.
    showLigandBindingSite(structureIndex, ligandId, interactions) {
        if (!this.viewer) return;

        // Ghost every structure first.
        this.structures.forEach(s => {
            this.viewer.setStyle({chain: s.mustangChain}, {cartoon: {color: s.color, opacity: 0.3}});
        });

        const target = this.structures[structureIndex];
        const mustangChain = target ? target.mustangChain : 'A';

        const alignedResidues = interactions
            .map(i => i.aligned_resi)
            .filter(r => r !== null && r !== undefined);

        alignedResidues.forEach(resi => {
            this.viewer.addStyle({chain: mustangChain, resi: resi}, {
                stick: {colorscheme: 'purpleCarbon', radius: 0.25},
                cartoon: {color: target ? target.color : '#8B5CF6', opacity: 1.0}
            });
        });

        if (alignedResidues.length > 0) {
            this.viewer.zoomTo({chain: mustangChain, resi: alignedResidues});
        } else {
            // No contact could be mapped into the aligned structure - avoid
            // zoomTo() on a bogus/empty selection blanking the viewport.
            this.viewer.zoomTo();
        }
        this.viewer.render();
    }

    highlightResidue(structureIndex, chain, resi, alignedResi) {
        if (!this.viewer) return;

        // Reset all cartoon styles to ghost
        this.structures.forEach(s => {
            this.viewer.setStyle({chain: s.mustangChain}, {cartoon: {color: s.color, opacity: 0.35}});
        });

        if (alignedResi === null || alignedResi === undefined) {
            // No known mapping into the aligned structure (e.g. this residue
            // was filtered out during cleaning) - nothing to select; avoid
            // zoomTo() on a bogus selection blanking the viewport.
            this.viewer.zoomTo();
            this.viewer.render();
            return;
        }

        const target = this.structures[structureIndex];
        const mustangChain = target ? target.mustangChain : chain;

        // Selection highlight uses the amber "tertiary" semantic (matches .row-selected)
        const selection = {chain: mustangChain, resi: alignedResi};
        this.viewer.addStyle(selection, {
            stick: {color: '#F59E0B', radius: 0.45},
            sphere: {color: '#F59E0B', scale: 1.3},
            cartoon: {color: '#F59E0B', opacity: 1.0}
        });

        this.viewer.zoomTo(selection);
        this.viewer.render();
    }

    highlightResidues(chainMapping) {
        // Highlights every residue in a {chain_id: [residue_numbers]} map at
        // once (e.g. every motif match across all structures), unlike
        // highlightResidue() above which only ever selects one residue in
        // one structure at a time. Ghosts once, then adds a style per match,
        // so the whole set stays visible together rather than each call
        // re-ghosting and wiping out the previous match's highlight.
        if (!this.viewer) return;

        this.structures.forEach(s => {
            this.viewer.setStyle({ chain: s.mustangChain }, { cartoon: { color: s.color, opacity: 0.35 } });
        });

        const selections = [];
        Object.entries(chainMapping || {}).forEach(([chain, residues]) => {
            if (!residues || residues.length === 0) return;
            const selection = { chain, resi: residues };
            this.viewer.addStyle(selection, {
                stick: { color: '#F59E0B', radius: 0.35 },
                cartoon: { color: '#F59E0B', opacity: 1.0 }
            });
            selections.push(selection);
        });

        if (selections.length === 0) {
            this.viewer.zoomTo();
        } else {
            this.viewer.zoomTo({ or: selections });
        }
        this.viewer.render();
    }

    resetCartoonStyles() {
        if (!this.viewer) return;
        this.viewer.removeAllSurfaces();
        this.structures.forEach(s => {
            this.viewer.setStyle({chain: s.mustangChain}, {cartoon: {color: s.color, opacity: 0.85}});
        });
        this.viewer.zoomTo();
        this.viewer.render();
    }

    reset() {
        this.structures = [];
        this.rmsdDf = null;
        this.currentRunId = null;
        if (this.viewer) {
            this.viewer.clear();
            this.viewer.render();
        }
        if (this.element) {
            this.element.querySelector("#ambient-placeholder").style.display = "flex";
            this._renderEmptyHUD();
        }
    }
}
