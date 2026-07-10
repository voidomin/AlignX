import { describe, it, expect, vi, afterEach } from 'vitest';
import { SettingsTab } from './SettingsTab.js';

vi.mock('../api.js', () => ({
    fetchSettings: vi.fn(),
    saveSettings: vi.fn(),
    resetSettings: vi.fn(),
}));

import { fetchSettings, saveSettings, resetSettings } from '../api.js';

const SAMPLE_SETTINGS = {
    mustang_backend: 'wsl',
    mustang_timeout: 600,
    max_proteins: 20,
    max_file_size_mb: 500,
    heatmap_colormap: 'viridis',
    viewer_default_style: 'cartoon',
};

describe('SettingsTab', () => {
    afterEach(() => {
        vi.clearAllMocks();
    });

    it('shows a loading state before settings arrive', () => {
        fetchSettings.mockReturnValue(new Promise(() => {})); // never resolves
        const tab = new SettingsTab();
        tab.render();

        expect(tab.element.querySelector('#settings-loading').classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('#settings-form').classList.contains('hidden')).toBe(true);
    });

    it('populates the form with fetched settings', async () => {
        fetchSettings.mockResolvedValue(SAMPLE_SETTINGS);
        const tab = new SettingsTab();
        tab.render();
        await Promise.resolve();
        await Promise.resolve();

        expect(tab.element.querySelector('#settings-loading').classList.contains('hidden')).toBe(true);
        expect(tab.element.querySelector('#settings-form').classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('#setting-mustang-backend').value).toBe('wsl');
        expect(tab.element.querySelector('#setting-mustang-timeout').value).toBe('600');
        expect(tab.element.querySelector('#setting-max-proteins').value).toBe('20');
        expect(tab.element.querySelector('#setting-heatmap-colormap').value).toBe('viridis');
    });

    it('shows an error message if settings fail to load', async () => {
        fetchSettings.mockRejectedValue(new Error('boom'));
        const tab = new SettingsTab();
        tab.render();
        await Promise.resolve();
        await Promise.resolve();

        expect(tab.element.querySelector('#settings-loading').textContent).toContain('Failed to load settings.');
    });

    it('saves the form values and shows success feedback', async () => {
        fetchSettings.mockResolvedValue(SAMPLE_SETTINGS);
        const updated = { ...SAMPLE_SETTINGS, max_proteins: 10 };
        saveSettings.mockResolvedValue(updated);

        const tab = new SettingsTab();
        tab.render();
        await Promise.resolve();
        await Promise.resolve();

        tab.element.querySelector('#setting-max-proteins').value = '10';
        tab.element.querySelector('#settings-save-btn').click();
        await Promise.resolve();
        await Promise.resolve();

        expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({ max_proteins: 10 }));
        expect(tab.element.querySelector('#settings-feedback').textContent).toContain('saved successfully');
        expect(tab.element.querySelector('#setting-max-proteins').value).toBe('10');
    });

    it('shows an error message when saving fails validation', async () => {
        fetchSettings.mockResolvedValue(SAMPLE_SETTINGS);
        saveSettings.mockRejectedValue(new Error("backend must be 'auto', 'native', or 'wsl'"));

        const tab = new SettingsTab();
        tab.render();
        await Promise.resolve();
        await Promise.resolve();

        tab.element.querySelector('#settings-save-btn').click();
        await Promise.resolve();
        await Promise.resolve();

        const feedback = tab.element.querySelector('#settings-feedback');
        expect(feedback.textContent).toContain("backend must be");
        expect(feedback.className).toContain('text-error');
    });

    it('restores defaults and repopulates the form', async () => {
        fetchSettings.mockResolvedValue({ ...SAMPLE_SETTINGS, max_proteins: 5 });
        resetSettings.mockResolvedValue(SAMPLE_SETTINGS);

        const tab = new SettingsTab();
        tab.render();
        await Promise.resolve();
        await Promise.resolve();

        expect(tab.element.querySelector('#setting-max-proteins').value).toBe('5');

        tab.element.querySelector('#settings-reset-btn').click();
        await Promise.resolve();
        await Promise.resolve();

        expect(resetSettings).toHaveBeenCalled();
        expect(tab.element.querySelector('#setting-max-proteins').value).toBe('20');
        expect(tab.element.querySelector('#settings-feedback').textContent).toContain('Defaults restored');
    });
});
