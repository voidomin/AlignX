import { describe, it, expect } from 'vitest';
import { dotColorForType, buildContactRow } from './interactionRenderers';

describe('interactionRenderers', () => {
    describe('dotColorForType', () => {
        it.each([
            ['Hydrogen Bond', 'bg-accent'],
            ['Salt Bridge', 'bg-success'],
            ['Van der Waals', 'bg-muted'],
            ['Metal Coordination', 'bg-error'],
            ['Polar Contact', 'bg-secondary'],
            ['Something Unknown', 'bg-secondary'],
        ])('maps %s to %s', (type, expected) => {
            expect(dotColorForType(type)).toBe(expected);
        });
    });

    describe('buildContactRow', () => {
        it('renders residue, chain, resi, distance, and type', () => {
            const row = buildContactRow({ resn: 'HIS', chain: 'A', resi: 87, distance: 2.14, type: 'Salt Bridge' });

            expect(row.tagName).toBe('TR');
            expect(row.textContent).toContain('HIS');
            expect(row.textContent).toContain('A');
            expect(row.textContent).toContain('87');
            expect(row.textContent).toContain('2.1');
            expect(row.textContent).toContain('Salt Bridge');
        });

        it('falls back to "residue" then "UNK" when resn is missing', () => {
            const row = buildContactRow({ residue: 'TYR', chain: 'A', resi: 42, distance: 3.27, type: 'Polar Contact' });
            expect(row.textContent).toContain('TYR');

            const rowUnk = buildContactRow({ chain: 'A', resi: 42, distance: 3.27, type: 'Polar Contact' });
            expect(rowUnk.textContent).toContain('UNK');
        });
    });
});
