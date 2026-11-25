# Qrumy — Development Checklist

Legend: `[ ]` not started · `[~]` in progress · `[x]` done and tested

## Phase 0 — Planning
- [x] Inspect repository (only planning docs; no code, schema or data)
- [x] Architecture v0.2 (Python/Django) approved
- [x] Decisions: same repo · Events before Assets · redirects on `qrumy.com/q/` (short domain
      later) · free beta · open signup · en (default) + az · Django Admin with Unfold

## Phase 1 — Foundation ✅ (2026-11-25)
- [x] Project skeleton, settings split (base/dev/test/prod), pinned requirements
- [x] Custom User (email login) + allauth: signup with mandatory email verification, login,
      logout, remember-me, password reset/change, email management, TOTP 2FA, Google OAuth
      (activates when keys are set), login rate limits
- [x] Organizations, memberships, invitations (hashed tokens, 7-day expiry, email match),
      5 roles + capability matrix, role-change/removal rules, owner protection
- [x] Tenancy: URL-scoped org resolution (404 for non-members), `TenantModel` + `for_org()`,
      `require_capability`; isolation suite (every org route + object routes + coverage
      guard), verified by mutation test
- [x] Subscriptions: plans, features, limits, overrides, usage counters, one-current-
      subscription DB constraint, Beta plan auto-assigned; team-member limit enforced
- [x] Billing: `PaymentGateway` contract + `ManualGateway` (no fake payments), staff plan
      assignment (audited), plan & billing page
- [x] Audit log (tenant + staff actions), in-app notifications, async email via Celery
- [x] Super-admin: Django Admin + Unfold at a configurable path; allauth login only;
      non-staff get 404; MFA required for staff (prod); suspend/activate users & orgs
- [x] Design system: tokens, Inter (self-hosted, az glyphs), components, app/auth/account/
      marketing layouts, responsive + mobile drawer; strict CSP (no inline JS/CSS)
- [x] Dashboard shell with module-aware navigation, org switcher, getting-started, activity
- [x] Landing + pricing pages (en/az), SEO: canonical, hreflang, OG, JSON-LD, sitemap, robots
- [x] English + Azerbaijani (391 strings); CI test for catalog completeness/placeholders
- [x] Docker image, dev + prod Compose, Nginx (TLS, unknown-host rejection), health checks;
      production stack verified end to end (TLS → Gunicorn → Postgres; Redis → Celery → email)
- [x] CI workflow: ruff, import-linter, migrations check, compilemessages, pytest, asset build
- Tests: 59 passing on PostgreSQL 16

