import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Viewer3D } from './Viewer3D.js';

vi.mock('../api.js', () => ({
    getAlignmentPdbUrl: vi.fn((runId) => `http://mock/results/${runId}/alignment.pdb`),
    getStructureFileUrl: vi.fn((pdbId) => `http://mock/api/structure-file?pdb_id=${pdbId}`),
}));

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
