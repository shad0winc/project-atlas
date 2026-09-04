#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_DIR="$PROJECT_DIR/modules/sports-backend"
MODULE_ENV_FILE="$MODULE_DIR/.env"
EXAMPLE_ENV_FILE="$MODULE_DIR/.env.example"
COMPOSE_FILE="$MODULE_DIR/docker-compose.yml"

if [[ -f "$MODULE_ENV_FILE" && ! -L "$MODULE_ENV_FILE" ]]; then
    env_file="$MODULE_ENV_FILE"
else
    env_file="$EXAMPLE_ENV_FILE"
fi

docker compose \
    --env-file "$env_file" \
    -f "$COMPOSE_FILE" \
    down

echo 'Sports backend containers removed.'
echo 'Persistent state was preserved:'
echo '  /mnt/storage/configs/dispatcharr'
echo '  /mnt/storage/configs/teamarr'
