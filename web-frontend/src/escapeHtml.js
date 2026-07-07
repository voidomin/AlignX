// Escapes a value for safe interpolation into an innerHTML template
// literal. Most of this app's data (run IDs, timestamps) is server-
// generated and already constrained to a safe charset, but pdb_ids
// originate from user input at job-submission time - relying on that
// upstream validation always holding is exactly the kind of assumption
// that breaks quietly later. Anything interpolated into innerHTML from
// data that ultimately traces back to a request body should go through
// this first.
export function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
