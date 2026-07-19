#!/usr/bin/env bash

atlas_command_health() {
  local format="${1:-json}"

  case "$format" in
    json)
      PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -m atlas.health
      ;;
    --compact|compact)
      PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -m atlas.health --compact
      ;;
    *)
      echo "Usage: atlas health [json|--compact]" >&2
      return 1
      ;;
  esac
}
