import { fetchSettings, saveSettings, resetSettings } from '../api';

const MUSTANG_BACKENDS = ['auto', 'native', 'wsl'];
const VIEWER_STYLES = ['cartoon', 'stick', 'sphere', 'line'];
const COLORMAPS = [
    { value: 'viridis', label: 'Viridis (Default)' },
    { value: 'plasma', label: 'Plasma' },
    { value: 'inferno', label: 'Inferno' },
    { value: 'magma', label: 'Magma' },
    { value: 'cividis', label: 'Cividis' },
    { value: 'RdBu_r', label: 'Red-Blue (Divergent)' },
    { value: 'Spectral_r', label: 'Spectral' },
];

export class SettingsTab {
    element = null;
    settings = null;

    render() {
        const div = document.createElement('div');
        div.className = "editorial-section";
        div.id = "tab-settings-container";

        div.innerHTML = `
            <header class="section-head">
                <div>
                    <span class="eyebrow">Fig. — System Configuration</span>
                    <h2 class="section-title">Settings</h2>
                </div>
                <div class="section-caption">Changes affect every user of this deployment, and take effect on the next alignment/download - not any run already in progress.</div>
            </header>

            <div class="section-body flex flex-col gap-8">
                <div id="settings-loading" class="text-center py-8 text-secondary font-body-sm">
                    <span class="animate-spin material-symbols-outlined text-[18px]">sync</span>
                    Loading settings...
                </div>
                <div id="settings-form" class="hidden flex-col gap-8">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-8">
                        <div class="flex flex-col gap-4">
                            <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Mustang execution</span>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Execution backend</span>
                                <select id="setting-mustang-backend" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                                    ${MUSTANG_BACKENDS.map(b => `<option value="${b}">${b}</option>`).join('')}
                                </select>
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Execution timeout (seconds)</span>
                                <input id="setting-mustang-timeout" type="number" min="60" max="3600" step="60" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary" />
                            </label>
                        </div>

                        <div class="flex flex-col gap-4">
                            <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Limits &amp; performance</span>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Max proteins per run</span>
                                <input id="setting-max-proteins" type="number" min="2" max="100" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary" />
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Max PDB file size (MB)</span>
                                <input id="setting-max-file-size" type="number" min="10" max="2000" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm font-mono text-primary" />
                            </label>
                        </div>
                    </div>

                    <div class="flex flex-col gap-4 border-t border-border pt-6">
                        <span class="font-label-md text-label-md text-secondary uppercase tracking-wider">Visualization</span>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-8">
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Heatmap colormap</span>
                                <select id="setting-heatmap-colormap" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                                    ${COLORMAPS.map(c => `<option value="${c.value}">${c.label}</option>`).join('')}
                                </select>
                            </label>
                            <label class="flex flex-col gap-1">
                                <span class="font-label-sm text-label-sm text-secondary uppercase">Default 3D style</span>
                                <select id="setting-viewer-style" class="bg-surface-raised border border-border rounded-md px-3 py-2 font-body-sm text-primary">
                                    ${VIEWER_STYLES.map(s => `<option value="${s}">${s}</option>`).join('')}
                                </select>
                            </label>
                        </div>
                    </div>

                    <div id="settings-feedback" class="font-body-sm"></div>

                    <div class="flex gap-3 border-t border-border pt-6">
                        <button id="settings-save-btn" class="btn-primary py-2 px-4 rounded-md font-label-md text-label-md">Save Changes</button>
                        <button id="settings-reset-btn" class="btn-secondary py-2 px-4 rounded-md font-label-md text-label-md">Restore Defaults</button>
                    </div>
                </div>
            </div>
        `;

        this.element = div;
        this.setupEventListeners();
        this.loadSettings();
        return div;
    }

    setupEventListeners() {
        this.element.querySelector('#settings-save-btn').addEventListener('click', () => this.save());
        this.element.querySelector('#settings-reset-btn').addEventListener('click', () => this.reset());
    }

    async loadSettings() {
        try {
            this.settings = await fetchSettings();
            this.populateForm();
            this.element.querySelector('#settings-loading').classList.add('hidden');
            this.element.querySelector('#settings-form').classList.remove('hidden');
            this.element.querySelector('#settings-form').classList.add('flex');
        } catch (err) {
            console.error("Failed to load settings:", err);
            this.element.querySelector('#settings-loading').textContent = "Failed to load settings.";
        }
    }

    populateForm() {
        const s = this.settings;
        this.element.querySelector('#setting-mustang-backend').value = s.mustang_backend;
        this.element.querySelector('#setting-mustang-timeout').value = s.mustang_timeout;
        this.element.querySelector('#setting-max-proteins').value = s.max_proteins;
        this.element.querySelector('#setting-max-file-size').value = s.max_file_size_mb;
        this.element.querySelector('#setting-heatmap-colormap').value = s.heatmap_colormap;
        this.element.querySelector('#setting-viewer-style').value = s.viewer_default_style;
    }

    readForm() {
        return {
            mustang_backend: this.element.querySelector('#setting-mustang-backend').value,
            mustang_timeout: Number.parseInt(this.element.querySelector('#setting-mustang-timeout').value, 10),
            max_proteins: Number.parseInt(this.element.querySelector('#setting-max-proteins').value, 10),
            max_file_size_mb: Number.parseInt(this.element.querySelector('#setting-max-file-size').value, 10),
            heatmap_colormap: this.element.querySelector('#setting-heatmap-colormap').value,
            viewer_default_style: this.element.querySelector('#setting-viewer-style').value,
        };
    }

    showFeedback(message, isError) {
        const el = this.element.querySelector('#settings-feedback');
        el.textContent = message;
        el.className = `font-body-sm ${isError ? 'text-error' : 'text-success'}`;
    }

    async save() {
        try {
            this.settings = await saveSettings(this.readForm());
            this.populateForm();
            this.showFeedback('Settings saved successfully.', false);
        } catch (err) {
            console.error("Failed to save settings:", err);
            this.showFeedback(err.message || 'Failed to save settings.', true);
        }
    }

    async reset() {
        try {
            this.settings = await resetSettings();
            this.populateForm();
            this.showFeedback('Defaults restored.', false);
        } catch (err) {
            console.error("Failed to reset settings:", err);
            this.showFeedback(err.message || 'Failed to reset settings.', true);
        }
    }
}
