import { describe, it, expect } from 'vitest';
import { createInsightIconSvg } from './insightIcons';

const KNOWN_ICONS = [
    'check_circle', 'warning', 'info', 'military_tech', 'compare_arrows',
    'flag', 'medication', 'biotech', 'science', 'group_work', 'verified',
    'star', 'trending_down', 'diamond',
];

describe('createInsightIconSvg', () => {
    it('returns null for an unrecognized icon name', () => {
        expect(createInsightIconSvg('not_a_real_icon')).toBeNull();
        expect(createInsightIconSvg(undefined)).toBeNull();
        expect(createInsightIconSvg('')).toBeNull();
    });

    it.each(KNOWN_ICONS)('returns a real <svg> element with at least one shape for "%s"', (iconName) => {
        const svg = createInsightIconSvg(iconName);
        expect(svg).not.toBeNull();
        expect(svg.tagName.toLowerCase()).toBe('svg');
        expect(svg.namespaceURI).toBe('http://www.w3.org/2000/svg');
        expect(svg.children.length).toBeGreaterThan(0);
        expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
    });

    it('never uses innerHTML/insertAdjacentHTML - built entirely from real SVG child elements', () => {
        const svg = createInsightIconSvg('check_circle');
        expect(svg.innerHTML).not.toBe('');
        // Every child must be a real namespaced SVG element, not raw markup.
        Array.from(svg.children).forEach(child => {
            expect(child.namespaceURI).toBe('http://www.w3.org/2000/svg');
        });
    });
});
