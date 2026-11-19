/**
 * Modal displaying all keyboard shortcuts for StructScope.
 */
export function showShortcutsModal() {
    const existing = document.getElementById('shortcuts-modal-overlay');
    if (existing) {
        existing.remove();
        return;
    }

    const overlay = document.createElement('div');
    overlay.id = 'shortcuts-modal-overlay';
    overlay.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity duration-200';

    overlay.innerHTML = `
        <div class="relative w-full max-w-2xl bg-surface border border-border rounded-xl shadow-2xl p-6 flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
            <div class="flex items-start justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center text-accent">
                        <span class="material-symbols-outlined text-[24px]">keyboard</span>
                    </div>
                    <div>
                        <h3 class="font-headline-sm text-headline-sm font-bold text-primary">Keyboard Shortcuts</h3>
                        <p class="font-body-sm text-body-sm text-secondary">Quick navigation and 3D molecular instrument controls.</p>
                    </div>
                </div>
                <button id="close-shortcuts-modal-btn" type="button" class="text-secondary hover:text-primary p-1 rounded-md transition-colors" aria-label="Close shortcuts modal">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <!-- Shortcuts Grid -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <!-- Group 1: Navigation -->
                <div class="p-3.5 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-2.5">
                    <span class="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-accent">Tabs &amp; Navigation</span>
                    <div class="flex items-center justify-between text-body-sm">
                        <span class="text-secondary">Jump to tab (1 to 9)</span>
                        <div class="flex gap-1 font-mono">
                            <kbd class="px-1.5 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">1</kbd>
                            <span class="text-muted">–</span>
                            <kbd class="px-1.5 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">9</kbd>
                        </div>
                    </div>
                    <div class="flex items-center justify-between text-body-sm">
                        <span class="text-secondary">Switch adjacent tabs</span>
                        <div class="flex gap-1">
                            <kbd class="px-1.5 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">←</kbd>
                            <kbd class="px-1.5 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">→</kbd>
                        </div>
                    </div>
                    <div class="flex items-center justify-between text-body-sm">
                        <span class="text-secondary">First / Last tab</span>
                        <div class="flex gap-1">
                            <kbd class="px-1.5 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">Home</kbd>
                            <kbd class="px-1.5 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">End</kbd>
                        </div>
                    </div>
                </div>

                <!-- Group 2: 3D Molecular Viewport -->
                <div class="p-3.5 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-2.5">
                    <span class="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-accent">3D Viewport Controls</span>
                    <div class="flex items-center justify-between text-body-sm">
                        <span class="text-secondary">Reset camera &amp; center</span>
                        <kbd class="px-2 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">R</kbd>
                    </div>
                    <div class="flex items-center justify-between text-body-sm">
                        <span class="text-secondary">Toggle continuous spin</span>
                        <kbd class="px-2 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">S</kbd>
                    </div>
                    <div class="flex items-center justify-between text-body-sm">
                        <span class="text-secondary">Distance measure mode</span>
                        <kbd class="px-2 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">M</kbd>
                    </div>
                    <div class="flex items-center justify-between text-body-sm">
                        <span class="text-secondary">Toggle fullscreen</span>
                        <kbd class="px-2 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">F</kbd>
                    </div>
                </div>

                <!-- Group 3: Help & Reference -->
                <div class="p-3.5 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-2.5 sm:col-span-2">
                    <span class="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-accent">Assistance &amp; Modals</span>
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div class="flex items-center justify-between text-body-sm">
                            <span class="text-secondary">Lab Guide &amp; Glossary</span>
                            <kbd class="px-2 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">H</kbd>
                        </div>
                        <div class="flex items-center justify-between text-body-sm">
                            <span class="text-secondary">This shortcut sheet</span>
                            <kbd class="px-2 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">?</kbd>
                        </div>
                        <div class="flex items-center justify-between text-body-sm">
                            <span class="text-secondary">Close active modal</span>
                            <kbd class="px-2 py-0.5 rounded bg-surface border border-border text-[11px] font-mono text-primary">Esc</kbd>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Pro-tip footer -->
            <div class="flex items-center justify-between pt-3 border-t border-border-subtle text-body-sm text-secondary">
                <span class="font-label-sm text-[11px] text-muted">Shortcuts are disabled while focused inside inputs or search boxes.</span>
                <button id="dismiss-shortcuts-btn" type="button" class="btn-primary px-3 py-1.5 rounded-md font-label-sm text-label-sm">Got it</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const close = () => {
        overlay.remove();
        document.removeEventListener('keydown', onKeyDown);
    };

    const onKeyDown = (e) => {
        if (e.key === 'Escape') {
            close();
        }
    };

    overlay.querySelector('#close-shortcuts-modal-btn')?.addEventListener('click', close);
    overlay.querySelector('#dismiss-shortcuts-btn')?.addEventListener('click', close);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) close();
    });
    document.addEventListener('keydown', onKeyDown);
}
