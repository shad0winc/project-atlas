#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"

source "$ATLAS_CONFIG_FILE"

pass=true

check() {
  label="$1"
  shift

  if "$@" >/dev/null 2>&1; then
    echo "OK   $label"
  else
    echo "FAIL $label"
    pass=false
  fi
}

echo "Sports Module Verification"
echo

check "Module directory present" test -d "$ATLAS_PROJECT_DIR/modules/sports"
check "Module README present" test -f "$ATLAS_PROJECT_DIR/modules/sports/README.md"
check "Module compose present" test -f "$ATLAS_PROJECT_DIR/modules/sports/docker-compose.yml"
check "Runtime config directory present" test -d "$ATLAS_CONFIG_ROOT/sportyfin"
check "Sports input directory present" test -d "$ATLAS_CONFIG_ROOT/sportyfin/input"
check "Sports output directory present" test -d "$ATLAS_CONFIG_ROOT/sportyfin/output"
check "Sports logs directory present" test -d "$ATLAS_CONFIG_ROOT/sportyfin/logs"
check "Sports state directory present" test -d "$ATLAS_CONFIG_ROOT/sportyfin/state"
check "Sports media directory present" test -d "$ATLAS_MEDIA_ROOT/Sports"
check "Module compose valid" docker compose -f "$ATLAS_PROJECT_DIR/modules/sports/docker-compose.yml" config
check "Module metadata present" test -f "$ATLAS_PROJECT_DIR/modules/sports/module.conf"
check "Module environment example present" test -f "$ATLAS_PROJECT_DIR/modules/sports/.env.example"
check "Module update script present" test -x "$ATLAS_PROJECT_DIR/modules/sports/scripts/update.sh"

check "Sports feed container running" \
  sh -c "[ \"$(docker inspect --format '{{.State.Running}}' atlas-sports-feed 2>/dev/null)\" = true ]"

check "Sports feed container healthy" \
  sh -c "[ \"$(docker inspect --format '{{.State.Health.Status}}' atlas-sports-feed 2>/dev/null)\" = healthy ]"

check "Sports controller container running" \
  sh -c "[ \"$(docker inspect --format '{{.State.Running}}' atlas-sports-controller 2>/dev/null)\" = true ]"

check "Sports controller container healthy" \
  sh -c "[ \"$(docker inspect --format '{{.State.Health.Status}}' atlas-sports-controller 2>/dev/null)\" = healthy ]"

check "Sports controller heartbeat fresh" \
  sh -c '
    heartbeat="/mnt/storage/configs/sportyfin/state/controller-heartbeat"

    test -f "$heartbeat" \
      && test $(( $(date +%s) - $(stat -c %Y "$heartbeat") )) -lt 90
  '

check "Sports provider health available" \
  test -f "$ATLAS_CONFIG_ROOT/sportyfin/state/provider-health.json"

