#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"
MODULE_ENV_FILE="$PROJECT_DIR/modules/sports/.env"
OPERATOR_ENV_FILE="$PROJECT_DIR/.env"

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

if [[ ! -f "$OPERATOR_ENV_FILE" || -L "$OPERATOR_ENV_FILE" ]]; then
  echo "ERROR: Atlas operator environment must be a regular non-symlink file." >&2
  exit 1
fi

puid="$(sed -n 's/^PUID=//p' "$OPERATOR_ENV_FILE" | tail -1)"
pgid="$(sed -n 's/^PGID=//p' "$OPERATOR_ENV_FILE" | tail -1)"

if [[ ! "$puid" =~ ^[0-9]+$ || ! "$pgid" =~ ^[0-9]+$ ]]; then
  echo "ERROR: Numeric PUID and PGID are required in the Atlas operator environment." >&2
  exit 1
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

required_writable_paths=(
  "$ATLAS_CONFIG_ROOT/sportyfin/input"
  "$ATLAS_CONFIG_ROOT/sportyfin/output"
  "$ATLAS_CONFIG_ROOT/sportyfin/logs"
  "$ATLAS_CONFIG_ROOT/sportyfin/state"
  "$ATLAS_CONFIG_ROOT/sportyfin/recordings"
  "$ATLAS_MEDIA_ROOT/Sports"
)

chown "$puid:$pgid" "${required_writable_paths[@]}"

chmod 755 \
  "$ATLAS_CONFIG_ROOT/sportyfin" \
  "${required_writable_paths[@]}"

for path in "${required_writable_paths[@]}"; do
  actual_uid="$(stat -c '%u' "$path")"
  actual_gid="$(stat -c '%g' "$path")"

  if [[ "$actual_uid" != "$puid" || "$actual_gid" != "$pgid" ]]; then
    echo "ERROR: Sports runtime ownership installation failed: $path" >&2
    echo "Expected UID:GID ${puid}:${pgid}; found ${actual_uid}:${actual_gid}." >&2
    exit 1
  fi
done

echo "Sports module directories prepared."
echo "Sports runtime ownership prepared for UID:GID ${puid}:${pgid}."
echo "No services were started."
