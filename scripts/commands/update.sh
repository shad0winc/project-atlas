#!/usr/bin/env bash

atlas_command_update() {
  atlas_print_header

  echo "Starting Atlas update..."
  echo

  echo "Pre-update doctor:"
  atlas_command_doctor

  echo
  echo "Pulling latest container images..."
  docker compose -f "$ATLAS_PROJECT_DIR/docker-compose.yml" pull

  echo
  echo "Recreating containers..."
  docker compose -f "$ATLAS_PROJECT_DIR/docker-compose.yml" up -d

  echo
  echo "Cleaning unused images..."
  docker image prune -f

  echo
  echo "Post-update doctor:"
  atlas_command_doctor

  echo
  echo "Post-update verify:"
  atlas_command_verify

  echo
  echo "Atlas update complete."
}
