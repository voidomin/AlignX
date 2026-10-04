import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { showDesktopModal } from './DesktopModal.js';

describe('showDesktopModal', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('renders the desktop download modal into document.body', () => {
        showDesktopModal();
        const modal = document.getElementById('desktop-download-modal');
        expect(modal).not.toBeNull();
        expect(modal.textContent).toContain('StructScope Desktop Edition');
        expect(modal.textContent).toContain('docker run -p 8000:8000 alignx');
    });

    it('clicking close button removes modal from DOM', () => {
        showDesktopModal();
        const closeBtn = document.getElementById('close-desktop-modal-btn');
        closeBtn.click();
        expect(document.getElementById('desktop-download-modal')).toBeNull();
    });

    it('clicking dismiss button removes modal from DOM', () => {
        showDesktopModal();
        const dismissBtn = document.getElementById('dismiss-desktop-modal-btn');
        dismissBtn.click();
        expect(document.getElementById('desktop-download-modal')).toBeNull();
    });

    it('calling showDesktopModal repeatedly replaces any previous modal without duplicates', () => {
        showDesktopModal();
        showDesktopModal();
        const modals = document.querySelectorAll('#desktop-download-modal');
        expect(modals.length).toBe(1);
    });
});
