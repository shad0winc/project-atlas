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
check "Sports media directory present" test -d "$ATLAS_MEDIA_ROOT/Sports"
check "Module compose valid" docker compose -f "$ATLAS_PROJECT_DIR/modules/sports/docker-compose.yml" config
check "Module metadata present" test -f "$ATLAS_PROJECT_DIR/modules/sports/module.conf"
check "Module environment example present" test -f "$ATLAS_PROJECT_DIR/modules/sports/.env.example"
check "Module update script present" test -x "$ATLAS_PROJECT_DIR/modules/sports/scripts/update.sh"
check "Sports feed container running" \
  docker inspect --format '{{.State.Running}}' atlas-sports-feed

check "Sports feed container healthy" \
  sh -c "[ \"$(docker inspect --format '{{.State.Health.Status}}' atlas-sports-feed 2>/dev/null)\" = healthy ]"

check "Sports health endpoint reachable" \
  curl -fsS http://127.0.0.1:8097/health

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
