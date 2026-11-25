# Beta launch checklist

Legend: ✅ done in code and verified · 🟡 needs a decision or access from the product owner

## Product
- ✅ QR Management, Surveys & Feedback, Asset Management (Events postponed)
- ✅ English + Azerbaijani everywhere (UI, public pages, emails)
- ✅ Free Beta plan with limits; no payments collected

## Security
- ✅ `manage.py check --deploy` clean (HSTS preload intentionally off until HTTPS is permanent)
- ✅ No known vulnerabilities in Python (`pip-audit`) or npm dependencies
- ✅ Strict CSP, Permissions-Policy, HSTS, secure cookies, unknown hosts rejected by Nginx
- ✅ Tenant-isolation suite over every organization route (mutation-tested per module)
- ✅ Admin: hidden path, staff-only, MFA required; staff actions audited
- ✅ Abuse: destination validation + blocklist (also enforced at scan time), admin suspension
- ✅ Public forms: signed tokens, honeypots, rate limits; scans are never blocked by rate limits

## Reliability
- ✅ Cached scan path makes zero database queries; load test ≈ 900 scans/s, p50 38 ms
  (single VPS container, 4 Gunicorn workers, through Nginx TLS)
- ✅ Backups + restore drill + disaster-recovery restore tested end to end
- ✅ Health check, deploy script, error monitoring (Sentry, privacy-preserving)

## Needs the product owner 🟡
- 🟡 **VPS**: provider, size (2–4 vCPU / 4–8 GB), SSH access for deployment
- 🟡 **DNS**: `qrumy.com` / `www` A records → VPS; SPF / DKIM / DMARC for the email provider
- 🟡 **Email provider** (Postmark, Amazon SES, Mailgun, Brevo, …) — without it no sign-up
  verification emails are delivered
- 🟡 **Terms of Service and Privacy Policy** texts (en + az), reviewed by a lawyer
- 🟡 **Off-site backup storage** (S3-compatible: Backblaze B2, Hetzner, AWS S3, …)
- 🟡 Optional: Sentry project (DSN), MaxMind GeoLite2 licence key, Google Safe Browsing key,
  Google OAuth client
