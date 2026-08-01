#!/usr/bin/env bash

atlas_command_service_help() {
  cat <<'HELP'
Project Atlas Service Lifecycle

Usage:
  atlas service
  atlas service help
  atlas service list [--json]

Commands:
  list    List configured Atlas-managed services
  help    Show this help text

The Service Lifecycle CLI is read-only.
HELP
}

atlas_service_python() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m atlas.service_lifecycle_cli "$@"
}

atlas_command_service() {
  local subcommand="${1:-help}"

  case "$subcommand" in
    help|-h|--help)
      atlas_command_service_help
      ;;
    list)
      shift
      atlas_service_python list "$@"
      ;;
    *)
      printf 'Unknown service command: %s\n' "$subcommand" >&2
      printf 'Run: atlas service help\n' >&2
      return 2
      ;;
  esac
}
