#!/usr/bin/env bash

atlas_command_logs() {
  local container="${1:-}"

  if [[ -z "$container" ]]; then
    echo "Usage: atlas logs <container>"
    return 1
  fi

  docker logs "$container" --tail=100 -f
}
