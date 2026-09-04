#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_DIR="$PROJECT_DIR/modules/sports-backend"
MODULE_ENV_FILE="$MODULE_DIR/.env"
COMPOSE_FILE="$MODULE_DIR/docker-compose.yml"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[[ -f "$MODULE_ENV_FILE" && ! -L "$MODULE_ENV_FILE" ]] ||
    fail "Sports backend .env must be a regular non-symlink file."

chmod 600 "$MODULE_ENV_FILE"

for path in \
    /mnt/storage/configs/dispatcharr \
    /mnt/storage/configs/teamarr
do
    [[ -d "$path" ]] ||
        fail "Required persistent directory is missing: $path"
done

docker compose \
    --env-file "$MODULE_ENV_FILE" \
    -f "$COMPOSE_FILE" \
    pull

docker compose \
    --env-file "$MODULE_ENV_FILE" \
    -f "$COMPOSE_FILE" \
    up -d

"$MODULE_DIR/scripts/verify.sh"

echo 'Sports backend update complete.'
