# Qrumy — Architecture & MVP Plan (v0.1, for approval)

Status: **DRAFT — awaiting approval. No application code has been written.**
Date: 2026-11-25

---

## 0. Current state of the repository

| Item | Finding |
|---|---|
| Repository | `nijatsattarov/dergah`, empty (no commits, no remote branches) |
| Existing code / schema / data | None — greenfield. Nothing to preserve or migrate. |
| Toolchain in dev container | PHP 8.3.6 (pdo_mysql, gd, intl, redis, sodium, zip), Composer, Node 22, Redis 7, Docker. No local MySQL (will run MySQL 8 in Docker for tests). |

---

## 1. Architectural problems found in the specification

These are the issues that would cause rework or risk later if not decided now.

### 1.1 Scope is ~6 products; the MVP must be cut hard
Each module (QR, Surveys, Assets, Events, AI, Agency) is a standalone SaaS in its own
right. Building all of them to the depth described before launch would take a single
team many months. The plan below ships **Foundation + QR + Surveys** first, then
**Event lead capture**, then **basic Assets**. AI and Agency come after that.

### 1.2 Event exhibitors break the simple "one organization owns the row" tenancy model
Organizer and exhibitors are *different companies* sharing one event. Leads captured
by Exhibitor A must be invisible to Exhibitor B and, by default, to the organizer as
raw personal data (organizer sees aggregates). So `organization_id` alone is not
enough. The design adds a second scope:

- An event belongs to the organizer's organization.
- `event_exhibitors` is a participation record. It optionally links to the exhibitor's
  **own** Qrumy organization (`exhibitor_organization_id`), so that exhibitor keeps
  its leads in its own account after the event (an onboarding hook for us).
- `event_leads` carry `event_exhibitor_id` and are authorized by **exhibitor
  membership**, not by organizer membership. Organizer access to raw leads is an
  explicit, per-event, consent-backed setting.

This is the single highest-risk isolation area and will get dedicated tests.

### 1.3 Agency = organizations that manage other organizations
If organizations are flat now, Phase 7 becomes a rewrite. We add
`organizations.parent_organization_id` (nullable) and an `organization_type`
(`standard | agency`) from day one. Nothing uses them until Phase 7, but the tenancy
resolver and policies are written so that "agency member acting on client org" is an
added rule, not a new model.

### 1.4 Static QR codes cannot be tracked
Static codes encode the payload directly, so scans never touch our servers. The UI
must say so plainly ("Static — no scan analytics"). Several listed types (PDF, Image,
Video, Menu, Multi-link, Coupon, Survey, Feedback, Event, Product info) **require a
hosted landing page**, so they are always dynamic. Only URL, Text, Wi-Fi, vCard,
Phone, SMS, Email, WhatsApp and Location can be static.

### 1.5 Dynamic QR redirect abuse is the main business risk
Dynamic redirect services are a common phishing vector. If `qrumy.com` gets on Google
Safe Browsing or a spam blocklist, **every** customer's printed QR breaks *and* the
marketing site goes down with it. Mitigations:

- **Recommendation:** serve redirects from a separate short domain (e.g.
  `qrumy.link/abc123`, to be decided). That protects the main domain, and a shorter
  URL gives a less dense, more scannable QR. `qrumy.com/q/{code}` stays supported
  as a route, configurable by env.
- URL checks on create/update (Safe Browsing API or a similar service, behind an
  interface), plus a domain blocklist.
- Rate limits on QR creation for free accounts, and admin suspension.
- Printed codes are permanent: short codes are **immutable** and never reused.

### 1.6 Scan tracking must not slow the redirect
The redirect endpoint is the hottest path in the system. Design: resolve the code
from cache, then write a minimal scan row (or dispatch to the queue when Redis is
available), then return a 302. Parsing (UA, geo, bot detection) and **daily rollup
tables** happen asynchronously. Dashboards read rollups, never raw scans. Raw scans
get a configurable retention period, and IPs are stored only as a salted hash
(daily-rotating salt, which also gives "estimated unique scans").

### 1.7 QR styling vs. library capabilities
Eye shapes, module patterns, frames and logos are not all supported by every PHP
library. **Recommendation: `chillerlan/php-qrcode` (v5)**, which supports custom
module and finder rendering in SVG and raster output. Frames and CTA text are composed
as an SVG layer around the code. Scannability guards: enforce minimum
foreground/background contrast, use error correction H when a logo is present, cap the
logo at about 20% of the area, and keep a quiet zone. An optional server-side decode
check can be added later.

