#!/usr/bin/env bash

atlas_command_sustained_use() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.sustained_use.cli "$@"
}
