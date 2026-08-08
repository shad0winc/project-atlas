#!/usr/bin/env bash

atlas_restore_usage() {
  cat <<'HELP'
Usage:
  atlas restore inspect <archive>
  atlas restore verify <archive>
  atlas restore stage <archive>
  atlas restore validate-stage <staging-root>
  atlas restore plan <staging-root>
  atlas restore --help

Recovery inspection, verification, and planning are read-only. `stage` validates
archive members and extracts only into a new private directory beneath `/tmp`;
it never targets live Atlas state. `plan` validates the staged state and maps
only declared surfaces to canonical destinations. Live apply remains unavailable.
HELP
}

atlas_restore_require_archive() {
  local archive="$1"

  [[ -n "$archive" ]] || {
    echo 'ERROR: restore archive path is required.' >&2
    return 2
  }

  [[ -f "$archive" && ! -L "$archive" ]] || {
    printf 'ERROR: restore archive is not a regular file: %s\n' \
      "$archive" >&2
    return 1
  }
}

atlas_restore_inspect() {
  local archive="$1"
  local backup_info recovery_format manifest

  atlas_restore_require_archive "$archive" || return $?

  tar -tzf "$archive" >/dev/null 2>&1 || {
    echo 'ERROR: restore archive is unreadable.' >&2
    return 1
  }

  echo 'Atlas Restore Inspection'
  echo
  printf 'Archive: %s\n' "$archive"
  printf 'Size: %s\n' "$(du -h "$archive" | awk '{print $1}')"
  echo

  if backup_info="$(tar -xOzf "$archive" BACKUP_INFO.txt 2>/dev/null)"; then
    echo 'Backup information:'
    printf '%s\n' "$backup_info" | sed 's/^/  /'
  else
    echo 'Backup information: unavailable'
  fi

  echo

  if recovery_format="$(tar -xOzf "$archive" RECOVERY_FORMAT 2>/dev/null)"; then
    printf 'Recovery format: %s\n' "$recovery_format"
  else
    echo 'Recovery format: legacy/undeclared'
    echo 'Recovery state: configuration-only historical archive'
    echo 'Restore verification: unavailable'
    return 0
  fi

  if manifest="$(tar -xOzf "$archive" RECOVERY_MANIFEST.tsv 2>/dev/null)"; then
    echo
    echo 'Recovery manifest:'
    printf '%s\n' "$manifest" | sed 's/^/  /'
  else
    echo 'Recovery manifest: unavailable'
  fi

  echo
  echo 'Inspection only: archive validity has not been asserted.'
}

atlas_restore_verify() {
  local archive="$1"

  atlas_restore_require_archive "$archive" || return $?

  atlas_backup_recovery_validate_archive "$archive" || {
    echo 'Atlas Restore Verification: FAIL' >&2
    return 1
  }

  echo 'Atlas Restore Verification'
  echo
  printf 'Archive: %s\n' "$archive"
  echo 'Recovery state: state-complete'
  echo 'Restore capability: unverified'
  echo 'Integrity: PASS'
  echo
  echo 'Atlas Restore Verification: PASS'
}

atlas_restore_stage() {
  local archive="$1"
  local stage_root

  atlas_restore_require_archive "$archive" || return $?
  atlas_restore_load_recovery_library

  stage_root="$(atlas_backup_recovery_stage_archive "$archive" /tmp)" || {
    echo 'Atlas Restore Staging: FAIL' >&2
    return 1
  }

  echo 'Atlas Restore Staging'
  echo
  printf 'Archive: %s\n' "$archive"
  printf 'Staging root: %s\n' "$stage_root"
  echo 'Archive member safety: PASS'
  echo 'Staged integrity: PASS'
  echo 'Live state mutation: none'
  echo
  echo 'Atlas Restore Staging: PASS'
}

