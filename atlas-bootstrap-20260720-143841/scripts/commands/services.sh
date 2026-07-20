#!/usr/bin/env bash

atlas_command_services() {
  cd "$ATLAS_PROJECT_DIR"
  docker compose ps
}
