# ---------- Stage 1: front-end assets (build-time only) ----------
FROM node:22-slim AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY scripts ./scripts
COPY assets ./assets
COPY templates ./templates
COPY apps ./apps
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 1000 app
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
COPY --from=assets /app/static/dist ./static/dist
COPY --from=assets /app/static/vendor ./static/vendor
RUN SECRET_KEY=build-only SITE_URL=https://build.invalid python manage.py compilemessages --ignore=.venv \
 && SECRET_KEY=build-only SITE_URL=https://build.invalid python manage.py collectstatic --noinput \
 && mkdir -p /app/media && chown -R app:app /app/media
USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
