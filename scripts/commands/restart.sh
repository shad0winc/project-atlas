#!/usr/bin/env bash

atlas_command_restart() {
  cd "$ATLAS_PROJECT_DIR"
  docker compose restart
}
