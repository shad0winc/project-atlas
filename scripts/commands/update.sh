#!/usr/bin/env bash

atlas_update_validate_scope() {
  case "$1" in
    core|ingress|all) return 0 ;;
    *)
      printf 'ERROR: unsupported update scope: %s\n' "$1" >&2
      return 2
      ;;
  esac
}

atlas_update_validate_migration() {
  [[ "${1:-}" == '--migration' && "${2:-}" == 'none' ]] || {
    echo 'ERROR: updates require an explicit "--migration none" declaration.' >&2
    echo 'State-changing migrations require release-specific recovery evidence.' >&2
    return 2
  }
}

atlas_update_core_apply() {
  docker compose -f "$ATLAS_PROJECT_DIR/docker-compose.yml" pull || return 1
  docker compose -f "$ATLAS_PROJECT_DIR/docker-compose.yml" up -d || return 1
}

atlas_update_ingress_apply() {
  local compose_file="$ATLAS_PROJECT_DIR/stack/ingress.yml"
  docker compose -f "$compose_file" pull caddy || return 1
  docker compose -f "$compose_file" build portal api || return 1
  docker compose -f "$compose_file" up -d || return 1
}

atlas_update_apply_scope() {
  case "$1" in
    core) atlas_update_core_apply ;;
    ingress) atlas_update_ingress_apply ;;
    all) atlas_update_core_apply && atlas_update_ingress_apply ;;
  esac
}

atlas_update_post_verify() {
  local scope="$1"
  echo 'Post-update doctor:'
  atlas_command_doctor || return 1
  echo 'Post-update verify:'
  atlas_command_verify || return 1
  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    echo 'Post-update ingress verification:'
    "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh" || return 1
  fi
}

atlas_update_latest_backup() {
  ls -1t "$ATLAS_BACKUP_DIR"/atlas-*.tar.gz 2>/dev/null | head -n 1
}

atlas_update_fail_after_maintenance() {
  local identifier="$1"
  local message="$2"
  local record
  record="$(atlas_deployment_record_dir "$identifier")"
  atlas_deployment_set_status "$record" failed || true
  printf 'ERROR: %s\n' "$message" >&2
  echo 'Maintenance mode remains enabled.' >&2
  echo 'Deployment lock remains held for explicit recovery.' >&2
  printf 'Recovery command: atlas deployment rollback %s\n' "$identifier" >&2
  return 1
}

atlas_command_update() {
  local scope="${1:-}"
  local previous_record
  local identifier
  local backup_file

  atlas_print_header
  [[ -n "$scope" ]] || {
    echo 'Usage: atlas update <core|ingress|all> --migration none' >&2
    return 2
  }
  atlas_update_validate_scope "$scope" || return $?
  atlas_update_validate_migration "${2:-}" "${3:-}" || return $?
  atlas_deployment_validate_source || return 1

  previous_record="$(atlas_deployment_require_current_record)" || return 1
  atlas_deployment_verify_runtime "$previous_record" || {
    echo 'ERROR: production runtime differs from the verified baseline.' >&2
    return 1
  }

  identifier="$(atlas_deployment_new_id update)"
  atlas_deployment_acquire_lock "$identifier" || return 1

  if ! atlas_deployment_prepare_update "$identifier" "$scope" "$previous_record"; then
    atlas_deployment_release_lock "$identifier"
    echo 'ERROR: pre-update recovery capture failed.' >&2
    return 1
  fi

  echo "Deployment ID: $identifier"
  echo "Atlas deployment scope: $scope"
  echo 'Migration declaration: none'

  if ! atlas_command_doctor; then
    atlas_deployment_set_status "$(atlas_deployment_record_dir "$identifier")" aborted
    atlas_deployment_release_lock "$identifier"
    echo 'ERROR: pre-update doctor failed; runtime was not mutated.' >&2
    return 1
  fi

  if ! atlas_command_maintenance enable; then
    atlas_deployment_set_status "$(atlas_deployment_record_dir "$identifier")" aborted
    atlas_deployment_release_lock "$identifier"
    return 1
  fi

  if ! atlas_command_backup --notes \
    "Pre-update deployment backup for $identifier ($scope)"
  then
    atlas_update_fail_after_maintenance "$identifier" 'pre-update backup failed.'
    return 1
  fi

  backup_file="$(atlas_update_latest_backup)" || {
    atlas_update_fail_after_maintenance "$identifier" 'backup identity could not be resolved.'
    return 1
  }
  if ! atlas_deployment_record_backup "$identifier" "$backup_file"; then
    atlas_update_fail_after_maintenance "$identifier" 'backup validation/recording failed.'
    return 1
  fi

  if ! atlas_update_apply_scope "$scope"; then
    atlas_update_fail_after_maintenance "$identifier" 'update apply failed.'
    return 1
  fi

  if ! atlas_update_post_verify "$scope"; then
    atlas_update_fail_after_maintenance "$identifier" 'post-update verification failed.'
    return 1
  fi

  if ! atlas_command_maintenance disable; then
    echo 'ERROR: deployment verified, but maintenance could not be disabled.' >&2
    echo 'Deployment lock remains held for operator recovery.' >&2
    return 1
  fi

  if ! atlas_update_post_verify "$scope"; then
    atlas_command_maintenance enable || true
    atlas_update_fail_after_maintenance "$identifier" \
      'public post-maintenance verification failed.'
    return 1
  fi

  if ! atlas_deployment_complete_update "$identifier"; then
    atlas_command_maintenance enable || true
    atlas_update_fail_after_maintenance "$identifier" \
      'new production baseline capture failed.'
    return 1
  fi

  atlas_deployment_release_lock "$identifier"
  echo "Atlas update complete: $identifier"
  echo 'Rollback assets were not pruned.'
}
