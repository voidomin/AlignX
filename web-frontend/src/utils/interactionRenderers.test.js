import { describe, it, expect, vi } from 'vitest';
import { dotColorForType, buildContactRow, isHydrophobicResidue, getResidueChargeColor, getResidueHydrophobicityColor, render2DInteractionMap } from './interactionRenderers';

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

    describe('residue classification helpers', () => {
        it('identifies hydrophobic residues', () => {
            expect(isHydrophobicResidue('LEU')).toBe(true);
            expect(isHydrophobicResidue('val')).toBe(true);
            expect(isHydrophobicResidue('ASP')).toBe(false);
            expect(isHydrophobicResidue(null)).toBe(false);
        });

        it('maps residue charge to colors', () => {
            expect(getResidueChargeColor('ARG')).toBe('#3B82F6'); // Positive
            expect(getResidueChargeColor('ASP')).toBe('#EF4444'); // Negative
            expect(getResidueChargeColor('SER')).toBe('#10B981'); // Polar
            expect(getResidueChargeColor('ALA')).toBe('#9CA3AF'); // Nonpolar
        });

        it('maps residue hydrophobicity to colors', () => {
            expect(getResidueHydrophobicityColor('ILE')).toBe('#EAB308');
            expect(getResidueHydrophobicityColor('GLU')).toBe('#06B6D4');
        });
    });

    describe('render2DInteractionMap', () => {
        it('handles null container gracefully', () => {
            expect(() => render2DInteractionMap(null, 'LIG', [])).not.toThrow();
        });

        it('renders empty contacts state', () => {
            const container = document.createElement('div');
            render2DInteractionMap(container, 'RET', []);
            expect(container.textContent).toContain('No contacts available');
        });

        it('renders SVG map with lines, center node, and interactive residue nodes', () => {
            const container = document.createElement('div');
            const onResidueClick = vi.fn();
            const contacts = [
                { resn: 'TYR', chain: 'A', resi: 191, distance: 2.8, type: 'Hydrogen Bond' },
                { resn: 'ARG', chain: 'A', resi: 104, distance: 3.1, type: 'Salt Bridge' },
                { resn: 'ZN', chain: 'A', resi: 301, distance: 2.2, type: 'Metal Coordination' },
                { resn: 'LEU', chain: 'A', resi: 45, distance: 3.9, type: 'Van der Waals' },
            ];

            render2DInteractionMap(container, 'RET_A_296', contacts, onResidueClick);

            const svg = container.querySelector('svg');
            expect(svg).not.toBeNull();
            expect(container.textContent).toContain('RET');
            expect(container.textContent).toContain('TYR191');
            expect(container.textContent).toContain('ARG104');
            expect(container.textContent).toContain('ZN301');

            const nodes = container.querySelectorAll('g.cursor-pointer');
            expect(nodes.length).toBe(4);

            nodes[0].dispatchEvent(new MouseEvent('click', { bubbles: true }));
            expect(onResidueClick).toHaveBeenCalledWith(contacts[0]);
        });
    });
});

