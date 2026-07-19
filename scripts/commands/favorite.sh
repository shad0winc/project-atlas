#!/usr/bin/env bash

atlas_command_favorite() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.favorite_cli "$@"
}
