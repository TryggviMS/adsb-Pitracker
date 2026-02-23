#!/bin/bash
# scripts/recompose.sh
# Usage:
#   ./scripts/recompose.sh        # production
#   ./scripts/recompose.sh --dev  # development (WSL2)

set -e

DEV=false
if [[ "$1" == "--dev" ]]; then
  DEV=true
fi

REPO=$(git rev-parse --show-toplevel)

echo "==> Postgres"
cd $REPO/docker/postgres
docker compose --env-file ../../.env.postgres down

if [ "$DEV" = true ]; then
  echo "    (dev mode - exposing port 5433)"
  docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file ../../.env.postgres up -d
else
  docker compose --env-file ../../.env.postgres up -d
fi

echo "==> Reconnecting postgres to adsb_net"
docker network connect adsb_net postgis_db 2>/dev/null || true

echo "==> Python"
cd $REPO/docker/python
docker compose down

if [ "$DEV" = true ]; then
  echo "    (dev mode - mounting live source files)"
  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
else
  docker compose up -d --build
fi

echo "==> Nginx"
cd $REPO/docker/nginx
docker compose down
docker compose up -d

echo "==> Done. Network status:"
docker network inspect adsb_net | grep Name