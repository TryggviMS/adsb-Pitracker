#!/bin/bash
# scripts/recompose.sh
#
# Usage:
#   ./scripts/recompose.sh        # production
#   ./scripts/recompose.sh --dev  # development (WSL2)

set -e

DEV=false

if [[ "$1" == "--dev" ]]; then
  DEV=true
fi

REPO=$(git rev-parse --show-toplevel)

echo "======================================"
if [ "$DEV" = true ]; then
  echo "   RECOMPOSE: DEVELOPMENT MODE"
else
  echo "   RECOMPOSE: PRODUCTION MODE"
fi
echo "======================================"

# --------------------------------------------------
# Aircraft database
# --------------------------------------------------

echo "==> Downloading aircraft database"

CSV_FILE="$REPO/ADSB/aircraft-database-complete-2025-08.csv"

if [ -f "$CSV_FILE" ]; then
  echo "    (skipping - file already exists)"
else
  mkdir -p "$REPO/ADSB"

  wget -P "$REPO/ADSB" \
    https://s3.opensky-network.org/data-samples/metadata/aircraft-database-complete-2025-08.csv
fi


# --------------------------------------------------
# Postgres
# --------------------------------------------------

echo "==> Postgres"

cd "$REPO/docker/postgres"

docker compose --env-file ../../.env.postgres down

if [ "$DEV" = true ]; then
  echo "    (dev mode - exposing port 5433)"

  docker compose \
    -f docker-compose.yml \
    -f docker-compose.dev.yml \
    --env-file ../../.env.postgres \
    up -d
else
  docker compose \
    --env-file ../../.env.postgres \
    up -d
fi


# --------------------------------------------------
# Connect Postgres to ADS-B network
# --------------------------------------------------

echo "==> Reconnecting postgres to adsb_net"

docker network connect adsb_net postgis_db 2>/dev/null || true


# --------------------------------------------------
# Python / Flask
# --------------------------------------------------

echo "==> Python"

cd "$REPO/docker/python"

docker compose down

if [ "$DEV" = true ]; then
  echo "    (dev mode - mounting live source files)"

  docker compose \
    -f docker-compose.yml \
    -f docker-compose.dev.yml \
    up -d --build
else
  docker compose \
    up -d --build
fi


# --------------------------------------------------
# Nginx
# --------------------------------------------------

echo "==> Nginx"

cd "$REPO/docker/nginx"

docker compose down
docker compose up -d


# --------------------------------------------------
# Static data permissions
# --------------------------------------------------

echo "==> Fixing static data directory permissions"

mkdir -p "$REPO/web/static/data"

sudo chown -R "$(whoami):$(whoami)" \
  "$REPO/web/static/data/"


# --------------------------------------------------
# Development seed data
# --------------------------------------------------

if [ "$DEV" = true ]; then
  echo "==> Copying seed aircraft.json (dev only)"

  cp \
    "$REPO/docs/DEV/aircraft_for_dev.json" \
    "$REPO/web/static/data/aircraft.json"
fi


# --------------------------------------------------
# Done
# --------------------------------------------------

echo ""
echo "======================================"
echo "   Done"
echo "======================================"

echo "==> Network status:"

docker network inspect adsb_net | grep Name