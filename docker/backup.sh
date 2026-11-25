#!/usr/bin/env bash
# Qrumy backup: PostgreSQL dump + media files, verified, rotated, optionally copied off-site.
# Run on the server from the project directory (cron example in docs/DEPLOYMENT.md):
#   ./docker/backup.sh
# Settings (environment or .env): BACKUP_DIR (default ./backups), BACKUP_KEEP_DAYS (14),
#   BACKUP_RCLONE_REMOTE (optional, e.g. "b2:qrumy-backups") → copied with `rclone copy`.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.prod.yml"
DEST="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"

DB_FILE="$DEST/db-$STAMP.dump"
MEDIA_FILE="$DEST/media-$STAMP.tar.gz"

echo "→ Dumping database"
$COMPOSE exec -T db pg_dump -U qrumy -Fc qrumy > "$DB_FILE"
echo "→ Verifying dump"
$COMPOSE exec -T db pg_restore --list < "$DB_FILE" > /dev/null
echo "→ Archiving media"
$COMPOSE exec -T web tar -C /app/media -czf - . > "$MEDIA_FILE"
tar -tzf "$MEDIA_FILE" > /dev/null
(cd "$DEST" && sha256sum "$(basename "$DB_FILE")" "$(basename "$MEDIA_FILE")" > "checksums-$STAMP.sha256")

if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
  echo "→ Copying off-site to $BACKUP_RCLONE_REMOTE"
  rclone copy "$DEST" "$BACKUP_RCLONE_REMOTE" --include "*-$STAMP.*"
fi

echo "→ Removing local backups older than $KEEP_DAYS days"
find "$DEST" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'media-*.tar.gz' -o -name 'checksums-*.sha256' \) -mtime "+$KEEP_DAYS" -print -delete

echo "✓ Backup complete: $DB_FILE ($(du -h "$DB_FILE" | cut -f1)), $MEDIA_FILE ($(du -h "$MEDIA_FILE" | cut -f1))"
