// "Editorial Instrument" design system (v4): warm dark ground, serif headings +
// sans UI + monospace data, one coral accent, exactly one hard-shadow
// ("brutalist") primary button, a two-tier elevation system for the
// persistent 3D viewer vs. flat tab content. See docs/design/DESIGN.md.
//
// Moved here from index.html's inline <script id="tailwind-config"> when the
// SPA switched off the Tailwind Play CDN (browser-side JIT, not for
// production) to a proper Vite-bundled build. Loaded via the `@config`
// directive in src/style.css - same object, just no longer inline JS.
module.exports = {
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                bg: "#100E0B",
                surface: "#171310",
                "surface-raised": "#1E1813",
                border: "#2C2620",
                "border-subtle": "#221D18",
                primary: "#EDE7DC",
                secondary: "#A79E8E",
                muted: "#625B4E",
                accent: "#E2846A",
                "accent-muted": "#35281F",
                tertiary: "#F59E0B",
                success: "#8FAE83",
                error: "#EF4444",
                warning: "#F59E0B",
            },
            borderRadius: {
                lg: "0.625rem",
            },
            spacing: {
                gap: "24px",
                "max-container": "1440px",
                margin: "24px",
                base: "8px",
            },
            boxShadow: {
                // Two-tier elevation: flat tab content stays borderless per the
                // editorial-section pattern; the persistent 3D viewer panel gets
                // a soft lift so it reads as a distinct, floating instrument
                // rather than just another column.
                panel: "0 1px 0 rgba(0, 0, 0, 0.35), 0 12px 32px -16px rgba(0, 0, 0, 0.55)",
            },
            fontFamily: {
                "body-sm": ["Inter"],
                "label-md": ["Inter"],
                "body-lg": ["Inter"],
                "headline-md": ["Georgia", "Iowan Old Style", "Times New Roman", "serif"],
                "label-sm": ["Inter"],
                "headline-lg": ["Georgia", "Iowan Old Style", "Times New Roman", "serif"],
                "body-md": ["Inter"],
                "headline-sm": ["Georgia", "Iowan Old Style", "Times New Roman", "serif"],
                mono: ["ui-monospace", "SF Mono", "Consolas", "monospace"],
            },
            fontSize: {
                "body-sm": ["14px", { lineHeight: "1.5", fontWeight: "400" }],
                "label-md": ["12px", { lineHeight: "1", letterSpacing: "0.05em", fontWeight: "600" }],
                "body-lg": ["18px", { lineHeight: "1.6", fontWeight: "400" }],
                "headline-md": ["24px", { lineHeight: "1.3", fontWeight: "600" }],
                "label-sm": ["11px", { lineHeight: "1", fontWeight: "500" }],
                "headline-lg": ["32px", { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "700" }],
                "body-md": ["16px", { lineHeight: "1.5", fontWeight: "400" }],
                "headline-sm": ["20px", { lineHeight: "1.4", fontWeight: "600" }],
            },
        },
    },
};
