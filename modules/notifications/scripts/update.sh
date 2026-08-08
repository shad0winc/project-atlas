#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"

module_id="notifications"
MODULE_DIR="$PROJECT_DIR/modules/$module_id"
MODULE_ENV_FILE="$MODULE_DIR/.env"

if [[ ! -f "$MODULE_ENV_FILE" || -L "$MODULE_ENV_FILE" ]]; then
  echo "ERROR: Notifications module environment must be a regular non-symlink file." >&2
  exit 1
fi

chmod 0600 "$MODULE_ENV_FILE"

cd "$PROJECT_DIR"

echo "Updating Notifications module..."
echo

if ! docker compose \
    -f "$MODULE_DIR/docker-compose.yml" \
    config >/dev/null; then
  echo "Module Compose configuration is invalid."
  exit 1
fi

docker compose \
  -f "$MODULE_DIR/docker-compose.yml" \
  build

docker compose \
  -f "$MODULE_DIR/docker-compose.yml" \
  up -d

echo
echo "Notifications module update complete."
