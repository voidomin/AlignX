import { describe, it, expect } from 'vitest';
import { renderDomainList, renderGoTermList, renderFeatureList, renderCatalyticSiteList, renderFunctionSummary } from './annotationRenderers';

describe('annotationRenderers', () => {
    describe('renderDomainList', () => {
        it('returns an empty string for an empty or missing list', () => {
            expect(renderDomainList([])).toBe('');
            expect(renderDomainList(null)).toBe('');
            expect(renderDomainList(undefined)).toBe('');
        });

        it('renders a name/type row per domain, using the default heading', () => {
            const html = renderDomainList([{ name: 'Globin', type: 'domain' }]);
            expect(html).toContain('Domains / families');
            expect(html).toContain('Globin');
            expect(html).toContain('domain');
        });

        it('shows a neighbor_count badge when present (Discover context)', () => {
            const html = renderDomainList([{ name: 'Globin', type: 'domain', neighbor_count: 4 }]);
            expect(html).toContain('4 neighbors');
        });

        it('omits the neighbor_count badge when absent (Compare-mode context)', () => {
            const html = renderDomainList([{ name: 'Globin', type: 'domain' }]);
            expect(html).not.toContain('neighbors');
        });

        it('accepts a custom heading', () => {
            const html = renderDomainList([{ name: 'Globin', type: 'domain' }], 'Common domains / families');
            expect(html).toContain('Common domains / families');
        });

        it('shows a "Highlight in 3D" button when a domain has highlight_chains', () => {
            const html = renderDomainList([
                { name: 'Globin', type: 'domain', highlight_chains: { A: [2, 3, 4] } },
            ]);
            expect(html).toContain('Highlight in 3D');
            expect(html).toContain('data-domain-index="0"');
        });

        it('omits the button when highlight_chains is absent (Discover neighbor domains)', () => {
            const html = renderDomainList([{ name: 'Globin', type: 'domain', neighbor_count: 4 }]);
            expect(html).not.toContain('Highlight in 3D');
        });
    });

    describe('renderGoTermList', () => {
        it('returns an empty string for an empty or missing list', () => {
            expect(renderGoTermList([])).toBe('');
            expect(renderGoTermList(null)).toBe('');
        });

        it('renders name (falling back to id) grouped under its aspect', () => {
            const html = renderGoTermList([{ id: 'GO:0005344', name: 'oxygen carrier activity', aspect: 'molecular_function' }]);
            expect(html).toContain('oxygen carrier activity');
            expect(html).toContain('Molecular function');
        });

        it('falls back to the raw aspect value for an unrecognized aspect', () => {
            const html = renderGoTermList([{ id: 'GO:0005344', name: 'oxygen carrier activity', aspect: 'F' }]);
            expect(html).toContain('>F<');
        });

        it('falls back to the raw GO id when no name is resolved', () => {
            const html = renderGoTermList([{ id: 'GO:0005344', aspect: 'F' }]);
            expect(html).toContain('GO:0005344');
        });

        it('groups terms with a missing aspect under "Unspecified aspect"', () => {
            const html = renderGoTermList([{ id: 'GO:0005344', name: 'oxygen carrier activity' }]);
            expect(html).toContain('Unspecified aspect');
        });

        it('groups multiple terms under their own aspect sub-headers in a fixed order', () => {
            const html = renderGoTermList([
                { id: 'GO:1', name: 'a cellular component term', aspect: 'cellular_component' },
                { id: 'GO:2', name: 'a molecular function term', aspect: 'molecular_function' },
                { id: 'GO:3', name: 'a biological process term', aspect: 'biological_process' },
            ]);
            const mfIndex = html.indexOf('Molecular function');
            const bpIndex = html.indexOf('Biological process');
            const ccIndex = html.indexOf('Cellular component');
            expect(mfIndex).toBeGreaterThan(-1);
            expect(mfIndex).toBeLessThan(bpIndex);
            expect(bpIndex).toBeLessThan(ccIndex);
        });
    });

    describe('renderFeatureList', () => {
        it('returns an empty string for an empty or missing list', () => {
            expect(renderFeatureList([])).toBe('');
            expect(renderFeatureList(null)).toBe('');
            expect(renderFeatureList(undefined)).toBe('');
        });

        it('renders type, description, and residue position, using the default heading', () => {
            const html = renderFeatureList([
                { type: 'Binding site', description: 'proximal binding residue', start: 88, end: 88 },
            ]);
            expect(html).toContain('UniProt features');
            expect(html).toContain('Binding site');
            expect(html).toContain('proximal binding residue');
            expect(html).toContain('88');
        });

        it('shows a residue range when start and end differ', () => {
            const html = renderFeatureList([{ type: 'Natural variant', description: '', start: 10, end: 12 }]);
            expect(html).toContain('10-12');
        });

        it('accepts a custom heading', () => {
            const html = renderFeatureList([{ type: 'Binding site', description: '', start: 1, end: 1 }], 'Custom heading');
            expect(html).toContain('Custom heading');
        });

        it('shows a "Highlight in 3D" button when a feature has highlight_chains', () => {
            const html = renderFeatureList([
                { type: 'Binding site', description: '', start: 88, end: 88, highlight_chains: { A: [88] } },
            ]);
            expect(html).toContain('Highlight in 3D');
            expect(html).toContain('data-feature-index="0"');
        });

        it('omits the button when highlight_chains is absent (non-AlphaFold structures)', () => {
            const html = renderFeatureList([{ type: 'Binding site', description: '', start: 88, end: 88 }]);
            expect(html).not.toContain('Highlight in 3D');
        });

        it('accepts a custom button class, for callers rendering more than one list from the same feature type', () => {
            const html = renderFeatureList(
                [{ type: 'Glycosylation', description: '', start: 4, end: 4, highlight_chains: { A: [4] } }],
                'PTM sites',
                'ptm-highlight-btn',
            );
            expect(html).toContain('ptm-highlight-btn');
            expect(html).not.toContain('feature-highlight-btn');
        });
    });

    describe('renderCatalyticSiteList', () => {
        it('returns an empty string for an empty or missing list', () => {
            expect(renderCatalyticSiteList([])).toBe('');
            expect(renderCatalyticSiteList(null)).toBe('');
            expect(renderCatalyticSiteList(undefined)).toBe('');
        });

        it('renders enzyme name, EC number, and per-residue reference-PDB/role info', () => {
            const html = renderCatalyticSiteList([
                {
                    mcsa_id: 1,
                    enzyme_name: 'glutamate racemase',
                    ec_numbers: ['5.1.1.3'],
                    residues: [
                        { roles_summary: 'proton acceptor', reference_pdb_id: '1b73', chain: 'A', resi: 7, code: 'Asp' },
                    ],
                },
            ]);
            expect(html).toContain('Catalytic sites (M-CSA)');
            expect(html).toContain('glutamate racemase');
            expect(html).toContain('5.1.1.3');
            expect(html).toContain('Asp7');
            expect(html).toContain('1b73 chain A');
            expect(html).toContain('proton acceptor');
        });

        it('has no "Highlight in 3D" button - M-CSA residues are reported against its own reference PDB, not this app\'s structure numbering', () => {
            const html = renderCatalyticSiteList([
                { mcsa_id: 1, enzyme_name: 'test enzyme', ec_numbers: [], residues: [] },
            ]);
            expect(html).not.toContain('Highlight in 3D');
        });
    });

    describe('renderFeatureList overflow capping', () => {
        const makeFeatures = (n) => Array.from({ length: n }, (_, i) => ({ type: 'Binding site', description: '', start: i, end: i }));

        it('shows no "Show all" button and no hidden rows when under the cap', () => {
            const html = renderFeatureList(makeFeatures(5));
            expect(html).not.toContain('Show all');
            expect(html).not.toContain('feature-overflow-row');
        });

        it('hides rows past the cap and shows a "Show all N" button grouped by buttonClass', () => {
            const html = renderFeatureList(makeFeatures(20), 'UniProt features', 'feature-highlight-btn');
            expect(html).toContain('Show all 20');
            expect(html).toContain('data-feature-overflow-group="feature-highlight-btn"');
            const hiddenRowCount = (html.match(/feature-overflow-row/g) || []).length;
            expect(hiddenRowCount).toBe(5); // 20 - default capAt of 15
        });
    });

    describe('renderFunctionSummary', () => {
        it('returns an empty string for missing text', () => {
            expect(renderFunctionSummary('')).toBe('');
            expect(renderFunctionSummary(null)).toBe('');
            expect(renderFunctionSummary(undefined)).toBe('');
        });

        it('renders plain text with no references block when there are no PubMed citations', () => {
            const html = renderFunctionSummary('Binds oxygen reversibly.');
            expect(html).toContain('Binds oxygen reversibly.');
            expect(html).not.toContain('reference');
        });

        it('strips an inline PubMed citation group and appends it as real links in a collapsed references list', () => {
            const html = renderFunctionSummary('Binds oxygen reversibly (PubMed:12345, PubMed:67890).');
            expect(html).not.toContain('(PubMed:12345');
            expect(html).toContain('Binds oxygen reversibly.');
            expect(html).toContain('2 references');
            expect(html).toContain('https://pubmed.ncbi.nlm.nih.gov/12345/');
            expect(html).toContain('https://pubmed.ncbi.nlm.nih.gov/67890/');
        });

        it('uses singular "reference" for exactly one citation', () => {
            const html = renderFunctionSummary('Binds oxygen (PubMed:12345).');
            expect(html).toContain('1 reference');
            expect(html).not.toContain('1 references');
        });

        it('fails closed and leaves a non-PubMed parenthetical untouched', () => {
            const html = renderFunctionSummary('Binds oxygen (see Figure 2).');
            expect(html).toContain('(see Figure 2)');
            expect(html).not.toContain('reference');
        });

        it('escapes HTML in the summary text', () => {
            const html = renderFunctionSummary('<script>alert(1)</script>');
            expect(html).not.toContain('<script>');
            expect(html).toContain('&lt;script&gt;');
        });
    });
});
