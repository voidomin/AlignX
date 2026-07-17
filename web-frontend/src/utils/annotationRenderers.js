// Shared between DiscoveryPanel.js (Foldseek-neighbor-aggregated domains/GO
// terms, each carrying a neighbor_count) and AnalyticsTab.js's Annotations
// sub-tab (a structure's own domains/GO terms - no neighbor_count at all,
// since there's nothing to aggregate across). Both shapes render
// identically except for that optional count badge.

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

// UniProt's own curated sequence features (active/binding sites, PTMs,
// disulfide bonds, natural variants) - see annotation_aggregator.py's
// fetch_uniprot_features()/aggregate_for_structure(). Same AlphaFold-only
// highlight_chains precedent as renderDomainList() above - only ever
// present when the caller's feature objects actually carry it.
// buttonClass defaults to the original single-list class name for back-
// compat; AnalyticsTab.js now calls this twice (once for PTM-type
// features, once for everything else) with a distinct class per call so
// each call's own data-feature-index can be looked up against the right
// filtered array, instead of colliding on a shared index space.
export function renderFeatureList(features, heading = 'UniProt features', buttonClass = 'feature-highlight-btn') {
    if (!features?.length) return '';
    return `
        <div class="flex flex-col gap-2">
            <span class="eyebrow">${heading}</span>
            ${features.map((f, i) => `
                <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${f.type}${f.description ? ` <span class="text-secondary text-[11px]">(${f.description})</span>` : ''} <span class="font-mono text-[11px] text-secondary">${f.start === f.end ? f.start : `${f.start}-${f.end}`}</span></span>
                    ${f.highlight_chains ? `<button type="button" class="${buttonClass} font-label-sm text-label-sm text-accent hover:underline" data-feature-index="${i}">Highlight in 3D</button>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

// Real curated catalytic/active-site residues from M-CSA (see
// annotation_aggregator.py's fetch_catalytic_site_residues) - unlike
// domains/features above, each residue is reported against M-CSA's own
// curated reference PDB entry rather than this app's structure numbering
// (M-CSA documents catalytic sites per specific solved structure, not as
// a UniProt position), so there's no "Highlight in 3D" button here - this
// is read-only descriptive annotation, the same honest-fallback pattern
// the CATH/oligomeric-assembly badges already use elsewhere in this app.
export function renderCatalyticSiteList(catalyticSites, heading = 'Catalytic sites (M-CSA)') {
    if (!catalyticSites?.length) return '';
    return `
        <div class="flex flex-col gap-2">
            <span class="eyebrow">${heading}</span>
            ${catalyticSites.map(site => `
                <div class="flex flex-col gap-1 py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${site.enzyme_name}${site.ec_numbers?.length ? ` <span class="font-mono text-secondary text-[11px]">(EC ${site.ec_numbers.join(', ')})</span>` : ''}</span>
                    <span class="font-body-sm text-[11px] text-secondary">
                        ${site.residues.map(r => `${r.code || '?'}${r.resi ?? '?'} (${r.reference_pdb_id || '?'} chain ${r.chain || '?'})${r.roles_summary ? ` - ${r.roles_summary}` : ''}`).join('; ')}
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
