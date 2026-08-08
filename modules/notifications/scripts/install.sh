#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_ENV_FILE="$PROJECT_DIR/modules/notifications/.env"

if [[ -L "$MODULE_ENV_FILE" ]]; then
  echo "ERROR: Notifications module environment must not be a symbolic link." >&2
  exit 1
fi

if [[ -e "$MODULE_ENV_FILE" ]]; then
  if [[ ! -f "$MODULE_ENV_FILE" ]]; then
    echo "ERROR: Notifications module environment must be a regular file." >&2
    exit 1
  fi

  chmod 0600 "$MODULE_ENV_FILE"
fi

NOTIFICATIONS_ROOT="/mnt/storage/configs/atlas/notifications"
NOTIFICATIONS_LOG_DIR="$NOTIFICATIONS_ROOT/logs"

mkdir -p \
  "$NOTIFICATIONS_ROOT" \
  "$NOTIFICATIONS_LOG_DIR"

chmod 755 \
  "$NOTIFICATIONS_ROOT" \
  "$NOTIFICATIONS_LOG_DIR"

echo "Notifications module directories prepared."
echo "No services were started."
