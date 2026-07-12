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
check "Module compose present" test -f "$MODULE_DIR/docker-compose.yml"
check "Module environment example present" test -f "$MODULE_DIR/.env.example"
check "Module install script present" test -x "$MODULE_DIR/scripts/install.sh"
check "Module uninstall script present" test -x "$MODULE_DIR/scripts/uninstall.sh"
check "Module update script present" test -x "$MODULE_DIR/scripts/update.sh"
check "Module compose valid" docker compose -f "$MODULE_DIR/docker-compose.yml" config

echo

if [[ "$pass" == true ]]; then
  echo "$module_name Status: PASS"
else
  echo "$module_name Status: FAIL"
  exit 1
fi
