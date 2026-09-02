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

atlas_update_validate_build_context_permissions() {
  local path
  local absolute
  local mode
  local other_digit
  local directory
  local directory_absolute
  local directory_mode
  local directory_other_digit
  local count=0

  while IFS= read -r -d '' path; do
    [[ -n "$path" ]] || continue

    absolute="$ATLAS_PROJECT_DIR/$path"

    [[ -e "$absolute" || -L "$absolute" ]] || {
      printf 'ERROR: tracked build-context path is missing: %s\n' \
        "$path" >&2
      return 1
    }

    # Symlink access is governed by the target and parent-directory
    # traversal contract rather than symlink mode bits.
    [[ -L "$absolute" ]] && continue

    [[ -f "$absolute" ]] || continue

    count=$((count + 1))

    mode="$(stat -c '%a' "$absolute")" || return 1
    other_digit="${mode: -1}"

    if (( (10#$other_digit & 4) == 0 )); then
      printf \
        'ERROR: tracked build-context file is not readable by container runtime user: %s (mode=%s)\n' \
        "$path" \
        "$mode" >&2
      return 1
    fi

    directory="$(dirname "$path")"

    while [[ "$directory" != '.' ]]; do
      directory_absolute="$ATLAS_PROJECT_DIR/$directory"

      [[ -d "$directory_absolute" ]] || {
        printf \
          'ERROR: tracked build-context parent directory is missing: %s\n' \
          "$directory" >&2
        return 1
      }

      directory_mode="$(stat -c '%a' "$directory_absolute")" ||
        return 1

      directory_other_digit="${directory_mode: -1}"

      if (( (10#$directory_other_digit & 1) == 0 )); then
        printf \
          'ERROR: tracked build-context directory is not traversable by container runtime user: %s (mode=%s)\n' \
          "$directory" \
          "$directory_mode" >&2
        return 1
      fi

      directory="$(dirname "$directory")"
    done
  done < <(
    git -C "$ATLAS_PROJECT_DIR" \
      ls-files -z -- "$@"
  )

  [[ "$count" -gt 0 ]] || {
    echo 'ERROR: tracked build-context validation selected no regular files.' >&2
    return 1
  }
}

atlas_update_validate_ingress_build_permissions() {
  atlas_update_validate_build_context_permissions \
    apps/api/pyproject.toml \
    apps/api/atlas_api \
    atlas \
    apps/portal \
    modules/sports/Dockerfile.private-api \
    modules/sports/src/private_api.py \
    modules/sports/src/subscriptions.py \
    modules/sports/src/providers
}

atlas_update_core_prepare() {
  docker compose \
    --env-file "$ATLAS_PROJECT_DIR/.env" \
    -f "$ATLAS_PROJECT_DIR/docker-compose.yml" \
    pull ||
    return 1
}

atlas_update_ingress_prepare() {
  local compose_file="$ATLAS_PROJECT_DIR/stack/ingress.yml"

  atlas_update_validate_ingress_build_permissions || {
    echo 'ERROR: ingress build-context permission validation failed.' >&2
    return 1
  }

  docker compose \
    --env-file "$ATLAS_PROJECT_DIR/.env" \
    -f "$compose_file" \
    pull caddy ||
    return 1

  docker compose \
    --env-file "$ATLAS_PROJECT_DIR/.env" \
    -f "$compose_file" \
    build portal api sports-writer ||
    return 1
}

atlas_update_prepare_scope() {
  case "$1" in
    core)
      atlas_update_core_prepare
      ;;
    ingress)
      atlas_update_ingress_prepare
      ;;
    all)
      atlas_update_core_prepare &&
        atlas_update_ingress_prepare
      ;;
  esac
}

atlas_update_verify_compose_images() {
  local compose_file="$1"
  local image
  local count=0

  [[ -f "$compose_file" ]] || {
    printf 'ERROR: target Compose file is missing: %s\n' "$compose_file" >&2
    return 1
  }

  while IFS= read -r image; do
    [[ -n "$image" ]] || continue

    count=$((count + 1))

    if ! docker image inspect "$image" >/dev/null 2>&1; then
      printf 'ERROR: target image is not locally available: %s\n' "$image" >&2
      return 1
    fi
  done < <(
    docker compose \
      --env-file "$ATLAS_PROJECT_DIR/.env" \
      -f "$compose_file" \
      config --images |
      LC_ALL=C sort -u
  )

  [[ "$count" -gt 0 ]] || {
    printf 'ERROR: target Compose image set is empty: %s\n' "$compose_file" >&2
    return 1
  }
}

atlas_update_verify_target_images() {
  local scope="$1"

  case "$scope" in
    core)
      atlas_update_verify_compose_images \
        "$ATLAS_PROJECT_DIR/docker-compose.yml"
      ;;
    ingress)
      atlas_update_verify_compose_images \
        "$ATLAS_PROJECT_DIR/stack/ingress.yml"
      ;;
    all)
      atlas_update_verify_compose_images \
        "$ATLAS_PROJECT_DIR/docker-compose.yml" &&
        atlas_update_verify_compose_images \
          "$ATLAS_PROJECT_DIR/stack/ingress.yml"
      ;;
  esac
}

