import { getAlignmentPdbUrl, getStructureFileUrl, fetchMutationTolerance, fetchAnnotations } from '../api';

// Qualitative palette for N-structure identity coloring. Deliberately avoids
// amber/#F59E0B (reserved for the residue-selection highlight) and the
// coral brand accent (reserved for UI chrome), so chain-identity color never
// collides with those other two semantic uses of color in the app.
const CHAIN_COLORS = ['#8B5CF6', '#06B6D4', '#EC4899', '#A3E635', '#FB923C', '#2DD4BF'];

function colorForIndex(i) {
    return CHAIN_COLORS[i % CHAIN_COLORS.length];
}

const STYLE_OPTIONS = [
    { key: 'cartoon', label: 'Cartoon' },
    { key: 'stick', label: 'Stick' },
    { key: 'sphere', label: 'Sphere' },
    { key: 'line', label: 'Line' },
];

const COLOR_SCHEME_OPTIONS = [
    { key: 'chain', label: 'Chain identity' },
    { key: 'secondary', label: 'Secondary structure' },
    { key: 'spectrum', label: 'Spectrum (N→C)' },
    { key: 'confidence', label: 'pLDDT Confidence' },
    { key: 'missense', label: 'Mutation tolerance (AlphaMissense)' },
    { key: 'domain', label: 'InterPro domains' },
];

// A distinct qualitative palette for domain coloring, deliberately
// different from CHAIN_COLORS above (a structure's own chain-identity
// color must stay visually distinguishable from "which domain a residue
// falls in," since a domain-colored view still shows per-structure
// context via the HUD, not via this palette) - and avoiding amber
// (#F59E0B, reserved for the residue-selection highlight) for the same
// reason CHAIN_COLORS does.
const DOMAIN_COLORS = ['#38BDF8', '#F472B6', '#84CC16', '#A78BFA', '#FB7185', '#2DD4BF', '#FBBF24', '#60A5FA'];

function colorForDomainIndex(i) {
    return DOMAIN_COLORS[i % DOMAIN_COLORS.length];
}

