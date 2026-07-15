import { describe, it, expect } from 'vitest';
import { renderDomainList, renderGoTermList, renderFeatureList } from './annotationRenderers';

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

        it('renders name (falling back to id) and aspect per term', () => {
            const html = renderGoTermList([{ id: 'GO:0005344', name: 'oxygen carrier activity', aspect: 'F' }]);
            expect(html).toContain('oxygen carrier activity');
            expect(html).toContain('(F)');
        });

        it('falls back to the raw GO id when no name is resolved', () => {
            const html = renderGoTermList([{ id: 'GO:0005344', aspect: 'F' }]);
            expect(html).toContain('GO:0005344');
        });

        it('shows n/a for a missing aspect', () => {
            const html = renderGoTermList([{ id: 'GO:0005344', name: 'oxygen carrier activity' }]);
            expect(html).toContain('(n/a)');
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
    });
});
