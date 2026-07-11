#!/usr/bin/env bash

ATLAS_CLI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ATLAS_PROJECT_DIR="$(cd "$ATLAS_CLI_ROOT/.." && pwd)"

# shellcheck disable=SC1091
source "$ATLAS_CLI_ROOT/lib/config.sh"

# shellcheck disable=SC1091
source "$ATLAS_CLI_ROOT/lib/output.sh"

atlas_initialize() {
  atlas_load_config
  cd "$ATLAS_PROJECT_DIR"
}
