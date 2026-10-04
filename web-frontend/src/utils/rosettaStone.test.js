import { describe, it, expect } from 'vitest';
import { ROSETTA_STONE_TERMS, renderRosettaTooltip } from './rosettaStone.js';

describe('rosettaStone utility', () => {
    it('defines definitions for all core scientific terms', () => {
        expect(ROSETTA_STONE_TERMS.rmsd).toBeDefined();
        expect(ROSETTA_STONE_TERMS.tmScore).toBeDefined();
        expect(ROSETTA_STONE_TERMS.ramachandran).toBeDefined();
        expect(ROSETTA_STONE_TERMS.ligandPocket).toBeDefined();
        expect(ROSETTA_STONE_TERMS.clinvar).toBeDefined();
        expect(ROSETTA_STONE_TERMS.discover).toBeDefined();
    });

    it('each term has title, badge, summary, detail, and ruleOfThumb', () => {
        Object.values(ROSETTA_STONE_TERMS).forEach(term => {
            expect(term.title).toBeTruthy();
            expect(term.badge).toBeTruthy();
            expect(term.summary).toBeTruthy();
            expect(term.detail).toBeTruthy();
            expect(term.ruleOfThumb).toBeTruthy();
        });
    });

    it('renderRosettaTooltip returns escaped HTML with badge and description', () => {
        const html = renderRosettaTooltip('rmsd', 'Average RMSD');
        expect(html).toContain('Average RMSD');
        expect(html).toContain('Shape Match');
        expect(html).toContain('Shape Difference (RMSD)');
    });

    it('renderRosettaTooltip handles customLabel being omitted', () => {
        const html = renderRosettaTooltip('tmScore');
        expect(html).toContain('Fold Match');
        expect(html).not.toContain('undefined');
    });

    it('renderRosettaTooltip handles unknown terms gracefully', () => {
        const html = renderRosettaTooltip('unknown_term', 'Fallback');
        expect(html).toBe('Fallback');
    });
});
