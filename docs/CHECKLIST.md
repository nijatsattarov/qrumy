# Qrumy — Development Checklist

Legend: `[ ]` not started · `[~]` in progress · `[x]` done and tested

## Phase 0 — Planning
- [x] Inspect repository (only planning docs; no code, schema or data)
- [x] Architecture v0.1 (Laravel) — superseded
- [x] Architecture v0.2 (Python/Django): ERD, dependency map, MVP, risks (docs/ARCHITECTURE.md)
- [x] Decisions: same repo · Events before Assets · separate short redirect domain ·
      free beta first · en + az · Django Admin for super-admin
- [ ] Architecture v0.2 approved
- [ ] Open questions resolved (ARCHITECTURE.md §11)

## Phase 1 — Foundation
- [ ] Project skeleton, pyproject, settings split, Docker Compose (web, worker, beat, postgres, redis, nginx)
- [ ] Custom User + allauth (register, login, logout, verify, reset, remember-me)
- [ ] Organizations, memberships, invitations, roles + capability matrix
- [ ] Tenancy base (TenantModel, middleware, mixins, DRF base) + isolation test harness
- [ ] Subscriptions: plans, features, limits, usage counters, Beta plan
- [ ] Billing interface + ManualGateway
- [ ] audit_logs, notifications base
- [ ] Django Admin (Unfold) super-admin with MFA
- [ ] Design tokens, Tailwind build, layouts, components
- [ ] Dashboard shell with module-aware navigation
- [ ] en/az i18n; landing page v1; SEO basics
- [ ] CI: ruff, pytest (PostgreSQL), import-linter

## Phase 2 — QR Management
## Phase 3 — Surveys
## Phase 4 — Events A (lead capture)
## Phase 5 — Events B (registration & check-in)
## Phase 6 — Assets basic
## Phase 7 — Beta launch preparation
