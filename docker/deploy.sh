#!/usr/bin/env bash
# Deploy the current branch on the server: pull, back up, rebuild, restart, verify.
#   ./docker/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.prod.yml"

echo "→ Pulling latest code"
git pull --ff-only

if $COMPOSE ps --services --filter status=running | grep -q '^db$'; then
  echo "→ Backing up before deploying"
  ./docker/backup.sh
fi

echo "→ Building and starting (migrations run automatically on web start)"
$COMPOSE up -d --build

echo "→ Waiting for the web container to become healthy"
for _ in $(seq 1 60); do
  status="$($COMPOSE ps web --format '{{.Health}}')"
  [ "$status" = "healthy" ] && break
  sleep 2
done
if [ "$status" != "healthy" ]; then
  echo "✗ web is '$status' — check: $COMPOSE logs web --tail 100" >&2
  exit 1
fi
$COMPOSE ps
echo "✓ Deployed $(git rev-parse --short HEAD)"