atlas_restore_validate_stage() {
  local requested="$1"
  local root before after

  [[ -n "$requested" ]] || {
    echo 'ERROR: isolated staging root is required.' >&2
    return 2
  }

  root="$(realpath -e -- "$requested" 2>/dev/null)" || {
    echo 'ERROR: isolated staging root is unavailable.' >&2
    return 1
  }

  [[ "$root" == "$requested" &&
     "$root" == /tmp/project-atlas-restore.* &&
     -d "$root" && ! -L "$root" ]] || {
    echo 'ERROR: validate-stage requires an isolated /tmp staging root.' >&2
    return 1
  }

  atlas_restore_load_recovery_library
  atlas_backup_recovery_validate_staged_restore "$root" || return 1

  before="$(atlas_backup_recovery_staged_state_digest "$root")" || return 1

  echo 'Atlas Staged Restore Consumer Validation'
  echo
  atlas_backup_recovery_validate_staged_consumers "$root" || {
    echo 'Atlas Staged Restore Consumer Validation: FAIL' >&2
    return 1
  }

  after="$(atlas_backup_recovery_staged_state_digest "$root")" || return 1
  [[ "$before" == "$after" ]] || {
    echo 'ERROR: consumer validation mutated staged recovery state.' >&2
    return 1
  }

  atlas_backup_recovery_validate_staged_restore "$root" || return 1

  echo
  echo 'Staged state mutation: none'
  echo 'Live state mutation: none'
  echo 'Atlas Staged Restore Consumer Validation: PASS'
}

atlas_restore_plan() {
  local requested="$1"
  local root before after

  [[ -n "$requested" ]] || {
    echo 'ERROR: isolated staging root is required.' >&2
    return 2
  }

  root="$(realpath -e -- "$requested" 2>/dev/null)" || {
    echo 'ERROR: isolated staging root is unavailable.' >&2
    return 1
  }

  [[ "$root" == "$requested" &&
     "$root" == /tmp/project-atlas-restore.* &&
     -d "$root" && ! -L "$root" ]] || {
    echo 'ERROR: restore plan requires an isolated /tmp staging root.' >&2
    return 1
  }

  atlas_restore_load_recovery_library
  atlas_backup_recovery_validate_staged_restore "$root" || return 1
  before="$(atlas_backup_recovery_staged_state_digest "$root")" || return 1

  atlas_backup_recovery_validate_staged_consumers "$root" || {
    echo 'Atlas Restore Plan: FAIL' >&2
    return 1
  }

  echo 'Atlas Restore Plan'
  echo
  printf 'Surface\tAction\tKind\tConsistency group\tStaged source\tLive destination\n'
  atlas_backup_recovery_restore_plan "$root" || {
    echo 'Atlas Restore Plan: FAIL' >&2
    return 1
  }

  after="$(atlas_backup_recovery_staged_state_digest "$root")" || return 1
  [[ "$before" == "$after" ]] || {
    echo 'ERROR: restore planning mutated staged recovery state.' >&2
    return 1
  }

  atlas_backup_recovery_validate_staged_restore "$root" || return 1

  echo
  echo 'Writer quiesce set: atlas-api, atlas-sports-controller, atlas-notifications-worker'
  echo 'Deployment/update mutual exclusion: required'
  echo 'Maintenance before live mutation: required'
  echo 'Pre-restore recovery point: required'
  echo 'Staged state mutation: none'
  echo 'Live state mutation: none'
  echo 'Atlas Restore Plan: PASS'
}

atlas_restore_load_recovery_library() {
  local recovery_library

  if declare -F atlas_backup_recovery_validate_archive >/dev/null; then
    return 0
  fi

  recovery_library="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
  )/lib/backup-recovery.sh"
  source "$recovery_library"
}

# M-023.25.7.3.1 production restore orchestration primitives.
#
# Live apply remains unavailable at the CLI in this checkpoint. These helpers
# prove the exact writer boundary, certified-production preflight, durable
# pre-restore recovery point, and consumer validation of the live state that
# was actually published. The mutating command is layered on only after these
# primitives have dedicated failure/recovery coverage.

atlas_restore_writer_containers() {
  printf '%s\n' \
    'atlas-api' \
    'atlas-sports-controller' \
    'atlas-notifications-worker'
}

