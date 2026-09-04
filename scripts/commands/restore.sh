#!/usr/bin/env bash

atlas_restore_usage() {
  cat <<'HELP'
Usage:
  atlas restore inspect <archive>
  atlas restore verify <archive>
  atlas restore stage <archive>
  atlas restore validate-stage <staging-root>
  atlas restore plan <staging-root>
  atlas restore apply <staging-root> --confirm-live
  atlas restore resume <restore-id> --confirm-live
  atlas restore abort <restore-id> --confirm-live
  atlas restore --help

Recovery inspection, verification, staging, and planning are read-only. Live
apply requires certified `main`, a verified deployment baseline, the shared
deployment lock, maintenance isolation, a durable pre-restore recovery point,
quiesced writers, explicit `--confirm-live`, and post-restore verification.
Held failures are recovered explicitly with `resume` or `abort`.
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

  if [[ -f "$root/RECOVERY_FORMAT" &&
        "$(<"$root/RECOVERY_FORMAT")" == '2' ]]
  then
    echo 'ERROR: recovery format 2 contains native Sports backend state; live restore is not implemented.' >&2
    return 1
  fi

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

# M-023.25.7.3.2 fail-closed live restore transaction.

atlas_restore_transaction_root() {
  local identifier="$1"

  atlas_deployment_valid_id "$identifier" || return 1
  printf '%s/restores/%s\n' "$ATLAS_RUNTIME_CONFIG_DIR" "$identifier"
}

atlas_restore_pending_recovery_point_file() {
  local identifier="$1"

  atlas_deployment_valid_id "$identifier" || return 1
  printf '%s/restores/.%s.recovery-point\n' \
    "$ATLAS_RUNTIME_CONFIG_DIR" "$identifier"
}

atlas_restore_preserve_recovery_point() {
  local identifier="$1"
  local backup_file="$2"
  local pending temporary

  [[ -f "$backup_file" && ! -L "$backup_file" ]] || return 1
  pending="$(atlas_restore_pending_recovery_point_file "$identifier")" || return 1
  mkdir -p "$(dirname "$pending")"
  temporary="$(mktemp "${pending}.XXXXXX")" || return 1
  chmod 0600 "$temporary"
  printf '%s\n' "$backup_file" > "$temporary"
  mv -f -- "$temporary" "$pending"
}

atlas_restore_attach_recovery_point() {
  local identifier="$1"
  local transaction="$2"
  local pending

  pending="$(atlas_restore_pending_recovery_point_file "$identifier")" || return 1
  [[ -d "$transaction" && ! -L "$transaction" && -f "$pending" ]] || return 1
  mv -- "$pending" "$transaction/pre-restore-backup"
  chmod 0600 "$transaction/pre-restore-backup"
}

atlas_restore_transaction_recovery_point() {
  local identifier="$1"
  local transaction="$2"
  local pending file backup_file

  file="$transaction/pre-restore-backup"
  if [[ ! -f "$file" ]]; then
    pending="$(atlas_restore_pending_recovery_point_file "$identifier")" || return 1
    file="$pending"
  fi

  [[ -f "$file" && ! -L "$file" ]] || {
    echo 'ERROR: restore transaction recovery point is unavailable.' >&2
    return 1
  }
  IFS= read -r backup_file < "$file"
  [[ -f "$backup_file" && ! -L "$backup_file" ]] || {
    echo 'ERROR: recorded pre-restore backup is unavailable.' >&2
    return 1
  }

  atlas_restore_load_recovery_library
  atlas_backup_recovery_validate_archive "$backup_file" || {
    echo 'ERROR: recorded pre-restore backup is invalid.' >&2
    return 1
  }
  printf '%s\n' "$backup_file"
}

atlas_restore_write_transaction_metadata() {
  local transaction="$1"
  local identifier="$2"
  local baseline_record="$3"
  local staged_root="$4"
  local staged_digest="$5"
  local metadata="$transaction/restore-metadata"
  local temporary

  [[ -d "$transaction" && ! -L "$transaction" ]] || return 1
  temporary="$(mktemp "$transaction/.restore-metadata.XXXXXX")" || return 1
  chmod 0600 "$temporary"
  {
    printf 'restore_id=%s\n' "$identifier"
    printf 'baseline_id=%s\n' "$(basename "$baseline_record")"
    printf 'source_commit=%s\n' "$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)"
    printf 'staging_root=%s\n' "$staged_root"
    printf 'staged_digest=%s\n' "$staged_digest"
    printf 'created_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$temporary"
  mv -f -- "$temporary" "$metadata"
}

atlas_restore_verify_runtime_boundary() {
  atlas_command_doctor || return 1
  atlas_command_verify || return 1
  "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh" || return 1
}

atlas_restore_verify_maintenance_isolation() {
  "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh"
}

atlas_restore_cleanup_before_mutation() {
  local identifier="$1"

  atlas_restore_start_writers || {
    echo 'CRITICAL: restore pre-mutation cleanup could not restart writers.' >&2
    return 1
  }
  atlas_restore_wait_for_writers || {
    echo 'CRITICAL: restore pre-mutation cleanup writers are not ready.' >&2
    return 1
  }
  atlas_maintenance_disable || {
    echo 'CRITICAL: restore pre-mutation cleanup could not reopen maintenance.' >&2
    return 1
  }
  atlas_deployment_release_lock "$identifier" || return 1
}

atlas_restore_report_held_failure() {
  local identifier="$1"
  local message="$2"

  atlas_maintenance_enable >/dev/null 2>&1 || true
  printf 'ERROR: %s\n' "$message" >&2
  printf 'Restore transaction retained: %s\n' "$identifier" >&2
  echo 'Maintenance: retained' >&2
  echo 'Shared deployment lock: retained' >&2
  echo "Recovery: atlas restore resume $identifier --confirm-live" >&2
  echo "       or atlas restore abort $identifier --confirm-live" >&2
  return 1
}

atlas_restore_complete_applied_transaction() {
  local identifier="$1"
  local transaction="$2"

  atlas_restore_start_writers || {
    atlas_restore_report_held_failure \
      "$identifier" 'restored state applied but writers could not start.'
    return 1
  }
  atlas_restore_wait_for_writers || {
    atlas_restore_report_held_failure \
      "$identifier" 'restored state applied but writers did not become ready.'
    return 1
  }

  atlas_restore_verify_runtime_boundary || {
    atlas_restore_report_held_failure \
      "$identifier" 'post-restore verification failed under maintenance.'
    return 1
  }

  atlas_maintenance_disable || {
    atlas_restore_report_held_failure \
      "$identifier" 'unable to reopen public ingress after restore.'
    return 1
  }

  if ! atlas_restore_verify_runtime_boundary; then
    atlas_maintenance_enable >/dev/null 2>&1 || true
    atlas_restore_report_held_failure \
      "$identifier" 'public post-restore verification failed.'
    return 1
  fi

  atlas_backup_recovery_finalize_applied_state "$transaction" || {
    atlas_maintenance_enable >/dev/null 2>&1 || true
    atlas_restore_report_held_failure \
      "$identifier" 'restore verification passed but transaction finalization failed.'
    return 1
  }

  atlas_deployment_release_lock "$identifier" || {
    atlas_maintenance_enable >/dev/null 2>&1 || true
    echo 'CRITICAL: verified restore could not release the shared deployment lock.' >&2
    return 1
  }

  printf 'Live restore complete: %s\n' "$identifier"
}

atlas_restore_apply_live() {
  local requested="$1"
  local baseline_record identifier transaction staged_digest
  local recovery_point

  baseline_record="$(atlas_restore_require_production_preflight "$requested")" || return 1
  atlas_restore_load_recovery_library
  staged_digest="$(atlas_backup_recovery_staged_state_digest "$requested")" || return 1
  identifier="$(atlas_deployment_new_id restore)" || return 1
  transaction="$(atlas_restore_transaction_root "$identifier")" || return 1

  atlas_deployment_acquire_lock "$identifier" || return 1

  if ! atlas_maintenance_enable; then
    atlas_deployment_release_lock "$identifier" || true
    return 1
  fi

  if ! atlas_restore_verify_maintenance_isolation; then
    atlas_maintenance_disable || true
    atlas_deployment_release_lock "$identifier" || true
    echo 'ERROR: maintenance isolation verification failed before restore.' >&2
    return 1
  fi

  if ! atlas_restore_stop_writers; then
    atlas_restore_cleanup_before_mutation "$identifier" || true
    return 1
  fi

  if ! atlas_restore_create_pre_restore_recovery_point "$identifier"; then
    atlas_restore_cleanup_before_mutation "$identifier" || true
    return 1
  fi
  recovery_point="$ATLAS_RESTORE_RECOVERY_POINT"

  if ! atlas_restore_preserve_recovery_point "$identifier" "$recovery_point"; then
    atlas_restore_cleanup_before_mutation "$identifier" || true
    return 1
  fi

  if ! atlas_backup_recovery_apply_staged_state "$requested" "$transaction"; then
    if [[ -d "$transaction" ]]; then
      atlas_restore_attach_recovery_point "$identifier" "$transaction" || true
      atlas_restore_write_transaction_metadata \
        "$transaction" "$identifier" "$baseline_record" \
        "$requested" "$staged_digest" || true
    fi
    atlas_restore_start_writers >/dev/null 2>&1 || true
    atlas_restore_wait_for_writers >/dev/null 2>&1 || true
    atlas_restore_report_held_failure \
      "$identifier" 'transactional state application failed.'
    return 1
  fi

  atlas_restore_attach_recovery_point "$identifier" "$transaction" || {
    atlas_restore_report_held_failure \
      "$identifier" 'unable to attach the pre-restore recovery point.'
    return 1
  }
  atlas_restore_write_transaction_metadata \
    "$transaction" "$identifier" "$baseline_record" \
    "$requested" "$staged_digest" || {
      atlas_restore_report_held_failure \
        "$identifier" 'unable to record restore transaction metadata.'
      return 1
    }

  if ! atlas_restore_validate_live_consumers; then
    if atlas_backup_recovery_revert_applied_state "$transaction"; then
      atlas_restore_start_writers >/dev/null 2>&1 || true
      atlas_restore_wait_for_writers >/dev/null 2>&1 || true
    fi
    atlas_restore_report_held_failure \
      "$identifier" 'restored live state failed consumer validation.'
    return 1
  fi

  atlas_restore_complete_applied_transaction "$identifier" "$transaction"
}

atlas_restore_require_held_transaction() {
  local identifier="$1"
  local transaction status

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid restore transaction identifier.' >&2
    return 2
  }
  atlas_deployment_validate_source || return 1
  transaction="$(atlas_restore_transaction_root "$identifier")" || return 1
  [[ -d "$transaction" && ! -L "$transaction" && -f "$transaction/status" ]] || {
    echo 'ERROR: restore transaction is unavailable.' >&2
    return 1
  }
  atlas_deployment_lock_matches "$identifier" || {
    echo 'ERROR: restore transaction does not own the shared deployment lock.' >&2
    return 1
  }
  [[ -f "$(atlas_maintenance_flag)" ]] || {
    echo 'ERROR: held restore recovery requires maintenance mode.' >&2
    return 1
  }
  status="$(<"$transaction/status")"
  case "$status" in
    applied-awaiting-verification|reverted)
      ;;
    *)
      printf 'ERROR: restore transaction is not recoverable from status: %s\n' \
        "$status" >&2
      return 1
      ;;
  esac
  atlas_restore_transaction_recovery_point "$identifier" "$transaction" >/dev/null || return 1
  printf '%s\n' "$transaction"
}

