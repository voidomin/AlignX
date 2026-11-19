import { describe, it, expect, afterEach } from 'vitest';
import { ROSETTA_STONE_TERMS, STUDENT_WALKTHROUGH_STEPS, renderRosettaTooltip, showGlossaryModal } from './rosettaStone.js';

describe('rosettaStone utility', () => {
    afterEach(() => {
        document.getElementById('rosetta-glossary-modal')?.remove();
    });

    it('defines definitions for all core scientific terms', () => {
        expect(ROSETTA_STONE_TERMS.rmsd).toBeDefined();
        expect(ROSETTA_STONE_TERMS.tmScore).toBeDefined();
        expect(ROSETTA_STONE_TERMS.ramachandran).toBeDefined();
        expect(ROSETTA_STONE_TERMS.ligandPocket).toBeDefined();
        expect(ROSETTA_STONE_TERMS.clinvar).toBeDefined();
        expect(ROSETTA_STONE_TERMS.discover).toBeDefined();
        expect(ROSETTA_STONE_TERMS.rmsf).toBeDefined();
        expect(ROSETTA_STONE_TERMS.sasa).toBeDefined();
        expect(ROSETTA_STONE_TERMS.bFactor).toBeDefined();
        expect(ROSETTA_STONE_TERMS.shannonEntropy).toBeDefined();
        expect(STUDENT_WALKTHROUGH_STEPS).toHaveLength(4);
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

    it('showGlossaryModal opens the interactive Student Lab Guide & Rosetta Stone modal and filters cards', () => {
        const modal = showGlossaryModal();
        expect(document.getElementById('rosetta-glossary-modal')).toBe(modal);
        expect(modal.querySelectorAll('.rosetta-glossary-card')).toHaveLength(10);

        const searchInput = modal.querySelector('#glossary-search-input');
        searchInput.value = 'Shannon';
        searchInput.dispatchEvent(new Event('input'));

        const visibleCards = Array.from(modal.querySelectorAll('.rosetta-glossary-card'))
            .filter(c => !c.classList.contains('hidden'));
        expect(visibleCards).toHaveLength(1);
        expect(visibleCards[0].textContent).toContain('Shannon Entropy');

        modal.querySelector('#close-glossary-modal-btn').click();
        expect(document.getElementById('rosetta-glossary-modal')).toBeNull();
    });
});