atlas_restore_writer_state() {
  local container="$1"

  docker inspect --format \
    '{{if not .State.Running}}stopped{{else if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' \
    "$container"
}

atlas_restore_require_writers_running() {
  local container state

  while IFS= read -r container; do
    state="$(atlas_restore_writer_state "$container" 2>/dev/null)" || {
      printf 'ERROR: restore writer is unavailable: %s\n' "$container" >&2
      return 1
    }
    case "$state" in
      running|healthy)
        ;;
      *)
        printf 'ERROR: restore writer is not ready: %s (%s)\n' \
          "$container" "$state" >&2
        return 1
        ;;
    esac
  done < <(atlas_restore_writer_containers)
}

atlas_restore_stop_writers() {
  local container

  while IFS= read -r container; do
    docker stop --time 30 "$container" >/dev/null || {
      printf 'ERROR: unable to quiesce restore writer: %s\n' \
        "$container" >&2
      return 1
    }
  done < <(atlas_restore_writer_containers)
}

atlas_restore_start_writers() {
  local container

  while IFS= read -r container; do
    docker start "$container" >/dev/null || {
      printf 'ERROR: unable to start restore writer: %s\n' \
        "$container" >&2
      return 1
    }
  done < <(atlas_restore_writer_containers)
}

atlas_restore_wait_for_writers() {
  local timeout_seconds="${ATLAS_RESTORE_WRITER_TIMEOUT_SECONDS:-120}"
  local deadline container state pending

  [[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || {
    echo 'ERROR: restore writer timeout must be a positive integer.' >&2
    return 1
  }

  deadline=$((SECONDS + timeout_seconds))
  while (( SECONDS < deadline )); do
    pending=false
    while IFS= read -r container; do
      state="$(atlas_restore_writer_state "$container" 2>/dev/null || true)"
      case "$state" in
        running|healthy)
          ;;
        unhealthy)
          printf 'ERROR: restore writer became unhealthy: %s\n' \
            "$container" >&2
          return 1
          ;;
        *)
          pending=true
          ;;
      esac
    done < <(atlas_restore_writer_containers)

    [[ "$pending" == false ]] && return 0
    sleep 2
  done

  echo 'ERROR: restore writers did not become ready before timeout.' >&2
  return 1
}

atlas_restore_require_production_preflight() {
  local requested="$1"
  local root before after current_record

  root="$(realpath -e -- "$requested" 2>/dev/null)" || {
    echo 'ERROR: live restore requires an existing isolated staging root.' >&2
    return 1
  }

  [[ "$root" == "$requested" &&
     "$root" == /tmp/project-atlas-restore.* &&
     -d "$root" && ! -L "$root" ]] || {
    echo 'ERROR: live restore requires an isolated /tmp staging root.' >&2
    return 1
  }

  atlas_deployment_validate_source || return 1
  current_record="$(atlas_deployment_require_current_record)" || return 1
  [[ -d "$current_record" ]] || return 1

  [[ ! -f "$(atlas_maintenance_flag)" ]] || {
    echo 'ERROR: live restore requires maintenance mode to be disabled at preflight.' >&2
    return 1
  }

  [[ ! -e "$(atlas_deployment_lock_dir)" ]] || {
    echo 'ERROR: live restore requires the shared deployment lock to be free.' >&2
    return 1
  }

  atlas_restore_load_recovery_library
  atlas_backup_recovery_validate_staged_restore "$root" || return 1
  before="$(atlas_backup_recovery_staged_state_digest "$root")" || return 1
  atlas_backup_recovery_validate_staged_consumers "$root" || return 1
  after="$(atlas_backup_recovery_staged_state_digest "$root")" || return 1
  [[ "$before" == "$after" ]] || {
    echo 'ERROR: live-restore preflight mutated staged recovery state.' >&2
    return 1
  }

  atlas_restore_require_writers_running || return 1
  printf '%s\n' "$current_record"
}

