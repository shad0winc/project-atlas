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
  printf '*\n' > "$(atlas_event_subscriber_filter_file "$subscriber")"

  atlas_ok "Subscriber registered: $subscriber"
}

atlas_event_subscriber_list() {
  atlas_event_initialize

  local subscriber_dir
  local found=0
  local cursor=""
  local subscriber=""
  local position=""
  local filter=""

  subscriber_dir="$(atlas_event_subscriber_dir)"

  mkdir -p "$subscriber_dir"

  for cursor in "$subscriber_dir"/*.cursor; do
    [[ -f "$cursor" ]] || continue

    found=1
    subscriber="$(basename "$cursor" .cursor)"
    position="$(cat "$cursor")"
    filter="$(atlas_event_subscriber_get_filter "$subscriber")"

    printf '%-20s cursor=%-8s filter=%s\n' \
      "$subscriber" \
      "$position" \
      "$filter"
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
  local filter

  filter="$(atlas_event_subscriber_get_filter "$subscriber")"

  cursor="$(atlas_event_subscriber_cursor "$subscriber")"
  position="$(cat "$cursor")"
  event_count="$(wc -l < "$ATLAS_EVENT_LOG")"

  if (( position >= event_count )); then
    echo "No pending events."
    return 0
  fi

  tail -n "+$((position + 1))" "$ATLAS_EVENT_LOG" \
    | atlas_event_filter_stream "$filter"
}

atlas_event_subscriber_consume() {
  local subscriber="${1:-}"

  if ! atlas_event_subscriber_exists "$subscriber"; then
    atlas_fail "Unknown subscriber: $subscriber"
    return 1
  fi

  local cursor=""
  local current_position=""
  local event_count=""
  local filter=""

  cursor="$(atlas_event_subscriber_cursor "$subscriber")"
  current_position="$(cat "$cursor")"
  event_count="$(wc -l < "$ATLAS_EVENT_LOG")"
  filter="$(atlas_event_subscriber_get_filter "$subscriber")"

  if (( current_position >= event_count )); then
    echo "No pending events."
    return 0
  fi

  tail -n "+$((current_position + 1))" "$ATLAS_EVENT_LOG" \
    | atlas_event_filter_stream "$filter"

  printf '%s\n' "$event_count" > "$cursor"
}

atlas_event_subscriber_filter_file() {
  local subscriber="$1"
  printf '%s/%s.filter\n' "$(atlas_event_subscriber_dir)" "$subscriber"
}

atlas_event_subscriber_filter() {
  local subscriber="${1:-}"
  local filter="${2:-}"

  if ! atlas_event_subscriber_exists "$subscriber"; then
    atlas_fail "Unknown subscriber: $subscriber"
    return 1
  fi

  local filter_file
  filter_file="$(atlas_event_subscriber_filter_file "$subscriber")"

  if [[ -z "$filter" ]]; then
    filter='*'
  fi

  printf '%s\n' "$filter" > "$filter_file"

  atlas_ok "Subscriber filter updated: $subscriber"
  echo "Filter: $filter"
}

atlas_event_subscriber_get_filter() {
  local subscriber="$1"
  local filter_file

  filter_file="$(atlas_event_subscriber_filter_file "$subscriber")"

  if [[ -f "$filter_file" ]]; then
    cat "$filter_file"
  else
    printf '*\n'
  fi
}

atlas_event_filter_stream() {
  local filter="${1:-*}"

  python3 -c '
import fnmatch
import json
import sys

patterns = sys.argv[1].split("|")

for line in sys.stdin:
    line = line.rstrip("\n")

    if not line:
        continue

    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        continue

    event = record.get("event", "")

    if any(fnmatch.fnmatchcase(event, pattern) for pattern in patterns):
        print(line)
' "$filter"
}
