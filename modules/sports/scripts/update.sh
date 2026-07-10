#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_DIR="$PROJECT_DIR/modules/sports"

cd "$PROJECT_DIR"

echo "Updating Sports module..."
echo

docker compose \
  -f docker-compose.yml \
  -f docker-compose.sports.yml \
  pull atlas-sports-feed

docker compose \
  -f docker-compose.yml \
  -f docker-compose.sports.yml \
  up -d atlas-sports-feed

echo
echo "Sports module update complete."
