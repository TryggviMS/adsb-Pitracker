#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/media/trygg/tryggvi_flakkari/adsb_backups"
DB_CONTAINER="postgis_db"
DB_NAME="spatial_db"
DB_USER="admin"
KEEP_DAYS=30

# Ensure drive is mounted
if ! mountpoint -q "$(dirname "$BACKUP_DIR")"; then
  echo "[ERROR] Drive not mounted at $(dirname "$BACKUP_DIR")"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

DATE="$(date +%F)"
OUT="$BACKUP_DIR/adsb_${DATE}.dump"
TMP="$OUT.tmp"

echo "[INFO] Creating backup: $OUT"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$TMP"

# basic sanity: non-empty file
if [ ! -s "$TMP" ]; then
  echo "[ERROR] Backup file is empty: $TMP"
  rm -f "$TMP"
  exit 1
fi

mv "$TMP" "$OUT"
chmod 600 "$OUT"

echo "[INFO] Rotating backups older than ${KEEP_DAYS} days"
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +"$KEEP_DAYS" -print -delete

echo "[INFO] Done. Latest:"
ls -lh "$OUT"
