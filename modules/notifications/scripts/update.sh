#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"

module_id="notifications"
MODULE_DIR="$PROJECT_DIR/modules/$module_id"

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
