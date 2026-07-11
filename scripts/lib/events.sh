#!/usr/bin/env bash

ATLAS_EVENT_DIR="${ATLAS_EVENT_DIR:-/mnt/storage/configs/atlas/runtime}"
ATLAS_EVENT_LOG="${ATLAS_EVENT_LOG:-$ATLAS_EVENT_DIR/events.jsonl}"

atlas_event_initialize() {
  mkdir -p "$ATLAS_EVENT_DIR"
  touch "$ATLAS_EVENT_LOG"
}

atlas_event_publish() {
  local event="${1:-}"
  local payload="${2:-}"

  if [[ -z "$payload" ]]; then
    payload='{}'
  fi

  if [[ -z "$event" ]]; then
    echo "Event name required"
    return 1
  fi

  atlas_event_initialize

  local timestamp
  timestamp="$(date --utc --iso-8601=seconds)"

  python3 - "$timestamp" "$event" "$payload" >> "$ATLAS_EVENT_LOG" <<'PY'
import json
import sys

timestamp = sys.argv[1]
event = sys.argv[2]
payload_raw = sys.argv[3]

try:
    payload = json.loads(payload_raw)
except json.JSONDecodeError:
    payload = payload_raw

record = {
    "timestamp": timestamp,
    "event": event,
    "payload": payload,
}

print(json.dumps(record, separators=(",", ":")))
PY

  atlas_ok "Event published: $event"
}

atlas_event_list() {
  atlas_event_initialize

  if [[ ! -s "$ATLAS_EVENT_LOG" ]]; then
    echo "No events recorded."
    return 0
  fi

  cat "$ATLAS_EVENT_LOG"
}

atlas_event_tail() {
  atlas_event_initialize
  tail -n 20 "$ATLAS_EVENT_LOG"
}
