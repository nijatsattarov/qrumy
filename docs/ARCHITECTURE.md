# Qrumy — Architecture & MVP Plan (v0.2 — Python/Django, for approval)

Status: **DRAFT — awaiting approval. No application code has been written.**
Date: 2026-11-25
Supersedes: v0.1 (Laravel/PHP draft, commit `0e68522`, kept in git history only).

---

## 0. Current state & decisions already made

| Item | Finding / decision |
|---|---|
| Repository | `nijatsattarov/dergah`. It contains only `docs/ARCHITECTURE.md` and `docs/CHECKLIST.md` (planning documents). No application code, schema or data, so **there is nothing to migrate.** The stack change only replaces this plan. |
| Dev container | Python 3.13, PostgreSQL 16, Redis 7, Docker, Chromium/Playwright (for end-to-end tests) |
| Stack | **Python only.** Django + DRF, PostgreSQL, Celery + Redis, Django Templates + Tailwind + HTMX (+ Alpine where needed), Docker Compose, Nginx, Gunicorn. No PHP, no Laravel, no React. |
| Repo | Build Qrumy in this repository ✔ |
| Phase order | Events before Assets ✔ |
| Redirect domain | Separate short domain for dynamic QR redirects ✔ (name still to be chosen; configurable by env) |
| Billing | **Free beta first.** Plans, limits and entitlements are built; no payment provider is integrated yet. |
| Languages | **English + Azerbaijani** (UI, marketing site, public pages, emails) |
| Super-admin | Customized **Django Admin**. This replaces the earlier Filament choice, which was PHP-only. |

---

## 1. Architectural problems and how this design handles them

### 1.1 Scope (six products)
Each module is a SaaS product on its own. The plan ships **Foundation → QR → Surveys →
Events (lead capture) → Events (registration/check-in) → basic Assets**, then hardens
for the beta launch. AI and Agency come after the beta.

### 1.2 Exhibitor leads break simple organization tenancy
Organizer and exhibitors are different companies inside one event. Design:
- `events.Event` belongs to the organizer's organization.
- `events.Exhibitor` is a participation record. It can optionally link to the
  exhibitor's **own** Qrumy organization, so the exhibitor keeps its leads in its own
  account after the event.
- `events.Lead` is authorized by **exhibitor membership** (`ExhibitorMember`), not by
  organizer membership. The organizer sees aggregates by default. Raw lead access is
  an explicit, per-event, consent-backed setting.
- This area gets a dedicated isolation test suite.

### 1.3 Agency needs groundwork now
`Organization.parent` (nullable FK to self) and `Organization.kind`
(`standard | agency`) exist from day one. Permission checks go through one
`organizations.access` service, so "agency member acting on client org" becomes an
added rule in Phase 10, not a rewrite.

### 1.4 Static QR codes cannot be tracked
Static codes never reach our servers, and the UI says so. Types that need a hosted page
(PDF, Image, Menu, Multi-link, Coupon, App download, Survey, Event, Product info,
Feedback) are always dynamic.

### 1.5 Redirect abuse (main business risk)
- Separate **short redirect domain** (decided). The redirect host gets its own minimal
  URLconf (`request.urlconf` set by middleware), so the redirect app cannot reach
  dashboard routes, and `qrumy.com` is shielded from blocklisting.
- Destination validation: only `http`/`https` schemes, a blocked-domain list, and an
  optional Safe Browsing (or similar) check behind a `UrlReputation` interface.
- Creation rate limits during the free beta; admin can suspend a QR code or an
  organization with one action.
- Short codes are **immutable and never reused**.

### 1.6 Redirect speed
The redirect view is the hottest path:
1. Look up the short code in Redis (cache hit) or Postgres (cache miss).
2. Check status and expiry.
3. Push a minimal scan record (code, time, IP hash, UA, referrer, UTM) to a Redis list.
4. Return 302.

