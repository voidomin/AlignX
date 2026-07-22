import { escapeHtml } from '../escapeHtml';

// Shared between DiscoveryPanel.js (Foldseek-neighbor-aggregated domains/GO
// terms, each carrying a neighbor_count) and AnalyticsTab.js's Annotations
// sub-tab (a structure's own domains/GO terms - no neighbor_count at all,
// since there's nothing to aggregate across). Both shapes render
// identically except for that optional count badge.
//
// `heading` may be passed as '' by AnalyticsTab.js when it wraps a list's
// own <details>/<summary> around the returned HTML - the list's own label
// row would otherwise be redundant with that summary text.

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
            ${heading ? `<span class="eyebrow">${heading}</span>` : ''}
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
// A well-annotated protein can carry 50-100+ features, each with an
// identical repeated "Highlight in 3D" link - capAt bounds the initial
// render to keep the panel scannable, with a "Show all N" button (grouped
// by buttonClass, already unique per call site) revealing the rest without
// a re-render, wired up by the caller the same way it wires the highlight
// buttons.
export function renderFeatureList(features, heading = 'UniProt features', buttonClass = 'feature-highlight-btn', capAt = 15) {
    if (!features?.length) return '';
    const overflowCount = features.length - capAt;
    return `
        <div class="flex flex-col gap-2">
            ${heading ? `<span class="eyebrow">${heading}</span>` : ''}
            ${features.map((f, i) => `
                <div class="flex justify-between items-center py-1.5 border-b border-border-subtle${i >= capAt ? ' hidden feature-overflow-row' : ''}" ${i >= capAt ? `data-feature-overflow-group="${buttonClass}"` : ''}>
                    <span class="font-body-sm">${f.type}${f.description ? ` <span class="text-secondary text-[11px]">(${f.description})</span>` : ''} <span class="font-mono text-[11px] text-secondary">${f.start === f.end ? f.start : `${f.start}-${f.end}`}</span></span>
                    ${f.highlight_chains ? `<button type="button" class="${buttonClass} font-label-sm text-label-sm text-accent hover:underline" data-feature-index="${i}">Highlight in 3D</button>` : ''}
                </div>
            `).join('')}
            ${overflowCount > 0 ? `<button type="button" class="feature-show-all-btn font-label-sm text-label-sm text-accent hover:underline self-start" data-feature-overflow-group="${buttonClass}">Show all ${features.length}</button>` : ''}
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
// Pulled out of renderCatalyticSiteList's template so the residue-list join
// below isn't a template literal nested inside another one.
function _formatCatalyticResidue(r) {
    const code = r.code || '?';
    const resi = r.resi ?? '?';
    const pdbId = r.reference_pdb_id || '?';
    const chain = r.chain || '?';
    const roles = r.roles_summary ? ` - ${r.roles_summary}` : '';
    return `${code}${resi} (${pdbId} chain ${chain})${roles}`;
}

export function renderCatalyticSiteList(catalyticSites, heading = 'Catalytic sites (M-CSA)') {
    if (!catalyticSites?.length) return '';
    return `
        <div class="flex flex-col gap-2">
            ${heading ? `<span class="eyebrow">${heading}</span>` : ''}
            ${catalyticSites.map(site => {
                const residuesText = site.residues.map(_formatCatalyticResidue).join('; ');
                const ecText = site.ec_numbers?.length ? ` <span class="font-mono text-secondary text-[11px]">(EC ${site.ec_numbers.join(', ')})</span>` : '';
                return `
                <div class="flex flex-col gap-1 py-1.5 border-b border-border-subtle">
                    <span class="font-body-sm">${site.enzyme_name}${ecText}</span>
                    <span class="font-body-sm text-[11px] text-secondary">
                        ${residuesText}
                    </span>
                </div>
            `;
            }).join('')}
        </div>
    `;
}

// QuickGO's real `goAspect` field (see annotation_aggregator.py's
// fetch_quickgo_annotations) comes through as raw snake_case
// ("molecular_function", "biological_process", "cellular_component") -
// mapped to a readable label here, falling back to the raw value itself
// for anything unrecognized rather than hiding it.
const ASPECT_LABELS = {
    molecular_function: 'Molecular function',
    biological_process: 'Biological process',
    cellular_component: 'Cellular component',
};
const ASPECT_ORDER = ['molecular_function', 'biological_process', 'cellular_component'];

export function renderGoTermList(goTerms, heading = 'GO terms') {
    if (!goTerms?.length) return '';
    const groups = new Map();
    for (const g of goTerms) {
        const key = g.aspect || 'unspecified';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(g);
    }
    const orderedKeys = [
        ...ASPECT_ORDER.filter(k => groups.has(k)),
        ...[...groups.keys()].filter(k => !ASPECT_ORDER.includes(k)),
    ];
    return `
        <div class="flex flex-col gap-3">
            ${heading ? `<span class="eyebrow">${heading}</span>` : ''}
            ${orderedKeys.map(key => `
                <div class="flex flex-col gap-1">
                    <span class="font-label-sm text-[11px] text-secondary uppercase tracking-wider">${ASPECT_LABELS[key] || (key === 'unspecified' ? 'Unspecified aspect' : key)}</span>
                    ${groups.get(key).map(g => `
                        <div class="flex justify-between items-center py-1.5 border-b border-border-subtle">
                            <span class="font-body-sm">${g.name || g.id}</span>
                            ${g.neighbor_count != null ? `<span class="font-mono text-[11px] text-secondary">${g.neighbor_count} neighbors</span>` : ''}
                        </div>
                    `).join('')}
                </div>
            `).join('')}
        </div>
    `;
}

// UniProt's real free-text function_summary routinely embeds inline
// citation groups mid-sentence, e.g. "...binds oxygen (PubMed:12345,
// PubMed:67890)." - conservative regex only strips a group that's
// *entirely* PubMed ids; anything else about the parenthetical is left
// untouched (fail closed) rather than risk mangling real UniProt prose.
// Citation data isn't discarded - each id becomes a real, clickable link
// in a collapsed references list appended after the paragraph.
const PUBMED_CITATION_GROUP_RE = /\s*\(((?:PubMed:\d+)(?:,\s*PubMed:\d+)*)\)/g;

export function renderFunctionSummary(text) {
    if (!text) return '';
    const ids = [];
    const stripped = escapeHtml(text).replace(PUBMED_CITATION_GROUP_RE, (match, group) => {
        const groupIds = group.match(/\d+/g);
        if (!groupIds) return match;
        ids.push(...groupIds);
        return '';
    }).trim();
    const refsHtml = ids.length
        ? `
            <details class="mt-1">
                <summary class="font-label-sm text-label-sm text-accent cursor-pointer select-none">${ids.length} reference${ids.length === 1 ? '' : 's'}</summary>
                <div class="flex flex-col gap-1 pt-1">
                    ${ids.map(id => `<a href="https://pubmed.ncbi.nlm.nih.gov/${id}/" target="_blank" rel="noopener noreferrer" class="font-body-sm text-[11px] text-accent hover:underline">PubMed:${id}</a>`).join('')}
                </div>
            </details>
        `
        : '';
    return `<div class="font-body-sm text-primary py-2">${stripped}${refsHtml}</div>`;
}
