#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"

source "$ATLAS_CONFIG_FILE"

mkdir -p "$ATLAS_CONFIG_ROOT/sportyfin"
mkdir -p "$ATLAS_MEDIA_ROOT/Sports"

echo "Sports module directories prepared."
echo "No services were started."