atlas_update_wait_for_ingress_readiness() {
  local attempts="${ATLAS_UPDATE_READINESS_ATTEMPTS:-18}"
  local interval="${ATLAS_UPDATE_READINESS_INTERVAL_SECONDS:-5}"
  local attempt
  local container
  local state
  local status
  local health
  local pending

  [[ "$attempts" =~ ^[1-9][0-9]*$ ]] || {
    printf \
      'ERROR: ATLAS_UPDATE_READINESS_ATTEMPTS must be a positive integer: %s\n' \
      "$attempts" >&2
    return 1
  }

  [[ "$interval" =~ ^[0-9]+$ ]] || {
    printf \
      'ERROR: ATLAS_UPDATE_READINESS_INTERVAL_SECONDS must be a non-negative integer: %s\n' \
      "$interval" >&2
    return 1
  }

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    pending=0

    for container in \
      atlas-api \
      atlas-portal \
      atlas-caddy
    do
      state="$(
        atlas_update_ingress_container_state "$container"
      )" || {
        printf \
          'ERROR: ingress readiness failed: unable to inspect %s\n' \
          "$container" >&2
        return 1
      }

      IFS='|' read -r status health <<<"$state"

      if [[ "$status" != 'running' ]]; then
        printf \
          'ERROR: ingress readiness failed: %s is not running (status=%s health=%s)\n' \
          "$container" \
          "${status:-missing}" \
          "${health:-missing}" >&2
        return 1
      fi

      case "$health" in
        healthy)
          ;;
        starting)
          pending=1
          ;;
        unhealthy|missing|'')
          printf \
            'ERROR: ingress readiness failed: %s health=%s\n' \
            "$container" \
            "${health:-missing}" >&2
          return 1
          ;;
        *)
          printf \
            'ERROR: ingress readiness failed: %s has unexpected health state=%s\n' \
            "$container" \
            "$health" >&2
          return 1
          ;;
      esac
    done

    if [[ "$pending" -eq 0 ]]; then
      return 0
    fi

    if [[ "$attempt" -ge "$attempts" ]]; then
      printf \
        'ERROR: ingress readiness timed out after %s attempts.\n' \
        "$attempts" >&2
      return 1
    fi

    atlas_update_readiness_sleep "$interval"
  done

  return 1
}

atlas_update_ingress_container_state() {
  local container="$1"

  docker inspect \
    --format \
    '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' \
    "$container" \
    2>/dev/null
}

atlas_update_readiness_sleep() {
  sleep "$1"
}

atlas_update_core_apply() {
  docker compose \
    --env-file "$ATLAS_PROJECT_DIR/.env" \
    -f "$ATLAS_PROJECT_DIR/docker-compose.yml" \
    up -d \
    --no-build \
    --pull never ||
    return 1
}

atlas_update_ingress_apply() {
  local compose_file="$ATLAS_PROJECT_DIR/stack/ingress.yml"

  source "$ATLAS_PROJECT_DIR/scripts/lib/audit-runtime.sh"
  source "$ATLAS_PROJECT_DIR/scripts/lib/identity-writer-runtime.sh"
  source "$ATLAS_PROJECT_DIR/scripts/lib/favorites-runtime.sh"

  atlas_audit_runtime_provision || {
    echo 'ERROR: security audit runtime provisioning failed.' >&2
    return 1
  }

  atlas_identity_writer_runtime_provision || {
    echo 'ERROR: identity writer runtime provisioning failed.' >&2
    return 1
  }

  atlas_favorites_runtime_provision || {
    echo 'ERROR: Favorites runtime provisioning failed.' >&2
    return 1
  }

  docker compose \
    --env-file "$ATLAS_PROJECT_DIR/.env" \
    -f "$compose_file" \
    up -d \
    --no-build \
    --pull never ||
    return 1

  docker restart atlas-caddy >/dev/null || {
    echo 'ERROR: unable to activate Caddy ingress configuration.' >&2
    return 1
  }
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

  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    echo 'Post-update ingress readiness:'

    atlas_update_wait_for_ingress_readiness || {
      echo 'ERROR: ingress readiness failed.' >&2
      return 1
    }
  fi

  echo 'Post-update doctor:'
  atlas_command_doctor || return 1

  echo 'Post-update verify:'
  atlas_command_verify || return 1

  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    echo 'Post-update ingress verification:'
    "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh" || return 1
  fi
}

