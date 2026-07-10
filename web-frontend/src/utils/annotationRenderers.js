// Shared between DiscoverTab.js (Foldseek-neighbor-aggregated domains/GO
// terms, each carrying a neighbor_count) and AnalyticsTab.js's Annotations
// sub-tab (Compare-mode, one structure's own domains/GO terms - no
// neighbor_count at all, since there's nothing to aggregate across). Both
// shapes render identically except for that optional count badge.

export function renderDomainList(domains, heading = 'Domains / families') {
    if (!domains || !domains.length) return '';
    return `
        <div class="flex flex-col gap-2">
            <span class="eyebrow">${heading}</span>
            ${domains.map(d => `
                <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${d.name} <span class="text-secondary text-[11px]">(${d.type})</span></span>
                    ${d.neighbor_count != null ? `<span class="font-mono text-[11px] text-secondary">${d.neighbor_count} neighbors</span>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

export function renderGoTermList(goTerms, heading = 'GO terms') {
    if (!goTerms || !goTerms.length) return '';
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
