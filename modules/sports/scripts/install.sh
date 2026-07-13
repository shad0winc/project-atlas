#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"

source "$ATLAS_CONFIG_FILE"

mkdir -p \
  "$ATLAS_CONFIG_ROOT/sportyfin" \
  "$ATLAS_CONFIG_ROOT/sportyfin/input" \
  "$ATLAS_CONFIG_ROOT/sportyfin/output" \
  "$ATLAS_CONFIG_ROOT/sportyfin/logs" \
  "$ATLAS_CONFIG_ROOT/sportyfin/state" \
  "$ATLAS_MEDIA_ROOT/Sports"

chmod 755 \
  "$ATLAS_CONFIG_ROOT/sportyfin" \
  "$ATLAS_CONFIG_ROOT/sportyfin/input" \
  "$ATLAS_CONFIG_ROOT/sportyfin/output" \
  "$ATLAS_CONFIG_ROOT/sportyfin/logs" \
  "$ATLAS_CONFIG_ROOT/sportyfin/state" \
  "$ATLAS_MEDIA_ROOT/Sports"

echo "Sports module directories prepared."
echo "No services were started."
