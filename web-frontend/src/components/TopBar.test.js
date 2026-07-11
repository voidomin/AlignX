import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TopBar } from './TopBar.js';

vi.mock('../api.js', () => ({
    fetchMemoryStats: vi.fn(),
    fetchHealth: vi.fn(),
    triggerClearMemory: vi.fn(),
}));

import { fetchMemoryStats, fetchHealth } from '../api.js';

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

    describe('tab strip scroll affordance', () => {
        it('renders 10 tabs and a scroll-left/scroll-right button pair, hidden by default', () => {
            const bar = makeBar();
            bar.render();

            expect(bar.element.querySelectorAll('.tab-trigger')).toHaveLength(10);
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
