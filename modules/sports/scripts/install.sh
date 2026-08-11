#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"
MODULE_ENV_FILE="$PROJECT_DIR/modules/sports/.env"

if [[ -L "$MODULE_ENV_FILE" ]]; then
  echo "ERROR: Sports module environment must not be a symbolic link." >&2
  exit 1
fi

if [[ -e "$MODULE_ENV_FILE" ]]; then
  if [[ ! -f "$MODULE_ENV_FILE" ]]; then
    echo "ERROR: Sports module environment must be a regular file." >&2
    exit 1
  fi

  chmod 0600 "$MODULE_ENV_FILE"
fi

source "$ATLAS_CONFIG_FILE"

mkdir -p \
  "$ATLAS_CONFIG_ROOT/sportyfin" \
  "$ATLAS_CONFIG_ROOT/sportyfin/input" \
  "$ATLAS_CONFIG_ROOT/sportyfin/output" \
  "$ATLAS_CONFIG_ROOT/sportyfin/logs" \
  "$ATLAS_CONFIG_ROOT/sportyfin/state" \
  "$ATLAS_CONFIG_ROOT/sportyfin/recordings" \
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
