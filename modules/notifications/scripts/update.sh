#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"

module_id="notifications"
MODULE_DIR="$PROJECT_DIR/modules/$module_id"
MODULE_ENV_FILE="$MODULE_DIR/.env"
OPERATOR_ENV_FILE="$PROJECT_DIR/.env"

if [[ ! -f "$MODULE_ENV_FILE" || -L "$MODULE_ENV_FILE" ]]; then
  echo "ERROR: Notifications module environment must be a regular non-symlink file." >&2
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

for path in \
  /mnt/storage/configs/atlas/notifications \
  /mnt/storage/configs/atlas/notifications/logs
do
  if [[ ! -d "$path" ]]; then
    echo "ERROR: Required Notifications writable directory is missing: $path" >&2
    exit 1
  fi

  actual_uid="$(stat -c '%u' "$path")"
  actual_gid="$(stat -c '%g' "$path")"

  if [[ "$actual_uid" != "$puid" || "$actual_gid" != "$pgid" ]]; then
    echo "ERROR: Notifications runtime ownership precondition failed: $path" >&2
    echo "Expected UID:GID ${puid}:${pgid}; found ${actual_uid}:${actual_gid}." >&2
    echo "Refusing to recreate the non-root Notifications worker." >&2
    exit 1
  fi
done

event_log='/mnt/storage/configs/atlas/runtime/events.jsonl'
event_reader_gid='20000'
cursor='/mnt/storage/configs/atlas/runtime/subscribers/module-notifications.cursor'
filter='/mnt/storage/configs/atlas/runtime/subscribers/module-notifications.filter'

for path in "$event_log" "$cursor" "$filter"; do
  if [[ ! -f "$path" ]]; then
    echo "ERROR: Required Notifications Runtime Bus file is missing: $path" >&2
    exit 1
  fi
done

cursor_uid="$(stat -c '%u' "$cursor")"
cursor_gid="$(stat -c '%g' "$cursor")"

if [[ "$cursor_uid" != "$puid" || "$cursor_gid" != "$pgid" ]]; then
  echo "ERROR: Notifications cursor ownership precondition failed." >&2
  echo "Expected UID:GID ${puid}:${pgid}; found ${cursor_uid}:${cursor_gid}." >&2
  echo "Refusing to recreate the non-root Notifications worker." >&2
  exit 1
fi

if ! setpriv \
    --reuid="$puid" \
    --regid="$pgid" \
    --groups="$event_reader_gid" \
    test -r "$event_log"; then
  echo "ERROR: Notifications runtime identity cannot read the Runtime Bus event journal." >&2
  echo "Refusing to recreate the non-root Notifications worker." >&2
  exit 1
fi

if ! setpriv \
    --reuid="$puid" \
    --regid="$pgid" \
    --clear-groups \
    test -r "$filter"; then
  echo "ERROR: Notifications runtime identity cannot read its Runtime Bus filter." >&2
  echo "Refusing to recreate the non-root Notifications worker." >&2
  exit 1
fi

cd "$PROJECT_DIR"

echo "Updating Notifications module..."
echo

if ! docker compose \
    --env-file "$OPERATOR_ENV_FILE" \
    --project-name notifications \
    -f "$MODULE_DIR/docker-compose.yml" \
    config >/dev/null; then
  echo "Module Compose configuration is invalid."
  exit 1
fi

docker compose \
  --env-file "$OPERATOR_ENV_FILE" \
  --project-name notifications \
  -f "$MODULE_DIR/docker-compose.yml" \
  build

docker compose \
  --env-file "$OPERATOR_ENV_FILE" \
  --project-name notifications \
  -f "$MODULE_DIR/docker-compose.yml" \
  up -d

echo
echo "Notifications module update complete."
