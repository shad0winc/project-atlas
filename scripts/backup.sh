#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
stamp="$(date +%Y%m%d-%H%M%S)"
dest="$BACKUPS/project-atlas-configs-$stamp.tar.gz"
mkdir -p "$BACKUPS"
docker compose stop
tar -czf "$dest" -C "$DATA_DIR" configs
docker compose up -d
echo "$dest"
