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
    }
};

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
