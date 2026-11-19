import { escapeHtml } from '../escapeHtml';

/**
 * The Rosetta Stone translates complex structural biology jargon
 * into clear, intuitive concepts for non-biotech and student users.
 */
export const ROSETTA_STONE_TERMS = {
    rmsd: {
        title: 'Shape Difference (RMSD)',
        badge: 'Shape Match',
        summary: 'Measures how much the 3D structures diverge on average in Angstroms (Å).',
        detail: 'Scores below 2.0 Å mean the proteins are nearly identical twins in 3D shape; scores above 4.0 Å indicate noticeably different shapes.',
        ruleOfThumb: '< 2.0 Å: Close match | > 4.0 Å: Distinct difference'
    },
    tmScore: {
        title: 'Fold Family Match (TM-score)',
        badge: 'Fold Match',
        summary: 'A normalized similarity score ranging from 0.0 to 1.0.',
        detail: 'Unlike sequence-only comparisons, TM-score evaluates 3D architecture. Any score above 0.5 proves both proteins share the exact same structural fold family.',
        ruleOfThumb: '> 0.50: Same structural fold family | < 0.30: Unrelated folds'
    },
    ramachandran: {
        title: 'Protein Physical Health (Ramachandran)',
        badge: 'Backbone Health',
        summary: 'A quality check on the protein backbone dihedral angles.',
        detail: 'Checks if amino acid residues sit in physically natural, unstrained geometry. Outliers highlight possible structural distortion or modeling errors.',
        ruleOfThumb: '> 95% Favored: Healthy physical model'
    },
    ligandPocket: {
        title: 'Medicine Docking Cavity (Binding Pocket)',
        badge: 'Drug Target',
        summary: 'A 3D surface cavity where drug molecules can anchor.',
        detail: 'Identifies druggable pockets on the protein surface where therapeutic compounds or natural cofactors bind to switch biological activity on or off.',
        ruleOfThumb: 'Larger volume & high SASA indicate prime docking sites'
    },
    clinvar: {
        title: 'Human Disease Link (ClinVar)',
        badge: 'Medical Impact',
        summary: 'Connects genetic mutations directly to human medical records.',
        detail: 'Surfaces whether a specific amino acid substitution is medically classified as Pathogenic (causes disease), Benign (harmless variation), or Uncertain.',
        ruleOfThumb: 'Pathogenic = Clinically confirmed disease variant'
    },
    discover: {
        title: 'Unknown Protein Decoder (Discovery Mode)',
        badge: 'Mystery Decoder',
        summary: 'Predicts biological function for unannotated 3D models.',
        detail: 'Searches global structural databases using Foldseek to find known proteins that share the same 3D fold, then aggregates functional GO terms and domains.',
        ruleOfThumb: 'Structure is conserved millions of years longer than sequence'
    },
    rmsf: {
        title: 'Per-Residue Flexibility (RMSF)',
        badge: 'Loop Motion',
        summary: 'Shows which individual amino acid positions move or flex the most across aligned structures.',
        detail: 'High RMSF peaks usually correspond to flexible surface loops or hinge regions that open and close during catalysis, while low RMSF valleys mark the rigid structural core.',
        ruleOfThumb: 'Low (< 1.0 Å): Rigid core | High (> 2.5 Å): Flexible loop or hinge'
    },
    sasa: {
        title: 'Exposed Surface Area (SASA)',
        badge: 'Water Exposure',
        summary: 'Measures how much of a pocket or residue is reachable by water molecules (in Å²).',
        detail: 'Solvent Accessible Surface Area (Shrake-Rupley) tells you whether a binding site is buried deep inside the protein core or open on the surface for ligands to enter.',
        ruleOfThumb: 'High SASA = Exposed surface cleft | Low SASA = Buried hydrophobic pocket'
    },
    bFactor: {
        title: 'Atomic Uncertainty / Confidence (B-factor & pLDDT)',
        badge: 'Model Confidence',
        summary: 'Indicates thermal vibration in crystal structures (B-factor) or AI confidence in AlphaFold models (pLDDT).',
        detail: 'In X-ray crystallography, lower B-factors mean sharper, more certain atomic coordinates. In AlphaFold predictions, the B-factor column stores pLDDT (0-100), where > 90 is very high confidence.',
        ruleOfThumb: 'Crystal B-factor < 30: Ordered | AlphaFold pLDDT > 70: Confident fold'
    },
    shannonEntropy: {
        title: 'Evolutionary Conservation (Shannon Entropy)',
        badge: 'Evolution Score',
        summary: 'Measures how strictly evolution preserves each amino acid across related species.',
        detail: 'Calculated from NCBI BLAST homologs: positions that never mutate across hundreds of species (low entropy / high conservation) almost always form the catalytic active site or essential fold core.',
        ruleOfThumb: 'Strictly conserved residues = Essential for biological function'
    }
};

