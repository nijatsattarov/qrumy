#!/usr/bin/env bash
# Qrumy restore.
#
# Default (safe): restore a dump into a SEPARATE scratch database and compare row counts
# with the live database — use this for the regular restore drill. Nothing live changes.
#   ./docker/restore.sh backups/db-20261125T120000Z.dump
#
# Disaster recovery (destructive): replace the live database and media with a backup.
# Stops the app, drops and recreates the database. Asks you to type REPLACE to continue.
#   ./docker/restore.sh --replace-live backups/db-….dump backups/media-….tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.prod.yml"
SCRATCH_DB="qrumy_restore_check"
TABLES="accounts_user organizations_organization qr_management_qrcode analytics_scandaily surveys_response assets_asset audit_logs_auditlog"

count_rows() {  # $1 = database
  for t in $TABLES; do
    printf "%-28s %s\n" "$t" "$($COMPOSE exec -T db psql -U qrumy -d "$1" -tAc "SELECT count(*) FROM $t" 2>/dev/null || echo missing)"
  done
}

if [ "${1:-}" = "--replace-live" ]; then
  DB_FILE="${2:?dump file required}"; MEDIA_FILE="${3:?media archive required}"
  echo "!! This REPLACES the live database and media files with:"
  echo "   $DB_FILE"; echo "   $MEDIA_FILE"
  read -r -p "Type REPLACE to continue: " answer
  [ "$answer" = "REPLACE" ] || { echo "Aborted."; exit 1; }
  $COMPOSE stop web worker beat
  $COMPOSE exec -T db dropdb -U qrumy --if-exists qrumy
  $COMPOSE exec -T db createdb -U qrumy qrumy
  $COMPOSE exec -T db pg_restore -U qrumy -d qrumy --no-owner < "$DB_FILE"
  $COMPOSE run --rm --no-deps -T --entrypoint sh web -c "find /app/media -mindepth 1 -delete; tar -C /app/media -xzf -" < "$MEDIA_FILE"
  $COMPOSE start web worker beat
  echo "✓ Live data restored."; count_rows qrumy
  exit 0
fi

DB_FILE="${1:?usage: restore.sh <dump> | --replace-live <dump> <media.tar.gz>}"
echo "→ Restoring $DB_FILE into scratch database $SCRATCH_DB (live data is not touched)"
$COMPOSE exec -T db dropdb -U qrumy --if-exists "$SCRATCH_DB"
$COMPOSE exec -T db createdb -U qrumy "$SCRATCH_DB"
$COMPOSE exec -T db pg_restore -U qrumy -d "$SCRATCH_DB" --no-owner < "$DB_FILE"
echo; echo "Rows in backup:"; count_rows "$SCRATCH_DB"
echo; echo "Rows in live database:"; count_rows qrumy
$COMPOSE exec -T db dropdb -U qrumy "$SCRATCH_DB"
echo; echo "✓ Restore drill finished (scratch database removed)."
