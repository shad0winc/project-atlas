#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"

if [[ ! -f "$ATLAS_CONFIG_FILE" ]]; then
  echo "Missing Atlas config: $ATLAS_CONFIG_FILE"
  exit 1
fi

source "$ATLAS_CONFIG_FILE"

module_id="__MODULE_ID__"

mkdir -p "$ATLAS_CONFIG_ROOT/$module_id"
mkdir -p "$ATLAS_STORAGE_ROOT/$module_id"

echo "$module_id module directories prepared."
echo "No services were started."