Celery workers drain the list in batches, enrich each scan (user-agent parsing, bot
filter, geo-IP), bulk-insert raw rows, and update **daily rollup** tables. Dashboards
read only the rollups. Raw scans have configurable retention, and the IP is stored
only as a hash with a daily-rotating salt, which also gives "estimated unique scans".
Partitioning by month (Postgres declarative partitioning) is ready for when volume
needs it.

### 1.7 QR styling and scannability
- **`segno`** generates the QR matrix (pure Python, full error-correction control).
- A Qrumy **custom renderer** draws modules and finder "eyes" with selectable shapes,
  colors, logo, frame and CTA text. It outputs SVG natively and PNG via Pillow.
- Scannability guards: minimum contrast ratio, error correction H when a logo is used,
  logo ≤ ~20% of the area, enforced quiet zone.
- **Automated decode check** using `zxing-cpp` (Python wheels): every style preset in
  tests, and the user's design on save, so we don't ship codes that cannot be scanned.

### 1.8 Payments
Free beta, so no gateway yet. The `billing` app defines a `PaymentGateway` interface
and a `ManualGateway` (admin-assigned plans, always logged as manual). Nothing ever
marks a payment as successful without a real gateway. Provider choice (Stripe vs a
Merchant-of-Record such as Paddle) is made before paid plans launch.

### 1.9 Personal data of non-users (leads, attendees, respondents)
Required from the start: consent checkbox with the stored consent text and version,
unsubscribe links, per-contact export and delete, and retention settings. Follow-up
emails go only to contacts with recorded consent.

### 1.10 Public, unauthenticated pages
Survey pages, asset profiles, fault forms, lead capture pages, tickets and redirects
resolve the tenant **from an unguessable token**, never from a session. All of them
are rate-limited and have a honeypot (captcha optional).

### 1.11 Django-specific pitfalls handled up front
- **Custom user model** (email login) is created before the first migration. It cannot
  be changed cheaply later.
- **Django has no global query scopes.** Tenancy is enforced by explicit, mandatory
  patterns (see §2.2) and a test suite, not by thread-local "magic".
- **Django's built-in Groups/Permissions are global**, not per-organization. They are
  used only for staff (super-admin) access. Tenant roles live on `Membership`.
- **Alpine.js and Content-Security-Policy:** use Alpine's CSP build so that no
  `unsafe-eval` is needed.
- **Azerbaijani text:** Inter covers ə, ğ, ı, ş, ç, ö, ü. URL slugs use a small
  az→Latin transliteration (e.g. ə→e). Postgres collation and search are configured
  for mixed az/en content.
- **Time zones:** `USE_TZ=True`, stored in UTC, shown in the org's or event's time
  zone (default `Asia/Baku`, configurable).

---

## 2. Recommended final architecture

**Modular monolith**: one Django project, independent Django apps, one PostgreSQL
database, Celery workers on Redis.

```
                         ┌────────────────────── Django project "qrumy" ───────────────────────┐
  qrumy.com ──► Nginx ──►│ Gunicorn                                                             │
  <short-domain> ───────►│  ├─ Marketing (i18n: /en, /az)   ├─ App UI (/app/<org>/…, HTMX)      │
                         │  ├─ Public pages (/s/, /e/, /a/)  ├─ REST API (/api/v1, DRF)          │
                         │  ├─ Redirect URLconf (short domain only)                             │
                         │  └─ Super-admin (/<secret-path>/, Django Admin, staff + 2FA)         │
                         │                                                                      │
                         │  PRODUCT APPS:  qr_management* · surveys · events · assets ·          │
                         │                 agency · ai_intelligence                             │
                         │  PLATFORM APPS: core · accounts · organizations · subscriptions ·    │
                         │                 billing · analytics · notifications · audit_logs     │
                         └─────────┬──────────────────────────────┬─────────────────────────────┘
                              PostgreSQL 16                  Redis 7 (cache, sessions, broker,
                                                             scan buffer)
                                                               ├─► Celery workers
                                                               └─► Celery beat (schedules)
   * qr_management is both a product (QR Codes) and the shared QR engine other apps use.
```

