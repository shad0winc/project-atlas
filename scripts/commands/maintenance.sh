#!/usr/bin/env bash

atlas_maintenance_directory() {
  printf '%s\n' "${ATLAS_MAINTENANCE_DIR:-$ATLAS_RUNTIME_CONFIG_DIR/maintenance}"
}

atlas_maintenance_flag() {
  printf '%s/enabled\n' "$(atlas_maintenance_directory)"
}

atlas_maintenance_status() {
  local flag
  flag="$(atlas_maintenance_flag)"

  if [[ -f "$flag" ]]; then
    echo 'Atlas maintenance mode: enabled'
  else
    echo 'Atlas maintenance mode: disabled'
  fi
}

atlas_maintenance_enable() {
  local directory
  local flag
  local temporary

  directory="$(atlas_maintenance_directory)"
  flag="$directory/enabled"

  mkdir -p "$directory"
  temporary="$(mktemp "$directory/.enabled.XXXXXX")"

  if ! chmod 0644 "$temporary" || ! mv -f -- "$temporary" "$flag"; then
    rm -f -- "$temporary"
    echo 'ERROR: unable to enable Atlas maintenance mode.' >&2
    return 1
  fi

  echo 'Atlas maintenance mode: enabled'
}

atlas_maintenance_disable() {
  local flag
  flag="$(atlas_maintenance_flag)"

  if ! rm -f -- "$flag"; then
    echo 'ERROR: unable to disable Atlas maintenance mode.' >&2
    return 1
  fi

  echo 'Atlas maintenance mode: disabled'
}

atlas_command_maintenance() {
  local action="${1:-status}"

  case "$action" in
    status)
      atlas_maintenance_status
      ;;
    enable)
      atlas_maintenance_enable
      ;;
    disable)
      atlas_maintenance_disable
      ;;
    help|-h|--help)
      cat <<'HELP'
Usage:
  atlas maintenance status
  atlas maintenance enable
  atlas maintenance disable

Maintenance mode is enforced at the public Caddy ingress boundary.
Backend services remain running while public Portal and API traffic receives
HTTP 503. The dedicated ingress liveness endpoint remains available.
HELP
      ;;
    *)
      printf 'Unknown maintenance action: %s\n' "$action" >&2
      echo 'Run: atlas maintenance help' >&2
      return 2
      ;;
  esac
}
