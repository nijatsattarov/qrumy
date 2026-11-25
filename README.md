# Qrumy

QR-powered business platform: QR management, surveys & feedback, asset management and
event lead capture — one account, one team, one QR infrastructure. Domain: **qrumy.com**.

> Status: **Phases 1–3 and 6 complete** (Foundation, QR Management, Surveys, Asset Management). Events (4–5) are postponed. Product modules are built phase by phase —
> see [`docs/CHECKLIST.md`](docs/CHECKLIST.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Stack
Python 3.13 · Django 5.2 LTS · DRF · PostgreSQL 16 · Celery + Redis · Django templates +
Tailwind CSS v4 + HTMX + Alpine.js (CSP build) · Django Admin (Unfold) · Docker Compose ·
Nginx · Gunicorn. Languages: English (default) and Azerbaijani.

## Local development

Requirements: Python 3.12+, Node 22 (build-time only), PostgreSQL 16, Redis 7 — or just Docker.

### With Docker
```bash
docker compose up --build
```
Then open http://localhost:8000. Run migrations the first time:
```bash
docker compose exec web python manage.py migrate
```

### Without Docker
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
npm install && npm run build          # Tailwind CSS, HTMX, Alpine, fonts → static/
cp .env.example .env                  # adjust DATABASE_URL / REDIS_URL
python manage.py migrate
python manage.py compilemessages --ignore=.venv
python manage.py createsuperuser
python manage.py runserver
celery -A config worker -l info       # second terminal (emails, background jobs)
celery -A config beat -l info         # third terminal (processes QR scans every 15 s)
```
While editing templates: `npm run watch:css`.

The super-admin lives at `/qadmin/` (configurable with `QRUMY_ADMIN_PATH`). In production,
staff must enable two-factor authentication before the admin opens.

## Quality checks
```bash
ruff check .            # lint
lint-imports            # enforces app layering (docs/ARCHITECTURE.md §5)
pytest                  # needs PostgreSQL (DATABASE_URL)
```
The test suite includes a **tenant-isolation suite** (`tests/test_tenant_isolation.py`)
that attacks every organization-scoped URL from another organization, and fails if a new
object-level route is added without an isolation test.

## Translations
```bash
python manage.py makemessages -l az --ignore=.venv --ignore=node_modules
# translate locale/az/LC_MESSAGES/django.po, then:
python manage.py compilemessages --ignore=.venv
```
`tests/test_translations.py` fails if any Azerbaijani string is missing or a placeholder
was changed.

## Deployment
See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
