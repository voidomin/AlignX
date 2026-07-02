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
});
