import { describe, it, expect } from 'vitest';
import { escapeHtml } from './escapeHtml';

describe('escapeHtml', () => {
    it('escapes the 5 HTML-significant characters', () => {
        expect(escapeHtml('<script>alert(1)</script>')).toBe(
            '&lt;script&gt;alert(1)&lt;/script&gt;'
        );
        expect(escapeHtml('a & b')).toBe('a &amp; b');
        expect(escapeHtml(`"quoted" 'single'`)).toBe('&quot;quoted&quot; &#39;single&#39;');
    });

    it('leaves plain text untouched', () => {
        expect(escapeHtml('4RLT')).toBe('4RLT');
        expect(escapeHtml('discover_1783340803')).toBe('discover_1783340803');
    });

    it('handles null/undefined/numbers without throwing', () => {
        expect(escapeHtml(null)).toBe('');
        expect(escapeHtml(undefined)).toBe('');
        expect(escapeHtml(0)).toBe('0');
    });

    it('neutralizes an attribute-breakout payload', () => {
        const payload = `"><img src=x onerror=alert(1)>`;
        const escaped = escapeHtml(payload);
        expect(escaped).not.toContain('<img');
        expect(escaped).not.toContain('">');
    });
});
