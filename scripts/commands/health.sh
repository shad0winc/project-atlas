#!/usr/bin/env bash

atlas_health_python() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.health \
      --project-dir "$ATLAS_PROJECT_DIR" \
      --storage-root "$ATLAS_STORAGE_ROOT" \
      --media-root "$ATLAS_MEDIA_ROOT" \
      --downloads-root "$ATLAS_DOWNLOADS_ROOT" \
      "$@"
}

atlas_command_health() {
  local format="${1:-json}"

  case "$format" in
    json)
      atlas_health_python --format json
      ;;
    --compact|compact)
      atlas_health_python --format json --compact
      ;;
    *)
      echo "Usage: atlas health [json|--compact]" >&2
      return 1
      ;;
  esac
}