### 1.8 Payments depend on where the business is registered
Stripe is not available to merchants in every country. If the legal entity cannot use
Stripe, a **Merchant-of-Record** provider (Paddle, Lemon Squeezy) is usually the
simplest route for selling internationally (it also handles VAT and sales tax). The
billing layer will be a `PaymentGateway` interface, plus a `ManualGateway` for
development and admin-granted plans. It never fakes success: a dev "activation" is an
explicit admin action that is logged as such.

### 1.9 Email consent and personal data (GDPR-style)
Lead capture, event registration and follow-up emails process personal data of
people who are **not** Qrumy users. Required from the start: a consent checkbox and
the stored consent text/version per lead/attendee, unsubscribe links, a per-org sender
identity, and data export/deletion per contact. Follow-up emails are sent only to
contacts with recorded consent.

### 1.10 Public, unauthenticated surfaces bypass tenant scoping
Survey pages, asset profiles, fault forms, lead capture pages, ticket pages and
redirects are public. They must resolve their tenant **from an unguessable token**,
never from a user session. They also need rate limiting and spam protection
(honeypot, plus an optional captcha).

### 1.11 Things the spec does not mention but that affect the schema
- **Localization (i18n):** public survey and event pages almost certainly need
  multiple languages. Build with Laravel translations and per-org default locale from
  day one (UI strings), with per-survey translations later.
- **Time zones:** store UTC, render in the organization's or event's time zone.
- **Camera check-in requires HTTPS** (browser camera API); offline check-in is out of
  scope as the spec says.
- **File uploads (PDF/image/video QR):** size caps per plan, MIME sniffing, files kept
  off the public web root, and served via signed or streamed routes. Video should
  link to external hosting in the MVP, not host large files.

---

## 2. Recommended final architecture

**Modular monolith on Laravel**, one deployable app, one MySQL database.

```
            ┌───────────────────────── Laravel application ─────────────────────────┐
 Browser ──►│  Web (Blade + Tailwind + Alpine)     Public pages     Redirect endpoint │
            │           │                              │                  │          │
            │   ┌───────▼──────────── Core (shared kernel) ──────────────▼───────┐  │
            │   │ Auth · Organizations · Memberships/Roles · Tenancy · Entitlements│ │
            │   │ Billing · QR Engine (render + short codes) · Analytics · Files  │  │
            │   │ Notifications · Audit log · Activity feed · Settings/Flags      │  │
            │   └───────▲──────────▲──────────▲──────────▲──────────▲─────────────┘  │
            │        QR Mgmt   Surveys    Events     Assets   (Intelligence, Agency) │
            │   Modules depend on Core only. Modules never import each other;       │
            │   cross-module links go through Core contracts (e.g. "Qrable").       │
            └──────────────┬───────────────────────────┬─────────────────────────────┘
                     MySQL 8 (single schema)      Redis (cache/queue/sessions)
                                                    └─► Queue workers (Supervisor)
                                                    └─► Scheduler (cron)
```

Key decisions:

| Concern | Decision | Why |
|---|---|---|
| Framework | Current stable Laravel major at setup time, PHP 8.3 | As specified; 8.3 is installed |
| Module system | Plain Laravel: `app/Modules/<Name>` with its own ServiceProvider that registers routes, views, migrations and policies. No `nwidart/laravel-modules`. | Avoid a heavy dependency; easy to extract later |
| Tenancy | Single database, `organization_id` on every tenant row; `BelongsToOrganization` trait with global scope + explicit `TenantContext` service; policies on every controller action; tests per module | Cheapest to run on a VPS; isolation enforced server-side |
| Roles | Role per membership (`owner, admin, manager, member, viewer`) + a config capability matrix checked by Gates/Policies | Covers the spec without `spatie/permission`; custom roles can come later |
| Plans/limits | `Entitlements` service: features (bool) + limits (int) resolved from plan + add-ons + per-org overrides; usage counters | One place for "can this org do X / how many" |
| Shared QR | One `qr_codes` table is the **single redirect/short-code registry**. Surveys, exhibitor pages and assets attach via a polymorphic `qrable` target. Event **tickets** use their own token table (volume, different lifecycle). | "Shared QR infrastructure" without coupling modules |
| Frontend | Blade components as the design system, Tailwind (tokens as CSS variables), Alpine, Vite. Chart.js for charts. SortableJS for the survey builder. A small, maintained JS scanner for check-in. | Matches spec; minimal JS |
| Admin panel | Separate `/admin` area, separate guard and `admin_users` table, custom Blade on the same design system | Stack consistency; avoids Livewire; admin is small initially |
| Queues/cache | Redis when available; `database` driver fallback | VPS-friendly |
| Storage | Laravel filesystem disks; `local` now, S3-compatible via config | As specified |
| AI (later) | `AiProvider` interface, usage metered through Entitlements, server-side only | Vendor-neutral |
| Geo-IP | MaxMind GeoLite2 local DB (free license key) behind `GeoLocator` interface; country/region/city only | No per-request API cost; no GPS claims |

