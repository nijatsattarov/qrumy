# Deployment (single VPS, Docker Compose)

Target: Ubuntu 24.04 LTS, 2–4 vCPU, 4–8 GB RAM, Docker Engine + Compose plugin.

**Hostinger VPS:** choose the *Ubuntu 24.04 with Docker* template (or plain Ubuntu 24.04 and
install Docker with `curl -fsSL https://get.docker.com | sh`). Point the domain's `A`
records to the VPS IP in hPanel → DNS. Hostinger's panel firewall can stay off when `ufw`
is used as below (otherwise allow ports 22, 80 and 443 there too).

## 1. First-time setup
```bash
git clone <repo> /srv/qrumy && cd /srv/qrumy
cp .env.example .env
```
Edit `.env`:

| Variable | Value |
|---|---|
| `SECRET_KEY` | long random string (`python3 -c "import secrets;print(secrets.token_urlsafe(50))"`) |
| `POSTGRES_PASSWORD` | long random string |
| `ALLOWED_HOSTS` | `qrumy.com,www.qrumy.com` |
| `SITE_URL` | `https://qrumy.com` |
| `QRUMY_ADMIN_PATH` | a non-obvious path, e.g. `ops-7f3k/` |
| `RESEND_API_KEY` | API key from resend.com (**Sending access** is enough) — switches email delivery to Resend |
| `DEFAULT_FROM_EMAIL` | `Qrumy <no-reply@qrumy.com>` — the domain must be verified in Resend |
| `CERTS_DIR` | `/etc/letsencrypt/live/qrumy.com` |
| `SENTRY_DSN` | optional, enables error monitoring (Sentry) |
| `SECRET_KEY_FALLBACKS` | previous secret keys while rotating `SECRET_KEY` (comma-separated) |
| `SECURE_HSTS_PRELOAD` | `True` only after HTTPS is permanent on all subdomains |
| `QRUMY_QR_BASE_URL` | `https://qrumy.com/q/` — **printed into every dynamic QR code; never change it for existing codes** |
| `QRUMY_GEOIP_CITY_DB` | path to MaxMind GeoLite2-City `.mmdb` (optional; without it, country/city stay empty) |
| `QRUMY_COUNTRY_HEADER` | `HTTP_CF_IPCOUNTRY` if Qrumy runs behind Cloudflare (country only) |
| `QRUMY_SAFE_BROWSING_KEY` | optional Google Safe Browsing key (blocks known-malicious destinations) |

> Without `RESEND_API_KEY`, emails are only printed to the container log and **no emails are
> delivered** (sign-up verification will not reach users).

### Email with Resend
1. In Resend → **Domains** → add `qrumy.com` (or a subdomain such as `mail.qrumy.com`).
2. Add the DNS records Resend shows (SPF `TXT`, DKIM `TXT`/`CNAME`, optional `MX` for the
   bounce subdomain) at your DNS provider and wait until Resend marks the domain *Verified*.
3. Add a DMARC record, e.g. `_dmarc.qrumy.com TXT "v=DMARC1; p=none; rua=mailto:dmarc@qrumy.com"`
   (move to `p=quarantine` once reports look clean).
4. Create an API key with **Sending access**, put it in `.env` as `RESEND_API_KEY`, set
   `DEFAULT_FROM_EMAIL`, and restart: `docker compose -f docker-compose.prod.yml up -d`.
5. Test: `docker compose -f docker-compose.prod.yml exec web python manage.py sendtestemail you@example.com`

## 2. TLS certificate (Let's Encrypt)
DNS: `A` records for `qrumy.com` and `www.qrumy.com` → VPS IP. Then:
```bash
sudo apt install certbot
sudo certbot certonly --standalone -d qrumy.com -d www.qrumy.com
```
Renewal: `certbot renew --pre-hook "docker compose -f /srv/qrumy/docker-compose.prod.yml stop nginx" --post-hook "docker compose -f /srv/qrumy/docker-compose.prod.yml start nginx"` (cron, twice daily).

