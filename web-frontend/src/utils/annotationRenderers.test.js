import { describe, it, expect } from 'vitest';
import { renderDomainList, renderGoTermList } from './annotationRenderers';

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
});
