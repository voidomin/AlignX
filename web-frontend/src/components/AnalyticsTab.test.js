import { describe, it, expect } from 'vitest';
import { AnalyticsTab } from './AnalyticsTab.js';

function makeTab() {
    return new AnalyticsTab();
}

describe('AnalyticsTab', () => {
    it('shows the pre-run placeholder for insights before any run', () => {
        const tab = makeTab();
        tab.render();

        expect(tab.element.querySelectorAll('#analytics-insights-list li')).toHaveLength(0);
        const empty = tab.element.querySelector('#analytics-insights-empty');
        expect(empty.classList.contains('hidden')).toBe(false);
        expect(empty.textContent).toContain('Run alignment');
    });

    it('renders insight bullets with **bold** markdown converted to <strong>', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, null, [], [
            '**Best Match**: `4RLT` and `3UG9` are nearly identical (0.42 Å).',
            'Plain insight with no markdown.',
        ]);

        const items = tab.element.querySelectorAll('#analytics-insights-list li');
        expect(items).toHaveLength(2);
        expect(items[0].innerHTML).toContain('<strong>Best Match</strong>');
        expect(items[1].textContent).toBe('Plain insight with no markdown.');
        expect(tab.element.querySelector('#analytics-insights-empty').classList.contains('hidden')).toBe(true);
    });

    it('escapes HTML in insight text before applying markdown formatting', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, null, [], [
            '**Bold** <img src=x onerror=alert(1)>',
        ]);

        const item = tab.element.querySelector('#analytics-insights-list li');
        expect(item.querySelector('img')).toBeNull();
        expect(item.innerHTML).toContain('&lt;img');
        expect(item.innerHTML).toContain('<strong>Bold</strong>');
    });

    it('shows the "no insights" empty state for a completed run with none', () => {
        const tab = makeTab();
        tab.render();

        tab.updateResults('run_1', null, null, null, [], []);

        expect(tab.element.querySelectorAll('#analytics-insights-list li')).toHaveLength(0);
        const empty = tab.element.querySelector('#analytics-insights-empty');
        expect(empty.classList.contains('hidden')).toBe(false);
        expect(empty.textContent).toContain('No automated insights available');
    });

    it('sub-tab switching still works, including the new insights sub-tab', () => {
        const tab = makeTab();
        tab.render();

        tab.switchSubTab('insights');
        expect(tab.element.querySelector('[data-panel="insights"]').classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('[data-panel="quality"]').classList.contains('hidden')).toBe(true);

        tab.switchSubTab('rmsf');
        expect(tab.element.querySelector('[data-panel="rmsf"]').classList.contains('hidden')).toBe(false);
        expect(tab.element.querySelector('[data-panel="insights"]').classList.contains('hidden')).toBe(true);
    });
});