### 2.1 Key decisions

| Concern | Decision | Why |
|---|---|---|
| Versions | Python 3.13 (min 3.12), **Django 5.2 LTS**, DRF 3.16, Celery 5.5, PostgreSQL 16, Redis 7 | LTS supported to April 2028; every dependency supports it |
| Settings | `config/settings/{base,dev,test,prod}.py` + `django-environ` | 12-factor; secrets only in env |
| Auth | **`django-allauth`**: email login, verification, password reset, remember-me, rate-limited login, Google OAuth (configured later), MFA/TOTP (built in, enabled later) | Covers the whole auth spec with one well-maintained library |
| Tenancy | Org in URL (`/app/<org_slug>/…`), `OrganizationMiddleware` + membership check, `TenantModel` base, `OrgScopedQuerySet.for_org()`, view mixins and DRF base viewsets that **always** scope; isolation test suite. Postgres Row-Level Security as optional defence in depth (Phase 7). | Explicit, testable; multi-org and agency switching are natural |
| Roles | `Membership.role` ∈ owner/admin/manager/member/viewer + capability matrix (`organizations/capabilities.py`) checked via `require_capability` decorator/mixin and DRF permission classes | Per-tenant roles without bending Django's global permissions |
| Plans & limits | `subscriptions.entitlements`: `org.can("qr.dynamic")`, `org.limit("qr.dynamic.max")`, usage counters; a **Beta plan** is assigned to all orgs during the beta | Limits work now; paid plans need no rework |
| Shared QR | `qr_management.QRCode` is the single short-code registry. Other apps hold an FK to it (e.g. `Survey.qr_code`, `Asset.qr_code`, `Exhibitor.capture_qr`). Each sets a `purpose`; apps register a resolver in `AppConfig.ready()`. Event **tickets** use their own token model (high volume, different lifecycle). | Real FKs (no GenericForeignKey); dependencies point to the platform only |
| Frontend | Django Templates; components as `{% include %}`-based partials + `django-template-partials` for HTMX fragments; `django-htmx`; HTMX 2; Alpine (CSP build); Tailwind v4 built in a Docker build stage (Node only at build time, not in production); Chart.js; SortableJS (survey builder); a maintained JS scanner for camera check-in | Matches spec; no SPA |
| Design tokens | CSS variables in `static/src/tokens.css` mapped into the Tailwind theme (navy palette from the spec); Inter font self-hosted | Global restyling from one file |
| i18n | Django i18n; `LANGUAGES = [("en"), ("az")]`; `i18n_patterns` for the marketing site; user/org language preference; `.po` files for en/az. User-authored content (survey questions, event pages) gets optional per-language fields (JSONB) from Phase 3. | Both languages from day one |
| API | DRF under `/api/v1`. Session auth for in-app JS (check-in scanner, builder saves); per-org hashed API keys later. `drf-spectacular` for OpenAPI. | Spec requires REST where needed |
| Background jobs | Celery + Redis; `django-celery-beat` for schedules; tasks receive `organization_id` explicitly, never an implicit context | Safe tenancy in workers |
| Email | `django-anymail` (provider-agnostic) sent via Celery; templates in en/az | Swap providers by config |
| Files | Django storages: local now, `django-storages` S3 later; validation with `python-magic` + Pillow, size caps per plan; private files served through Nginx `X-Accel-Redirect` after a permission check | Secure uploads |
| Analytics libs | `ua-parser` (UA), crawler list + heuristics (bots), `geoip2` + MaxMind GeoLite2 local DB (country/region/city only) | No per-scan API cost; no GPS claims |
| Super-admin | Django Admin themed with **`django-unfold`** (Tailwind-based, modern), staff-only, MFA required, non-default URL, every write audited | Premium admin with little custom code |
| Security | Django CSRF/autoescape/ORM parameterization, `django-csp`, `django-ratelimit` on public endpoints, allauth login throttling, HSTS, secure cookies, safe-redirect validator, `audit_logs` for sensitive actions | Spec §19 |
| Quality | `pytest` + `pytest-django` + `factory_boy`, tests against real PostgreSQL; Playwright for key end-to-end flows; `ruff`; `mypy` + `django-stubs` on platform apps; `pre-commit` | "Works end to end", not "pages render" |
| Observability | Structured logging, `sentry-sdk` (optional DSN), health endpoint | Launch readiness |

