#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_DIR="$PROJECT_DIR/modules/sports"

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
