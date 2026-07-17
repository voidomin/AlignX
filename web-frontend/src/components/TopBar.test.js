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
});