atlas_restore_create_pre_restore_recovery_point() {
  local identifier="$1"
  local output backup_file

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid restore transaction identifier.' >&2
    return 1
  }

  output="$(
    atlas_command_backup \
      --notes "Pre-restore recovery point for $identifier"
  )" || {
    echo 'ERROR: pre-restore recovery point failed.' >&2
    return 1
  }
  printf '%s\n' "$output"

  backup_file="$(
    awk '
      /^File:$/ {getline; sub(/^[[:space:]]+/, ""); print; exit}
    ' <<< "$output"
  )"

  [[ -n "$backup_file" && -f "$backup_file" && ! -L "$backup_file" ]] || {
    echo 'ERROR: backup command did not publish a recovery point.' >&2
    return 1
  }

  atlas_restore_load_recovery_library
  atlas_backup_recovery_validate_archive "$backup_file" || {
    echo 'ERROR: pre-restore recovery point failed validation.' >&2
    return 1
  }

  ATLAS_RESTORE_RECOVERY_POINT="$backup_file"
  export ATLAS_RESTORE_RECOVERY_POINT
}

atlas_restore_validate_live_consumers() {
  local snapshot_root manifest status=0

  atlas_restore_load_recovery_library
  snapshot_root="$(
    mktemp -d /tmp/project-atlas-live-restore-verify.XXXXXX
  )" || return 1
  chmod 0700 "$snapshot_root"
  manifest="$snapshot_root/RECOVERY_MANIFEST.tsv"

  printf '%s\t%s\t%s\t%s\n' \
    'surface' 'archive_path' 'requirement' 'policy' \
    > "$manifest"
  printf '%s\t%s\t%s\t%s\n' \
    'project-configuration' '.' 'required' 'configuration-only' \
    >> "$manifest"

  if ! atlas_backup_recovery_snapshot_state "$snapshot_root" >> "$manifest"; then
    echo 'ERROR: unable to capture live state for restore verification.' >&2
    status=1
  elif ! atlas_backup_recovery_validate_staged_consumers "$snapshot_root"; then
    echo 'ERROR: restored live state failed consumer validation.' >&2
    status=1
  fi

  rm -rf -- "$snapshot_root"
  return "$status"
}

atlas_command_restore() {
  atlas_print_header

  local command="${1:-}"

  case "$command" in
    inspect)
      [[ "$#" -eq 2 ]] || {
        echo 'ERROR: restore inspect requires exactly one archive.' >&2
        atlas_restore_usage >&2
        return 2
      }
      atlas_restore_inspect "$2"
      ;;
    verify)
      [[ "$#" -eq 2 ]] || {
        echo 'ERROR: restore verify requires exactly one archive.' >&2
        atlas_restore_usage >&2
        return 2
      }
      atlas_restore_load_recovery_library
      atlas_restore_verify "$2"
      ;;
    stage)
      [[ "$#" -eq 2 ]] || {
        echo 'ERROR: restore stage requires exactly one archive.' >&2
        atlas_restore_usage >&2
        return 2
      }
      atlas_restore_stage "$2"
      ;;
    validate-stage)
      [[ "$#" -eq 2 ]] || {
        echo 'ERROR: restore validate-stage requires exactly one staging root.' >&2
        atlas_restore_usage >&2
        return 2
      }
      atlas_restore_validate_stage "$2"
      ;;
    plan)
      [[ "$#" -eq 2 ]] || {
        echo 'ERROR: restore plan requires exactly one staging root.' >&2
        atlas_restore_usage >&2
        return 2
      }
      atlas_restore_plan "$2"
      ;;
    --help|-h|help)
      [[ "$#" -eq 1 ]] || {
        echo 'ERROR: restore help does not accept additional arguments.' >&2
        return 2
      }
      atlas_restore_usage
      ;;
    apply)
      echo 'ERROR: live restore apply is not implemented or authorized.' >&2
      echo 'Use: atlas restore inspect <archive>' >&2
      echo '     atlas restore verify <archive>' >&2
      return 2
      ;;
    '')
      atlas_restore_usage >&2
      return 2
      ;;
    *)
      printf 'ERROR: unknown restore command: %s\n' "$command" >&2
      atlas_restore_usage >&2
      return 2
      ;;
  esac
}