### 2.2 Tenancy pattern (mandatory for every product app)

```python
class TenantModel(models.Model):            # core/models.py
    organization = models.ForeignKey("organizations.Organization",
                                     on_delete=models.CASCADE, db_index=True)
    objects = OrgScopedManager()            # .for_org(org) is the only sanctioned entry point
    class Meta: abstract = True

class OrgScopedViewMixin:                   # core/views.py
    model = None
    capability = None                       # e.g. "qr.edit"
    def get_queryset(self):
        return self.model.objects.for_org(self.request.organization)
```

`request.organization` is set only after the middleware verifies the user's
membership. Objects are always fetched through the scoped queryset, so an ID from
another organization returns **404**, not 403. The isolation suite automatically
visits every app URL with another organization's object IDs and expects 404.

---

## 3. Project structure

```
dergah/                          (repository root)
├─ config/                       Django project: settings/, urls.py, urls_redirect.py,
│                                celery.py, wsgi.py, asgi.py
├─ apps/
│  ├─ core/            base models (TimeStamped, TenantModel, PublicToken), mixins,
│  │                   capability decorators, safe-redirect + upload validators, CSV export,
│  │                   template components, design system, dashboard shell, marketing pages
│  ├─ accounts/        custom User (email login), allauth adapters, profile, language pref
│  ├─ organizations/   Organization, Membership, Invitation, roles/capabilities,
│  │                   middleware, org switcher, team management
│  ├─ subscriptions/   Plan, PlanFeature, Subscription, FeatureOverride, UsageCounter,
│  │                   entitlements service, module registry (which products are on)
│  ├─ billing/         PaymentGateway interface, ManualGateway, Invoice (later: real provider)
│  ├─ audit_logs/      AuditLog (admin + sensitive tenant actions), ActivityLog (feed)
│  ├─ notifications/   Notification model, in-app + email channels, preferences, templates
│  ├─ analytics/       scan ingestion (Redis buffer → Celery), UA/bot/geo enrichment,
│  │                   rollups, reporting queries, CSV export
│  ├─ qr_management/   QRCode, Folder, Tag, HostedFile; QR engine (segno + renderer),
│  │                   type payload schemas, redirect view, bulk CSV, export, abuse checks
│  ├─ surveys/         Survey, Question, Option, Response, Answer, ResponseNote;
│  │                   builder, public pages, embed, NPS/CSAT/CES scoring, analytics
│  ├─ events/          Event, Exhibitor, ExhibitorMember, Stand, Lead, LeadNote,
│  │                   FollowUpTask, FollowUpTemplate, RegistrationForm, Attendee,
│  │                   Ticket, CheckIn; organizer & exhibitor dashboards
│  ├─ assets/          Asset, Category, Location (tree), AssetDocument, FaultReport,
│  │                   MaintenanceRecord (later: schedules, tasks)
│  ├─ agency/          (Phase 10) client workspaces, branding, client reports
│  └─ ai_intelligence/ (Phase 9) AIProvider interface, usage metering, insight jobs
│     each app: models.py, services/, selectors.py, views/, api/, forms.py, tasks.py,
│               admin.py, urls.py, templates/<app>/, migrations/, tests/
├─ templates/          base layouts: marketing, app, public, email
├─ static/src/         tokens.css, app.css (Tailwind entry), js/ (htmx, alpine, charts)
├─ locale/az/, locale/en/
├─ docker/             Dockerfile (multi-stage), nginx.conf, entrypoints
├─ docker-compose.yml  (dev)   docker-compose.prod.yml
├─ tests/e2e/          Playwright end-to-end flows
├─ pyproject.toml      (deps, ruff, pytest, mypy config)
└─ docs/               ARCHITECTURE.md, CHECKLIST.md, DEPLOYMENT.md, decisions/
```