---

## 3. Folder structure

```
app/
  Core/
    Auth/            (controllers, OAuth driver stubs, 2FA-ready columns)
    Organizations/   (Organization, Membership, Invitation, TenantContext, middleware)
    Authorization/   (Role enum, capability matrix, base policies)
    Billing/         (Plan, Subscription, Entitlements, PaymentGateway contracts, ManualGateway)
    Qr/              (QrRenderer, ShortCodeGenerator, Qrable contract, styling DTOs)
    Analytics/       (ScanRecorder, UserAgentParser, BotDetector, GeoLocator, rollup jobs)
    Files/           (secure upload service, MIME/size validation)
    Audit/           (AuditLog, ActivityLog)
    Notifications/
    Settings/        (system settings, feature flags)
    Support/         (shared helpers, base controller, CSV export)
  Modules/
    QrManagement/    {Models, Http/Controllers, Http/Requests, Services, Policies,
                      Jobs, routes/web.php, database/migrations, resources/views,
                      QrManagementServiceProvider.php}
    Surveys/         (same layout)
    Events/          (same layout)
    Assets/          (same layout)
    Intelligence/    (later)
    Agency/          (later)
  Admin/             (admin guard, controllers, views)
config/qrumy.php     (domains, retention, capability matrix, module registry)
resources/
  css/tokens.css     (design tokens → Tailwind theme)
  views/components/  (design-system Blade components: button, input, card, table, stat…)
  views/layouts/     (marketing, app, public, admin)
  views/marketing/   (landing, pricing, SEO pages)
tests/
  Feature/Core/…  Feature/Modules/<Module>/…  Unit/…
  Feature/Isolation/ (cross-tenant attack tests for every module)
docker/              (nginx, php-fpm, mysql, compose files)
docs/                (this file, decisions/ADRs, CHECKLIST.md, DEPLOYMENT.md)
```

---

## 4. Database ERD (MVP scope)

All tenant tables carry `organization_id` (FK, indexed) and timestamps; most carry
soft deletes. IDs are `bigint` internally; anything exposed publicly uses a separate
random token or ULID.

### 4.1 Core

```mermaid
erDiagram
  users ||--o{ memberships : has
  organizations ||--o{ memberships : has
  organizations ||--o{ invitations : sends
  organizations ||--o| organizations : "parent (agency, later)"
  organizations ||--o{ subscriptions : has
  plans ||--o{ plan_features : defines
  plans ||--o{ subscriptions : "subscribed to"
  organizations ||--o{ feature_overrides : has
  organizations ||--o{ usage_counters : tracks
  subscriptions ||--o{ invoices : bills
  organizations ||--o{ audit_logs : logs
  organizations ||--o{ activity_logs : feeds

  users { bigint id; string name; string email; string password; timestamp email_verified_at; string google_id; text two_factor_secret; string status }
  organizations { bigint id; string name; string slug; string logo_path; string website; string industry; char country; string timezone; string locale; bigint owner_id; bigint parent_organization_id; string type; string status }
  memberships { bigint id; bigint user_id; bigint organization_id; string role }
  plans { bigint id; string key; string name; int price_monthly_cents; int price_yearly_cents; int trial_days; bool is_public }
  plan_features { bigint plan_id; string feature_key; bool enabled; int limit_value }
  subscriptions { bigint id; bigint organization_id; bigint plan_id; string status; string interval; string gateway; string gateway_ref; timestamp trial_ends_at; timestamp current_period_end; timestamp cancels_at }
  usage_counters { bigint organization_id; string metric; string period; int value }
```

### 4.2 QR Management & analytics

