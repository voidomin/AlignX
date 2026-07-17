import { describe, it, expect, vi } from 'vitest';
import { wireArrowKeyNavigation } from './tabKeyboardNav';

function makeNav(count) {
    const nav = document.createElement('div');
    for (let i = 0; i < count; i++) {
        const btn = document.createElement('button');
        btn.dataset.key = `tab-${i}`;
        nav.appendChild(btn);
    }
    document.body.appendChild(nav);
    return nav;
}

function fire(target, key) {
    target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
}

describe('wireArrowKeyNavigation', () => {
    it('ArrowRight moves focus to the next button and activates it', () => {
        const nav = makeNav(3);
        const activate = vi.fn();
        wireArrowKeyNavigation(nav, 'button', activate);
        const buttons = nav.querySelectorAll('button');
        buttons[0].focus();

        fire(buttons[0], 'ArrowRight');

        expect(document.activeElement).toBe(buttons[1]);
        expect(activate).toHaveBeenCalledWith(buttons[1]);
    });

    it('ArrowRight wraps from the last button to the first', () => {
        const nav = makeNav(3);
        const activate = vi.fn();
        wireArrowKeyNavigation(nav, 'button', activate);
        const buttons = nav.querySelectorAll('button');
        buttons[2].focus();

        fire(buttons[2], 'ArrowRight');

        expect(document.activeElement).toBe(buttons[0]);
    });

    it('ArrowLeft wraps from the first button to the last', () => {
        const nav = makeNav(3);
        const activate = vi.fn();
        wireArrowKeyNavigation(nav, 'button', activate);
        const buttons = nav.querySelectorAll('button');
        buttons[0].focus();

        fire(buttons[0], 'ArrowLeft');

        expect(document.activeElement).toBe(buttons[2]);
    });

    it('Home jumps to the first button, End jumps to the last', () => {
        const nav = makeNav(4);
        const activate = vi.fn();
        wireArrowKeyNavigation(nav, 'button', activate);
        const buttons = nav.querySelectorAll('button');
        buttons[2].focus();

        fire(buttons[2], 'End');
        expect(document.activeElement).toBe(buttons[3]);

        fire(buttons[3], 'Home');
        expect(document.activeElement).toBe(buttons[0]);
    });

    it('ignores keys other than Arrow/Home/End', () => {
        const nav = makeNav(2);
        const activate = vi.fn();
        wireArrowKeyNavigation(nav, 'button', activate);
        const buttons = nav.querySelectorAll('button');
        buttons[0].focus();

        fire(buttons[0], 'Enter');

        expect(document.activeElement).toBe(buttons[0]);
        expect(activate).not.toHaveBeenCalled();
    });

    it('does nothing if focus is outside the tracked buttons', () => {
        const nav = makeNav(2);
        const activate = vi.fn();
        wireArrowKeyNavigation(nav, 'button', activate);
        const outside = document.createElement('input');
        document.body.appendChild(outside);
        outside.focus();

        fire(outside, 'ArrowRight');

        expect(activate).not.toHaveBeenCalled();
    });
});
