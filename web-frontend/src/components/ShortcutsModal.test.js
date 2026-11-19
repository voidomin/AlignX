import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { showShortcutsModal } from './ShortcutsModal.js';

describe('ShortcutsModal', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('renders the modal overlay with all shortcut categories', () => {
        showShortcutsModal();
        const overlay = document.getElementById('shortcuts-modal-overlay');
        expect(overlay).not.toBeNull();
        expect(overlay.textContent).toContain('Keyboard Shortcuts');
        expect(overlay.textContent).toContain('Tabs & Navigation');
        expect(overlay.textContent).toContain('3D Viewport Controls');
        expect(overlay.textContent).toContain('Assistance & Modals');
    });

    it('toggles off when called a second time', () => {
        showShortcutsModal();
        expect(document.getElementById('shortcuts-modal-overlay')).not.toBeNull();
        showShortcutsModal();
        expect(document.getElementById('shortcuts-modal-overlay')).toBeNull();
    });

    it('closes on close button click', () => {
        showShortcutsModal();
        const closeBtn = document.getElementById('close-shortcuts-modal-btn');
        closeBtn.click();
        expect(document.getElementById('shortcuts-modal-overlay')).toBeNull();
    });

    it('closes on dismiss button click', () => {
        showShortcutsModal();
        const dismissBtn = document.getElementById('dismiss-shortcuts-btn');
        dismissBtn.click();
        expect(document.getElementById('shortcuts-modal-overlay')).toBeNull();
    });

    it('closes on Escape key press', () => {
        showShortcutsModal();
        expect(document.getElementById('shortcuts-modal-overlay')).not.toBeNull();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(document.getElementById('shortcuts-modal-overlay')).toBeNull();
    });

    it('closes when clicking the backdrop overlay', () => {
        showShortcutsModal();
        const overlay = document.getElementById('shortcuts-modal-overlay');
        overlay.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(document.getElementById('shortcuts-modal-overlay')).toBeNull();
    });
});