Code layout rule inside apps: **views stay thin**. Writes go through `services/`
(business logic, transactions, audit calls); reads go through `selectors.py`. This
prevents giant views and duplicated logic.

---

## 4. Database ERD (MVP scope, PostgreSQL)

Conventions: `bigint` PKs internally; public identifiers are separate random tokens or
ULIDs; all tenant tables carry `organization_id` (FK + index) and `created_at` /
`updated_at`. Flexible data uses JSONB. Uniqueness rules are DB constraints (e.g. one
check-in per ticket).

### 4.1 Platform

```mermaid
erDiagram
  accounts_user ||--o{ organizations_membership : has
  organizations_organization ||--o{ organizations_membership : has
  organizations_organization ||--o{ organizations_invitation : sends
  organizations_organization |o--o{ organizations_organization : "parent (agency)"
  organizations_organization ||--o{ subscriptions_subscription : has
  subscriptions_plan ||--o{ subscriptions_planfeature : defines
  subscriptions_plan ||--o{ subscriptions_subscription : "subscribed to"
  organizations_organization ||--o{ subscriptions_featureoverride : has
  organizations_organization ||--o{ subscriptions_usagecounter : tracks
  organizations_organization ||--o{ audit_logs_auditlog : logs
  organizations_organization ||--o{ notifications_notification : receives

  accounts_user { bigint id; citext email UK; string full_name; string language; bool is_staff; timestamp date_joined }
  organizations_organization { bigint id; string name; string slug UK; string logo; string website; string industry; char country; string timezone; string language; bigint owner_id; bigint parent_id; string kind; string status }
  organizations_membership { bigint user_id; bigint organization_id; string role; "UK(user, org)" }
  subscriptions_plan { string key UK; string name; int price_monthly_cents; int price_yearly_cents; int trial_days; bool is_public; bool is_beta }
  subscriptions_planfeature { bigint plan_id; string feature_key; bool enabled; int limit_value }
  subscriptions_subscription { bigint organization_id; bigint plan_id; string status; string interval; string gateway; string gateway_ref; timestamp trial_ends_at; timestamp current_period_end }
  subscriptions_usagecounter { bigint organization_id; string metric; string period; int value }
  audit_logs_auditlog { bigint actor_id; bigint organization_id; string action; string target_type; string target_id; jsonb changes; inet_hash ip_hash; timestamp at }
```

### 4.2 QR management & analytics

```mermaid
erDiagram
  organizations_organization ||--o{ qr_qrcode : owns
  qr_folder ||--o{ qr_qrcode : contains
  qr_qrcode }o--o{ qr_tag : tagged
  qr_qrcode ||--o{ qr_hostedfile : hosts
  qr_qrcode ||--o{ analytics_scan : records
  qr_qrcode ||--o{ analytics_scandaily : "rolled up"

  qr_qrcode { bigint id; bigint organization_id; bigint folder_id; string name; string qr_type; string mode "static|dynamic"; string short_code UK "immutable"; string purpose "standalone|survey|asset|exhibitor"; jsonb payload; text destination_url; jsonb style; string status "active|paused|suspended"; timestamp expires_at; bigint created_by_id }
  analytics_scan { bigint id; bigint qr_code_id; bigint organization_id; timestamp scanned_at "BRIN"; char ip_hash; char country; string region; string city; string device; string os; string browser; text referrer; jsonb utm; bool is_bot }
  analytics_scandaily { bigint qr_code_id; date day; string dimension; string value; int scans; int unique_scans; "UK(qr, day, dimension, value)" }
```

### 4.3 Surveys

