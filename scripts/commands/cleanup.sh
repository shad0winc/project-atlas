#!/usr/bin/env bash

atlas_command_cleanup() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.cleanup_cli "$@"
}
