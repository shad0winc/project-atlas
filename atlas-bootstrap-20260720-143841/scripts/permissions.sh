#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
mkdir -p "$DATA_DIR" "$DOWNLOADS" "$MEDIA" "$CONFIG" "$BACKUPS"
chown -R "${PUID}:${PGID}" "$DATA_DIR"
chmod -R u+rwX,g+rwX "$DATA_DIR"
echo "Permissions repaired."
