import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Viewer3D } from './Viewer3D.js';

vi.mock('../api.js', () => ({
    getAlignmentPdbUrl: vi.fn((runId) => `http://mock/results/${runId}/alignment.pdb`),
    getStructureFileUrl: vi.fn((pdbId) => `http://mock/api/structure-file?pdb_id=${pdbId}`),
    fetchMutationTolerance: vi.fn(),
    fetchAnnotations: vi.fn(),
}));

import { fetchMutationTolerance, fetchAnnotations } from '../api.js';

function makeMockViewer() {
    return {
        setStyle: vi.fn(),
        addStyle: vi.fn(),
        setBackgroundColor: vi.fn(),
        addModel: vi.fn(),
        clear: vi.fn(),
        render: vi.fn(),
        resize: vi.fn(),
        zoomTo: vi.fn(),
        spin: vi.fn(),
        pngURI: vi.fn(() => 'data:image/png;base64,mock'),
        setClickable: vi.fn(),
        addLabel: vi.fn(() => ({ id: Math.random() })),
        removeLabel: vi.fn(),
        removeAllLabels: vi.fn(),
        addLine: vi.fn(() => ({ id: Math.random() })),
        removeAllShapes: vi.fn(),
        addSurface: vi.fn(),
        removeAllSurfaces: vi.fn(),
        getModel: vi.fn(() => ({ selectedAtoms: vi.fn(() => []) })),
    };
}

let mockViewer;

beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, text: async () => 'MOCK PDB DATA' });
    fetchMutationTolerance.mockResolvedValue({ tolerance: { accession: null, per_residue_average: {} } });
    fetchAnnotations.mockResolvedValue({ annotation: { domains: [] } });
    window.$3Dmol = {
        createViewer: vi.fn(() => {
            mockViewer = makeMockViewer();
            return mockViewer;
        }),
        rasmolElementColors: {},
        SurfaceType: { SAS: 'SAS' },
    };
    HTMLElement.prototype.requestFullscreen = vi.fn();
    document.exitFullscreen = vi.fn();
});

afterEach(() => {
    delete window.$3Dmol;
    vi.restoreAllMocks();
    vi.useRealTimers();
});

function makeViewer() {
    const v = new Viewer3D();
    v.render();
    v.init3Dmol();
    return v;
}

async function loadTwoStructures(v) {
    await v.loadSuperposition('run_1', ['4RLT', '3UG9'], { '4RLT': 'A', '3UG9': 'B' }, null);
}