```mermaid
erDiagram
  organizations_organization ||--o{ surveys_survey : owns
  qr_qrcode |o--o| surveys_survey : "distributes"
  surveys_survey ||--o{ surveys_question : has
  surveys_question ||--o{ surveys_option : has
  surveys_survey ||--o{ surveys_response : receives
  surveys_response ||--o{ surveys_answer : contains
  surveys_response ||--o{ surveys_responsenote : annotated

  surveys_survey { bigint id; bigint organization_id; string public_token UK; bigint qr_code_id; string title; jsonb title_i18n; text description; jsonb theme; jsonb settings; timestamp closes_at; int response_limit; string status }
  surveys_question { bigint survey_id; string qtype; string label; jsonb label_i18n; bool required; int position; jsonb config; jsonb logic "later" }
  surveys_response { bigint survey_id; bigint organization_id; string source; string status "open|resolved"; bigint assigned_to_id; bool completed; timestamp submitted_at; string language }
  surveys_answer { bigint response_id; bigint question_id; text value_text; numeric value_number; jsonb value_json }
```

### 4.4 Events

```mermaid
erDiagram
  organizations_organization ||--o{ events_event : organizes
  events_event ||--o{ events_exhibitor : hosts
  organizations_organization |o--o{ events_exhibitor : "exhibitor's own org"
  events_exhibitor ||--o{ events_exhibitormember : staff
  events_exhibitor |o--o| events_stand : at
  qr_qrcode |o--o| events_exhibitor : "capture QR"
  events_exhibitor ||--o{ events_lead : captures
  events_lead ||--o{ events_leadnote : has
  events_lead ||--o{ events_followuptask : has
  events_followuptemplate ||--o{ events_followuptask : uses
  events_event ||--o{ events_registrationform : has
  events_event ||--o{ events_attendee : registers
  events_attendee ||--o| events_ticket : holds
  events_ticket ||--o| events_checkin : "checked in (UK)"

  events_event { bigint id; bigint organization_id; string slug; string name; jsonb name_i18n; string event_type; timestamp starts_at; timestamp ends_at; string timezone; string venue; bool is_public; int capacity; jsonb settings "organizer_lead_access, consent_text" }
  events_exhibitor { bigint id; bigint event_id; bigint exhibitor_org_id; string company_name; string capture_token UK; jsonb lead_fields }
  events_exhibitormember { bigint exhibitor_id; bigint user_id; string role }
  events_lead { bigint id; bigint exhibitor_id; bigint event_id; string full_name; citext email; string phone; string company; string job_title; jsonb answers; string temperature; string stage; bigint assigned_to_id; bool consent_marketing; string consent_version; string source }
  events_attendee { bigint id; bigint event_id; string full_name; citext email; string status; jsonb answers; bool consent_marketing }
  events_ticket { bigint attendee_id; char token_hash UK "QR holds random token only" }
  events_checkin { bigint ticket_id UK; bigint checked_in_by_id; timestamp checked_in_at }
```

### 4.5 Assets (basic MVP)

```mermaid
erDiagram
  organizations_organization ||--o{ assets_asset : owns
  assets_category ||--o{ assets_asset : classifies
  assets_location ||--o{ assets_asset : located
  assets_location |o--o{ assets_location : parent
  qr_qrcode |o--o| assets_asset : profile
  assets_asset ||--o{ assets_assetdocument : has
  assets_asset ||--o{ assets_faultreport : receives
  assets_asset ||--o{ assets_maintenancerecord : history

  assets_asset { bigint id; bigint organization_id; string asset_code; string name; bigint category_id; string brand; string model; string serial_number; date purchase_date; date warranty_expires_at; int purchase_price_cents; bigint location_id; bigint responsible_user_id; string status; jsonb custom_fields; string public_visibility; bigint qr_code_id }
  assets_location { bigint organization_id; bigint parent_id; string kind "branch|building|floor|room|department"; string name; string path "materialized" }
  assets_faultreport { bigint asset_id; string category; text description; string priority; string status; string reporter_name; bigint reported_by_id }
  assets_maintenancerecord { bigint asset_id; string kind; date performed_on; bigint technician_id; int cost_cents; text notes }
```