export const STUDENT_WALKTHROUGH_STEPS = [
    {
        step: '1',
        title: 'Load a Classic Pair in Workspace',
        description: 'Pick a curated Quick Start example (such as Active vs. Inactive Kinase or Hemoglobin) or type 2+ PDB/AlphaFold IDs.',
    },
    {
        step: '2',
        title: 'Run 3D Structural Superposition',
        description: 'Click "Run Alignment" to superimpose the proteins in 3D with Mustang and calculate pairwise RMSD & TM-scores.',
    },
    {
        step: '3',
        title: 'Read the Sequence & 3D Verdict',
        description: 'Open the Sequence tab to see if the 3D fold is conserved even when sequence identity is low (< 30%), and click any residue to focus it in 3D.',
    },
    {
        step: '4',
        title: 'Inspect Pockets, Quality & Export',
        description: 'Check Ramachandran backbone health in Analytics, inspect drug bioactivity in Ligands, and download your PDF Lab Report or Jupyter Notebook.',
    },
];

/**
 * Renders an inline help badge with tooltip for a scientific term.
 * @param {string} termKey - Key in ROSETTA_STONE_TERMS
 * @param {string} [customLabel] - Optional custom label to display next to badge
 * @returns {string} HTML string
 */
export function renderRosettaTooltip(termKey, customLabel = '') {
    const term = ROSETTA_STONE_TERMS[termKey];
    if (!term) return escapeHtml(customLabel);

    const safeTitle = escapeHtml(term.title);
    const safeDetail = escapeHtml(term.detail);
    const safeRule = escapeHtml(term.ruleOfThumb);
    const safeBadge = escapeHtml(term.badge);
    const labelHtml = customLabel ? `<span class="mr-1">${escapeHtml(customLabel)}</span>` : '';

    return `
        <span class="inline-flex items-center gap-1 group relative cursor-help select-none">
            ${labelHtml}
            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-surface-raised border border-border-subtle text-secondary group-hover:text-accent transition-colors" title="${safeTitle}: ${safeDetail}">
                <span class="material-symbols-outlined text-[13px] mr-0.5 text-accent">lightbulb</span>
                ${safeBadge}
            </span>
            <span class="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 rounded-lg bg-surface border border-border shadow-panel text-[12px] leading-relaxed text-primary opacity-0 group-hover:opacity-100 transition-opacity z-50">
                <span class="font-bold text-accent block mb-1">${safeTitle}</span>
                <span class="text-secondary block mb-1.5">${safeDetail}</span>
                <span class="text-[11px] font-mono text-muted block border-t border-border-subtle pt-1">${safeRule}</span>
            </span>
        </span>
    `;
}

/**
 * Opens the interactive Rosetta Stone Student Glossary & Lab Walkthrough modal.
 */
