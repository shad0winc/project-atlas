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

# Finish the current subscriber batch before exiting. Do not advance its cursor
# independently of the existing successful processing path.
stopping=0
sleep_pid=""
request_stop() {
  stopping=1
  if [[ -n "$sleep_pid" ]]; then
    kill -TERM "$sleep_pid" 2>/dev/null || true
  fi
}
trap request_stop TERM INT

while [[ "$stopping" == 0 ]]; do
  if ! atlas_event_subscriber_process \
      "$SUBSCRIBER" \
      "$PROCESSOR" >/dev/null; then
    echo "WARN Notifications processing failed; events remain pending." >&2
  fi

  [[ "$stopping" == 0 ]] || break
  touch "$WORKER_HEARTBEAT"

  sleep "$PROCESS_INTERVAL" &
  sleep_pid=$!
  if [[ "$stopping" == 1 ]]; then
    kill -TERM "$sleep_pid" 2>/dev/null || true
  fi
  if ! wait "$sleep_pid"; then
    [[ "$stopping" == 1 ]] || exit 1
  fi
  # Reap an interrupted sleep before the worker exits.
  wait "$sleep_pid" 2>/dev/null || true
  sleep_pid=""
done
exit 0
