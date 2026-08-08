#!/usr/bin/env bash

# Canonical M-023.25 recovery-state registry.
#
# Columns:
#   surface | source | archive path | requirement | kind | consistency group
#
# This registry describes recovery ownership only. It does not copy, archive,
# delete, or restore state.

atlas_backup_recovery_surface_rows() {
  local sports_root

  : "${ATLAS_CONFIG_ROOT:?ATLAS_CONFIG_ROOT is required}"
  : "${ATLAS_RUNTIME_CONFIG_DIR:?ATLAS_RUNTIME_CONFIG_DIR is required}"
  : "${ATLAS_USERS_DIR:?ATLAS_USERS_DIR is required}"
  : "${ATLAS_IDENTITY_DIR:?ATLAS_IDENTITY_DIR is required}"
  : "${ATLAS_REQUESTS_DIR:?ATLAS_REQUESTS_DIR is required}"
  : "${ATLAS_SCHEDULER_STATE_FILE:?ATLAS_SCHEDULER_STATE_FILE is required}"
  : "${ATLAS_ARI_DIR:?ATLAS_ARI_DIR is required}"

  sports_root="${SPORTS_CONFIG_DIR:-${ATLAS_CONFIG_ROOT}/sportyfin}"

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'users' \
    "$ATLAS_USERS_DIR" \
    'state/users' \
    'required' \
    'directory' \
    'identity'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'identity-invitations' \
    "$ATLAS_IDENTITY_DIR/invitations" \
    'state/identity/invitations' \
    'optional' \
    'directory' \
    'identity'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'favorites' \
    "$ATLAS_IDENTITY_DIR/favorites" \
    'state/identity/favorites' \
    'required' \
    'directory' \
    'identity'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'requests' \
    "$ATLAS_REQUESTS_DIR/requests.json" \
    'state/requests/requests.json' \
    'optional' \
    'file' \
    'requests'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'scheduler' \
    "$ATLAS_SCHEDULER_STATE_FILE" \
    'state/scheduler/tasks.json' \
    'required' \
    'file' \
    'scheduler'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'runtime-events' \
    "$ATLAS_RUNTIME_CONFIG_DIR/runtime/events.jsonl" \
    'state/runtime/events.jsonl' \
    'required' \
    'file' \
    'runtime-events'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'runtime-subscribers' \
    "$ATLAS_RUNTIME_CONFIG_DIR/runtime/subscribers" \
    'state/runtime/subscribers' \
    'required' \
    'directory' \
    'runtime-events'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'retention' \
    "$ATLAS_ARI_DIR" \
    'state/retention' \
    'required' \
    'directory' \
    'retention'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'sports-subscriptions' \
    "$sports_root/state/subscriptions.json" \
    'state/sports/subscriptions.json' \
    'required' \
    'file' \
    'sports'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'sports-recordings' \
    "$sports_root/recordings/recordings.json" \
    'state/sports/recordings.json' \
    'required' \
    'file' \
    'sports'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'sports-scheduler' \
    "$ATLAS_RUNTIME_CONFIG_DIR/runtime/scheduler/sports.json" \
    'state/sports/scheduler.json' \
    'required' \
    'file' \
    'sports'
}

atlas_backup_recovery_validate_registry() {
  local surface source archive requirement kind group
  local count=0
  declare -A seen_surfaces=()
  declare -A seen_archives=()

  while IFS=$'\t' read -r \
    surface source archive requirement kind group
  do
    [[ -n "$surface" && -n "$source" && -n "$archive" ]] || {
      echo 'ERROR: recovery registry contains an incomplete row.' >&2
      return 1
    }

    [[ "$surface" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
      printf 'ERROR: invalid recovery surface: %s\n' "$surface" >&2
      return 1
    }

    [[ "$source" == /* ]] || {
      printf 'ERROR: recovery source is not absolute: %s\n' "$source" >&2
      return 1
    }

    [[ "$archive" == state/* && "$archive" != /* ]] || {
      printf 'ERROR: invalid recovery archive path: %s\n' "$archive" >&2
      return 1
    }

    [[ "/$archive/" != *'/../'* && "/$archive/" != *'/./'* ]] || {
      printf 'ERROR: unsafe recovery archive path: %s\n' "$archive" >&2
      return 1
    }

    [[ "$requirement" == 'required' || "$requirement" == 'optional' ]] || {
      printf 'ERROR: invalid recovery requirement: %s\n' "$requirement" >&2
      return 1
    }

    [[ "$kind" == 'file' || "$kind" == 'directory' ]] || {
      printf 'ERROR: invalid recovery source kind: %s\n' "$kind" >&2
      return 1
    }

    [[ "$group" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
      printf 'ERROR: invalid recovery consistency group: %s\n' "$group" >&2
      return 1
    }

    [[ -z "${seen_surfaces[$surface]+x}" ]] || {
      printf 'ERROR: duplicate recovery surface: %s\n' "$surface" >&2
      return 1
    }

    [[ -z "${seen_archives[$archive]+x}" ]] || {
      printf 'ERROR: duplicate recovery archive path: %s\n' "$archive" >&2
      return 1
    }

    seen_surfaces[$surface]=1
    seen_archives[$archive]=1
    count=$((count + 1))
  done < <(atlas_backup_recovery_surface_rows)

  [[ "$count" -eq 11 ]] || {
    printf 'ERROR: expected 11 recovery surfaces, found %s.\n' "$count" >&2
    return 1
  }
}
