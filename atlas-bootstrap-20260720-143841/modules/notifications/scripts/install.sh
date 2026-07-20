#!/usr/bin/env bash
set -euo pipefail

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
