#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"

module_id="__MODULE_ID__"
MODULE_DIR="$PROJECT_DIR/modules/$module_id"

cd "$PROJECT_DIR"

echo "Updating $module_id module..."
echo

if ! docker compose -f "$MODULE_DIR/docker-compose.yml" config >/dev/null; then
  echo "Module Compose configuration is invalid."
  exit 1
fi

echo "No module services are currently defined."
echo "$module_id module update complete."
