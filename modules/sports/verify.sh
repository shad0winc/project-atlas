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
check "Sports media directory present" test -d "$ATLAS_MEDIA_ROOT/Sports"
check "Module compose valid" docker compose -f "$ATLAS_PROJECT_DIR/modules/sports/docker-compose.yml" config

echo

if [ "$pass" = true ]; then
  echo "Sports Module Status: PASS"
else
  echo "Sports Module Status: FAIL"
  exit 1
fi
