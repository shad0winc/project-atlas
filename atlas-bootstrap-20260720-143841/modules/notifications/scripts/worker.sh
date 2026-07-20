#!/usr/bin/env bash
set -euo pipefail

ATLAS_PROJECT_DIR="/opt/project-atlas"
ATLAS_CLI_ROOT="$ATLAS_PROJECT_DIR/scripts"

SUBSCRIBER="module-notifications"
PROCESSOR="$ATLAS_PROJECT_DIR/modules/notifications/src/processor.py"

WORKER_STATE_DIR="/mnt/storage/configs/atlas/notifications"
WORKER_HEARTBEAT="$WORKER_STATE_DIR/worker-heartbeat"

PROCESS_INTERVAL="${ATLAS_NOTIFICATIONS_INTERVAL:-5}"

# shellcheck disable=SC1091
source "$ATLAS_CLI_ROOT/lib/common.sh"

atlas_initialize

mkdir -p "$WORKER_STATE_DIR"

echo "Atlas Notifications Worker"
echo "Subscriber: $SUBSCRIBER"
echo "Interval:   ${PROCESS_INTERVAL}s"
echo

while true; do
  if ! atlas_event_subscriber_process \
      "$SUBSCRIBER" \
      "$PROCESSOR" >/dev/null; then
    echo "WARN Notifications processing failed; events remain pending." >&2
  fi

  touch "$WORKER_HEARTBEAT"

  sleep "$PROCESS_INTERVAL"
done