describe('Viewer3D', () => {
    it('renders all expected control ids', () => {
        const v = makeViewer();
        [
            '#viewer-style-picker', '#viewer-colorscheme-picker', '#btn-toggle-surface', '#btn-reset-view',
            '#btn-toggle-spin', '#btn-toggle-fullscreen', '#btn-toggle-measure', '#btn-screenshot',
            '#viewer-canvas-3dmol', '#ambient-placeholder', '#hud-structure-legend', '#hud-rmsd-container',
        ].forEach(sel => {
            expect(v.element.querySelector(sel), `missing ${sel}`).toBeTruthy();
        });
    });

    it('init3Dmol passes preserveDrawingBuffer: true', () => {
        makeViewer();
        expect(window.$3Dmol.createViewer).toHaveBeenCalledWith(
            expect.anything(),
            expect.objectContaining({ preserveDrawingBuffer: true })
        );
    });

    describe('loadSuperposition / loadSingleStructure regression', () => {
        it('builds structures, loads the model, and styles each chain', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            expect(v.structures).toHaveLength(2);
            expect(mockViewer.addModel).toHaveBeenCalledWith('MOCK PDB DATA', 'pdb');
            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, expect.objectContaining({ cartoon: expect.any(Object) }));
            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'B' }, expect.objectContaining({ cartoon: expect.any(Object) }));
            expect(mockViewer.zoomTo).toHaveBeenCalled();
            expect(mockViewer.render).toHaveBeenCalled();
        });

        it('loadSingleStructure uses an empty (whole-model) selector', async () => {
            const v = makeViewer();
            await v.loadSingleStructure('4RLT');

            expect(v.structures).toEqual([expect.objectContaining({ pdbId: '4RLT', mustangChain: null })]);
            expect(mockViewer.setStyle).toHaveBeenCalledWith({}, expect.objectContaining({ cartoon: expect.any(Object) }));
        });

        it('loadSingleStructure adds the model as "pdb" format for real PDB text', async () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: true, text: async () => 'HEADER\nATOM      1  N   MET A   1\n' });
            const v = makeViewer();
            await v.loadSingleStructure('4RLT');

            expect(mockViewer.addModel).toHaveBeenCalledWith(expect.stringContaining('ATOM'), 'pdb');
        });

        it('loadSingleStructure adds the model as "cif" format for a real mmCIF file (AlphaFold-sourced structures)', async () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: true, text: async () => 'data_AF-P69905-F1\n#\n_entry.id AF-P69905-F1\n' });
            const v = makeViewer();
            await v.loadSingleStructure('AF-P69905-F1');

            expect(mockViewer.addModel).toHaveBeenCalledWith(expect.stringContaining('data_'), 'cif');
        });
    });

    describe('style switcher', () => {
        it('renders 4 options and defaults to cartoon active', () => {
            const v = makeViewer();
            const options = v.element.querySelectorAll('.viewer-style-option');
            expect(options).toHaveLength(4);
            const cartoonBtn = v.element.querySelector('.viewer-style-option[data-style="cartoon"]');
            expect(cartoonBtn.classList.contains('bg-surface-raised')).toBe(true);
        });

        it('selecting a style updates currentStyle, re-applies to every loaded structure, and closes the popover', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.setStyle.mockClear();

            const details = v.element.querySelector('#viewer-style-picker');
            details.open = true;
            v.element.querySelector('.viewer-style-option[data-style="stick"]').click();

            expect(v.currentStyle).toBe('stick');
            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, expect.objectContaining({ stick: expect.any(Object) }));
            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'B' }, expect.objectContaining({ stick: expect.any(Object) }));
            expect(details.open).toBe(false);
        });
    });

    describe('color schemes', () => {
        it('selecting secondary structure sets colorscheme: ssPyMOL', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.setStyle.mockClear();

            v.element.querySelector('.viewer-colorscheme-option[data-scheme="secondary"]').click();

            expect(v.currentColorScheme).toBe('secondary');
            expect(mockViewer.setStyle).toHaveBeenCalledWith(expect.anything(), { cartoon: expect.objectContaining({ colorscheme: 'ssPyMOL' }) });
        });

        it('selecting spectrum sets colorscheme: spectrum', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            v.element.querySelector('.viewer-colorscheme-option[data-scheme="spectrum"]').click();

            expect(v.currentColorScheme).toBe('spectrum');
            expect(mockViewer.setStyle).toHaveBeenCalledWith(expect.anything(), { cartoon: expect.objectContaining({ colorscheme: 'spectrum' }) });
        });

        it('the confidence option is disabled with no pLDDT structures, and clicking it while disabled has no effect', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            const confBtn = v.element.querySelector('.viewer-colorscheme-option[data-scheme="confidence"]');
            expect(confBtn.disabled).toBe(true);
            confBtn.click();
            expect(v.currentColorScheme).toBe('chain');
        });

        it('the confidence option is enabled once an AF- structure is loaded', async () => {
            const v = makeViewer();
            await v.loadSuperposition('run_1', ['AF-P69905-F1', '3UG9'], {}, null);

            const confBtn = v.element.querySelector('.viewer-colorscheme-option[data-scheme="confidence"]');
            expect(confBtn.disabled).toBe(false);
        });
    });

    describe('auto-spin', () => {
        it('toggles viewer.spin("y") / spin(false) and active-state classes', () => {
            const v = makeViewer();
            const btn = v.element.querySelector('#btn-toggle-spin');

            btn.click();
            expect(mockViewer.spin).toHaveBeenCalledWith('y');
            expect(v.isSpinning).toBe(true);
            expect(btn.classList.contains('bg-surface-raised')).toBe(true);

            btn.click();
            expect(mockViewer.spin).toHaveBeenCalledWith(false);
            expect(v.isSpinning).toBe(false);
            expect(btn.classList.contains('bg-surface-raised')).toBe(false);
        });
    });

    describe('fullscreen', () => {
        it('clicking the button calls requestFullscreen when not already fullscreen', () => {
            const v = makeViewer();
            v.element.querySelector('#btn-toggle-fullscreen').click();
            expect(v.element.requestFullscreen).toHaveBeenCalled();
        });

        it('a fullscreenchange event flips the icon/state and triggers a resize', async () => {
            vi.useFakeTimers();
            const v = makeViewer();
            Object.defineProperty(document, 'fullscreenElement', { value: v.element, configurable: true });

            v.element.dispatchEvent(new Event('fullscreenchange'));
            const btn = v.element.querySelector('#btn-toggle-fullscreen');
            expect(btn.querySelector('.material-symbols-outlined').textContent).toBe('fullscreen_exit');
            expect(btn.classList.contains('bg-surface-raised')).toBe(true);

            await vi.runAllTimersAsync();
            expect(mockViewer.resize).toHaveBeenCalled();

            Object.defineProperty(document, 'fullscreenElement', { value: null, configurable: true });
        });
    });

    describe('click-to-inspect', () => {
        it('registers setClickable after loading a structure', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            expect(mockViewer.setClickable).toHaveBeenCalledWith({}, true, expect.any(Function));
        });

        it('invoking the click callback in inspect mode (default) adds exactly one label with residue identity', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            const callback = mockViewer.setClickable.mock.calls.at(-1)[2];
            callback({ resn: 'ALA', resi: 12, chain: 'A', x: 1, y: 2, z: 3 });

            expect(mockViewer.addLabel).toHaveBeenCalledWith(
                expect.stringContaining('ALA'),
                expect.objectContaining({ position: { x: 1, y: 2, z: 3 } })
            );
            expect(mockViewer.addLabel.mock.calls[0][0]).toContain('12');
            expect(mockViewer.addLabel.mock.calls[0][0]).toContain('A');
        });

        it('a second click removes the previous label instead of stacking', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            const callback = mockViewer.setClickable.mock.calls.at(-1)[2];

            callback({ resn: 'ALA', resi: 12, chain: 'A', x: 1, y: 2, z: 3 });
            callback({ resn: 'GLY', resi: 45, chain: 'B', x: 4, y: 5, z: 6 });

            expect(mockViewer.removeLabel).toHaveBeenCalledTimes(1);
            expect(mockViewer.addLabel).toHaveBeenCalledTimes(2);
        });
    });

    describe('screenshot', () => {
        it('clicking the button calls pngURI() and triggers a download with the expected filename', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

            v.element.querySelector('#btn-screenshot').click();

            expect(mockViewer.pngURI).toHaveBeenCalled();
            expect(clickSpy).toHaveBeenCalled();
            clickSpy.mockRestore();
        });
    });

    describe('measurement tool', () => {
        function getClickCallback() {
            return mockViewer.setClickable.mock.calls.at(-1)[2];
        }

        it('toggling the button sets interactionMode to measure', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.element.querySelector('#btn-toggle-measure').click();
            expect(v.interactionMode).toBe('measure');
        });

        it('first click stores a marker and does not draw a line yet', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.element.querySelector('#btn-toggle-measure').click();
            const callback = getClickCallback();

            callback({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });

            expect(v.measurePoints).toHaveLength(1);
            expect(mockViewer.addLabel).toHaveBeenCalledWith('A', expect.any(Object));
            expect(mockViewer.addLine).not.toHaveBeenCalled();
        });

        it('second click computes the correct distance and draws a connector + midpoint label', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.element.querySelector('#btn-toggle-measure').click();
            const callback = getClickCallback();

            callback({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
            callback({ resn: 'GLY', resi: 2, chain: 'A', x: 3, y: 4, z: 0 });

            expect(v.measurePoints).toHaveLength(2);
            expect(mockViewer.addLine).toHaveBeenCalledTimes(1);
            const distanceLabelText = mockViewer.addLabel.mock.calls.find(c => c[0].includes('Å'))[0];
            expect(distanceLabelText).toContain('5.00');
        });

        it('a third click clears the completed pair and starts a fresh measurement', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.element.querySelector('#btn-toggle-measure').click();
            const callback = getClickCallback();

            callback({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
            callback({ resn: 'GLY', resi: 2, chain: 'A', x: 3, y: 4, z: 0 });
            mockViewer.removeAllLabels.mockClear();
            mockViewer.removeAllShapes.mockClear();

            callback({ resn: 'SER', resi: 3, chain: 'A', x: 9, y: 9, z: 9 });

            expect(mockViewer.removeAllLabels).toHaveBeenCalled();
            expect(mockViewer.removeAllShapes).toHaveBeenCalled();
            expect(v.measurePoints).toHaveLength(1);
            expect(v.measurePoints[0].resi).toBe(3);
        });

        it('toggling measure mode off clears in-progress measurement state', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            const measureBtn = v.element.querySelector('#btn-toggle-measure');
            measureBtn.click();
            getClickCallback()({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
            expect(v.measurePoints).toHaveLength(1);

            measureBtn.click();

            expect(v.interactionMode).toBe('inspect');
            expect(v.measurePoints).toHaveLength(0);
        });

        it('while in measure mode, clicks do not add inspect labels', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.element.querySelector('#btn-toggle-measure').click();
            mockViewer.addLabel.mockClear();

            getClickCallback()({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });

            expect(v.inspectLabelHandle).toBeNull();
        });
    });

    describe('existing ghost/highlight behavior', () => {
        it('showLigandBindingSite ghosts all structures then highlights contact residues', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.setStyle.mockClear();

            v.showLigandBindingSite(0, 'HEM_A_1', [{ aligned_resi: 5 }, { aligned_resi: 8 }]);

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, expect.objectContaining({ cartoon: expect.objectContaining({ opacity: 0.3 }) }));
            expect(mockViewer.addStyle).toHaveBeenCalledTimes(2);
            expect(mockViewer.zoomTo).toHaveBeenCalledWith({ chain: 'A', resi: [5, 8] });
        });

        it('highlightResidue ghosts then highlights one residue in amber', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.setStyle.mockClear();

            v.highlightResidue(1, 'B', 10, 7);

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'B' }, expect.objectContaining({ cartoon: expect.objectContaining({ opacity: 0.35 }) }));
            expect(mockViewer.addStyle).toHaveBeenCalledWith({ chain: 'B', resi: 7 }, expect.objectContaining({
                cartoon: expect.objectContaining({ color: '#F59E0B' }),
            }));
        });

        it('highlightResidues ghosts once then highlights every match in the map', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            v.highlightResidues({ A: [1, 2], B: [3] });

            expect(mockViewer.addStyle).toHaveBeenCalledWith({ chain: 'A', resi: [1, 2] }, expect.any(Object));
            expect(mockViewer.addStyle).toHaveBeenCalledWith({ chain: 'B', resi: [3] }, expect.any(Object));
        });
    });

    describe('surface toggle and reset view', () => {
        it('toggling surface on adds a SAS surface, toggling off removes it', () => {
            const v = makeViewer();
            const btn = v.element.querySelector('#btn-toggle-surface');

            btn.click();
            expect(mockViewer.addSurface).toHaveBeenCalledWith('SAS', expect.objectContaining({ opacity: 0.45 }));
            expect(v.isSurfaceVisible).toBe(true);

            btn.click();
            expect(mockViewer.removeAllSurfaces).toHaveBeenCalled();
            expect(v.isSurfaceVisible).toBe(false);
        });

        it('reset-view button re-centers the camera', () => {
            const v = makeViewer();
            v.element.querySelector('#btn-reset-view').click();
            expect(mockViewer.zoomTo).toHaveBeenCalled();
            expect(mockViewer.render).toHaveBeenCalled();
        });
    });

    describe('fullscreen exit', () => {
        it('clicking the button while already fullscreen calls exitFullscreen', () => {
            const v = makeViewer();
            Object.defineProperty(document, 'fullscreenElement', { value: v.element, configurable: true });

            v.element.querySelector('#btn-toggle-fullscreen').click();

            expect(document.exitFullscreen).toHaveBeenCalled();
            Object.defineProperty(document, 'fullscreenElement', { value: null, configurable: true });
        });
    });

    describe('style switcher - remaining representations', () => {
        it('selecting sphere applies a scale-based size param', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.setStyleRepresentation('sphere');
            expect(mockViewer.setStyle).toHaveBeenCalledWith(expect.anything(), { sphere: expect.objectContaining({ scale: 0.3 }) });
        });

        it('selecting line applies a linewidth-based size param', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.setStyleRepresentation('line');
            expect(mockViewer.setStyle).toHaveBeenCalledWith(expect.anything(), { line: expect.objectContaining({ linewidth: 2 }) });
        });
    });

    describe('pLDDT confidence color scheme', () => {
        it('applies a B-factor gradient for a pLDDT structure with numeric B-factors', async () => {
            const v = makeViewer();
            mockViewer.getModel.mockReturnValue({ selectedAtoms: vi.fn(() => [{ b: 40 }, { b: 90 }]) });
            await v.loadSuperposition('run_1', ['AF-P69905-F1', '3UG9'], {}, null);

            v.setColorScheme('confidence');

            expect(mockViewer.setStyle).toHaveBeenCalledWith(
                { chain: 'A' },
                { cartoon: expect.objectContaining({ colorscheme: { prop: 'b', gradient: 'roygb', min: 40, max: 90 } }) }
            );
        });

        it('falls back to identity color for a non-pLDDT structure even in confidence mode', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            v.setColorScheme('confidence');

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, { cartoon: expect.objectContaining({ color: expect.any(String) }) });
        });

        it('falls back to identity color for a pLDDT structure with no numeric B-factors', async () => {
            const v = makeViewer();
            mockViewer.getModel.mockReturnValue({ selectedAtoms: vi.fn(() => []) });
            await v.loadSuperposition('run_1', ['AF-P69905-F1', '3UG9'], {}, null);

            v.setColorScheme('confidence');

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, { cartoon: expect.objectContaining({ color: expect.any(String) }) });
        });
    });

    describe('AlphaMissense mutation-tolerance color scheme', () => {
        it('fetches tolerance for every structure and applies a colorfunc once loaded', async () => {
            fetchMutationTolerance.mockResolvedValue({
                tolerance: { accession: 'P69905', per_residue_average: { 10: 0.9 } },
            });
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('missense');

            expect(fetchMutationTolerance).toHaveBeenCalledWith('4RLT', 'A');
            expect(fetchMutationTolerance).toHaveBeenCalledWith('3UG9', 'B');
            expect(mockViewer.setStyle).toHaveBeenCalledWith(
                { chain: 'A' },
                { cartoon: expect.objectContaining({ colorfunc: expect.any(Function) }) }
            );
        });

        it('colors a residue with tolerance data and falls back to a neutral color otherwise', async () => {
            fetchMutationTolerance.mockResolvedValue({
                tolerance: { accession: 'P69905', per_residue_average: { 10: 1 } },
            });
            const v = makeViewer();
            await loadTwoStructures(v);
            await v.setColorScheme('missense');

            const [, styleArg] = mockViewer.setStyle.mock.calls[mockViewer.setStyle.mock.calls.length - 1];
            const colorfunc = styleArg.cartoon.colorfunc;
            expect(colorfunc({ resi: 10 })).toBe('#b23a3a');
            expect(colorfunc({ resi: 999 })).toBe('#4B5563');
        });

        it('falls back to identity color when no tolerance data resolves for any structure', async () => {
            fetchMutationTolerance.mockResolvedValue({ tolerance: { accession: null, per_residue_average: {} } });
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('missense');

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, { cartoon: expect.objectContaining({ color: expect.any(String) }) });
        });

        it('does not re-fetch tolerance data already cached for a structure', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('missense');
            fetchMutationTolerance.mockClear();
            await v.setColorScheme('missense');

            expect(fetchMutationTolerance).not.toHaveBeenCalled();
        });

        it('handles a fetch failure gracefully by falling back to identity color', async () => {
            fetchMutationTolerance.mockRejectedValue(new Error('boom'));
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('missense');

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, { cartoon: expect.objectContaining({ color: expect.any(String) }) });
        });
    });

    describe('InterPro domain color scheme', () => {
        it('fetches annotation for every structure and applies a colorfunc once loaded', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: { domains: [{ highlight_chains: { A: [10, 11, 12] } }] },
            });
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('domain');

            expect(fetchAnnotations).toHaveBeenCalledWith('4RLT', 'A');
            expect(fetchAnnotations).toHaveBeenCalledWith('3UG9', 'B');
            expect(mockViewer.setStyle).toHaveBeenCalledWith(
                { chain: 'A' },
                { cartoon: expect.objectContaining({ colorfunc: expect.any(Function) }) }
            );
        });

        it('gives each domain a distinct color and falls back to a neutral color outside any domain', async () => {
            fetchAnnotations.mockResolvedValue({
                annotation: {
                    domains: [
                        { highlight_chains: { A: [10] } },
                        { highlight_chains: { A: [20] } },
                    ],
                },
            });
            const v = makeViewer();
            await loadTwoStructures(v);
            await v.setColorScheme('domain');

            const [, styleArg] = mockViewer.setStyle.mock.calls[mockViewer.setStyle.mock.calls.length - 1];
            const colorfunc = styleArg.cartoon.colorfunc;
            const colorForDomain0 = colorfunc({ resi: 10 });
            const colorForDomain1 = colorfunc({ resi: 20 });
            expect(colorForDomain0).not.toBe(colorForDomain1);
            expect(colorfunc({ resi: 999 })).toBe('#4B5563');
        });

        it('falls back to identity color when no domain data resolves for any structure', async () => {
            fetchAnnotations.mockResolvedValue({ annotation: { domains: [] } });
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('domain');

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, { cartoon: expect.objectContaining({ color: expect.any(String) }) });
        });

        it('does not re-fetch annotation already cached for a structure', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('domain');
            fetchAnnotations.mockClear();
            await v.setColorScheme('domain');

            expect(fetchAnnotations).not.toHaveBeenCalled();
        });

        it('handles a fetch failure gracefully by falling back to identity color', async () => {
            fetchAnnotations.mockRejectedValue(new Error('boom'));
            const v = makeViewer();
            await loadTwoStructures(v);

            await v.setColorScheme('domain');

            expect(mockViewer.setStyle).toHaveBeenCalledWith({ chain: 'A' }, { cartoon: expect.objectContaining({ color: expect.any(String) }) });
        });
    });

    describe('line-style ghosting fallback', () => {
        it('dims the color toward the background instead of relying on opacity alone', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.setStyleRepresentation('line');
            mockViewer.setStyle.mockClear();

            v.highlightResidue(0, 'A', 10, 5);

            const [, styleArg] = mockViewer.setStyle.mock.calls[0];
            expect(styleArg.line.color).not.toBe('#8B5CF6');
            expect(styleArg.line.opacity).toBe(0.35);
        });
    });

    describe('RMSD HUD math', () => {
        it('computes the mean RMSD for a 2-structure run with a real matrix', async () => {
            const v = makeViewer();
            await v.loadSuperposition('run_1', ['4RLT', '3UG9'], {}, { index: ['4RLT', '3UG9'], data: [[0, 2.5], [2.5, 0]] });

            expect(v.element.querySelector('#hud-rmsd-container').textContent).toContain('2.50');
        });

        it('shows every pairwise value for a 3+ structure run', async () => {
            const v = makeViewer();
            await v.loadSuperposition('run_1', ['A', 'B', 'C'], {}, { index: ['A', 'B', 'C'], data: [[0, 1, 2], [1, 0, 3], [2, 3, 0]] });

            const text = v.element.querySelector('#hud-rmsd-container').textContent;
            expect(text).toContain('Pairwise RMSD');
            expect(text).toContain('1.00');
            expect(text).toContain('2.00');
            expect(text).toContain('3.00');
        });
    });

    describe('load failure handling', () => {
        it('loadSuperposition logs an error when the fetch response is not ok', async () => {
            global.fetch.mockResolvedValue({ ok: false, statusText: 'Not Found' });
            const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
            const v = makeViewer();

            await loadTwoStructures(v);

            expect(errSpy).toHaveBeenCalled();
        });

        it('loadSingleStructure logs an error when the fetch response is not ok', async () => {
            global.fetch.mockResolvedValue({ ok: false, statusText: 'Not Found' });
            const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
            const v = makeViewer();

            await v.loadSingleStructure('4RLT');

            expect(errSpy).toHaveBeenCalled();
        });
    });

    describe('edge cases for ghost/highlight zoom targets', () => {
        it('showLigandBindingSite with no mappable interactions zooms to the whole model instead of an empty selection', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.zoomTo.mockClear();

            v.showLigandBindingSite(0, 'HEM_A_1', [{ aligned_resi: null }]);

            expect(mockViewer.zoomTo).toHaveBeenCalledWith();
        });

        it('highlightResidue with no aligned_resi mapping avoids selecting a bogus residue', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.zoomTo.mockClear();

            v.highlightResidue(0, 'A', 10, null);

            expect(mockViewer.zoomTo).toHaveBeenCalledWith();
        });

        it('highlightResidues with an empty map zooms to the whole model', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.zoomTo.mockClear();

            v.highlightResidues({});

            expect(mockViewer.zoomTo).toHaveBeenCalledWith();
        });
    });

    describe('inspect label cleared by entering measure mode', () => {
        it('removes an existing inspect label when switching to measure mode', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            const callback = mockViewer.setClickable.mock.calls.at(-1)[2];
            callback({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
            expect(v.inspectLabelHandle).not.toBeNull();
            mockViewer.removeLabel.mockClear();

            v.element.querySelector('#btn-toggle-measure').click();

            expect(mockViewer.removeLabel).toHaveBeenCalled();
        });

        it('inspect click with no atom (clicked empty space) clears without adding a new label', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            const callback = mockViewer.setClickable.mock.calls.at(-1)[2];
            callback({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
            mockViewer.addLabel.mockClear();

            callback(null);

            expect(v.inspectLabelHandle).toBeNull();
            expect(mockViewer.addLabel).not.toHaveBeenCalled();
        });
    });

    describe('measurement connector fallback', () => {
        it('uses addCylinder when addLine is not available', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            delete mockViewer.addLine;
            mockViewer.addCylinder = vi.fn(() => ({ id: 'cyl' }));
            v.element.querySelector('#btn-toggle-measure').click();
            const callback = mockViewer.setClickable.mock.calls.at(-1)[2];

            callback({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
            callback({ resn: 'GLY', resi: 2, chain: 'A', x: 3, y: 4, z: 0 });

            expect(mockViewer.addCylinder).toHaveBeenCalledTimes(1);
        });
    });

    describe('guards on a viewer that never got a 3Dmol instance', () => {
        function makeUninitializedViewer() {
            const v = new Viewer3D();
            v.render();
            return v;
        }

        it('every viewer-dependent method no-ops instead of throwing', () => {
            const v = makeUninitializedViewer();
            expect(() => {
                v.toggleSpin();
                v.downloadScreenshot();
                v.showLigandBindingSite(0, 'HEM', []);
                v.highlightResidue(0, 'A', 1, 1);
                v.highlightResidues({ A: [1] });
                v.resetCartoonStyles();
                v._handleInspectClick({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
                v._handleMeasureClick({ resn: 'ALA', resi: 1, chain: 'A', x: 0, y: 0, z: 0 });
                v._wireClickHandler();
                v.reset();
            }).not.toThrow();
        });

        it('loadSuperposition/loadSingleStructure lazily call init3Dmol when no viewer exists yet', async () => {
            const v = makeUninitializedViewer();
            expect(v.viewer).toBeNull();

            await v.loadSuperposition('run_1', ['4RLT', '3UG9'], {}, null);

            expect(v.viewer).not.toBeNull();
            expect(window.$3Dmol.createViewer).toHaveBeenCalled();
        });
    });

    describe('window resize', () => {
        it('resizes the viewer on a window resize event', () => {
            makeViewer();
            window.dispatchEvent(new Event('resize'));
            expect(mockViewer.resize).toHaveBeenCalled();
        });
    });

    describe('ESM Atlas pLDDT detection', () => {
        it('treats an ESM- accession as a pLDDT structure too', async () => {
            const v = makeViewer();
            await v.loadSuperposition('run_1', ['ESM-MGYP002537940442', '3UG9'], {}, null);

            expect(v.hasPlddtStructures()).toBe(true);
        });
    });

    describe('confidence coloring on a single (non-aligned) structure', () => {
        it('applies the B-factor gradient using the whole-model selector', async () => {
            const v = makeViewer();
            mockViewer.getModel.mockReturnValue({ selectedAtoms: vi.fn(() => [{ b: 10 }, { b: 80 }]) });
            await v.loadSingleStructure('AF-P69905-F1');

            v.setColorScheme('confidence');

            expect(mockViewer.setStyle).toHaveBeenCalledWith(
                {},
                { cartoon: expect.objectContaining({ colorscheme: { prop: 'b', gradient: 'roygb', min: 10, max: 80 } }) }
            );
        });
    });

    describe('ghost/highlight with an out-of-range structure index', () => {
        it('showLigandBindingSite falls back to chain A and a default color when the index is invalid', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            v.showLigandBindingSite(99, 'HEM', [{ aligned_resi: 5 }]);

            expect(mockViewer.addStyle).toHaveBeenCalledWith(
                { chain: 'A', resi: 5 },
                expect.objectContaining({ cartoon: expect.objectContaining({ color: '#8B5CF6' }) })
            );
        });

        it('highlightResidue falls back to the given raw chain when the index is invalid', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            v.highlightResidue(99, 'Z', 10, 7);

            expect(mockViewer.zoomTo).toHaveBeenCalledWith({ chain: 'Z', resi: 7 });
        });
    });

    describe('highlightResidues with a missing or sparse chain mapping', () => {
        it('tolerates a null/undefined chainMapping', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);

            expect(() => v.highlightResidues(undefined)).not.toThrow();
            expect(mockViewer.zoomTo).toHaveBeenCalledWith();
        });

        it('skips a chain entry with an empty residue list', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            mockViewer.addStyle.mockClear();

            v.highlightResidues({ A: [], B: [3] });

            expect(mockViewer.addStyle).toHaveBeenCalledTimes(1);
            expect(mockViewer.addStyle).toHaveBeenCalledWith({ chain: 'B', resi: [3] }, expect.any(Object));
        });
    });

    describe('reset on a viewer that was never loaded or spinning', () => {
        it('is a no-op-safe reset from the default state', () => {
            const v = makeViewer();
            expect(() => v.reset()).not.toThrow();
            expect(v.isSpinning).toBe(false);
        });
    });

    describe('reset', () => {
        it('restores the ambient placeholder, empty HUD, and default style/color/spin/measure state', async () => {
            const v = makeViewer();
            await loadTwoStructures(v);
            v.setStyleRepresentation('stick');
            v.setColorScheme('spectrum');
            v.toggleSpin();
            v.element.querySelector('#btn-toggle-measure').click();

            v.reset();

            expect(v.structures).toEqual([]);
            expect(v.currentStyle).toBe('cartoon');
            expect(v.currentColorScheme).toBe('chain');
            expect(v.interactionMode).toBe('inspect');
            expect(v.isSpinning).toBe(false);
            expect(mockViewer.spin).toHaveBeenLastCalledWith(false);
            expect(v.element.querySelector('#ambient-placeholder').style.display).toBe('flex');
        });
    });
});
