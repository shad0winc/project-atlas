#!/usr/bin/env bash

atlas_maintenance_directory() {
  printf '%s\n' "${ATLAS_MAINTENANCE_DIR:-$ATLAS_RUNTIME_CONFIG_DIR/maintenance}"
}

atlas_maintenance_flag() {
  printf '%s/enabled\n' "$(atlas_maintenance_directory)"
}

atlas_maintenance_authority() {
  local action="$1"
  local source_root
  source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)" || return 1
  if [[ "$(atlas_maintenance_directory)" != "$ATLAS_RUNTIME_CONFIG_DIR/maintenance" ]]; then
    echo 'ERROR: maintenance directory override conflicts with the shared authority.' >&2
    return 1
  fi

  # Host-local fallback needs neither a live API nor a running socket service.
  # The authority validates ownership, the shared flock, recovery holds and audit.
  # Never fall back to direct touch/rm when it refuses.
  PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -B -m atlas.maintenance_control_cli \
      --runtime-root "$ATLAS_RUNTIME_CONFIG_DIR" "$action"
}

atlas_maintenance_status() { atlas_maintenance_authority status; }
atlas_maintenance_enable() { atlas_maintenance_authority enable; }
atlas_maintenance_disable() { atlas_maintenance_authority disable; }

atlas_command_maintenance() {
  local action="${1:-status}"
  case "$action" in
    status|enable|disable|repair-hold)
      atlas_maintenance_authority "$action"
      ;;
    help|-h|--help)
      cat <<'HELP'
Usage:
  atlas maintenance status
  atlas maintenance enable
  atlas maintenance disable
  atlas maintenance repair-hold

Maintenance permits authenticated global administrators while blocking ordinary
Portal and API access. Disable refuses while recovery ownership is held or state
is uncertain. Host repair-hold forces maintenance on after an interrupted control
transition; it never releases deployment ownership or opens ordinary access.
HELP
      ;;
    *)
      printf 'Unknown maintenance action: %s\n' "$action" >&2
      echo 'Run: atlas maintenance help' >&2
      return 2
      ;;
  esac
}

# Native callers must pass the transaction identity and the live parent flock.
# This helper can only enable; web clients cannot supply this context.
atlas_maintenance_transaction_enable() {
  local transaction_id="$1"
  local transaction_fd="$2"
  local source_root
  source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)" || return 1
  [[ "$(atlas_maintenance_directory)" == "$ATLAS_RUNTIME_CONFIG_DIR/maintenance" ]] || return 1
  PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -B -m atlas.maintenance_control_cli \
      --runtime-root "$ATLAS_RUNTIME_CONFIG_DIR" --transaction-id "$transaction_id" \
      --exclusion-fd "$transaction_fd" transaction-enable
}

# Completion checkpoint: prove the existing hold under the owning transaction.
# No flag or recovery ownership is removed. Ordinary reopening is a later action.
atlas_maintenance_transaction_hold() {
  local transaction_id="$1"
  local transaction_fd="$2"
  local source_root
  source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)" || return 1
  [[ "$(atlas_maintenance_directory)" == "$ATLAS_RUNTIME_CONFIG_DIR/maintenance" ]] || return 1
  PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -B -m atlas.maintenance_control_cli \
      --runtime-root "$ATLAS_RUNTIME_CONFIG_DIR" --transaction-id "$transaction_id" \
      --exclusion-fd "$transaction_fd" transaction-check-held
}
