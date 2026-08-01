#!/usr/bin/env bash

atlas_command_discovery_help() {
  cat <<'HELP'
Project Atlas Discovery

Usage:
  atlas discovery
  atlas discovery help
  atlas discovery indexers
  atlas discovery categories
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

The read-only Discovery command interface is established, but its functional
subcommands will be connected to Prowlarr in the next implementation step.
HELP
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

    indexers|categories|applications|health|report)
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
