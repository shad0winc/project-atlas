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
  local source="${3:-atlas}"

  if [[ -z "$event" ]]; then
    echo "Event name required"
    return 1
  fi

  if [[ -z "$payload" ]]; then
    payload='{}'
  fi

  atlas_event_initialize

  local timestamp
  timestamp="$(date --utc --iso-8601=seconds)"

  local event_id
  event_id="evt-$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"

  python3 - \
    "$event_id" \
    "$timestamp" \
    "$source" \
    "$event" \
    "$payload" >> "$ATLAS_EVENT_LOG" <<'PY'
import json
import sys

event_id = sys.argv[1]
timestamp = sys.argv[2]
source = sys.argv[3]
event = sys.argv[4]
payload_raw = sys.argv[5]

try:
    payload = json.loads(payload_raw)
except json.JSONDecodeError:
    payload = payload_raw

record = {
    "schema": 2,
    "id": event_id,
    "timestamp": timestamp,
    "source": source,
    "event": event,
    "payload": payload,
}

print(json.dumps(record, separators=(",", ":")))
PY

  atlas_ok "Event published: $event"
  echo "ID:   $event_id"
  echo "Source: $source"
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
