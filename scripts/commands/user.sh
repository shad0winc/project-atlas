#!/usr/bin/env bash

atlas_command_user() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.user_cli "$@"
}

atlas_command_users() {
  atlas_command_user list "$@"
}
