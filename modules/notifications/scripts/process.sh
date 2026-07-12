#!/usr/bin/env bash
set -euo pipefail

ATLAS_PROJECT_DIR="/opt/project-atlas"
ATLAS_CLI_ROOT="$ATLAS_PROJECT_DIR/scripts"

# shellcheck disable=SC1091
source "$ATLAS_CLI_ROOT/lib/common.sh"

atlas_initialize

SUBSCRIBER="module-notifications"
PROCESSOR="$ATLAS_PROJECT_DIR/modules/notifications/src/processor.py"

if [[ ! -x "$PROCESSOR" ]]; then
  atlas_fail "Notifications processor unavailable: $PROCESSOR"
  exit 1
fi

atlas_event_subscriber_process \
  "$SUBSCRIBER" \
  "$PROCESSOR"
