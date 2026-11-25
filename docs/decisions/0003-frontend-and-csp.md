# ADR 0003 — Front-end build and Content-Security-Policy

Date: 2026-11-25 · Status: accepted

**Decision.** Strict CSP (`script-src 'self'`, `style-src 'self'`, no inline code).
Alpine uses its CSP build, so components are registered in `static/js/app.js`; HTMX runs
with eval and script tags disabled. Node is used **only at build time** (Tailwind v4 CLI,
copying vendored HTMX/Alpine/Inter into `static/vendor`). Tailwind source lives in
`assets/` (outside `static/`) so `collectstatic` never processes it. Inline `style`
attributes are not used (e.g. usage bars are `<progress>` elements).
The Django Admin (Unfold) is excluded from CSP because it relies on inline scripts; it is
staff-only and MFA-protected.