export function showGlossaryModal() {
    const existing = document.getElementById('rosetta-glossary-modal');
    if (existing) {
        existing.remove();
    }

    const overlay = document.createElement('div');
    overlay.id = 'rosetta-glossary-modal';
    overlay.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm transition-opacity duration-200';

    const stepsHtml = STUDENT_WALKTHROUGH_STEPS.map(s => `
        <div class="p-3 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1">
            <div class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-accent-muted text-accent font-mono text-[11px] font-bold flex items-center justify-center shrink-0">${escapeHtml(s.step)}</span>
                <span class="font-label-md text-label-md font-semibold text-primary">${escapeHtml(s.title)}</span>
            </div>
            <p class="font-body-sm text-[11px] text-secondary leading-relaxed pl-7">${escapeHtml(s.description)}</p>
        </div>
    `).join('');

    const cardsHtml = Object.entries(ROSETTA_STONE_TERMS).map(([key, term]) => `
        <div data-term-card="${escapeHtml(key)}" class="rosetta-glossary-card p-3.5 rounded-lg bg-surface-raised border border-border-subtle flex flex-col gap-1.5">
            <div class="flex items-center justify-between gap-2">
                <span class="font-label-md text-label-md font-semibold text-primary">${escapeHtml(term.title)}</span>
                <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-accent-muted text-accent shrink-0">${escapeHtml(term.badge)}</span>
            </div>
            <p class="font-body-sm text-body-sm text-primary">${escapeHtml(term.summary)}</p>
            <p class="font-body-sm text-[11px] text-secondary leading-relaxed">${escapeHtml(term.detail)}</p>
            <div class="mt-auto pt-1.5 border-t border-border-subtle font-mono text-[11px] text-accent">
                Rule of thumb: ${escapeHtml(term.ruleOfThumb)}
            </div>
        </div>
    `).join('');

    overlay.innerHTML = `
        <div class="relative w-full max-w-4xl bg-surface border border-border rounded-xl shadow-2xl p-6 flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
            <div class="flex items-start justify-between gap-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center text-accent shrink-0">
                        <span class="material-symbols-outlined text-[22px]">school</span>
                    </div>
                    <div>
                        <h3 class="font-headline-sm text-headline-sm font-bold text-primary">Student Lab Guide &amp; Rosetta Stone Glossary</h3>
                        <p class="font-body-sm text-body-sm text-secondary">Plain-English guide to structural alignment workflows, metrics, and drug discovery indicators.</p>
                    </div>
                </div>
                <button id="close-glossary-modal-btn" type="button" class="text-secondary hover:text-primary p-1 rounded-md transition-colors" aria-label="Close glossary modal">
                    <span class="material-symbols-outlined text-[20px]">close</span>
                </button>
            </div>

            <div class="flex flex-col gap-2">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">4-Step Lab Workflow</span>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    ${stepsHtml}
                </div>
            </div>

            <div class="flex flex-col gap-2.5 pt-2 border-t border-border">
                <div class="flex flex-wrap items-center justify-between gap-2">
                    <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Rosetta Stone Metric Dictionary (10 Core Concepts)</span>
                    <input id="glossary-search-input" type="search" placeholder="Filter terms (e.g. RMSD, TM-score, ClinVar)..." aria-label="Filter glossary terms" class="bg-surface-raised border border-border-subtle rounded-md px-2.5 py-1 font-body-sm text-body-sm text-primary focus:outline-none focus:border-accent w-64" />
                </div>
                <div id="glossary-cards-grid" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    ${cardsHtml}
                </div>
            </div>

            <div class="flex items-center justify-end pt-2 border-t border-border">
                <button id="dismiss-glossary-modal-btn" type="button" class="btn-secondary px-4 py-1.5 rounded-md font-label-md text-label-md">Got it</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const closeModal = () => overlay.remove();
    overlay.querySelector('#close-glossary-modal-btn')?.addEventListener('click', closeModal);
    overlay.querySelector('#dismiss-glossary-modal-btn')?.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });

    const searchInput = overlay.querySelector('#glossary-search-input');
    searchInput?.addEventListener('input', () => {
        const q = searchInput.value.trim().toLowerCase();
        overlay.querySelectorAll('.rosetta-glossary-card').forEach(card => {
            const match = !q || card.textContent.toLowerCase().includes(q);
            card.classList.toggle('hidden', !match);
        });
    });

    return overlay;
}
