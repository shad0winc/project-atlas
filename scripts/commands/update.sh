#!/usr/bin/env bash

atlas_update_lock_directory() {
  printf '%s\n' "${ATLAS_DEPLOYMENT_LOCK_DIR:-$ATLAS_RUNTIME_CONFIG_DIR/deployments/update.lock}"
}

atlas_update_validate_scope() {
  case "$1" in
    core|ingress|all)
      return 0
      ;;
    *)
      printf 'ERROR: unsupported update scope: %s\n' "$1" >&2
      echo 'Usage: atlas update [core|ingress|all]' >&2
      return 2
      ;;
  esac
}

atlas_update_validate_source() {
  local branch
  local head
  local origin_main

  branch="$(git -C "$ATLAS_PROJECT_DIR" branch --show-current)" || return 1

  if [[ "$branch" != 'main' ]]; then
    printf 'ERROR: production updates require main; current branch is %s.\n' \
      "${branch:-detached}" >&2
    return 1
  fi

  if [[ -n "$(git -C "$ATLAS_PROJECT_DIR" status --porcelain)" ]]; then
    echo 'ERROR: production updates require a clean working tree.' >&2
    return 1
  fi

  head="$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)" || return 1
  origin_main="$(git -C "$ATLAS_PROJECT_DIR" rev-parse origin/main)" || {
    echo 'ERROR: origin/main cannot be resolved.' >&2
    return 1
  }

  if [[ "$head" != "$origin_main" ]]; then
    echo 'ERROR: local main must exactly match origin/main before deployment.' >&2
    return 1
  fi

  return 0
}

atlas_update_acquire_lock() {
  local lock_dir
  lock_dir="$(atlas_update_lock_directory)"

  mkdir -p "$(dirname "$lock_dir")"

  if ! mkdir "$lock_dir" 2>/dev/null; then
    printf 'ERROR: deployment lock already exists: %s\n' "$lock_dir" >&2
    echo 'Inspect the existing deployment before attempting recovery.' >&2
    return 1
  fi

  {
    printf 'pid=%s\n' "$$"
    printf 'started_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'commit=%s\n' "$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)"
  } > "$lock_dir/owner"
}

atlas_update_release_lock() {
  local lock_dir
  lock_dir="$(atlas_update_lock_directory)"
  rm -f -- "$lock_dir/owner"
  rmdir -- "$lock_dir"
}

atlas_update_core_apply() {
  docker compose \
    -f "$ATLAS_PROJECT_DIR/docker-compose.yml" \
    pull || return 1

  docker compose \
    -f "$ATLAS_PROJECT_DIR/docker-compose.yml" \
    up -d || return 1
}

atlas_update_ingress_apply() {
  local compose_file="$ATLAS_PROJECT_DIR/stack/ingress.yml"

  docker compose -f "$compose_file" pull caddy || return 1
  docker compose -f "$compose_file" build portal api || return 1
  docker compose -f "$compose_file" up -d || return 1
}

atlas_update_apply_scope() {
  local scope="$1"

  case "$scope" in
    core)
      atlas_update_core_apply
      ;;
    ingress)
      atlas_update_ingress_apply
      ;;
    all)
      atlas_update_core_apply && atlas_update_ingress_apply
      ;;
  esac
}

atlas_update_post_verify() {
  local scope="$1"

  echo 'Post-update doctor:'
  atlas_command_doctor || return 1

  echo
  echo 'Post-update verify:'
  atlas_command_verify || return 1

  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    echo
    echo 'Post-update ingress verification:'
    "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh" || return 1
  fi
}

atlas_update_failure() {
  local message="$1"

  printf 'ERROR: %s\n' "$message" >&2
  echo 'Maintenance mode remains enabled.' >&2
  echo 'Deployment lock remains held for explicit recovery.' >&2
  return 1
}

atlas_command_update() {
  local scope="${1:-core}"
  local commit

  atlas_print_header

  atlas_update_validate_scope "$scope" || return $?

  echo "Atlas deployment scope: $scope"
  echo

  if ! atlas_update_validate_source; then
    echo 'ERROR: deployment source gate failed before runtime mutation.' >&2
    return 1
  fi

  commit="$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)"

  if ! atlas_update_acquire_lock; then
    return 1
  fi

  echo 'Pre-update doctor:'
  if ! atlas_command_doctor; then
    atlas_update_release_lock
    echo 'ERROR: pre-update doctor failed; runtime was not mutated.' >&2
    return 1
  fi

  echo
  echo 'Enabling maintenance mode...'
  if ! atlas_command_maintenance enable; then
    atlas_update_release_lock
    echo 'ERROR: maintenance mode could not be enabled.' >&2
    return 1
  fi

  echo
  echo 'Creating required pre-update backup...'
  if ! atlas_command_backup \
    --notes \
    "Pre-update deployment backup for ${commit} (${scope})"
  then
    atlas_update_failure 'pre-update backup failed; deployment stopped.'
    return 1
  fi

  echo
  echo 'Applying approved update...'
  if ! atlas_update_apply_scope "$scope"; then
    atlas_update_failure 'update apply failed.'
    return 1
  fi

  echo
  if ! atlas_update_post_verify "$scope"; then
    atlas_update_failure 'post-update verification failed.'
    return 1
  fi

  echo
  echo 'Disabling maintenance mode...'
  if ! atlas_command_maintenance disable; then
    atlas_update_failure 'verification passed but maintenance disable failed.'
    return 1
  fi

  atlas_update_release_lock

  echo
  echo 'Atlas update complete.'
  echo 'Rollback assets were not pruned.'
}