---

## 5. App dependency map

```
 Layer 0  core
 Layer 1  accounts · organizations · audit_logs
 Layer 2  subscriptions · billing · notifications
 Layer 3  analytics · qr_management (shared QR engine + QR product)
 Layer 4  surveys · events · assets              ← product apps
 Layer 5  ai_intelligence · agency                ← read product data via each app's
                                                    selectors / registered "insight providers"
```
Rules: an app may import only from lower layers. **Product apps never import each
other.** Cross-app reactions use Django signals or registries defined in a lower
layer (e.g. "QR resolver", "dashboard widget", "navigation item", "entitlement key").
An `import-linter` contract in CI enforces the layers.

---

## 6. MVP (free beta) scope

**In the beta:**
- Platform: signup/login/verify/reset/remember-me (en/az), organizations, invitations,
  5 roles, tenancy, Beta plan with limits, module enable/disable, Django Admin
  super-admin (users, orgs, plans, feature flags, QR abuse suspension, audit log),
  dashboard overview, design system, landing + pricing ("Free during beta") + SEO.
- QR: static + dynamic; URL, Text, Wi-Fi, vCard, Phone, SMS, Email, WhatsApp,
  Location, Social, Multi-link, PDF, Image, Menu, App download, Coupon, Survey link;
  folders, tags, search, filter, pause, expiry; styling with decode check; PNG/SVG;
  CSV bulk create; ZIP bulk export; analytics with rollups, filters, CSV export, bot
  filtering.
- Surveys: builder (all listed question types; conditional logic later), public page
  (en/az), QR/link/embed, NPS/CSAT/CES, analytics, response management.
- Events A: events, exhibitors, lead capture pages + QR, qualification, pipeline,
  assignment, notes, follow-up tasks + templates (manual send, consent only),
  organizer and exhibitor dashboards, CSV export.
- Events B: registration forms, attendees, QR tickets (email), camera + manual
  check-in, duplicate prevention, stats.
- Assets basic: assets, categories, location tree, QR profile with visibility levels,
  public fault reporting, maintenance history, simple stats.

**After the beta:** payment provider, Google OAuth activation, enforced 2FA for users,
survey conditional logic + per-language content editor, preventive maintenance and
task workflow + notifications, automated follow-ups, AI, Agency/white-label, PDF
export, custom domains, public API keys.

---

## 7. Phases

| # | Phase | Main deliverables | Size |
|---|---|---|---|
| 1 | Foundation | Repo skeleton, Docker Compose (web, worker, beat, postgres, redis, nginx), settings, CI config, custom User + allauth, organizations / memberships / invitations / roles, tenancy base + isolation harness, subscriptions + Beta plan + entitlements, billing interface, audit_logs, notifications base, Unfold admin, design system + layouts, dashboard shell, en/az i18n, landing v1 | L |
| 2 | QR Management | QR engine + decode check, types, styling, static/dynamic, short-domain redirect, scan pipeline + rollups, folders/tags, bulk CSV, export, analytics UI, abuse controls | L |
| 3 | Surveys | Builder (HTMX + SortableJS), public pages, embed, scoring, analytics, response management | M–L |
| 4 | Events A | Lead capture end to end + dashboards | L |
| 5 | Events B | Registration, tickets, check-in | M |
| 6 | Assets basic | Assets, locations, QR profile, fault reports, maintenance history | M |
| 7 | Beta launch prep | Security review (+ optional Postgres RLS), performance test of redirect path, backups + restore test, Sentry, deployment docs, VPS deploy | M |
| 8 | Assets advanced | Schedules, task workflow, notifications | M |
| 9 | ai_intelligence | Provider interface, feedback sentiment and summaries, lead summaries, reports | M–L |
| 10 | agency | Client orgs, switching, client reports, white-label base | L |
| 11 | billing | Real payment provider, upgrades/downgrades, invoices | M |

