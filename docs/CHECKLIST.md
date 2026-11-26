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
- [x] Transactional email provider: Resend (DNS records are set at deployment)
- [x] Terms of Service / Privacy Policy pages (texts drafted and published, editable in the admin)
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

## Phase 7 — Beta launch preparation (code complete, deployment pending) — 2026-11-25
- [x] Security review: deploy checks, dependency audits, manual review of raw HTML/SQL/redirects
- [x] Domain blocklist enforced at scan time; Permissions-Policy; secret key rotation support
- [x] Scan rate limiting no longer blocks people (shared IPs); limited scans aren't counted
- [x] Zero-query cached scan path (test) and load test through Nginx TLS (~900 scans/s)
- [x] Backup / restore scripts; restore drill and disaster recovery tested; deploy script
- [x] Sentry with privacy-preserving settings
- [x] Branded HTML emails for sign-up, confirmation and password reset (en/az)
- [x] Terms / Privacy pages managed in the admin (versioned, en/az); sign-up consent recorded
- [x] Terms of Service and Privacy Policy texts (en/az, v2026-11-25) seeded by a data migration
      (never overwrites admin edits); simple safe formatting (`## ` headings, `- ` lists)
- [x] Email via Resend (anymail); console backend when no key is set
- [x] Super-admin dashboard (admin home): users, organizations, QR codes, scans, surveys,
      assets, paid subscriptions / expected MRR, sign-up and scan charts, latest sign-ups
- [x] Blog (en/az): posts written in the admin (drafts, scheduling, cover and inline images,
      safe formatting), list + post pages, JSON-LD, sitemap, navigation; 2 starter posts
- [x] Free QR generator on the homepage, no account: website, Wi-Fi, text, phone, SMS,
      email, WhatsApp, location, vCard (static only, nothing stored); pattern / corner /
      frame shapes, colours, call to action, logo; live preview with test scan; PNG + SVG;
      rate-limited. Dynamic codes, landing pages, surveys and assets lead to sign-up
- [x] Account deletion (audit e-mail anonymised); ownership transfer; organization deletion
- [x] Tests: 243 passing; Azerbaijani translations: 1,212 strings
- [ ] Deployment to the VPS and go-live items — see docs/LAUNCH.md

## Round of fixes and new products — 2026-11-26
- [x] Language switching via plain links; returns to the same page in the other language;
      remembered for sign-up / emails / app; also in the app's user menu
- [x] "example.com" accepted in every link field; mobile app menu; copy buttons; blog covers
- [x] Admin fully in Azerbaijani (Unfold translations in locale_vendor/)
- [x] Google sign-in (button, terms recorded, setup in DEPLOYMENT.md §10)
- [x] Pop-up offers managed in the admin
- [x] Multi-link pages with platform icons and names
- [x] Qrumy Card: person/company cards, 4 templates, any colour, photo/cover, about, contacts,
      map, social links, gallery (12), 6-step editor with live phone preview, publish → QR,
      vCard "Save contact", share button, views/saves/clicks stats, plan limit `cards.max`
- [x] Production refuses to start with a localhost SITE_URL
- [x] Digital Menu: menus → categories (order, hide) → items (photo, price, discount, portion,
      availability, labels, sizes, extras); design (colour, logo, cover, 3 layouts) and guest
      info (hours, address, Wi-Fi); publish → QR (PNG/SVG); public page with category tabs,
      search and item sheet; views, top items and categories; plan limit `menus.max`;
      replaces the old PDF menu in the QR type picker (old codes keep working)
- [x] Event Lead Capture (Events A): events, collection points (stands / exhibitors / staff)
      with their own QR codes, public mobile lead form (consent, honeypot, signed token, rate
      limit), staff quick-add, hot/warm/cold, stages, assignee, notes, follow-up tasks, CSV,
      stats, in-app + email notifications, private read-only exhibitor link (hashed, revocable)
- [ ] Events B: registration, tickets, check-in; exhibitor accounts in their own organization
- [x] Contact page (en/az) edited in the admin, contact form → admin + email, spam protection
