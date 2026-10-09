import {
    getAlignmentReportUrl,
    getLabNotebookIpynbUrl,
    getReportZipUrl,
    getPymolScriptUrl,
    getChimeraxScriptUrl,
    getRmsdCsvUrl,
    getCitationsUrl,
} from '../api';
import { escapeHtml } from '../escapeHtml';

export const REPORT_SECTIONS = [
    {
        key: 'summary',
        label: 'Executive Overview',
        description: 'Global RMSD, TM-score, Mustang sequence identity, and alignment length.',
        defaultChecked: true,
    },
    {
        key: 'insights',
        label: 'Structural Insights',
        description: 'Plain-English biochemical findings, fold classification, and secondary structure.',
        defaultChecked: true,
    },
    {
        key: 'heatmap',
        label: 'Pairwise RMSD Heatmap',
        description: 'Color-coded all-against-all structural deviation matrix.',
        defaultChecked: true,
    },
    {
        key: 'tree',
        label: 'Phylogenetic Tree',
        description: 'Neighbor-joining hierarchical tree diagram derived from structural distances.',
        defaultChecked: true,
    },
    {
        key: 'matrix',
        label: 'Numerical Metric Matrix',
        description: 'Raw pairwise distance table and detailed chain-by-chain stats.',
        defaultChecked: true,
    },
];

export const PRESETS = {
    executive: {
        label: 'Executive Summary',
        icon: 'summarize',
        badge: '1-Page',
        description: 'Compact high-level overview with key alignment metrics and structural insights.',
        sections: ['summary', 'insights'],
    },
    appendix: {
        label: 'Full Publication Appendix',
        icon: 'library_books',
        badge: 'Complete',
        description: 'Everything included: complete figures, phylogenetic tree, and all matrices.',
        sections: ['summary', 'insights', 'heatmap', 'tree', 'matrix'],
    },
    drugDiscovery: {
        label: 'Drug Discovery Brief',
        icon: 'science',
        badge: 'Focused',
        description: 'Targeted overview focusing on summary metrics and pairwise deviation matrix.',
        sections: ['summary', 'matrix'],
    },
};