atlas_restore_resume_live() {
  local identifier="$1"
  local transaction status

  transaction="$(atlas_restore_require_held_transaction "$identifier")" || return 1
  status="$(<"$transaction/status")"
  [[ "$status" == 'applied-awaiting-verification' ]] || {
    echo 'ERROR: only an applied restore transaction can be resumed.' >&2
    return 1
  }

  atlas_restore_stop_writers || {
    atlas_restore_report_held_failure \
      "$identifier" 'unable to quiesce writers for restore resume.'
    return 1
  }
  atlas_restore_validate_live_consumers || {
    atlas_restore_start_writers >/dev/null 2>&1 || true
    atlas_restore_wait_for_writers >/dev/null 2>&1 || true
    atlas_restore_report_held_failure \
      "$identifier" 'live state remains invalid; resume refused.'
    return 1
  }

  atlas_restore_complete_applied_transaction "$identifier" "$transaction"
}

atlas_restore_abort_live() {
  local identifier="$1"
  local transaction status

  transaction="$(atlas_restore_require_held_transaction "$identifier")" || return 1
  status="$(<"$transaction/status")"

  atlas_restore_stop_writers || {
    atlas_restore_report_held_failure \
      "$identifier" 'unable to quiesce writers for restore abort.'
    return 1
  }

  if [[ "$status" == 'applied-awaiting-verification' ]]; then
    atlas_backup_recovery_revert_applied_state "$transaction" || {
      atlas_restore_report_held_failure \
        "$identifier" 'unable to revert the applied restore state.'
      return 1
    }
  fi

  atlas_restore_validate_live_consumers || {
    atlas_restore_start_writers >/dev/null 2>&1 || true
    atlas_restore_wait_for_writers >/dev/null 2>&1 || true
    atlas_restore_report_held_failure \
      "$identifier" 'reverted live state failed consumer validation.'
    return 1
  }

  atlas_restore_start_writers || {
    atlas_restore_report_held_failure \
      "$identifier" 'reverted restore writers could not start.'
    return 1
  }
  atlas_restore_wait_for_writers || {
    atlas_restore_report_held_failure \
      "$identifier" 'reverted restore writers did not become ready.'
    return 1
  }
  atlas_restore_verify_runtime_boundary || {
    atlas_restore_report_held_failure \
      "$identifier" 'reverted restore failed verification under maintenance.'
    return 1
  }

  atlas_maintenance_disable || {
    atlas_restore_report_held_failure \
      "$identifier" 'unable to reopen public ingress after restore abort.'
    return 1
  }
  if ! atlas_restore_verify_runtime_boundary; then
    atlas_maintenance_enable >/dev/null 2>&1 || true
    atlas_restore_report_held_failure \
      "$identifier" 'public verification failed after restore abort.'
    return 1
  fi

  printf '%s\n' 'aborted' > "$transaction/status"
  atlas_deployment_release_lock "$identifier" || {
    atlas_maintenance_enable >/dev/null 2>&1 || true
    return 1
  }
  printf 'Live restore aborted and previous state retained: %s\n' "$identifier"
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
      [[ "$#" -eq 3 && "${3:-}" == '--confirm-live' ]] || {
        echo 'ERROR: restore apply requires <staging-root> --confirm-live.' >&2
        return 2
      }
      atlas_restore_apply_live "$2"
      ;;
    resume)
      [[ "$#" -eq 3 && "${3:-}" == '--confirm-live' ]] || {
        echo 'ERROR: restore resume requires <restore-id> --confirm-live.' >&2
        return 2
      }
      atlas_restore_resume_live "$2"
      ;;
    abort)
      [[ "$#" -eq 3 && "${3:-}" == '--confirm-live' ]] || {
        echo 'ERROR: restore abort requires <restore-id> --confirm-live.' >&2
        return 2
      }
      atlas_restore_abort_live "$2"
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
