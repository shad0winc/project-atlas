#!/usr/bin/env bash

atlas_command_favorite() {
  ATLAS_JELLYFIN_URL="${ATLAS_JELLYFIN_URL:-http://127.0.0.1:8096}" \
    ATLAS_JELLYFIN_API_KEY="${ATLAS_JELLYFIN_API_KEY:-}" \
    PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.favorite_cli "$@"
}
