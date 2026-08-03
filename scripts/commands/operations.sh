#!/usr/bin/env bash

atlas_command_operations_help() {
  cat <<'EOF'
Atlas Operations

Usage:
  atlas operations help
  atlas operations report [--json] [--report-id REPORT_ID]
  atlas operations save [--json] [--report-id REPORT_ID]
  atlas operations latest [--json]
  atlas operations history [--limit LIMIT] [--json]
  atlas operations compare [--json] [--include-unchanged]

Commands:
  report    Collect the current live Operations report
  save      Collect and persist a new Operations report
  latest    Render the latest persisted Operations report
  history   Render persisted Operations report history
  compare   Compare the two newest persisted Operations reports
  help      Show this help text

Options:
  --json                  Render deterministic JSON output
  --report-id REPORT_ID   Override the report identifier
EOF
}

atlas_operations_python() {
  python3 -m atlas.operations_cli "$@"
}

atlas_command_operations() {
  local subcommand="${1:-help}"

  case "$subcommand" in
    help|-h|--help)
      if [[ "$#" -gt 1 ]]; then
        printf \
          'ERROR: operations help does not accept additional arguments.\n' \
          >&2
        atlas_command_operations_help >&2
        return 2
      fi

      atlas_command_operations_help
      ;;

    report)
      shift
      atlas_operations_python report "$@"
      ;;

    save)
      shift
      atlas_operations_python save "$@"
      ;;

    latest)
      shift
      atlas_operations_python latest "$@"
      ;;

    history)
      shift
      atlas_operations_python history "$@"
      ;;

    compare)
      shift
      atlas_operations_python compare "$@"
      ;;

    *)
      printf \
        'Unknown operations command: %s\n' \
        "$subcommand" \
        >&2
      printf \
        'Run: atlas operations help\n' \
        >&2
      return 2
      ;;
  esac
}
