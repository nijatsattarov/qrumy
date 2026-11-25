# Deployment (single VPS, Docker Compose)

Target: Ubuntu 24.04 LTS, 2–4 vCPU, 4–8 GB RAM, Docker Engine + Compose plugin.

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
| `EMAIL_BACKEND` | e.g. `anymail.backends.postmark.EmailBackend` (any Anymail provider) |
| `ANYMAIL` | provider settings, e.g. `POSTMARK_SERVER_TOKEN=...` |
| `DEFAULT_FROM_EMAIL` | `Qrumy <no-reply@qrumy.com>` |
| `CERTS_DIR` | `/etc/letsencrypt/live/qrumy.com` |
| `SENTRY_DSN` | optional (requires `pip install sentry-sdk` in the image) |

> Without an email provider, `EMAIL_BACKEND` defaults to the console backend and **no
> emails are delivered** (sign-up verification will not reach users).

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
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

## 5. Backups (set up before launch)
Nightly database dump + media copy to off-site S3-compatible storage:
```bash
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U qrumy -Fc qrumy > /backups/qrumy-$(date +%F).dump
```
Keep 7 daily / 4 weekly / 3 monthly. Test a restore before launch:
`pg_restore -U qrumy -d qrumy_restore --clean /backups/<file>.dump`.

## Services
| Service | Role |
|---|---|
| `nginx` | TLS, HTTP→HTTPS redirect, rejects unknown hosts, serves public media |
| `web` | Gunicorn (Django); static files via WhiteNoise |
| `worker` | Celery worker (emails, background jobs) |
| `beat` | Celery beat (scheduled jobs, stored in the database) |
| `db` | PostgreSQL 16 |
| `redis` | cache, sessions, Celery broker |
