#!/usr/bin/env bash

atlas_command_retention() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.retention_cli "$@"
}