Each phase ends with: tests passing on PostgreSQL, the isolation suite green,
Playwright flows for that phase green, checklist updated, and a short report to you.
The next phase starts only after that.

---

## 8. Technical risks

| Risk | Impact | Mitigation |
|---|---|---|
| Cross-tenant leak (esp. exhibitor leads) | Critical | Mandatory scoped querysets, 404-on-foreign-ID, automated isolation suite, optional RLS |
| Redirect domain blocklisted | Critical | Separate short domain, URL checks, beta rate limits, one-click suspension |
| Free beta attracts spam and abuse | High | Email verification before dynamic QR, low beta limits, URL checks, admin review queue |
| Redirect latency under scan spikes | High | Redis lookup + buffered writes, async enrichment, rollups, load test in Phase 7 |
| Unscannable styled codes | High | Contrast/logo/ECC rules + zxing-cpp decode check |
| Personal-data compliance | High | Consent records, unsubscribe, export/delete, retention |
| Scope creep | High | Phase gates; post-beta list |
| Celery tasks running without tenant context | Medium | Tasks take `organization_id` explicitly; helper re-loads scoped objects |
| Two-language maintenance | Medium | All strings via gettext from day one; CI fails if az catalog is missing strings |
| Email deliverability | Medium | Transactional provider via anymail, SPF/DKIM/DMARC |

---

## 9. Infrastructure requirements

- **Beta VPS:** 2–4 vCPU, 4–8 GB RAM, 80 GB SSD, Ubuntu 24.04 LTS, Docker Engine +
  Compose plugin.
- Containers: `nginx`, `web` (Gunicorn), `worker` (Celery), `beat` (Celery beat),
  `postgres` (16), `redis` (7). Volumes for Postgres, Redis, media.
- Domains: `qrumy.com` (+ `www`), and the short redirect domain (to be purchased).
  TLS via Certbot/Let's Encrypt, or Cloudflare in front.
- Transactional email provider account; MaxMind GeoLite2 free license key;
  optional Sentry DSN; optional URL-reputation API key.
- Off-site backups: nightly `pg_dump` + media sync to S3-compatible storage
  (7 daily / 4 weekly / 3 monthly), with a restore drill before launch.

## 10. Deployment architecture

```
         (optional) Cloudflare — DNS, TLS, DDoS, static caching
                           │
   ┌────────────────────── VPS: docker compose -f docker-compose.prod.yml ──────────────────────┐
   │  nginx :443 ── qrumy.com ───────► web (gunicorn, N workers) ──┐                             │
   │       │      └ short domain ───► web (same image, redirect URLconf)                         │
   │       ├─ /static/ (collected, hashed)                         ├──► postgres (volume)         │
   │       └─ /protected-media/ (X-Accel-Redirect after auth)      ├──► redis (volume)            │
   │                                    worker (celery) ◄──────────┤                              │
   │                                    beat   (celery beat) ◄─────┘                              │
   └────────────────────────────────────────────────────────────────────────────────────────────┘
          nightly backup container ──► off-site S3-compatible storage
```

Deploy steps: build image (Tailwind compiled in a Node build stage, Python runtime
stage) → `migrate` → `collectstatic` → restart `web`/`worker`/`beat` with health
checks. Scaling path: managed Postgres → more `web`/`worker` replicas → media to S3.
No code changes needed.

---

## 11. Open questions (still needed)

1. **Short redirect domain name:** which domain will you buy (e.g. `qrumy.link`,
   `qrumy.az`, `qrm.az`…)? Development uses a placeholder from env.
2. **Beta signups:** open signup with strict limits (recommended), or invite / waitlist
   only?
3. **Default language** for `qrumy.com` with no language prefix: Azerbaijani or English
   (with browser-language detection either way)?
4. **Admin theme:** `django-unfold` (recommended) or plain Django Admin?