atlas_update_publish_dashboard_runtime() {
  local scope="$1"

  case "$scope" in
    core)
      return 0
      ;;
    ingress|all)
      ;;
    *)
      printf 'ERROR: unsupported Dashboard runtime publication scope: %s\n' \
        "$scope" >&2
      return 2
      ;;
  esac

  echo 'Post-update Dashboard runtime publication:'

  "$ATLAS_PROJECT_DIR/scripts/atlas-dashboard-runtime.sh" \
    publish-all ||
    return 1
}

atlas_update_latest_backup() {
  ls -1t "$ATLAS_BACKUP_DIR"/atlas-*.tar.gz 2>/dev/null |
    head -n 1
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

  if ! atlas_deployment_prepare_update \
    "$identifier" \
    "$scope" \
    "$previous_record"
  then
    atlas_deployment_release_lock "$identifier"

    echo 'ERROR: pre-update recovery capture failed.' >&2
    return 1
  fi

  echo "Deployment ID: $identifier"
  echo "Atlas deployment scope: $scope"
  echo 'Migration declaration: none'

  if ! atlas_command_doctor; then
    atlas_deployment_set_status \
      "$(atlas_deployment_record_dir "$identifier")" \
      aborted

    atlas_deployment_release_lock "$identifier"

    echo 'ERROR: pre-update doctor failed; runtime was not mutated.' >&2
    return 1
  fi

  # Network acquisition and first-party builds happen before maintenance.
  if ! atlas_update_prepare_scope "$scope"; then
    atlas_deployment_set_status \
      "$(atlas_deployment_record_dir "$identifier")" \
      aborted

    atlas_deployment_release_lock "$identifier"

    echo 'ERROR: target artifact acquisition failed before maintenance.' >&2
    return 1
  fi

  # Every image named by the post-acquisition Compose render must now exist.
  if ! atlas_update_verify_target_images "$scope"; then
    atlas_deployment_set_status \
      "$(atlas_deployment_record_dir "$identifier")" \
      aborted

    atlas_deployment_release_lock "$identifier"

    echo 'ERROR: target image completeness verification failed before maintenance.' >&2
    return 1
  fi

  echo 'Target artifact preflight: PASS'

  if ! atlas_command_maintenance enable; then
    atlas_deployment_set_status \
      "$(atlas_deployment_record_dir "$identifier")" \
      aborted

    atlas_deployment_release_lock "$identifier"

    return 1
  fi

  if ! atlas_command_backup --notes \
    "Pre-update deployment backup for $identifier ($scope)"
  then
    atlas_update_fail_after_maintenance \
      "$identifier" \
      'pre-update backup failed.'

    return 1
  fi

  backup_file="$(atlas_update_latest_backup)" || {
    atlas_update_fail_after_maintenance \
      "$identifier" \
      'backup identity could not be resolved.'

    return 1
  }

  if ! atlas_deployment_record_backup "$identifier" "$backup_file"; then
    atlas_update_fail_after_maintenance \
      "$identifier" \
      'backup validation/recording failed.'

    return 1
  fi

  # Maintenance-window apply is deterministic: no pulls and no builds.
  if ! atlas_update_apply_scope "$scope"; then
    atlas_update_fail_after_maintenance \
      "$identifier" \
      'update apply failed.'

    return 1
  fi

  if ! atlas_update_post_verify "$scope"; then
    atlas_update_fail_after_maintenance \
      "$identifier" \
      'post-update verification failed.'

    return 1
  fi

  if ! atlas_update_publish_dashboard_runtime "$scope"; then
    atlas_update_fail_after_maintenance \
      "$identifier" \
      'Dashboard runtime publication failed.'

    return 1
  fi

  if ! atlas_command_maintenance disable; then
    echo 'ERROR: deployment verified, but maintenance could not be disabled.' >&2
    echo 'Deployment lock remains held for operator recovery.' >&2

    return 1
  fi

  if ! atlas_update_post_verify "$scope"; then
    atlas_command_maintenance enable || true

    atlas_update_fail_after_maintenance \
      "$identifier" \
      'public post-maintenance verification failed.'

    return 1
  fi

  if ! atlas_deployment_complete_update "$identifier"; then
    atlas_command_maintenance enable || true

    atlas_update_fail_after_maintenance \
      "$identifier" \
      'new production baseline capture failed.'

    return 1
  fi

  atlas_deployment_release_lock "$identifier"

  echo "Atlas update complete: $identifier"
  echo 'Rollback assets were not pruned.'
}