export function showExportModal({ runId, selectedPDBs = [] }) {
    const existing = document.getElementById('export-studio-modal');
    if (existing) {
        existing.remove();
    }

    const overlay = document.createElement('div');
    overlay.id = 'export-studio-modal';
    overlay.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm transition-opacity duration-200';

    if (!runId) {
        overlay.innerHTML = `
            <div class="relative w-full max-w-lg bg-surface border border-border rounded-xl shadow-2xl p-6 flex flex-col gap-4">
                <div class="flex items-start justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-lg bg-surface-raised flex items-center justify-center text-secondary">
                            <span class="material-symbols-outlined text-[24px]">description</span>
                        </div>
                        <div>
                            <h3 class="font-headline-sm text-headline-sm font-bold text-primary">Export Studio</h3>
                            <p class="font-body-sm text-body-sm text-secondary">No active alignment results to export.</p>
                        </div>
                    </div>
                    <button id="close-export-modal-btn" type="button" class="text-secondary hover:text-primary p-1 rounded-md transition-colors" aria-label="Close modal">
                        <span class="material-symbols-outlined text-[20px]">close</span>
                    </button>
                </div>
                <div class="p-4 rounded-lg bg-surface-raised border border-border-subtle font-body-sm text-secondary leading-relaxed">
                    Please select 2 or more structures and click <strong class="text-primary">Run Alignment</strong> in the Workspace tab, or load a completed run from the History tab.
                </div>
                <div class="flex justify-end pt-2">
                    <button id="dismiss-export-modal-btn" type="button" class="btn-primary px-4 py-2 rounded-md font-label-md text-label-md">
                        Understood
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();
        overlay.querySelector('#close-export-modal-btn')?.addEventListener('click', closeModal);
        overlay.querySelector('#dismiss-export-modal-btn')?.addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });
        return overlay;
    }

    const pdbListText = selectedPDBs.length > 0 ? selectedPDBs.join(', ') : 'Aligned Structures';

    overlay.innerHTML = `
        <div class="relative w-full max-w-3xl bg-surface border border-border rounded-xl shadow-2xl p-6 flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
            <!-- Header -->
            <div class="flex items-start justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center text-accent">
                        <span class="material-symbols-outlined text-[24px]">description</span>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="font-headline-sm text-headline-sm font-bold text-primary">Custom Report &amp; Export Studio</h3>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-success/20 text-success border border-success/30 uppercase font-semibold">Active Run</span>
                        </div>
                        <p class="font-body-sm text-body-sm text-secondary">
                            Run: <span class="font-mono text-primary">${escapeHtml(runId)}</span> &middot; ${escapeHtml(pdbListText)}
                        </p>
                    </div>
                </div>
                <button id="close-export-modal-btn" type="button" class="text-secondary hover:text-primary p-1 rounded-md transition-colors" aria-label="Close modal">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <!-- Presets Section -->
            <div class="flex flex-col gap-2">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">1-Click Presets</span>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                    ${Object.entries(PRESETS).map(([key, preset]) => `
                        <button type="button" data-preset="${key}" class="preset-btn p-3 rounded-lg bg-surface-raised border border-border-subtle hover:border-accent hover:bg-surface-raised/80 transition-all text-left flex flex-col gap-1.5 group cursor-pointer">
                            <div class="flex items-center justify-between">
                                <span class="material-symbols-outlined text-[20px] text-accent">${preset.icon}</span>
                                <span class="px-1.5 py-0.5 rounded text-[9px] font-mono bg-accent-muted text-accent font-semibold">${preset.badge}</span>
                            </div>
                            <span class="font-label-md text-label-md font-semibold text-primary group-hover:text-accent transition-colors">${preset.label}</span>
                            <span class="font-body-sm text-[11px] text-secondary leading-snug">${preset.description}</span>
                        </button>
                    `).join('')}
                </div>
            </div>

            <!-- Sections Customizer -->
            <div class="flex flex-col gap-2 pt-2 border-t border-border">
                <div class="flex items-baseline justify-between">
                    <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Report Figures &amp; Sections</span>
                    <button id="toggle-all-sections-btn" type="button" class="font-body-sm text-[11px] text-accent hover:underline">Deselect All</button>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    ${REPORT_SECTIONS.map(s => `
                        <label class="flex items-start gap-2.5 p-2.5 rounded-lg bg-surface-raised border border-border-subtle cursor-pointer hover:border-border transition-colors">
                            <input type="checkbox" data-section="${s.key}" class="export-section-checkbox mt-0.5 rounded border-border text-accent focus:ring-accent" ${s.defaultChecked ? 'checked' : ''}>
                            <div class="flex flex-col">
                                <span class="font-label-md text-label-md font-semibold text-primary">${s.label}</span>
                                <span class="font-body-sm text-[11px] text-secondary leading-snug">${s.description}</span>
                            </div>
                        </label>
                    `).join('')}
                </div>
            </div>

            <!-- Export Actions Grid -->
            <div class="flex flex-col gap-2 pt-2 border-t border-border">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Export Formats</span>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <!-- Custom HTML / PDF Report -->
                    <button id="export-html-report-btn" type="button" class="btn-primary p-3 rounded-lg flex items-center justify-between gap-3 text-left">
                        <div class="flex items-center gap-2.5">
                            <span class="material-symbols-outlined text-[20px]">print</span>
                            <div class="flex flex-col">
                                <span class="font-label-md text-label-md font-semibold">Custom Report (HTML / PDF)</span>
                                <span class="text-[11px] opacity-80">Renders selected sections for browser print &amp; PDF</span>
                            </div>
                        </div>
                        <span class="material-symbols-outlined text-[18px]">open_in_new</span>
                    </button>

                    <!-- Full Publication ZIP -->
                    <a id="export-zip-btn" href="${getReportZipUrl(runId)}" target="_blank" rel="noopener noreferrer" class="btn-secondary p-3 rounded-lg flex items-center justify-between gap-3 text-left">
                        <div class="flex items-center gap-2.5">
                            <span class="material-symbols-outlined text-[20px] text-accent">folder_zip</span>
                            <div class="flex flex-col">
                                <span class="font-label-md text-label-md font-semibold text-primary">Complete ZIP Bundle</span>
                                <span class="font-body-sm text-[11px] text-secondary">All PDBs, FASTAs, matrices &amp; figures</span>
                            </div>
                        </div>
                        <span class="material-symbols-outlined text-[18px] text-secondary">download</span>
                    </a>

                    <!-- Jupyter Notebook -->
                    <a id="export-ipynb-btn" href="${getLabNotebookIpynbUrl(runId)}" target="_blank" rel="noopener noreferrer" class="btn-secondary p-3 rounded-lg flex items-center justify-between gap-3 text-left">
                        <div class="flex items-center gap-2.5">
                            <span class="material-symbols-outlined text-[20px] text-accent">terminal</span>
                            <div class="flex flex-col">
                                <span class="font-label-md text-label-md font-semibold text-primary">Jupyter Notebook (.ipynb)</span>
                                <span class="font-body-sm text-[11px] text-secondary">Interactive runnable Python analysis</span>
                            </div>
                        </div>
                        <span class="material-symbols-outlined text-[18px] text-secondary">download</span>
                    </a>

                    <!-- RMSD CSV -->
                    <a id="export-csv-btn" href="${getRmsdCsvUrl(runId)}" target="_blank" rel="noopener noreferrer" class="btn-secondary p-3 rounded-lg flex items-center justify-between gap-3 text-left">
                        <div class="flex items-center gap-2.5">
                            <span class="material-symbols-outlined text-[20px] text-accent">table_chart</span>
                            <div class="flex flex-col">
                                <span class="font-label-md text-label-md font-semibold text-primary">Pairwise RMSD Matrix (CSV)</span>
                                <span class="font-body-sm text-[11px] text-secondary">Raw numerical distance dataset</span>
                            </div>
                        </div>
                        <span class="material-symbols-outlined text-[18px] text-secondary">download</span>
                    </a>
                </div>

                <!-- Secondary Session Scripts -->
                <div class="flex flex-wrap items-center gap-2 pt-1 text-label-sm">
                    <span class="font-body-sm text-[11px] text-secondary mr-1">Molecular Viewers:</span>
                    <a id="export-pymol-btn" href="${getPymolScriptUrl(runId)}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 rounded-md bg-surface-raised border border-border text-primary hover:border-accent text-[11px] font-mono flex items-center gap-1 transition-colors">
                        <span class="material-symbols-outlined text-[14px] text-accent">code</span>
                        PyMOL (.pml)
                    </a>
                    <a id="export-chimerax-btn" href="${getChimeraxScriptUrl(runId)}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 rounded-md bg-surface-raised border border-border text-primary hover:border-accent text-[11px] font-mono flex items-center gap-1 transition-colors">
                        <span class="material-symbols-outlined text-[14px] text-accent">code</span>
                        ChimeraX (.cxc)
                    </a>
                    <a id="export-citations-btn" href="${getCitationsUrl(runId)}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 rounded-md bg-surface-raised border border-border text-primary hover:border-accent text-[11px] font-mono flex items-center gap-1 transition-colors ml-auto">
                        <span class="material-symbols-outlined text-[14px] text-accent">format_quote</span>
                        Citations (BibTeX)
                    </a>
                </div>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-3 pt-3 border-t border-border">
                <button id="dismiss-export-modal-btn" type="button" class="btn-secondary px-4 py-2 rounded-md font-label-md text-label-md">
                    Done
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const closeModal = () => overlay.remove();
    overlay.querySelector('#close-export-modal-btn')?.addEventListener('click', closeModal);
    overlay.querySelector('#dismiss-export-modal-btn')?.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });

    const getSelectedSections = () => {
        const checkboxes = overlay.querySelectorAll('.export-section-checkbox:checked');
        return Array.from(checkboxes).map(cb => cb.dataset.section);
    };

    // Preset button click handling
    overlay.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const presetKey = btn.dataset.preset;
            const preset = PRESETS[presetKey];
            if (!preset) return;

            overlay.querySelectorAll('.export-section-checkbox').forEach(cb => {
                cb.checked = preset.sections.includes(cb.dataset.section);
            });

            overlay.querySelectorAll('.preset-btn').forEach(b => {
                b.classList.remove('border-accent', 'bg-accent/10');
            });
            btn.classList.add('border-accent', 'bg-accent/10');
        });
    });

    // Select all toggle
    const toggleAllBtn = overlay.querySelector('#toggle-all-sections-btn');
    if (toggleAllBtn) {
        toggleAllBtn.addEventListener('click', () => {
            const checkboxes = overlay.querySelectorAll('.export-section-checkbox');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => { cb.checked = !allChecked; });
            toggleAllBtn.textContent = allChecked ? 'Select All' : 'Deselect All';
        });
    }

    // HTML / PDF Report Launch
    const htmlReportBtn = overlay.querySelector('#export-html-report-btn');
    if (htmlReportBtn) {
        htmlReportBtn.addEventListener('click', () => {
            const sections = getSelectedSections();
            const url = getAlignmentReportUrl(runId, sections);
            window.open(url, '_blank');
        });
    }

    return overlay;
}
