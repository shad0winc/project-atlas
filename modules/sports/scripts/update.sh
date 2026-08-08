#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_DIR="$PROJECT_DIR/modules/sports"
MODULE_ENV_FILE="$MODULE_DIR/.env"

if [[ ! -f "$MODULE_ENV_FILE" || -L "$MODULE_ENV_FILE" ]]; then
  echo "ERROR: Sports module environment must be a regular non-symlink file." >&2
  exit 1
fi

chmod 0600 "$MODULE_ENV_FILE"

cd "$PROJECT_DIR"

echo "Updating Sports module..."
echo

docker compose \
  -f "$MODULE_DIR/docker-compose.yml" \
  pull

docker compose \
  -f "$MODULE_DIR/docker-compose.yml" \
  build

docker compose \
  -f "$MODULE_DIR/docker-compose.yml" \
  up -d \
  --remove-orphans

echo
echo "Sports module update complete."