## 3. Start
```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Migrations run automatically when `web` starts (`RUN_MIGRATIONS=1`). Check:
`docker compose -f docker-compose.prod.yml ps` (web must be `healthy`).

## 4. Update
```bash
./docker/deploy.sh   # pull → backup → build → restart → wait until healthy
```

## 5. Backups and restore drill
`docker/backup.sh` dumps PostgreSQL (verified with `pg_restore --list`), archives media files,
writes checksums, deletes local copies older than `BACKUP_KEEP_DAYS` (14) and, when
`BACKUP_RCLONE_REMOTE` is set (e.g. `b2:qrumy-backups`), copies them off-site with
[rclone](https://rclone.org) (`apt install rclone`, then `rclone config`).

Cron (as the deploy user, `crontab -e`):
```cron
15 3 * * * cd /srv/qrumy && ./docker/backup.sh >> /var/log/qrumy-backup.log 2>&1
30 4 * * 1 cd /srv/qrumy && ./docker/restore.sh "$(ls -t backups/db-*.dump | head -1)" >> /var/log/qrumy-restore-drill.log 2>&1
```
The weekly drill restores the newest dump into a **scratch database**, prints row counts next
to the live ones and removes the scratch database — live data is never touched.

Disaster recovery (destructive, asks you to type `REPLACE`):
```bash
./docker/restore.sh --replace-live backups/db-<stamp>.dump backups/media-<stamp>.tar.gz
```

## 6. Server hardening (once)
```bash
sudo apt install -y ufw unattended-upgrades fail2ban
sudo ufw default deny incoming && sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
sudo dpkg-reconfigure -plow unattended-upgrades
```
In `/etc/ssh/sshd_config`: `PasswordAuthentication no`, `PermitRootLogin no`, then
`sudo systemctl reload ssh`. PostgreSQL and Redis are not published on host ports by
`docker-compose.prod.yml`; keep it that way.

## 7. Error monitoring
Set `SENTRY_DSN` (and optionally `SENTRY_ENVIRONMENT`). Error reports exclude user details,
request bodies, SQL parameters and local variables. Point an uptime monitor at
`https://qrumy.com/healthz` (returns 200 when the app and database are up).

## 8. Legal pages
The Terms of Service and Privacy Policy (English and Azerbaijani, version `2026-11-25`) are
published automatically by `migrate` (texts in `apps/accounts/legal_texts/`). They appear at
`/terms/`, `/privacy/`, `/az/terms/`, `/az/privacy/`, in the footer and as a required checkbox at
sign-up; each user's accepted versions are stored.

To change them, open the admin → **Accounts → Legal documents**:
- small fixes (typos): edit the document and save — the page updates immediately;
- material changes: use "Save as new" with a new **version** (e.g. `2027-03-01`) and a
  publication time. The newest published version is shown; older ones stay for the record.
- Formatting: a line starting with `## ` is a heading, `- ` a list item, a blank line starts a
  new paragraph. HTML is not interpreted.

## 9. Blog
Write posts in the admin → **Marketing → Blog posts**. Each post is written in one language
(English or Azerbaijani) and appears at `/blog/<slug>/` or `/az/blog/<slug>/`. Leave
"published at" empty for a draft, set a future time to schedule. To put an image inside the
text, upload it under "Images for the text", save, and paste the line shown into the text.

## GeoIP (optional)
Create a free MaxMind account, download **GeoLite2-City.mmdb** and mount it into the
`web` container (e.g. `./var:/app/var:ro` and `QRUMY_GEOIP_CITY_DB=/app/var/GeoLite2-City.mmdb`).
Refresh it monthly (MaxMind's `geoipupdate` tool). Only country/region/city are derived; the
raw IP is hashed with a daily salt and never stored.

## Services
| Service | Role |
|---|---|
| `nginx` | TLS, HTTP→HTTPS redirect, rejects unknown hosts, serves public media and (via X-Accel) files behind QR codes |
| `web` | Gunicorn (Django); static files via WhiteNoise |
| `worker` | Celery worker (emails, background jobs) |
| `beat` | Celery beat: drains the scan buffer every 15 s, purges old raw scans |
| `db` | PostgreSQL 16 |
| `redis` | cache, sessions, Celery broker |
