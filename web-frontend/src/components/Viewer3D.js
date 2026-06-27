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
        div.className = "flex-1 glass-panel rounded-xl flex flex-col overflow-hidden relative shadow-2xl";
        div.innerHTML = `
            <!-- Viewport Header -->
            <div class="px-4 py-3 border-b border-white/10 flex justify-between items-center bg-black/20 z-10">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-gradient-start text-[20px]">view_in_ar</span>
                    <h3 class="font-body-md text-body-md font-semibold text-text-primary">Superposition Viewer</h3>
                </div>
                <div class="flex gap-2">
                    <button id="btn-toggle-surface" class="p-1.5 rounded bg-white/5 hover:bg-white/10 text-text-secondary transition-colors" title="Toggle Surface">
                        <span class="material-symbols-outlined text-[18px]">blur_on</span>
                    </button>
                    <button id="btn-reset-view" class="p-1.5 rounded bg-white/5 hover:bg-white/10 text-text-secondary transition-colors" title="Reset View">
                        <span class="material-symbols-outlined text-[18px]">center_focus_strong</span>
                    </button>
                </div>
            </div>

            <!-- 3D Canvas Area -->
            <div id="3d-canvas-container" class="flex-grow relative bg-[#050608] overflow-hidden min-h-[300px]">
                <!-- 3Dmol viewer div (positioned absolutely to fill the container) -->
                <div id="3dmol-viewer-canvas" class="w-full h-full absolute inset-0 z-0"></div>
                
                <!-- Overlay HUD Elements (z-10 to stay on top of the 3D canvas) -->
                <div class="absolute inset-0 z-10 pointer-events-none">
                    <!-- Decorative scientific grid background -->
                    <div class="absolute inset-0 opacity-20" style="background-image: radial-gradient(circle at center, rgba(255,255,255,0.1) 1px, transparent 1px); background-size: 24px 24px;"></div>
                    <!-- Central Reticle -->
                    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 border border-white/5 rounded-full flex items-center justify-center">
                        <div class="w-1 h-1 bg-white/30 rounded-full"></div>
                    </div>
                </div>

                <!-- Abstract representation of superimposed proteins (shown only before PDB loading) -->
                <div id="ambient-placeholder" class="absolute inset-0 flex items-center justify-center pointer-events-none z-5">
                    <!-- Protein A (Deep Purple) -->
                    <div class="w-64 h-64 border-4 border-[#8B5CF6]/40 rounded-[40%_60%_70%_30%] animate-[spin_20s_linear_infinite] filter blur-[2px] opacity-70"></div>
                    <!-- Protein B (Neon Cyan) -->
                    <div class="absolute w-56 h-56 border-4 border-[#06B6D4]/50 rounded-[30%_70%_40%_60%] animate-[spin_15s_linear_reverse_infinite] filter blur-[1px]"></div>
                    <!-- Alignment visual connection lines -->
                    <svg class="absolute inset-0 w-full h-full opacity-30" preserveaspectratio="none" viewbox="0 0 100 100">
                        <line stroke="#f9bd22" stroke-dasharray="1 1" stroke-width="0.2" x1="30" x2="60" y1="40" y2="60"></line>
                        <line stroke="#f9bd22" stroke-dasharray="1 1" stroke-width="0.2" x1="45" x2="55" y1="20" y2="70"></line>
                    </svg>
                </div>
                
                <!-- Glassmorphic HUD Labels -->
                <div class="absolute top-4 left-4 bg-[#11141c]/80 backdrop-blur-md border border-white/10 px-3 py-1.5 rounded-lg shadow-lg flex flex-col gap-1.5 z-10">
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-[#8B5CF6] shadow-[0_0_8px_#8B5CF6]"></div>
                        <span id="hud-reference-label" class="font-label-sm text-label-sm text-text-primary font-mono">Reference: --</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <div class="w-2 h-2 rounded-full bg-[#06B6D4] shadow-[0_0_8px_#06B6D4]"></div>
                        <span id="hud-target-label" class="font-label-sm text-label-sm text-text-primary font-mono">Target: --</span>
                    </div>
                </div>
                
                <!-- RMSD Overlay -->
                <div class="absolute top-4 right-4 bg-black/60 backdrop-blur-md border border-white/10 p-3 rounded-lg flex flex-col items-end z-10 font-mono">
                    <span class="font-label-sm text-label-sm text-text-secondary uppercase">Global RMSD</span>
                    <span id="rmsd-value-hud" class="font-headline-md text-headline-md text-success font-semibold">-- Å</span>
                </div>
            </div>
        `;
        this.element = div;
        this.setupEventListeners();
        return div;
    }

    init3Dmol() {
        const container = this.element.querySelector('#3dmol-viewer-canvas');
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
            
            // Reference (Chain A / MODEL 1) -> Violet
            this.viewer.setStyle({chain: 'A'}, {cartoon: {color: '#8B5CF6', opacity: 0.85}});
            this.viewer.setStyle({model: 0}, {cartoon: {color: '#8B5CF6', opacity: 0.85}});
            
            // Target (Chain B / MODEL 2) -> Cyan
            this.viewer.setStyle({chain: 'B'}, {cartoon: {color: '#06B6D4', opacity: 0.85}});
            this.viewer.setStyle({model: 1}, {cartoon: {color: '#06B6D4', opacity: 0.85}});
            
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

        // Add stick and sphere highlight in Neon Yellow/Gold '#f9bd22'
        const selection = {chain: chain, resi: parseInt(resi)};
        this.viewer.addStyle(selection, {
            stick: {color: '#f9bd22', radius: 0.45},
            sphere: {color: '#f9bd22', scale: 1.3},
            cartoon: {color: '#f9bd22', opacity: 1.0}
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