check "Sports provider healthy" \
  sh -c '
    jq -e "
      to_entries
      | length > 0
      and all(.value.status == \"healthy\")
    " /mnt/storage/configs/sportyfin/state/provider-health.json
  '

check "Sports visibility policy valid" \
  sh -c '
    cd /opt/project-atlas

    PYTHONPATH=modules/sports/src python3 - <<'"'"'PY'"'"'
from datetime import datetime, timezone

from lifecycle import should_surface_game


now = datetime(
    2026,
    7,
    13,
    18,
    0,
    tzinfo=timezone.utc,
)

checks = [
    not should_surface_game(
        {
            "lifecycle_state": "scheduled",
            "start_at": "2026-07-13T20:00:00+00:00",
        },
        now,
        pregame_minutes=60,
    ),
    should_surface_game(
        {
            "lifecycle_state": "scheduled",
            "start_at": "2026-07-13T18:45:00+00:00",
        },
        now,
        pregame_minutes=60,
    ),
    should_surface_game(
        {
            "lifecycle_state": "live",
        },
        now,
        pregame_minutes=60,
    ),
    should_surface_game(
        {
            "lifecycle_state": "grace",
        },
        now,
        pregame_minutes=60,
    ),
    not should_surface_game(
        {
            "lifecycle_state": "finished",
        },
        now,
        pregame_minutes=60,
    ),
]

raise SystemExit(
    0 if all(checks) else 1
)
PY
  '

check "Sports subscription resolver valid" \
  sh -c '
    cd /opt/project-atlas

    PYTHONPATH=modules/sports/src python3 - <<'"'"'PY'"'"'
from resolver import resolve_subscribed_games


game = {
    "id": "resolver-verification-game",
    "provider": "thesportsdb",
    "provider_event_id": "resolver-event",
    "provider_league_id": "resolver-league",
    "home_team_id": "resolver-team",
    "away_team_id": "resolver-opponent",
    "name": "Atlas Resolver Verification",
}

subscriptions = [
    {
        "subscription_id": "sub-team",
        "type": "team",
        "provider": "thesportsdb",
        "id": "resolver-team",
        "user": "michael",
    },
    {
        "subscription_id": "sub-league",
        "type": "league",
        "provider": "thesportsdb",
        "id": "resolver-league",
        "user": "test-user",
    },
    {
        "subscription_id": "sub-event",
        "type": "event",
        "provider": "thesportsdb",
        "id": "resolver-event",
        "user": "michael",
    },
]

resolved = resolve_subscribed_games(
    [game],
    subscriptions,
)

if len(resolved) != 1:
    raise SystemExit(1)

resolved_game = resolved[0]

checks = [
    resolved_game.get("subscription_count") == 3,
    resolved_game.get("subscription_types")
    == ["event", "league", "team"],
    resolved_game.get("subscribed_users")
    == ["michael", "test-user"],
    resolved_game.get("subscription_ids")
    == ["sub-event", "sub-league", "sub-team"],
]

raise SystemExit(
    0 if all(checks) else 1
)
PY
  '

check "Sports recording scheduler valid" \
  sh -c '
    cd /opt/project-atlas

    test_file="/tmp/atlas-sports-recording-verify.json"

    rm -f "$test_file"

    SPORTS_RECORDINGS_FILE="$test_file" \
    PYTHONPATH=modules/sports/src \
    python3 - <<'"'"'PY'"'"'
from datetime import datetime, timezone

from recordings import (
    plan_recordings,
    update_recording_statuses,
)


game = {
    "id": "recording-verification",
    "provider": "thesportsdb",
    "provider_event_id": "recording-verification-event",
    "name": "Atlas Recording Verification",
    "league": "NFL",
    "home_team": "Kansas City Chiefs",
    "away_team": "Los Angeles Rams",
    "start_at": "2026-08-15T20:00:00+00:00",
    "duration_minutes": 240,
    "stream_url": "http://example.invalid/recording-verification.m3u8",
    "subscription_count": 3,
    "subscription_ids": [
        "sub-event",
        "sub-league",
        "sub-team",
    ],
    "subscribed_users": [
        "michael",
    ],
}

plan_recordings([game])

tests = [
    (
        datetime(
            2026,
            8,
            15,
            19,
            50,
            tzinfo=timezone.utc,
        ),
        "pending",
    ),
    (
        datetime(
            2026,
            8,
            15,
            19,
            55,
            tzinfo=timezone.utc,
        ),
        "recording",
    ),
    (
        datetime(
            2026,
            8,
            16,
            0,
            15,
            tzinfo=timezone.utc,
        ),
        "completed",
    ),
]

for now, expected_status in tests:
    recordings = update_recording_statuses(
        now
    )

    recording = recordings[
        "recording-recording-verification"
    ]

    if recording.get("status") != expected_status:
        raise SystemExit(1)

recording = recordings[
    "recording-recording-verification"
]

checks = [
    recording.get("started_at")
    == "2026-08-15T19:55:00+00:00",
    recording.get("completed_at")
    == "2026-08-16T00:15:00+00:00",
    recording.get("subscription_count") == 3,
    recording.get("subscribed_users")
    == ["michael"],
]

raise SystemExit(
    0 if all(checks) else 1
)
PY

    result=$?

    rm -f "$test_file"

    exit "$result"
  '

check "Sports health endpoint reachable" \
  curl -fsS http://127.0.0.1:8097/health

check "Sports structured health endpoint valid" \
  sh -c '
    curl -fsS http://127.0.0.1:8097/health.json \
      | jq -e "
          .status == \"healthy\"
          and .controller.status == \"healthy\"
          and .providers.status == \"healthy\"
          and .recorder.status == \"healthy\"
          and .recordings.status == \"healthy\"
          and .storage.status == \"healthy\"
        "
  '

check "Jellyfin can reach Sports health report" \
  sh -c '
    docker exec jellyfin \
      curl -fsS http://atlas-sports-feed:8080/health.json \
      | jq -e ".status == \"healthy\""
  '

check "Sports M3U feed reachable" \
  curl -fsS http://127.0.0.1:8097/sports.m3u

check "Sports XMLTV feed reachable" \
  curl -fsS http://127.0.0.1:8097/sports.xml

check "Jellyfin can reach Sports feed" \
  docker exec jellyfin curl -fsS http://atlas-sports-feed:8080/health

echo

if [ "$pass" = true ]; then
  echo "Sports Module Status: PASS"
else
  echo "Sports Module Status: FAIL"
  exit 1
fi
