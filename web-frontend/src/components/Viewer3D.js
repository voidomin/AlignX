import { getAlignmentPdbUrl } from '../api';

export class Viewer3D {
    constructor() {
        this.element = null;
        this.viewer = null;
        this.currentRunId = null;
        this.isSurfaceVisible = false;
        this.activeSelections = {
            refId: '--',
            targetId: '--',
            refChain: '--',
            targetChain: '--'
        };
        this.rmsd = '--';
    }

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

                <!-- HUD Labels -->
                <div class="absolute top-4 left-4 bg-surface border border-border px-3 py-1.5 rounded-md flex flex-col gap-1.5 z-10">
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-[#8B5CF6]"></div>
                        <span id="hud-reference-label" class="font-label-sm text-label-sm text-primary font-mono">Reference: --</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-[#06B6D4]"></div>
                        <span id="hud-target-label" class="font-label-sm text-label-sm text-primary font-mono">Target: --</span>
                    </div>
                </div>

                <!-- RMSD Overlay -->
                <div class="absolute top-4 right-4 bg-surface border border-border p-3 rounded-md flex flex-col items-end z-10 font-mono">
                    <span class="font-label-sm text-label-sm text-secondary uppercase">Global RMSD</span>
                    <span id="rmsd-value-hud" class="font-headline-md text-headline-md text-success font-semibold">-- Å</span>
                </div>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
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

    async loadSuperposition(runId, refId, targetId, refChain, targetChain, rmsdValue) {
        if (!this.viewer) {
            this.init3Dmol();
        }
        
        this.currentRunId = runId;
        this.activeSelections = { refId, targetId, refChain, targetChain };
        this.rmsd = rmsdValue;

        // Hide spinner
        this.element.querySelector("#ambient-placeholder").style.display = "none";
        
        // Update HUD
        this.element.querySelector("#hud-reference-label").innerText = `Reference: ${refId} (Chain ${refChain})`;
        this.element.querySelector("#hud-target-label").innerText = `Target: ${targetId} (Chain ${targetChain})`;
        this.element.querySelector("#rmsd-value-hud").innerText = `${parseFloat(rmsdValue).toFixed(2)} Å`;

        try {
            const response = await fetch(getAlignmentPdbUrl(runId));
            if (!response.ok) {
                throw new Error(`Failed to fetch alignment PDB: ${response.statusText}`);
            }
            const pdbData = await response.text();
            
            this.viewer.clear();
            this.viewer.addModel(pdbData, "pdb");
            
            // Reference (Chain A) -> Violet
            this.viewer.setStyle({chain: 'A'}, {cartoon: {color: '#8B5CF6', opacity: 0.85}});
            
            // Target (Chain B) -> Cyan
            this.viewer.setStyle({chain: 'B'}, {cartoon: {color: '#06B6D4', opacity: 0.85}});
            
            this.viewer.zoomTo();
            this.viewer.render();
            this.isSurfaceVisible = false;
        } catch (err) {
            console.error("Error loading superposition coordinate data:", err);
        }
    }

    showLigandBindingSite(ligandId, interactions) {
        if (!this.viewer) return;
        
        // Reset base model style to faded ghost cartoon
        this.viewer.setStyle({chain: 'A'}, {cartoon: {color: '#8B5CF6', opacity: 0.3}});
        this.viewer.setStyle({chain: 'B'}, {cartoon: {color: '#06B6D4', opacity: 0.3}});

        // Highlight ligand as neon green sticks
        const parts = ligandId.split("_");
        const name = parts.slice(0, -2).join("_");
        const chain = parts[parts.length - 2];
        const resi = parseInt(parts[parts.length - 1]);
        
        const ligandSelection = {chain: chain, resi: resi, resn: name};
        this.viewer.addStyle(ligandSelection, {
            stick: {colorscheme: 'greenCarbon', radius: 0.35}
        });

        // Highlight pocket residues in bright white/purple
        interactions.forEach(i => {
            this.viewer.addStyle({chain: i.chain, resi: parseInt(i.resi)}, {
                stick: {colorscheme: 'purpleCarbon', radius: 0.25},
                cartoon: {color: i.chain === 'A' ? '#8B5CF6' : '#06B6D4', opacity: 1.0}
            });
        });

        this.viewer.zoomTo({chain: chain, resi: resi});
        this.viewer.render();
    }

    highlightResidue(chain, resi) {
        if (!this.viewer) return;

        // Reset all cartoon styles to ghost
        this.viewer.setStyle({chain: 'A'}, {cartoon: {color: '#8B5CF6', opacity: 0.35}});
        this.viewer.setStyle({chain: 'B'}, {cartoon: {color: '#06B6D4', opacity: 0.35}});

        // Selection highlight uses the amber "tertiary" semantic (matches .row-selected)
        const selection = {chain: chain, resi: parseInt(resi)};
        this.viewer.addStyle(selection, {
            stick: {color: '#F59E0B', radius: 0.45},
            sphere: {color: '#F59E0B', scale: 1.3},
            cartoon: {color: '#F59E0B', opacity: 1.0}
        });

        this.viewer.zoomTo(selection);
        this.viewer.render();
    }

    resetCartoonStyles() {
        if (!this.viewer) return;
        this.viewer.removeAllSurfaces();
        this.viewer.setStyle({chain: 'A'}, {cartoon: {color: '#8B5CF6', opacity: 0.85}});
        this.viewer.setStyle({chain: 'B'}, {cartoon: {color: '#06B6D4', opacity: 0.85}});
        this.viewer.zoomTo();
        this.viewer.render();
    }
}