```mermaid
erDiagram
  organizations ||--o{ qr_codes : owns
  qr_folders ||--o{ qr_codes : contains
  qr_codes }o--o{ tags : tagged
  qr_codes ||--o{ qr_scans : records
  qr_codes ||--o{ qr_scan_daily : "rolled up"
  qr_codes ||--o{ qr_assets_files : "hosted files"

  qr_codes { bigint id; bigint organization_id; bigint folder_id; string name; string type; string mode "static|dynamic"; string short_code "unique, immutable"; json payload; string destination_url; string qrable_type; bigint qrable_id; json style; string status "active|paused|suspended"; timestamp expires_at; bigint created_by }
  qr_scans { bigint id; bigint qr_code_id; bigint organization_id; timestamp scanned_at; char ip_hash; char country; string region; string city; string device; string os; string browser; string referrer; json utm; bool is_bot }
  qr_scan_daily { bigint qr_code_id; date day; string dimension; string value; int scans; int unique_scans }
```

### 4.3 Surveys

```mermaid
erDiagram
  organizations ||--o{ surveys : owns
  surveys ||--o{ survey_questions : has
  survey_questions ||--o{ survey_question_options : has
  surveys ||--o{ survey_responses : receives
  survey_responses ||--o{ survey_answers : contains
  survey_responses ||--o{ response_notes : annotated
  survey_responses }o--o{ tags : tagged

  surveys { bigint id; bigint organization_id; string public_token; string title; text description; json theme; json settings "anonymous, limits, redirect, thank-you"; timestamp closes_at; int response_limit; string status }
  survey_questions { bigint id; bigint survey_id; string type; string label; bool required; int position; json config; json logic "conditional logic, later" }
  survey_responses { bigint id; bigint survey_id; bigint organization_id; string source "qr|link|embed|email"; bigint qr_code_id; bool completed; bigint assigned_to; string status "open|resolved"; timestamp submitted_at }
  survey_answers { bigint response_id; bigint question_id; text value_text; decimal value_number; json value_json }
```

### 4.4 Events (lead capture first, then registration/check-in)

```mermaid
erDiagram
  organizations ||--o{ events : organizes
  events ||--o{ event_exhibitors : hosts
  organizations |o--o{ event_exhibitors : "exhibitor's own org (optional)"
  event_exhibitors ||--o{ event_exhibitor_users : staff
  event_exhibitors ||--o| event_stands : at
  event_exhibitors ||--o{ event_leads : captures
  event_leads ||--o{ event_lead_notes : has
  event_leads ||--o{ event_followup_tasks : has
  event_followup_templates ||--o{ event_followup_tasks : uses
  events ||--o{ event_registration_forms : has
  events ||--o{ event_attendees : registers
  event_attendees ||--o| event_tickets : holds
  event_tickets ||--o{ event_checkins : "checked in"

  events { bigint id; bigint organization_id; string slug; string name; string type; datetime starts_at; datetime ends_at; string timezone; string venue; bool is_public; int capacity; json settings "organizer_lead_access, consent text" }
  event_exhibitors { bigint id; bigint event_id; bigint exhibitor_organization_id; string company_name; string capture_token; json lead_fields }
  event_leads { bigint id; bigint event_exhibitor_id; bigint event_id; string first_name; string email; string phone; string company; json answers; string temperature "hot|warm|cold"; string stage; bigint assigned_to; bool consent_marketing; string consent_version; string source }
  event_attendees { bigint id; bigint event_id; string first_name; string email; string status; json answers; bool consent_marketing }
  event_tickets { bigint id; bigint attendee_id; char token_hash "QR holds random token only" }
  event_checkins { bigint id; bigint ticket_id; bigint checked_in_by; timestamp checked_in_at }
```

### 4.5 Assets (basic MVP)

```mermaid
erDiagram
  organizations ||--o{ assets : owns
  asset_categories ||--o{ assets : classifies
  asset_locations ||--o{ assets : located
  asset_locations ||--o| asset_locations : parent
  assets ||--o| qr_codes : "qrable"
  assets ||--o{ asset_documents : has
  assets ||--o{ fault_reports : receives
  assets ||--o{ maintenance_records : history
  assets ||--o{ asset_activity_logs : logs

  assets { bigint id; bigint organization_id; string asset_code; string name; bigint category_id; string brand; string model; string serial_number; date purchase_date; date warranty_expires_at; int purchase_price_cents; bigint location_id; bigint responsible_user_id; string status; json custom_fields; string public_visibility }
  asset_locations { bigint id; bigint organization_id; bigint parent_id; string type "branch|building|floor|room|department"; string name }
  fault_reports { bigint id; bigint asset_id; string category; text description; string priority; string status; string reporter_name; bigint reported_by }
  maintenance_records { bigint id; bigint asset_id; string kind "preventive|corrective"; date performed_on; bigint technician_id; int cost_cents; text notes }
```

