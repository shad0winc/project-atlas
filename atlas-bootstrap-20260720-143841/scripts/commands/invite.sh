#!/usr/bin/env bash

atlas_command_invite() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.invitation_cli "$@"
}
