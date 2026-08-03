#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"

module_id="notifications"
module_name="Atlas Notifications"
MODULE_DIR="$PROJECT_DIR/modules/$module_id"

if [[ ! -f "$ATLAS_CONFIG_FILE" ]]; then
  echo "Missing Atlas config: $ATLAS_CONFIG_FILE"
  exit 1
fi

source "$ATLAS_CONFIG_FILE"

pass=true

check() {
  local label="$1"
  shift

  if "$@" >/dev/null 2>&1; then
    echo "OK   $label"
  else
    echo "FAIL $label"
    pass=false
  fi
}

echo "$module_name Verification"
echo

check "Module directory present" test -d "$MODULE_DIR"
check "Module metadata present" test -f "$MODULE_DIR/module.conf"
check "Module README present" test -f "$MODULE_DIR/README.md"
check "Request notification documentation present" \
  grep -Fq "request.*" "$MODULE_DIR/README.md"
check "Ready to Watch documentation present" \
  grep -Fq "Ready to Watch" "$MODULE_DIR/README.md"
check "Request routing documentation present" \
  grep -Fq "anime_movie" "$MODULE_DIR/README.md"
check "Module compose present" test -f "$MODULE_DIR/docker-compose.yml"
check "Module environment example present" test -f "$MODULE_DIR/.env.example"
check "Module install script present" test -x "$MODULE_DIR/scripts/install.sh"
check "Module uninstall script present" test -x "$MODULE_DIR/scripts/uninstall.sh"
check "Module update script present" test -x "$MODULE_DIR/scripts/update.sh"
check "Module compose valid" docker compose -f "$MODULE_DIR/docker-compose.yml" config

check "Sports audience notification formatting valid" \
  sh -c '
    cd /opt/project-atlas

    PYTHONPATH=modules/notifications/src python3 - <<'"'"'PY'"'"'
from formatter import notification_fields
from processor import build_notification


event = {
    "id": "evt-audience-verification",
    "event": "sports.game-started",
    "source": "sports",
    "payload": {
        "game_id": "audience-verification-game",
        "game": "Atlas Audience Verification",
        "status": "started",
        "subscription_count": 3,
        "subscription_types": [
            "event",
            "league",
            "team",
        ],
        "subscribed_users": [
            "michael",
            "test-user",
        ],
        "subscription_ids": [
            "sub-event",
            "sub-league",
            "sub-team",
        ],
    },
}

notification = build_notification(event)

fields = {
    field["name"]: field["value"]
    for field in notification_fields(notification)
}

checks = [
    fields.get("Game")
    == "Atlas Audience Verification",
    fields.get("Followers")
    == "michael, test-user",
    fields.get("Subscription Matches")
    == "3",
    fields.get("Matched By")
    == "event, league, team",
]

raise SystemExit(
    0 if all(checks) else 1
)
PY
  '

check "Media request notification integration valid" \
  sh -c '
    cd /opt/project-atlas

    PYTHONPATH=modules/notifications/src python3 - <<'"'"'PYVERIFY'"'"'
from formatter import (
    notification_description,
    notification_fields,
    notification_route,
    notification_title,
)
from processor import build_notification


event = {
    "id": "evt-request-verification",
    "event": "request.available",
    "source": "media-requests",
    "payload": {
        "request_id": "req-verification",
        "user_id": "user-verification",
        "provider": "jellyseerr",
        "provider_request_id": "42",
        "provider_media_id": "550",
        "media_type": "anime_tv",
        "title": "Atlas Request Verification",
        "year": 2026,
        "season_number": 1,
        "status": "available",
        "terminal": True,
        "available_at": "2026-08-03T04:00:00Z",
        "occurred_at": "2026-08-03T04:00:00Z",
        "context": None,
        "metadata": {},
    },
}

notification = build_notification(event)

fields = {
    field["name"]: field["value"]
    for field in notification_fields(notification)
}

checks = [
    notification["severity"] == "success",
    notification_route(notification) == "anime_tv",
    notification_title(notification) == "Ready to Watch",
    notification_description(notification)
    == (
        "Atlas Request Verification (2026) "
        "is ready to watch."
    ),
    fields.get("Media") == "Atlas Request Verification",
    fields.get("Type") == "Anime Tv",
    fields.get("Status") == "Available",
    fields.get("Request ID") == "req-verification",
]

raise SystemExit(
    0 if all(checks) else 1
)
PYVERIFY
  '

echo

if [[ "$pass" == true ]]; then
  echo "$module_name Status: PASS"
else
  echo "$module_name Status: FAIL"
  exit 1
fi