`maintenance_schedules`, `asset_tasks` (full workflow) and notifications for overdue
items are post-MVP (Phase 4b), as section 22 of the spec allows.

---

## 5. Module dependency map

```
                 ┌──────────────┐
                 │     Core     │  Auth · Orgs · Roles · Tenancy · Entitlements · Billing
                 │              │  QR Engine · Analytics · Files · Audit · Notifications
                 └──────┬───────┘
      ┌──────────┬──────┴─────┬──────────┬─────────────┐
      ▼          ▼            ▼          ▼             ▼
 QR Management  Surveys     Events     Assets     Admin panel
      │          │            │          │
      └──────────┴─────┬──────┴──────────┘
                       ▼  (read-only, via module "insight providers")
                 Intelligence (Phase 6)
 Agency (Phase 7) = Core extension (parent orgs, client switching, branding) + reports
```

Rules: modules depend only on Core. A survey or asset "gets a QR" by implementing
Core's `Qrable` contract; QR Management lists all codes but does not import Survey
classes. Each module registers its own navigation item, entitlement keys and dashboard
widget with Core, so the sidebar shows only enabled modules.

---

## 6. MVP scope

**In MVP (launch):**
- Core: registration/login/verify/reset, remember-me, organizations, invitations,
  5 roles, tenancy, plans + entitlements + limits, manual/dev billing gateway, admin
  panel foundation (users, orgs, plans, QR abuse suspension, audit log), dashboard
  overview, design system, marketing landing + pricing + SEO basics.
- QR: static + dynamic, the 9 static-capable types + URL, Multi-link, PDF, Image,
  Menu (as PDF/link), App download, Coupon, Survey link; folders, tags, search, filter,
  pause/expire, styling (colors, logo, eye/module style, frame + CTA), PNG/SVG
  export, CSV bulk create, ZIP bulk export, scan analytics with rollups and CSV export,
  bot filtering.
- Surveys: builder (all listed question types except conditional logic), public page,
  QR/link/embed distribution, NPS/CSAT/CES, analytics, response management (filter,
  tag, assign, notes, resolve, export).
- Events, part A: event creation, exhibitors, exhibitor lead capture pages + QR,
  qualification (hot/warm/cold + custom fields), pipeline, assignment, notes,
  follow-up tasks + templates (manual send with consent), organizer/exhibitor
  dashboards, CSV export.
- Events, part B: registration forms, attendees, QR tickets, camera + manual
  check-in, duplicate prevention, attendance stats.
- Assets (basic): registration, categories, hierarchical locations, QR profile with
  visibility levels, fault reporting, basic maintenance history, simple stats.

**Post-MVP:** payment-provider integration (once the provider is chosen, it can come
before launch if paid plans must be live on day one), Google OAuth activation, 2FA,
survey conditional logic, preventive maintenance schedules + task workflow +
notifications, automated follow-ups, Intelligence, Agency/white-label, PDF export,
custom domains.

---

## 7. Development phases (proposed order)

The spec places Assets (4) before Events (5), but its own MVP section ranks Events
higher. **Proposal: Events before Assets.** Each phase ends with passing tests, a
checklist update and a demo-able workflow.

| # | Phase | Main deliverables | Relative size |
|---|---|---|---|
| 1 | Foundation | Laravel + Docker setup, design tokens and components, auth, orgs, invitations, roles, tenancy + isolation test harness, plans/entitlements, manual gateway, admin foundation, dashboard shell, landing page v1 | L |
| 2 | QR Management | QR engine, types, styling, static/dynamic, redirect endpoint, scan pipeline + rollups, folders/tags, bulk CSV, export, analytics UI, abuse controls | L |
| 3 | Surveys | Builder, public pages, embed, scoring, analytics, response management | M–L |
| 4 | Events A — lead capture | Events, exhibitors, capture pages, leads, pipeline, follow-ups, dashboards | L |
| 5 | Events B — registration & check-in | Forms, attendees, tickets, scanner, check-in stats | M |
| 6 | Assets basic | Assets, locations, QR profile, fault reports, maintenance history | M |
| 7 | Launch prep | Security review, performance (redirect path), backups, monitoring, deploy docs, payment provider | M |
| 8 | Assets advanced | Schedules, tasks workflow, notifications | M |
| 9 | Intelligence | Provider abstraction, feedback sentiment/summaries, lead summaries, reports | M–L |
| 10 | Agency | Client orgs, switching, client reports, white-label architecture | L |

