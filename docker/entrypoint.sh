#!/bin/sh
set -e

case "$1" in
  web)
    if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
      python manage.py migrate --noinput
    fi
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-30}" \
      --access-logfile - --error-logfile -
    ;;
  worker)
    exec celery -A config worker --loglevel "${LOG_LEVEL:-info}" --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    exec celery -A config beat --loglevel "${LOG_LEVEL:-info}"
    ;;
  *)
    exec "$@"
    ;;
esac
