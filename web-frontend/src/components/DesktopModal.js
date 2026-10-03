/**
 * Modal to present Desktop Edition options for users requiring heavy computation,
 * unlimited file sizes, or strict data privacy.
 */
export function showDesktopModal() {
    const existing = document.getElementById('desktop-download-modal');
    if (existing) {
        existing.remove();
    }

    const overlay = document.createElement('div');
    overlay.id = 'desktop-download-modal';
    overlay.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity duration-200';

    overlay.innerHTML = `
        <div class="relative w-full max-w-2xl bg-surface border border-border rounded-xl shadow-2xl p-6 flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
            <div class="flex items-start justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center text-accent">
                        <span class="material-symbols-outlined text-[24px]">desktop_windows</span>
                    </div>
                    <div>
                        <h3 class="font-headline-sm text-headline-sm font-bold text-primary">StructScope Desktop Edition</h3>
                        <p class="font-body-sm text-body-sm text-secondary">Run unlimited alignments &amp; custom structures with 100% privacy on your own PC.</p>
                    </div>
                </div>
                <button id="close-desktop-modal-btn" type="button" class="text-secondary hover:text-primary p-1 rounded-md transition-colors" aria-label="Close modal">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <!-- Key Benefits Grid -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div class="p-3 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1">
                    <span class="material-symbols-outlined text-[20px] text-accent">lock</span>
                    <span class="font-label-sm text-label-sm font-semibold text-primary">100% Private</span>
                    <span class="font-body-sm text-[12px] text-secondary">Your proprietary structures never leave your local computer.</span>
                </div>
                <div class="p-3 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1">
                    <span class="material-symbols-outlined text-[20px] text-accent">all_inclusive</span>
                    <span class="font-label-sm text-label-sm font-semibold text-primary">Zero Limits</span>
                    <span class="font-body-sm text-[12px] text-secondary">No server timeouts, RAM caps, or protein size restrictions.</span>
                </div>
                <div class="p-3 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1">
                    <span class="material-symbols-outlined text-[20px] text-accent">speed</span>
                    <span class="font-label-sm text-label-sm font-semibold text-primary">Full Performance</span>
                    <span class="font-body-sm text-[12px] text-secondary">Direct multi-core CPU and native Mustang/Foldseek speed.</span>
                </div>
            </div>

            <!-- Distribution Options -->
            <div class="flex flex-col gap-3">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Choose your local setup:</span>

                <!-- Option 1: Docker -->
                <div class="p-4 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md font-semibold text-primary flex items-center gap-1.5">
                            <span class="material-symbols-outlined text-[18px] text-accent">inventory_2</span>
                            Docker Container (Recommended)
                        </span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-accent-muted text-accent">Plug &amp; Play</span>
                    </div>
                    <span class="font-body-sm text-body-sm text-secondary">Pre-compiles Mustang binary and all dependencies inside an isolated container:</span>
                    <pre class="bg-surface p-2.5 rounded border border-border-subtle font-mono text-[12px] text-primary overflow-x-auto select-all">docker run -p 8000:8000 alignx</pre>
                </div>

                <!-- Option 2: Local Python Launcher -->
                <div class="p-4 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <span class="font-label-md text-label-md font-semibold text-primary flex items-center gap-1.5">
                            <span class="material-symbols-outlined text-[18px] text-accent">terminal</span>
                            Python Local Environment
                        </span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-surface border border-border text-secondary">Native</span>
                    </div>
                    <span class="font-body-sm text-body-sm text-secondary">Run directly on Windows (WSL/Bio3D), macOS, or Linux:</span>
                    <pre class="bg-surface p-2.5 rounded border border-border-subtle font-mono text-[12px] text-primary overflow-x-auto select-all">git clone https://github.com/voidomin/AlignX.git
cd AlignX &amp;&amp; python scripts/launch_desktop.py</pre>
                </div>
            </div>

            <div class="flex items-center justify-end gap-3 pt-3 border-t border-border">
                <a href="https://github.com/voidomin/AlignX" target="_blank" rel="noopener noreferrer" class="btn-secondary px-4 py-2 rounded-md font-label-md text-label-md flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-[16px]">code</span>
                    GitHub Repository
                </a>
                <button id="dismiss-desktop-modal-btn" type="button" class="btn-primary px-4 py-2 rounded-md font-label-md text-label-md">
                    Got it, thanks!
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const closeModal = () => overlay.remove();
    const closeBtn = overlay.querySelector('#close-desktop-modal-btn');
    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    const dismissBtn = overlay.querySelector('#dismiss-desktop-modal-btn');
    if (dismissBtn) dismissBtn.addEventListener('click', closeModal);

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });
}
