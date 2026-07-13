// Shared between DiscoverTab.js (Foldseek-neighbor-aggregated domains/GO
// terms, each carrying a neighbor_count) and AnalyticsTab.js's Annotations
// sub-tab (Compare-mode, one structure's own domains/GO terms - no
// neighbor_count at all, since there's nothing to aggregate across). Both
// shapes render identically except for that optional count badge.

// Compare mode's AlphaFold-sourced structures carry a highlight_chains map
// per domain (see annotation_aggregator.py's aggregate_for_structure) -
// AlphaFold residue numbering matches UniProt exactly by construction, so
// InterPro's domain positions are safe to use as real structure residue
// numbers there. Discover mode's neighbor-aggregated domains never carry
// this (a neighbor's domain position says nothing about where it'd fall in
// the query's own numbering), so the button only ever appears when the
// caller's domain objects actually have it - nothing here is Discover- or
// Compare-specific on its own.
export function renderDomainList(domains, heading = 'Domains / families') {
    if (!domains?.length) return '';
    return `
        <div class="flex flex-col gap-2">
            <span class="eyebrow">${heading}</span>
            ${domains.map((d, i) => `
                <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${d.name} <span class="text-secondary text-[11px]">(${d.type})</span></span>
                    <span class="flex items-center gap-3">
                        ${d.neighbor_count != null ? `<span class="font-mono text-[11px] text-secondary">${d.neighbor_count} neighbors</span>` : ''}
                        ${d.highlight_chains ? `<button type="button" class="domain-highlight-btn font-label-sm text-label-sm text-accent hover:underline" data-domain-index="${i}">Highlight in 3D</button>` : ''}
                    </span>
                </div>
            `).join('')}
        </div>
    `;
}

export function renderGoTermList(goTerms, heading = 'GO terms') {
    if (!goTerms?.length) return '';
    return `
        <div class="flex flex-col gap-2">
            <span class="eyebrow">${heading}</span>
            ${goTerms.map(g => `
                <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${g.name || g.id} <span class="text-secondary text-[11px]">(${g.aspect || 'n/a'})</span></span>
                    ${g.neighbor_count != null ? `<span class="font-mono text-[11px] text-secondary">${g.neighbor_count} neighbors</span>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}