Rough effort for one experienced full-stack developer: Phases 1–7 ≈ 14–20 weeks;
8–10 another 8–12 weeks. In this setup I build phase by phase in this repository and
you review between phases.

---

## 8. Technical risks

| Risk | Impact | Mitigation |
|---|---|---|
| Cross-tenant data leak (esp. exhibitor leads) | Critical | Global scopes + policies + dedicated isolation test suite that attacks every route with a foreign org's IDs |
| Redirect domain blocklisted due to abuse | Critical | Separate redirect domain, URL scanning, rate limits, fast admin suspension |
| Redirect latency / DB load under scan spikes | High | Cached code lookup, minimal write, async enrichment, rollups, raw-scan retention |
| Unscannable styled QR codes | High | Contrast/logo/ECC guards; preview; optional decode verification |
| Payment provider unavailable in the company's country | High | Gateway abstraction; decide MoR vs Stripe early |
| Personal-data compliance for leads and attendees | High | Consent records, unsubscribe, export/delete, retention settings |
| Scope creep across 6 products | High | Strict phase gates; post-MVP list above |
| Email deliverability | Medium | Transactional provider, SPF/DKIM/DMARC, per-org reply-to |
| File-upload abuse / storage cost | Medium | Plan-based caps, MIME sniffing, no video hosting in MVP |
| Global-scope pitfalls in queues/console | Medium | Jobs carry `organization_id` explicitly; `TenantContext` set per job |

---

## 9. Infrastructure requirements

- **Launch VPS:** 2–4 vCPU, 4–8 GB RAM, 80 GB SSD (Ubuntu 24.04 LTS).
- Nginx, PHP-FPM 8.3 + OPcache, MySQL 8, Redis, Supervisor (queue workers), cron
  (`schedule:run`), Certbot TLS.
- Transactional email provider (SMTP/API).
- MaxMind GeoLite2 license key (free) for geolocation.
- Optional: Safe Browsing (or similar) API key for URL checks; Sentry-compatible error
  monitoring.
- Off-site backups: nightly `mysqldump` + storage sync to S3-compatible storage
  (restic or similar), with 7/30-day retention and a tested restore.
- DNS: `qrumy.com` (app + marketing), plus the redirect short domain if approved.

## 10. Deployment architecture

```
            Cloudflare (optional: DNS, TLS, caching static marketing assets, DDoS)
                                   │
                 ┌──────────── VPS (Docker Compose or native) ────────────┐
                 │  Nginx ──► PHP-FPM (app)                                │
                 │            ├─ queue workers (Supervisor / container)    │
                 │            └─ scheduler (cron / container)              │
                 │  MySQL 8 (volume)     Redis (volume)                    │
                 │  storage/ (volume) ──► S3-compatible later              │
                 └─────────────────────────────────────────────────────────┘
                     nightly backups ──► off-site object storage
```

Zero-downtime-ish deploys: `git pull` (or image pull) → `composer install
--no-dev` → `npm run build` → `php artisan migrate --force` →
`config/route/view:cache` → `queue:restart`. Scaling path: move MySQL to a managed
instance, add a second app node behind a load balancer, and move files to S3. No
code changes are needed because sessions, cache and queue are already on Redis.

---

## 11. Decisions needed before implementation

1. **Repository:** build Qrumy in `nijatsattarov/dergah` (empty)?
2. **Phase order:** Events before Assets (recommended)?
3. **Redirect domain:** separate short domain (recommended), or `qrumy.com/q/…` only?
4. **Payments:** where is the selling entity registered, and do you prefer Stripe or
   a Merchant-of-Record (Paddle / Lemon Squeezy)? Must paid plans be live at launch?
5. **Languages:** English only at launch, or additional UI/public-page languages
   (which)?
6. **Admin panel:** custom Blade (recommended), or Filament (faster, adds Livewire)?
