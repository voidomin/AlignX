import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TopBar } from './TopBar.js';

vi.mock('../api.js', () => ({
    fetchMemoryStats: vi.fn(),
    fetchHealth: vi.fn(),
    triggerClearMemory: vi.fn(),
}));

import { fetchMemoryStats, fetchHealth, triggerClearMemory } from '../api.js';

function makeBar(overrides = {}) {
    return new TopBar({
        onTabChange: vi.fn(),
        onExportData: vi.fn(),
        onNewWorkspace: vi.fn(),
        ...overrides,
    });
}

describe('TopBar', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        fetchMemoryStats.mockResolvedValue({ ram_mb: 100 });
        fetchHealth.mockResolvedValue({ mustang_installed: true, mustang_message: 'Compiled Mustang found (WSL)' });
        // jsdom doesn't implement these layout/scroll APIs at all.
        Element.prototype.scrollIntoView = vi.fn();
        Element.prototype.scrollBy = vi.fn();
    });

    afterEach(() => {
        vi.clearAllMocks();
        vi.useRealTimers();
    });

    it('does not poll memory/health immediately on render, to avoid competing with the initial chain-metadata fetch', () => {
        const bar = makeBar();
        bar.render();

        expect(fetchMemoryStats).not.toHaveBeenCalled();
        expect(fetchHealth).not.toHaveBeenCalled();
    });

    it('polls once after an initial delay, then on a 20s interval', async () => {
        const bar = makeBar();
        bar.render();

        await vi.advanceTimersByTimeAsync(3000);
        expect(fetchMemoryStats).toHaveBeenCalledTimes(1);
        expect(fetchHealth).toHaveBeenCalledTimes(1);

        await vi.advanceTimersByTimeAsync(20000);
        expect(fetchMemoryStats).toHaveBeenCalledTimes(2);

        bar.destroy();
    });

    it('destroy() clears both the initial-poll timeout and the polling interval', async () => {
        const bar = makeBar();
        bar.render();
        bar.destroy();

        await vi.advanceTimersByTimeAsync(30000);
        expect(fetchMemoryStats).not.toHaveBeenCalled();
    });

    describe('alignment engine status', () => {
        it('shows Offline with a title explaining why when Mustang is not installed', async () => {
            fetchHealth.mockResolvedValue({ mustang_installed: false, mustang_message: null });
            const bar = makeBar();
            bar.render();

            await vi.advanceTimersByTimeAsync(3000);

            const healthEl = bar.element.querySelector('#topbar-health-status');
            expect(healthEl.innerText).toBe('Alignment engine: Offline');
            expect(healthEl.title).toBe('Mustang could not be found on the server');
            expect(healthEl.className).toContain('text-error');

            bar.destroy();
        });

        it('shows Disconnected with a title when the health check itself fails', async () => {
            fetchHealth.mockRejectedValue(new Error('network down'));
            const bar = makeBar();
            bar.render();

            await vi.advanceTimersByTimeAsync(3000);

            const healthEl = bar.element.querySelector('#topbar-health-status');
            expect(healthEl.innerText).toBe('Alignment engine: Disconnected');
            expect(healthEl.title).toBe('Could not reach the backend server');
            expect(healthEl.className).toContain('text-error');

            bar.destroy();
        });

        it('shows Ready with the Native/WSL mode in a title, mirroring the visible label', async () => {
            fetchHealth.mockResolvedValue({ mustang_installed: true, mustang_message: 'Compiled Mustang found, native binary' });
            const bar = makeBar();
            bar.render();

            await vi.advanceTimersByTimeAsync(3000);

            const healthEl = bar.element.querySelector('#topbar-health-status');
            expect(healthEl.innerText).toBe('Alignment engine: Ready');
            expect(healthEl.title).toBe('Runs via Mustang, in Native mode');

            bar.destroy();
        });
    });

    describe('free up memory button', () => {
        it('shows a transient "Clearing..." state, then restores its label once the request settles', async () => {
            triggerClearMemory.mockResolvedValue({ ram_mb: 42 });
            const bar = makeBar();
            bar.render();

            const freeBtn = bar.element.querySelector('#topbar-free-ram-btn');
            expect(freeBtn.textContent).toBe('Free up memory');

            freeBtn.click();
            expect(freeBtn.innerText).toBe('Clearing...');
            expect(freeBtn.disabled).toBe(true);

            await Promise.resolve();
            await Promise.resolve();

            expect(freeBtn.innerText).toBe('Free up memory');
            expect(freeBtn.disabled).toBe(false);
        });
    });

    describe('tab strip scroll affordance', () => {
        it('renders 9 tabs and a scroll-left/scroll-right button pair, hidden by default', () => {
            const bar = makeBar();
            bar.render();

            expect(bar.element.querySelectorAll('.tab-trigger')).toHaveLength(9);
            expect(bar.element.querySelector('#topbar-scroll-left').classList.contains('hidden')).toBe(true);
            expect(bar.element.querySelector('#topbar-scroll-right').classList.contains('hidden')).toBe(true);
        });

        it('scroll-right button scrolls the tab nav forward when clicked', () => {
            const bar = makeBar();
            bar.render();
            const nav = bar.element.querySelector('#topbar-tabs');

            bar.element.querySelector('#topbar-scroll-right').click();

            expect(nav.scrollBy).toHaveBeenCalledWith(expect.objectContaining({ left: expect.any(Number) }));
        });

        it('switching the active tab scrolls it into view', () => {
            const bar = makeBar();
            bar.render();

            bar.switchTab('settings');

            const activeBtn = bar.element.querySelector('.tab-trigger[data-tab="settings"]');
            expect(activeBtn.scrollIntoView).toHaveBeenCalled();
        });
    });

    describe('responsive layout', () => {
        it('stacks the header vertically below the lg breakpoint instead of crushing the tab strip to zero width', () => {
            const bar = makeBar();
            bar.render();

            const headerRow = bar.element.querySelector('.max-w-\\[1600px\\]');
            expect(headerRow.className).toContain('flex-col');
            expect(headerRow.className).toContain('lg:flex-row');

            const tabsWrapper = bar.element.querySelector('#topbar-tabs-wrapper');
            expect(tabsWrapper.className).toContain('w-full');
            expect(tabsWrapper.className).toContain('lg:w-auto');

            const actionsCluster = bar.element.querySelector('#topbar-free-ram-btn').closest('div');
            expect(actionsCluster.className).toContain('flex-wrap');
            expect(actionsCluster.className).toContain('lg:flex-nowrap');
        });
    });

    describe('tab strip keyboard navigation', () => {
        it('only the active tab is in the natural Tab order (roving tabindex)', () => {
            const bar = makeBar();
            bar.render();

            const tabs = bar.element.querySelectorAll('.tab-trigger');
            const activeTabs = Array.from(tabs).filter(t => t.tabIndex === 0);
            expect(activeTabs).toHaveLength(1);
            expect(activeTabs[0].dataset.tab).toBe('workspace');
        });

        it('ArrowRight moves focus and calls onTabChange for the next tab', () => {
            const onTabChange = vi.fn();
            const bar = makeBar({ onTabChange });
            document.body.appendChild(bar.render());

            const tabs = bar.element.querySelectorAll('.tab-trigger');
            tabs[0].focus();
            tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));

            expect(document.activeElement).toBe(tabs[1]);
            expect(onTabChange).toHaveBeenCalledWith(tabs[1].dataset.tab);
            expect(tabs[1].tabIndex).toBe(0);
            expect(tabs[0].tabIndex).toBe(-1);

            bar.element.remove();
        });

        it('exposes role="tablist"/role="tab" for the tab strip', () => {
            const bar = makeBar();
            bar.render();

            expect(bar.element.querySelector('#topbar-tabs').getAttribute('role')).toBe('tablist');
            expect(bar.element.querySelector('.tab-trigger').getAttribute('role')).toBe('tab');
        });
    });

    describe('workflow stage labels and active-run indicator', () => {
        it('renders 1. Setup, 2. Results, and 3. Manage stage labels', () => {
            const bar = makeBar();
            bar.render();

            expect(bar.element.querySelector('[data-group-label="Workspace"]').textContent).toContain('1. Setup');
            expect(bar.element.querySelector('[data-group-label="Results"]').textContent).toContain('2. Results');
            expect(bar.element.querySelector('[data-group-label="Manage"]').textContent).toContain('3. Manage');
        });

        it('dims Results tabs until setRunActive(true) is called, then restores them', () => {
            const bar = makeBar();
            bar.render();

            const seqBtn = bar.element.querySelector('.tab-trigger[data-tab="sequence"]');
            expect(seqBtn.className).toContain('opacity-75');
            expect(seqBtn.title).toContain('Run an alignment in Workspace first');
            expect(bar.element.querySelector('[data-group-label="Results"] .bg-accent')).toBeNull();

            bar.setRunActive(true);
            expect(seqBtn.className).not.toContain('opacity-75');
            expect(seqBtn.hasAttribute('title')).toBe(false);
            expect(bar.element.querySelector('[data-group-label="Results"] .bg-accent')).not.toBeNull();

            bar.setRunActive(false);
            expect(seqBtn.className).toContain('opacity-75');
            expect(bar.element.querySelector('[data-group-label="Results"] .bg-accent')).toBeNull();
        });

        it('tucks engine diagnostics, RAM readout, Free up memory, and Desktop App inside #topbar-system-disclosure', () => {
            const bar = makeBar();
            bar.render();

            const sysDisclosure = bar.element.querySelector('#topbar-system-disclosure');
            expect(sysDisclosure).not.toBeNull();
            expect(sysDisclosure.open).toBe(false);
            expect(sysDisclosure.querySelector('#topbar-health-status')).not.toBeNull();
            expect(sysDisclosure.querySelector('#topbar-ram-text')).not.toBeNull();
            expect(sysDisclosure.querySelector('#topbar-free-ram-btn')).not.toBeNull();
            expect(sysDisclosure.querySelector('#topbar-download-desktop-btn')).not.toBeNull();
        });

        it('opens the Student Lab Guide & Rosetta Stone Glossary modal when #topbar-glossary-btn is clicked', () => {
            const bar = makeBar();
            bar.render();

            const glossaryBtn = bar.element.querySelector('#topbar-glossary-btn');
            expect(glossaryBtn).not.toBeNull();
            glossaryBtn.click();

            const modal = document.getElementById('rosetta-glossary-modal');
            expect(modal).not.toBeNull();
            modal.remove();
        });
    });
});