// Shared "highlighted/selected" amber semantic (matches .row-selected) -
// used for both residue-selection highlighting and the measurement tool's
// markers/connector, since both mean "the thing the user explicitly picked."
const HIGHLIGHT_COLOR = '#F59E0B';

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

    // Representation + coloring are orthogonal choices, both applied via
    // _styleFor() - switching either re-applies to whatever's currently
    // loaded. 'confidence' replaces the old standalone confidenceColoringEnabled
    // boolean; it's just one of four color schemes now.
    currentStyle = 'cartoon';
    currentColorScheme = 'chain';
    // Keyed by pdbId -> { [authorResi]: averagePathogenicity } once fetched
    // (see loadMissenseScores) - unlike pLDDT, this can't be read off
    // atoms already in the loaded model, so it's a separate lazy fetch
    // rather than something _missenseColorPartFor can compute on its own.
    missenseScoresByPdbId = {};
    // Keyed by pdbId -> { [authorResi]: colorHex }, one color per InterPro
    // domain, flattened from that structure's own annotation fetch (see
    // loadDomainColors) - unlike the existing "Highlight in 3D" button
    // (one domain at a time, everything else ghosted), this colors every
    // domain simultaneously and persistently, the same way pLDDT/missense
    // color the whole structure by a per-residue value.
    domainColorsByPdbId = {};

    // Click behavior branches on this - 'inspect' (default, informational
    // residue lookup) vs 'measure' (2-click atom-to-atom distance). Mutually
    // exclusive by construction so at most one kind of on-canvas label/shape
    // set exists at a time (see _clearMeasurement/_clearInspectLabel).
    interactionMode = 'inspect';
    inspectLabelHandle = null;
    measurePoints = [];
    measureHandles = [];

    isSpinning = false;

    render() {
        const div = document.createElement('div');
        // v4: the persistent viewer is the one "raised" surface in the shell
        // (panel-raised + shadow-panel, see style.css/tailwind.config.js) -
        // everything else stays flat, so this one soft lift reads as
        // deliberate rather than the whole UI looking inconsistently boxy.
        div.className = "flex-1 panel-raised shadow-panel rounded-lg flex flex-col overflow-hidden relative [&:fullscreen]:rounded-none";
        div.innerHTML = `
            <!-- Viewport Header -->
            <div class="px-4 py-3 border-b border-border flex flex-col gap-2">
                <div class="flex justify-between items-center">
                    <h3 class="font-body-md text-body-md font-semibold text-primary">Superposition Viewer</h3>
                    <div class="flex gap-2 items-center">
                        <details id="viewer-style-picker" class="group relative">
                            <summary class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors cursor-pointer select-none flex items-center gap-0.5 list-none [&::-webkit-details-marker]:hidden" title="Representation Style" aria-label="Representation Style">
                                <span class="material-symbols-outlined text-[18px]">view_in_ar</span>
                                <span class="material-symbols-outlined text-[14px] group-open:rotate-180 transition-transform">expand_more</span>
                            </summary>
                            <div class="absolute right-0 top-full mt-1 z-20 bg-surface border border-border rounded-md shadow-panel p-1 flex flex-col gap-0.5 min-w-[130px]">
                                ${STYLE_OPTIONS.map(o => `
                                    <button data-style="${o.key}" class="viewer-style-option text-left px-2 py-1 rounded-sm font-label-sm text-label-sm text-secondary hover:text-primary hover:bg-surface-raised transition-colors">${o.label}</button>
                                `).join('')}
                            </div>
                        </details>
                        <details id="viewer-colorscheme-picker" class="group relative">
                            <summary class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors cursor-pointer select-none flex items-center gap-0.5 list-none [&::-webkit-details-marker]:hidden" title="Color Scheme" aria-label="Color Scheme">
                                <span class="material-symbols-outlined text-[18px]">palette</span>
                                <span class="material-symbols-outlined text-[14px] group-open:rotate-180 transition-transform">expand_more</span>
                            </summary>
                            <div class="absolute right-0 top-full mt-1 z-20 bg-surface border border-border rounded-md shadow-panel p-1 flex flex-col gap-0.5 min-w-[170px]">
                                ${COLOR_SCHEME_OPTIONS.map(o => `
                                    <button data-scheme="${o.key}" class="viewer-colorscheme-option text-left px-2 py-1 rounded-sm font-label-sm text-label-sm text-secondary hover:text-primary hover:bg-surface-raised transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-secondary" ${o.key === 'confidence' ? 'disabled' : ''}>${o.label}</button>
                                `).join('')}
                            </div>
                        </details>
                        <button id="btn-toggle-surface" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Surface" aria-label="Toggle Surface">
                            <span class="material-symbols-outlined text-[18px]">blur_on</span>
                        </button>
                        <button id="btn-reset-view" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Reset View" aria-label="Reset View">
                            <span class="material-symbols-outlined text-[18px]">center_focus_strong</span>
                        </button>
                    </div>
                </div>
                <div class="flex justify-end gap-2 items-center">
                    <button id="btn-toggle-spin" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Auto-Spin" aria-label="Toggle Auto-Spin">
                        <span class="material-symbols-outlined text-[18px]">autorenew</span>
                    </button>
                    <button id="btn-toggle-fullscreen" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Fullscreen" aria-label="Toggle Fullscreen">
                        <span class="material-symbols-outlined text-[18px]">fullscreen</span>
                    </button>
                    <button id="btn-toggle-measure" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Toggle Measurement Mode" aria-label="Toggle Measurement Mode">
                        <span class="material-symbols-outlined text-[18px]">straighten</span>
                    </button>
                    <button id="btn-screenshot" class="p-1.5 rounded-md hover:bg-surface-raised text-secondary hover:text-primary transition-colors" title="Download Screenshot (PNG)" aria-label="Download Screenshot (PNG)">
                        <span class="material-symbols-outlined text-[18px]">photo_camera</span>
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
        this._updateStylePickerUI();
        this._updateColorSchemePopoverUI();
        return div;
    }

    init3Dmol() {
        const container = this.element.querySelector('#viewer-canvas-3dmol');
        if (!container) return;

        container.innerHTML = "";
        this.viewer = $3Dmol.createViewer(container, {
            defaultcolors: $3Dmol.rasmolElementColors,
            // Needed for #btn-screenshot's pngURI() capture - without this,
            // some browsers clear the WebGL drawing buffer between frames
            // and a screenshot taken outside the render callback comes back
            // blank.
            preserveDrawingBuffer: true
        });
        this.viewer.setBackgroundColor("#050608");

        window.addEventListener('resize', () => {
            if (this.viewer) this.viewer.resize();
        });
    }

    setupEventListeners() {
        const toggleSurfaceBtn = this.element.querySelector('#btn-toggle-surface');
        const resetViewBtn = this.element.querySelector('#btn-reset-view');

        this.element.querySelectorAll('.viewer-style-option').forEach(btn => {
            btn.addEventListener('click', () => {
                this.setStyleRepresentation(btn.dataset.style);
                this.element.querySelector('#viewer-style-picker').open = false;
            });
        });

        // No `if (btn.disabled) return` guard needed here - disabled buttons
        // never dispatch click events at all (browsers suppress it), so
        // this listener simply never fires for the disabled option.
        this.element.querySelectorAll('.viewer-colorscheme-option').forEach(btn => {
            btn.addEventListener('click', () => {
                this.setColorScheme(btn.dataset.scheme);
                this.element.querySelector('#viewer-colorscheme-picker').open = false;
            });
        });

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

        this.element.querySelector('#btn-toggle-spin').addEventListener('click', () => {
            this.toggleSpin();
        });

        this.element.querySelector('#btn-toggle-fullscreen').addEventListener('click', () => {
            if (!document.fullscreenElement) {
                this.element.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        });

        // Registered once (this.element persists for the app's lifetime -
        // only one Viewer3D instance is ever created) rather than per
        // toggle, so this never accumulates duplicate listeners.
        this.element.addEventListener('fullscreenchange', () => {
            const isFs = document.fullscreenElement === this.element;
            const btn = this.element.querySelector('#btn-toggle-fullscreen');
            btn.querySelector('.material-symbols-outlined').textContent = isFs ? 'fullscreen_exit' : 'fullscreen';
            btn.classList.toggle('bg-surface-raised', isFs);
            btn.classList.toggle('text-primary', isFs);
            // The container's actual pixel box changes asynchronously
            // relative to this event - defer a frame, then again shortly
            // after as a defensive fallback for slower browsers.
            requestAnimationFrame(() => { if (this.viewer) this.viewer.resize(); });
            setTimeout(() => { if (this.viewer) this.viewer.resize(); }, 150);
        });

        this.element.querySelector('#btn-toggle-measure').addEventListener('click', () => {
            this.toggleMeasureMode();
        });

        this.element.querySelector('#btn-screenshot').addEventListener('click', () => {
            this.downloadScreenshot();
        });
    }

    _updateStylePickerUI() {
        this.element?.querySelectorAll('.viewer-style-option').forEach(btn => {
            const active = btn.dataset.style === this.currentStyle;
            btn.classList.toggle('bg-surface-raised', active);
            btn.classList.toggle('text-primary', active);
        });
    }

    _updateColorSchemePopoverUI() {
        this.element?.querySelectorAll('.viewer-colorscheme-option').forEach(btn => {
            const scheme = btn.dataset.scheme;
            if (scheme === 'confidence') {
                btn.disabled = !this.hasPlddtStructures();
            }
            const active = scheme === this.currentColorScheme;
            btn.classList.toggle('bg-surface-raised', active);
            btn.classList.toggle('text-primary', active);
        });
    }

    setStyleRepresentation(style) {
        this.currentStyle = style;
        this._updateStylePickerUI();
        this.resetCartoonStyles();
    }

    async setColorScheme(scheme) {
        this.currentColorScheme = scheme;
        this._updateColorSchemePopoverUI();
        if (scheme === 'missense') {
            await this.loadMissenseScores();
            // The scheme may have changed again while the fetch was in
            // flight (a quick double-click) - don't clobber a newer choice.
            if (this.currentColorScheme !== 'missense') return;
        }
        if (scheme === 'domain') {
            await this.loadDomainColors();
            if (this.currentColorScheme !== 'domain') return;
        }
        this.resetCartoonStyles();
    }

    // Fetches the real AlphaMissense mutation-tolerance overlay for every
    // loaded structure that doesn't have one cached yet. A structure with
    // no resolvable UniProt accession (e.g. ESM Atlas) or with no
    // published AlphaMissense data correctly gets an empty map back, not
    // an error - _missenseColorPartFor then falls back to a neutral color
    // for it rather than crashing.
    async loadMissenseScores() {
        const missing = this.structures.filter(s => !(s.pdbId in this.missenseScoresByPdbId));
        if (missing.length === 0) return;

        await Promise.all(missing.map(async (structure) => {
            try {
                const data = await fetchMutationTolerance(structure.pdbId, structure.sourceChain !== '?' ? structure.sourceChain : undefined);
                this.missenseScoresByPdbId[structure.pdbId] = data.tolerance?.per_residue_average || {};
            } catch (err) {
                console.error(`Failed to load mutation tolerance for ${structure.pdbId}:`, err);
                this.missenseScoresByPdbId[structure.pdbId] = {};
            }
        }));
    }

    // Fetches this structure's own InterPro domain annotation (the same
    // /api/annotations call AnalyticsTab's Annotations panel already uses)
    // for every loaded structure that doesn't have a domain-color map
    // cached yet, and flattens each domain's highlight_chains into one
    // {[resi]: colorHex} lookup per structure. A structure with no
    // resolvable UniProt accession or no InterPro coverage correctly gets
    // an empty map back, not an error.
    async loadDomainColors() {
        const missing = this.structures.filter(s => !(s.pdbId in this.domainColorsByPdbId));
        if (missing.length === 0) return;

        await Promise.all(missing.map(async (structure) => {
            try {
                const chain = structure.sourceChain !== '?' ? structure.sourceChain : undefined;
                const data = await fetchAnnotations(structure.pdbId, chain);
                const domains = data.annotation?.domains || [];
                const colorMap = {};
                domains.forEach((domain, i) => {
                    const residues = domain.highlight_chains?.[chain] || Object.values(domain.highlight_chains || {})[0];
                    (residues || []).forEach(resi => {
                        colorMap[resi] = colorForDomainIndex(i);
                    });
                });
                this.domainColorsByPdbId[structure.pdbId] = colorMap;
            } catch (err) {
                console.error(`Failed to load domain annotation for ${structure.pdbId}:`, err);
                this.domainColorsByPdbId[structure.pdbId] = {};
            }
        }));
    }

    // Same colorfunc shape as _missenseColorPartFor, keyed by domain
    // membership instead of a numeric score - residues outside any known
    // domain fall back to the same neutral gray missense uses for
    // "no data at this residue."
    _domainColorPartFor(structure) {
        const colors = this.domainColorsByPdbId[structure.pdbId];
        if (!colors || Object.keys(colors).length === 0) {
            return { color: structure.color };
        }
        return {
            colorfunc: (atom) => colors[atom.resi] ?? '#4B5563',
        };
    }

    // 3Dmol's own internal rAF-driven rotation - not a custom setInterval or
    // animation loop, so this costs nothing beyond what 3Dmol already does
    // per rendered frame.
    toggleSpin() {
        if (!this.viewer) return;
        this.isSpinning = !this.isSpinning;
        this.viewer.spin(this.isSpinning ? 'y' : false);
        const btn = this.element.querySelector('#btn-toggle-spin');
        btn.classList.toggle('bg-surface-raised', this.isSpinning);
        btn.classList.toggle('text-primary', this.isSpinning);
    }

    downloadScreenshot() {
        if (!this.viewer) return;
        this.viewer.render();
        const dataUri = this.viewer.pngURI();
        const pdbIdPart = (this.structures.length > 0
            ? this.structures.map(s => s.pdbId).join('_')
            : 'structure'
        ).replace(/[^A-Za-z0-9_.-]/g, '_');
        const a = document.createElement('a');
        a.href = dataUri;
        a.download = `structscope_${pdbIdPart}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    _buildStructures(pdbIds, chainSelections) {
        return pdbIds.map((pdbId, i) => ({
            pdbId,
            mustangChain: String.fromCodePoint(65 + i),
            sourceChain: chainSelections?.[pdbId] || '?',
            color: colorForIndex(i)
        }));
    }

    // Central style builder every load/reset/ghost call site routes
    // through, instead of the old scattered hardcoded {cartoon: {...}}
    // literals - so switching representation or color scheme at any time
    // correctly re-applies to whatever's currently loaded.
    _sizeParamsFor(rep) {
        switch (rep) {
            case 'stick': return { radius: 0.25 };
            case 'sphere': return { scale: 0.3 };
            case 'line': return { linewidth: 2 };
            case 'cartoon':
            default: return {};
        }
    }

    // AlphaFold writes pLDDT on a 0-100 scale, ESM Atlas as a 0-1 fraction -
    // rather than assuming either, this reads the real min/max B-factor
    // already present on the loaded model's atoms for each structure, so
    // the color gradient is correct regardless of which convention the
    // file used. Falls back to plain identity color when there's no model
    // yet or no numeric B-factors (e.g. a non-pLDDT structure mixed into
    // the same alignment).
    _plddtColorPartFor(structure) {
        if (!this._isPlddtStructure(structure.pdbId)) {
            return { color: structure.color };
        }
        const model = this.viewer?.getModel();
        if (!model) return { color: structure.color };

        const atoms = model.selectedAtoms(this._selectorFor(structure));
        const values = atoms.map(a => a.b).filter(v => typeof v === 'number');
        if (values.length === 0) return { color: structure.color };

        const min = Math.min(...values);
        const max = Math.max(...values);
        return { colorscheme: { prop: 'b', gradient: 'roygb', min, max } };
    }

    // Green (tolerant/benign, low pathogenicity) -> red (intolerant/likely
    // pathogenic, high pathogenicity), a linear interpolation the same way
    // pLDDT's gradient is a built-in 3Dmol one - AlphaMissense scores have
    // no equivalent built-in 3Dmol colorscheme name, so this is computed
    // directly instead of going through `colorscheme`.
    _missenseColorForScore(score) {
        const t = Math.max(0, Math.min(1, score));
        const from = { r: 0x22, g: 0xC5, b: 0x5E };
        const to = { r: 0xB2, g: 0x3A, b: 0x3A };
        const mix = (a, b) => Math.round(a + (b - a) * t);
        return `#${[mix(from.r, to.r), mix(from.g, to.g), mix(from.b, to.b)]
            .map(v => v.toString(16).padStart(2, '0'))
            .join('')}`;
    }

    // Unlike pLDDT (already on every atom as B-factor), AlphaMissense
    // scores are a separate per-residue lookup fetched into
    // missenseScoresByPdbId (see loadMissenseScores) - `colorfunc` lets
    // 3Dmol color each atom from that lookup directly, no need to write a
    // synthetic per-atom property first.
    _missenseColorPartFor(structure) {
        const scores = this.missenseScoresByPdbId[structure.pdbId];
        if (!scores || Object.keys(scores).length === 0) {
            return { color: structure.color };
        }
        return {
            colorfunc: (atom) => {
                const score = scores[atom.resi];
                return score === undefined ? '#4B5563' : this._missenseColorForScore(score);
            },
        };
    }

    _colorPartFor(structure) {
        switch (this.currentColorScheme) {
            case 'secondary':
                return { colorscheme: 'ssPyMOL' };
            case 'spectrum':
                return { colorscheme: 'spectrum' };
            case 'confidence':
                return this._plddtColorPartFor(structure);
            case 'missense':
                return this._missenseColorPartFor(structure);
            case 'domain':
                return this._domainColorPartFor(structure);
            case 'chain':
            default:
                return { color: structure.color };
        }
    }

    // Blends a hex color toward the background color by fraction t (0 =
    // unchanged, 1 = fully background) - used as a ghosting fallback for
    // the `line` representation, whose WebGL line primitives may not
    // support `opacity` the same way mesh-based representations do.
    _dimColor(hex, t) {
        const bg = { r: 0x05, g: 0x06, b: 0x08 };
        const n = Number.parseInt(hex.replace('#', ''), 16);
        const r = (n >> 16) & 0xff;
        const g = (n >> 8) & 0xff;
        const b = n & 0xff;
        const mix = (c, bgC) => Math.round(c + (bgC - c) * t);
        return `#${[mix(r, bg.r), mix(g, bg.g), mix(b, bg.b)]
            .map(v => v.toString(16).padStart(2, '0'))
            .join('')}`;
    }

    _styleFor(structure, { opacity = 0.85 } = {}) {
        const rep = this.currentStyle;
        let colorPart = this._colorPartFor(structure);
        if (rep === 'line' && opacity < 0.85 && colorPart.color) {
            colorPart = { color: this._dimColor(colorPart.color, 1 - opacity / 0.85) };
        }
        return { [rep]: { ...colorPart, opacity, ...this._sizeParamsFor(rep) } };
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
                this.viewer.setStyle(this._selectorFor(s), this._styleFor(s));
            });

            this._wireClickHandler();
            this.viewer.zoomTo();
            this.viewer.render();
            this.isSurfaceVisible = false;
            this._updateColorSchemePopoverUI();
        } catch (err) {
            console.error("Error loading superposition coordinate data:", err);
        }
    }

    // Discover mode's query structure: a raw, non-aligned single structure -
    // no Mustang chain re-lettering exists for it, so (unlike
    // loadSuperposition, which styles one lettered chain per structure)
    // this styles every chain in the file with one color, and there is no
    // RMSD to report. mustangChain is null on the single structures-entry
    // since there's no aligned-chain concept to map residues into (residue
    // highlighting isn't wired up for this mode).
    async loadSingleStructure(pdbId) {
        if (!this.viewer) {
            this.init3Dmol();
        }

        this.currentRunId = null;
        this.structures = [{ pdbId, mustangChain: null, sourceChain: null, color: colorForIndex(0) }];
        this.rmsdDf = null;

        this.element.querySelector("#ambient-placeholder").style.display = "none";
        this._renderSingleStructureHUD(pdbId);

        try {
            const response = await fetch(getStructureFileUrl(pdbId));
            if (!response.ok) {
                throw new Error(`Failed to fetch structure file: ${response.statusText}`);
            }
            const pdbData = await response.text();

            this.viewer.clear();
            // /api/structure-file serves whatever raw format the structure
            // was actually downloaded in - AlphaFold DB (and SWISS-MODEL)
            // structures are real mmCIF ("data_..." header), not PDB, unlike
            // loadSuperposition's alignment.pdb (always Mustang's own PDB
            // output, hardcoded "pdb" below is correct there). Sniffing the
            // content here avoids silently feeding mmCIF into 3Dmol's PDB
            // parser, which adds zero atoms with no error - a blank viewer,
            // not a crash.
            const format = pdbData.trimStart().startsWith('data_') ? 'cif' : 'pdb';
            this.viewer.addModel(pdbData, format);
            this.viewer.setStyle({}, this._styleFor(this.structures[0]));

            this._wireClickHandler();
            this.viewer.zoomTo();
            this.viewer.render();
            this.isSurfaceVisible = false;
            this._updateColorSchemePopoverUI();
        } catch (err) {
            console.error("Error loading single structure:", err);
        }
    }

    // (Re-)registered after every addModel/clear() call, not just once in
    // init3Dmol() - a fresh model can drop clickable bindings set on the
    // previous one. Branches on interactionMode rather than needing two
    // separate click handlers.
    _wireClickHandler() {
        if (!this.viewer) return;
        this.viewer.setClickable({}, true, (atom) => {
            if (this.interactionMode === 'measure') {
                this._handleMeasureClick(atom);
            } else {
                this._handleInspectClick(atom);
            }
        });
    }

    _renderSingleStructureHUD(pdbId) {
        const legend = this.element.querySelector('#hud-structure-legend');
        const rmsdBox = this.element.querySelector('#hud-rmsd-container');
        if (legend) legend.innerHTML = `
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full shrink-0" style="background-color: ${colorForIndex(0)};"></div>
                <span class="font-label-sm text-label-sm text-primary font-mono truncate">${pdbId}</span>
            </div>
        `;
        if (rmsdBox) rmsdBox.innerHTML = `
            <span class="font-label-sm text-label-sm text-secondary uppercase">Single Structure</span>
        `;
    }

    // AlphaFold ("AF-") and ESM Atlas ("ESM-") structures encode per-residue
    // pLDDT confidence in the B-factor column - mirrors the backend's own
    // is_plddt_model check (pdb_manager.py). Mustang's alignment output
    // preserves B-factor unmodified (confirmed by reading Mustang's own
    // source), so the loaded model already carries real pLDDT values with
    // no extra backend plumbing needed.
    _isPlddtStructure(pdbId) {
        const upper = (pdbId || '').toUpperCase();
        return upper.startsWith('AF-') || upper.startsWith('ESM-');
    }

    hasPlddtStructures() {
        return this.structures.some(s => this._isPlddtStructure(s.pdbId));
    }

    // A structure with no mustangChain (a single, non-aligned structure -
    // see loadSingleStructure) has no per-structure chain lettering to
    // select by, so it's styled as the whole model instead.
    _selectorFor(structure) {
        return structure.mustangChain ? { chain: structure.mustangChain } : {};
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
            this.viewer.setStyle(this._selectorFor(s), this._styleFor(s, { opacity: 0.3 }));
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

        // Reset all base styles to ghost
        this.structures.forEach(s => {
            this.viewer.setStyle(this._selectorFor(s), this._styleFor(s, { opacity: 0.35 }));
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

        // Selection highlight uses the shared amber "tertiary" semantic
        const selection = {chain: mustangChain, resi: alignedResi};
        this.viewer.addStyle(selection, {
            stick: {color: HIGHLIGHT_COLOR, radius: 0.45},
            sphere: {color: HIGHLIGHT_COLOR, scale: 1.3},
            cartoon: {color: HIGHLIGHT_COLOR, opacity: 1.0}
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

        // _selectorFor(), not a bare {chain: s.mustangChain} - a Discover-
        // mode single structure has mustangChain: null (no Mustang re-
        // lettering to key off of), and 3Dmol's selection syntax needs an
        // empty selector ({}, "everything") there rather than a literal
        // null chain value, which wouldn't reliably match anything.
        this.structures.forEach(s => {
            this.viewer.setStyle(this._selectorFor(s), this._styleFor(s, { opacity: 0.35 }));
        });

        const selections = [];
        Object.entries(chainMapping || {}).forEach(([chain, residues]) => {
            if (!residues || residues.length === 0) return;
            const selection = { chain, resi: residues };
            this.viewer.addStyle(selection, {
                stick: { color: HIGHLIGHT_COLOR, radius: 0.35 },
                cartoon: { color: HIGHLIGHT_COLOR, opacity: 1.0 }
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
        this.structures.forEach(s => {
            this.viewer.setStyle(this._selectorFor(s), this._styleFor(s));
        });
        this.viewer.zoomTo();
        this.viewer.render();
    }

    // Inspect mode: purely informational, single reusable label - never
    // disturbs camera/style state. At most one inspect label ever exists.
    _handleInspectClick(atom) {
        if (!this.viewer) return;
        if (this.inspectLabelHandle) {
            this.viewer.removeLabel(this.inspectLabelHandle);
            this.inspectLabelHandle = null;
        }
        if (!atom) return;

        const chainPart = atom.chain ? ` · Chain ${atom.chain}` : '';
        const text = `${atom.resn} ${atom.resi}${chainPart}`;
        this.inspectLabelHandle = this.viewer.addLabel(text, {
            position: { x: atom.x, y: atom.y, z: atom.z },
            backgroundColor: '#111318',
            backgroundOpacity: 0.85,
            fontColor: '#F5F5F5',
            fontSize: 12,
            borderThickness: 0
        });
        this.viewer.render();
    }

    _clearInspectLabel() {
        if (!this.viewer || !this.inspectLabelHandle) return;
        this.viewer.removeLabel(this.inspectLabelHandle);
        this.inspectLabelHandle = null;
    }

    // 2-click atom-to-atom distance measurement. A 3rd click clears the
    // completed pair and starts fresh, rather than requiring a separate
    // "clear" affordance - keeps the header control count down.
    _handleMeasureClick(atom) {
        if (!this.viewer || !atom) return;

        if (this.measurePoints.length >= 2) {
            this._clearMeasurement();
        }

        if (this.measurePoints.length === 0) {
            this.measurePoints.push(atom);
            const handle = this.viewer.addLabel('A', {
                position: { x: atom.x, y: atom.y, z: atom.z },
                backgroundColor: HIGHLIGHT_COLOR,
                backgroundOpacity: 0.9,
                fontColor: '#111318',
                fontSize: 11,
                borderThickness: 0
            });
            this.measureHandles.push(handle);
            this.viewer.render();
            return;
        }

        // 2nd click - complete the pair.
        const [a] = this.measurePoints;
        const b = atom;
        this.measurePoints.push(b);

        const distance = Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

        if (this.viewer.addLine) {
            this.measureHandles.push(this.viewer.addLine({
                start: { x: a.x, y: a.y, z: a.z },
                end: { x: b.x, y: b.y, z: b.z },
                color: HIGHLIGHT_COLOR,
                dashed: true
            }));
        } else if (this.viewer.addCylinder) {
            this.measureHandles.push(this.viewer.addCylinder({
                start: { x: a.x, y: a.y, z: a.z },
                end: { x: b.x, y: b.y, z: b.z },
                radius: 0.05,
                color: HIGHLIGHT_COLOR,
                dashed: true
            }));
        }

        const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
        this.measureHandles.push(this.viewer.addLabel(`${distance.toFixed(2)} Å`, {
            position: mid,
            backgroundColor: '#111318',
            backgroundOpacity: 0.85,
            fontColor: '#F5F5F5',
            fontSize: 12,
            borderThickness: 0
        }));

        this.viewer.render();
    }

    _clearMeasurement() {
        if (this.viewer) {
            this.viewer.removeAllLabels();
            this.viewer.removeAllShapes();
        }
        this.measurePoints = [];
        this.measureHandles = [];
    }

    toggleMeasureMode() {
        this.interactionMode = this.interactionMode === 'measure' ? 'inspect' : 'measure';
        this._clearMeasurement();
        this._clearInspectLabel();
        const btn = this.element.querySelector('#btn-toggle-measure');
        const isMeasuring = this.interactionMode === 'measure';
        btn.classList.toggle('bg-surface-raised', isMeasuring);
        btn.classList.toggle('text-primary', isMeasuring);
        if (this.viewer) this.viewer.render();
    }

    reset() {
        this.structures = [];
        this.rmsdDf = null;
        this.currentRunId = null;
        this.currentStyle = 'cartoon';
        this.currentColorScheme = 'chain';
        this.missenseScoresByPdbId = {};
        this.domainColorsByPdbId = {};
        this.interactionMode = 'inspect';
        this.measurePoints = [];
        this.measureHandles = [];
        this.inspectLabelHandle = null;
        if (this.isSpinning && this.viewer) {
            this.viewer.spin(false);
        }
        this.isSpinning = false;
        if (this.viewer) {
            this.viewer.clear();
            this.viewer.render();
        }
        if (this.element) {
            this.element.querySelector("#ambient-placeholder").style.display = "flex";
            this._renderEmptyHUD();
            this._updateStylePickerUI();
            this._updateColorSchemePopoverUI();
            const spinBtn = this.element.querySelector('#btn-toggle-spin');
            spinBtn.classList.remove('bg-surface-raised', 'text-primary');
            const measureBtn = this.element.querySelector('#btn-toggle-measure');
            measureBtn.classList.remove('bg-surface-raised', 'text-primary');
        }
    }
}
