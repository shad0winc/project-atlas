#!/usr/bin/env bash

atlas_command_discovery_help() {
  cat <<'HELP'
Project Atlas Discovery

Usage:
  atlas discovery
  atlas discovery help
  atlas discovery indexers [--json]
  atlas discovery categories [--json]
  atlas discovery applications
  atlas discovery health
  atlas discovery report

Commands:
  indexers       List configured discovery indexers
  categories     List discovery categories
  applications   List connected discovery applications
  health         Evaluate discovery health
  report         Generate a discovery report
  help           Show this help text

The indexers and categories commands are connected to the read-only
Prowlarr provider. Remaining subcommands will be introduced incrementally.
HELP
}

atlas_discovery_resolve_prowlarr_environment() {
  local config_dir=""
  local config_file=""
  local resolved_port=""
  local resolved_key=""

  if [[ -n "${ATLAS_PROWLARR_URL:-}" ]] &&
     [[ -n "${ATLAS_PROWLARR_API_KEY:-}" ]]; then
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    printf \
      'Discovery error: docker is required to resolve Prowlarr configuration.\n' \
      >&2
    return 1
  fi

  config_dir="$(
    docker inspect prowlarr \
      --format '{{range .Mounts}}{{if eq .Destination "/config"}}{{.Source}}{{end}}{{end}}' \
      2>/dev/null
  )"

  if [[ -z "$config_dir" ]]; then
    printf \
      'Discovery error: could not resolve the Prowlarr /config mount.\n' \
      >&2
    return 1
  fi

  config_file="$config_dir/config.xml"

  if [[ ! -f "$config_file" ]]; then
    printf \
      'Discovery error: Prowlarr config.xml was not found.\n' \
      >&2
    return 1
  fi

  read -r resolved_port resolved_key < <(
    python3 - "$config_file" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()

print(
    root.findtext("Port", default="9696").strip(),
    root.findtext("ApiKey", default="").strip(),
)
PY
  )

  if [[ -z "$resolved_port" ]]; then
    printf \
      'Discovery error: the Prowlarr port could not be resolved.\n' \
      >&2
    return 1
  fi

  if [[ -z "$resolved_key" ]]; then
    printf \
      'Discovery error: the Prowlarr API key could not be resolved.\n' \
      >&2
    return 1
  fi

  export ATLAS_PROWLARR_URL="${ATLAS_PROWLARR_URL:-http://127.0.0.1:${resolved_port}}"
  export ATLAS_PROWLARR_API_KEY="${ATLAS_PROWLARR_API_KEY:-$resolved_key}"
}

atlas_discovery_python() {
  atlas_discovery_resolve_prowlarr_environment || return 1

  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.discovery_cli "$@"
}

atlas_command_discovery_pending() {
  local subcommand="$1"

  printf \
    'Discovery subcommand is not implemented yet: %s\n' \
    "$subcommand" >&2

  printf \
    'Run: atlas discovery help\n' >&2

  return 2
}

atlas_command_discovery() {
  local subcommand="${1:-help}"

  case "$subcommand" in
    help|-h|--help)
      atlas_command_discovery_help
      ;;

    indexers)
      shift
      atlas_discovery_python indexers "$@"
      ;;

    categories)
      shift
      atlas_discovery_python categories "$@"
      ;;

    applications|health|report)
      atlas_command_discovery_pending "$subcommand"
      ;;

    *)
      printf \
        'Unknown discovery command: %s\n' \
        "$subcommand" >&2

      printf \
        'Run: atlas discovery help\n' >&2

      return 2
      ;;
  esac
}
