# ADR 0001 — Stack and architecture

Date: 2026-11-25 · Status: accepted

**Decision.** Python-only modular monolith: Django 5.2 LTS, PostgreSQL, Celery + Redis,
server-rendered templates with Tailwind/HTMX/Alpine, Docker Compose on one VPS.
Replaces the earlier Laravel draft at the product owner's request.

**Why.** One deployable, cheap to run, LTS-supported until April 2028; no SPA needed for
the product's interaction patterns.

**Consequences.** Apps are layered and the layering is enforced by `import-linter` in CI.
Lower layers reach higher ones only through hooks (`core.quotas`, `core.navigation`,
`organizations.signals`).
