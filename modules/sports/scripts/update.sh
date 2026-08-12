#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_DIR="$PROJECT_DIR/modules/sports"
MODULE_ENV_FILE="$MODULE_DIR/.env"
OPERATOR_ENV_FILE="$PROJECT_DIR/.env"

if [[ ! -f "$MODULE_ENV_FILE" || -L "$MODULE_ENV_FILE" ]]; then
  echo "ERROR: Sports module environment must be a regular non-symlink file." >&2
  exit 1
fi

if [[ ! -f "$OPERATOR_ENV_FILE" || -L "$OPERATOR_ENV_FILE" ]]; then
  echo "ERROR: Atlas operator environment must be a regular non-symlink file." >&2
  exit 1
fi

chmod 0600 "$MODULE_ENV_FILE"

puid="$(sed -n 's/^PUID=//p' "$OPERATOR_ENV_FILE" | tail -1)"
pgid="$(sed -n 's/^PGID=//p' "$OPERATOR_ENV_FILE" | tail -1)"

if [[ ! "$puid" =~ ^[0-9]+$ || ! "$pgid" =~ ^[0-9]+$ ]]; then
  echo "ERROR: Numeric PUID and PGID are required in the Atlas operator environment." >&2
  exit 1
fi

required_writable_paths=(
  /mnt/storage/configs/sportyfin/input
  /mnt/storage/configs/sportyfin/output
  /mnt/storage/configs/sportyfin/logs
  /mnt/storage/configs/sportyfin/state
  /mnt/storage/configs/sportyfin/recordings
  /mnt/storage/media/Sports
)

for path in "${required_writable_paths[@]}"; do
  if [[ ! -d "$path" ]]; then
    echo "ERROR: Required Sports writable directory is missing: $path" >&2
    exit 1
  fi

  actual_uid="$(stat -c '%u' "$path")"
  actual_gid="$(stat -c '%g' "$path")"

  if [[ "$actual_uid" != "$puid" || "$actual_gid" != "$pgid" ]]; then
    echo "ERROR: Sports runtime ownership precondition failed: $path" >&2
    echo "Expected UID:GID ${puid}:${pgid}; found ${actual_uid}:${actual_gid}." >&2
    echo "Refusing to recreate the non-root Sports controller." >&2
    exit 1
  fi
done

cd "$PROJECT_DIR"

echo "Updating Sports module..."
echo

docker compose \
  --env-file "$OPERATOR_ENV_FILE" \
  --project-name sports \
  -f "$MODULE_DIR/docker-compose.yml" \
  pull

docker compose \
  --env-file "$OPERATOR_ENV_FILE" \
  --project-name sports \
  -f "$MODULE_DIR/docker-compose.yml" \
  build

docker compose \
  --env-file "$OPERATOR_ENV_FILE" \
  --project-name sports \
  -f "$MODULE_DIR/docker-compose.yml" \
  up -d

echo
echo "Sports module update complete."
