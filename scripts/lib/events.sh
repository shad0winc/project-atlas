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

atlas_event_subscriber_dir() {
  printf '%s/subscribers\n' "$ATLAS_EVENT_DIR"
}

atlas_event_subscriber_cursor() {
  local subscriber="$1"
  printf '%s/%s.cursor\n' "$(atlas_event_subscriber_dir)" "$subscriber"
}

atlas_event_subscriber_exists() {
  local subscriber="$1"
  local cursor

  cursor="$(atlas_event_subscriber_cursor "$subscriber")"

  [[ -f "$cursor" ]]
}

atlas_event_subscriber_register() {
  local subscriber="${1:-}"

  if [[ -z "$subscriber" ]]; then
    echo "Subscriber name required"
    return 1
  fi

  if [[ ! "$subscriber" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    atlas_fail "Invalid subscriber name: $subscriber"
    return 1
  fi

  atlas_event_initialize
  mkdir -p "$(atlas_event_subscriber_dir)"

  local cursor
  cursor="$(atlas_event_subscriber_cursor "$subscriber")"

  if [[ -f "$cursor" ]]; then
    atlas_warn "Subscriber already registered: $subscriber"
    return 0
  fi

  printf '0\n' > "$cursor"

  atlas_ok "Subscriber registered: $subscriber"
}

atlas_event_subscriber_list() {
  atlas_event_initialize

  local subscriber_dir
  subscriber_dir="$(atlas_event_subscriber_dir)"

  mkdir -p "$subscriber_dir"

  local found=0
  local cursor
  local subscriber
  local position

  for cursor in "$subscriber_dir"/*.cursor; do
    [[ -f "$cursor" ]] || continue

    found=1
    subscriber="$(basename "$cursor" .cursor)"
    position="$(cat "$cursor")"

    printf '%-20s cursor=%s\n' "$subscriber" "$position"
  done

  if [[ "$found" -eq 0 ]]; then
    echo "No subscribers registered."
  fi
}

atlas_event_subscriber_pending() {
  local subscriber="${1:-}"

  if ! atlas_event_subscriber_exists "$subscriber"; then
    atlas_fail "Unknown subscriber: $subscriber"
    return 1
  fi

  local cursor
  local position
  local event_count

  cursor="$(atlas_event_subscriber_cursor "$subscriber")"
  position="$(cat "$cursor")"
  event_count="$(wc -l < "$ATLAS_EVENT_LOG")"

  if (( position >= event_count )); then
    echo "No pending events."
    return 0
  fi

  tail -n "+$((position + 1))" "$ATLAS_EVENT_LOG"
}

atlas_event_subscriber_consume() {
  local subscriber="${1:-}"

  if ! atlas_event_subscriber_exists "$subscriber"; then
    atlas_fail "Unknown subscriber: $subscriber"
    return 1
  fi

  local cursor
  local current_position
  local event_count

  cursor="$(atlas_event_subscriber_cursor "$subscriber")"
  current_position="$(cat "$cursor")"
  event_count="$(wc -l < "$ATLAS_EVENT_LOG")"

  if (( current_position >= event_count )); then
    echo "No pending events."
    return 0
  fi

  tail -n "+$((current_position + 1))" "$ATLAS_EVENT_LOG"

  printf '%s\n' "$event_count" > "$cursor"
}