### Known gaps / follow-ups (not blocking Phase 2)
- [ ] CI workflow not yet run on GitHub (push blocked: GitHub App access for nijatsattarov/qrumy)
- [ ] Transactional email provider + DNS (SPF/DKIM/DMARC) — needed before public launch
- [ ] Terms of Service / Privacy Policy pages (legal text must come from the business)
- [ ] Branded HTML versions of allauth emails (currently allauth's plain-text, translated)
- [ ] Off-site backups + restore drill (Phase 7)
- [ ] Optional Postgres Row-Level Security (Phase 7)

## Phase 2 — QR Management ✅ (2026-11-25)
- [x] QR engine: segno matrix + own renderer (SVG/PNG), 3 module shapes, 3 eye frames,
      3 eye centres, colours, logo, 4 frame styles with call-to-action (az glyphs)
- [x] Scannability: contrast rules + ZXing decode check on every save; 756-combination matrix passes
- [x] 15 types: website, multi-link & social, PDF, menu, image, contact card (vCard), WhatsApp,
      location, app download, coupon, text, Wi-Fi, phone, SMS, email; static vs dynamic rules
- [x] Hosted landing pages (links, vCard + .vcf, coupon, text, app chooser) and hosted files
- [x] `/q/<code>` redirect: cache, pause/expiry/suspension/deletion pages, never-reused codes
- [x] Scan pipeline: Redis buffer → Celery (15 s) → UA/bot/geo enrichment → daily rollups;
      no raw IP stored; unique estimates; retention purge; CDN country header support
- [x] UI: list with search/filters/sort/pagination (HTMX), folders, tags, bulk select actions,
      create/edit with live preview + test-scan status, detail page, PNG (512–4096)/SVG download
- [x] Bulk CSV create (all-or-nothing, quota-aware, template download), ZIP export (PNG/SVG)
- [x] Analytics: per-code and organization pages, 7/30/90/365-day ranges, bar chart with
      table view, 8 breakdowns, CSV export (formula-injection safe); dashboard widget
- [x] Abuse controls: URL validation, staff blocklist, optional Safe Browsing, creation rate
      limit, admin suspension with reason (audited), suspended page
- [x] Plan features: `qr.dynamic`, `qr.bulk`, `qr.file_mb`; module gating per plan
- [x] Tenant isolation extended to every QR/folder/analytics route (mutation-tested)
- [x] Azerbaijani translations (711 strings)
- [x] Production stack re-verified: Nginx TLS → scans → Celery rollups; PDF via X-Accel
- Tests: 150 passing on PostgreSQL 16 + Redis 7

### Phase 2 follow-ups
- [ ] GeoLite2 database on the server (needs a free MaxMind licence key) — until then
      country/city analytics stay empty unless a CDN country header is configured
- [ ] Video type (link to external hosting) and Survey/Event/Product types arrive with their modules
- [ ] Scan partitioning by month once volume requires it

## Phase 3 — Surveys & Feedback ✅ (2026-11-25)
- [x] Models: surveys, ordered questions, responses, answers, notes, tags, daily views
- [x] 14 question types: single, multiple, dropdown, rating 1–10, stars, NPS, CSAT, CES,
      yes/no, short text, long text, email, phone, date (server-side validation)
- [x] Builder (HTMX): add, edit with auto-save, reorder, delete; starter texts in the survey language
- [x] Settings: title, description, language, accent colour, logo, thank-you page, redirect,
      contact details with consent, closing date, response limit; publish / close / reopen; delete
- [x] Public page (mobile-first, en/az) + website embed + per-survey theme stylesheet;
      signed start token, honeypot, rate limits, row-locked limits, monthly quota
- [x] Distribution: direct link, email link, embed code, survey QR code (source tracking)
- [x] Results: responses, completion rate, NPS/CSAT/CES/average rating, trend chart,
      per-question distributions and latest text answers, 7/30/90/all-time ranges
- [x] Feedback management: filters (search, status, score, assignee, tag, period), detail with
      assign (notifies), internal notes, tags, resolve/reopen, CSV export (formula-safe)
- [x] Plan features `surveys.max`, `surveys.responses_month`; module gating; dashboard widget
- [x] Tenant isolation extended to all survey/question/response routes (mutation-tested)
- [x] Azerbaijani translations (937 strings)
- Tests: 194 passing

### Phase 3 follow-ups
- [ ] Conditional logic (show question if …) — data field exists, no UI/evaluation yet
- [ ] Per-language survey content (one language per survey today)
- [ ] Email distribution from Qrumy (needs the transactional email provider)

## Phase 4 — Events A (lead capture) — postponed by the product owner
## Phase 5 — Events B (registration & check-in) — postponed by the product owner
## Phase 6 — Asset Management (basic) ✅ (2026-11-25)
- [x] Assets with generated IDs, categories, brand/model/serial, purchase & warranty,
      supplier, department, responsible person, 7 statuses, custom fields, staff instructions
- [x] Location tree (branch › building › floor › room / department / area) with cycle protection;
      filters include sub-locations
- [x] QR label per asset (dynamic `asset` QR type) and public profile with 3 visibility levels
- [x] Public fault reporting by scan: category, description, priority, photo, reporter contact;
      spam protection; notifications + email for high/urgent
- [x] Fault workflow (assign, statuses, resolution) with optional repair log and asset status update
- [x] Maintenance history with costs; private photos/PDFs per asset; per-asset activity history
- [x] Asset list with search/filters, summary cards, CSV export (formula-safe); dashboard widget
- [x] Plan feature `assets.max`; module gating; tenant isolation for all asset routes (mutation-tested)
- [x] Azerbaijani translations (1,159 strings in total)
- Tests: 231 passing

### Phase 6 follow-ups (Phase 8)
- [ ] Preventive maintenance schedules, overdue and warranty-expiry notifications
- [ ] Bulk asset import from CSV
- [ ] Asset utilisation analytics

## Phase 7 — Beta launch preparation
