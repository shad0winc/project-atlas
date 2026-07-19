#!/usr/bin/env bash

atlas_command_scheduler() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.scheduler_cli "$@"
}
