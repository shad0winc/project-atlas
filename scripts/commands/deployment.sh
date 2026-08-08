#!/usr/bin/env bash

atlas_deployment_root() {
  printf '%s\n' "${ATLAS_DEPLOYMENT_DIR:-$ATLAS_RUNTIME_CONFIG_DIR/deployments}"
}

atlas_deployment_records_dir() {
  printf '%s/records\n' "$(atlas_deployment_root)"
}

atlas_deployment_current_file() {
  printf '%s/current\n' "$(atlas_deployment_root)"
}

atlas_deployment_lock_dir() {
  printf '%s/update.lock\n' "$(atlas_deployment_root)"
}

atlas_deployment_valid_id() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]
}

atlas_deployment_record_dir() {
  local identifier="$1"
  atlas_deployment_valid_id "$identifier" || return 1
  printf '%s/%s\n' "$(atlas_deployment_records_dir)" "$identifier"
}

atlas_deployment_record_value() {
  local record="$1"
  local key="$2"
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' \
    "$record/metadata"
}

atlas_deployment_set_status() {
  local record="$1"
  local status="$2"
  local temporary
  temporary="$(mktemp "$record/.status.XXXXXX")"
  printf '%s\n' "$status" > "$temporary"
  mv -f -- "$temporary" "$record/status"
}

atlas_deployment_set_current() {
  local identifier="$1"
  local root
  local temporary

  atlas_deployment_valid_id "$identifier" || return 1
  root="$(atlas_deployment_root)"
  mkdir -p "$root"
  temporary="$(mktemp "$root/.current.XXXXXX")"
  printf '%s\n' "$identifier" > "$temporary"
  mv -f -- "$temporary" "$(atlas_deployment_current_file)"
}

atlas_deployment_current_id() {
  local file
  local identifier
  file="$(atlas_deployment_current_file)"
  [[ -f "$file" ]] || return 1
  IFS= read -r identifier < "$file"
  atlas_deployment_valid_id "$identifier" || return 1
  printf '%s\n' "$identifier"
}

atlas_deployment_validate_source() {
  local branch
  local head
  local origin_main

  branch="$(git -C "$ATLAS_PROJECT_DIR" branch --show-current)" || return 1
  [[ "$branch" == 'main' ]] || {
    printf 'ERROR: production deployments require main; current branch is %s.\n' \
      "${branch:-detached}" >&2
    return 1
  }

  [[ -z "$(git -C "$ATLAS_PROJECT_DIR" status --porcelain)" ]] || {
    echo 'ERROR: production deployment requires a clean working tree.' >&2
    return 1
  }

  head="$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)" || return 1
  origin_main="$(git -C "$ATLAS_PROJECT_DIR" rev-parse origin/main)" || return 1
  [[ "$head" == "$origin_main" ]] || {
    echo 'ERROR: local main must exactly match origin/main before deployment.' >&2
    return 1
  }
}

atlas_deployment_acquire_lock() {
  local identifier="$1"
  local lock

  atlas_deployment_valid_id "$identifier" || return 1
  lock="$(atlas_deployment_lock_dir)"
  mkdir -p "$(dirname "$lock")"

  if ! mkdir "$lock" 2>/dev/null; then
    printf 'ERROR: deployment lock already exists: %s\n' "$lock" >&2
    return 1
  fi

  {
    printf 'deployment_id=%s\n' "$identifier"
    printf 'pid=%s\n' "$$"
    printf 'started_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$lock/owner"
}

atlas_deployment_lock_matches() {
  local identifier="$1"
  local owner="$(atlas_deployment_lock_dir)/owner"
  [[ -f "$owner" ]] || return 1
  grep -Fxq -- "deployment_id=$identifier" "$owner"
}

atlas_deployment_release_lock() {
  local identifier="$1"
  local lock
  lock="$(atlas_deployment_lock_dir)"
  atlas_deployment_lock_matches "$identifier" || {
    echo 'ERROR: refusing to release a deployment lock owned by another operation.' >&2
    return 1
  }
  rm -f -- "$lock/owner"
  rmdir -- "$lock"
}

atlas_deployment_archive_source() {
  local commit="$1"
  local output="$2"
  local temporary="${output}.partial"

  git -C "$ATLAS_PROJECT_DIR" archive \
    --format=tar.gz \
    --output="$temporary" \
    "$commit" || return 1

  tar -tzf "$temporary" >/dev/null 2>&1 || {
    rm -f -- "$temporary"
    return 1
  }

  mv -f -- "$temporary" "$output"
}

atlas_deployment_capture_images() {
  local record="$1"
  local output="$record/images.tsv"
  local temporary="$record/.images.tsv.partial"
  local surface
  local compose_relative
  local compose_file
  local identifiers
  local container
  local details

  : > "$temporary"

  while IFS='|' read -r surface compose_relative; do
    compose_file="$ATLAS_PROJECT_DIR/$compose_relative"
    [[ -f "$compose_file" ]] || return 1

    identifiers="$(docker compose -f "$compose_file" ps -q)" || return 1
    [[ -n "${identifiers//[[:space:]]/}" ]] || return 1

    while IFS= read -r container; do
      [[ -n "$container" ]] || continue
      details="$(docker inspect --format \
        '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.Name}}|{{.Config.Image}}|{{.Image}}' \
        "$container")" || return 1
      printf '%s|%s|%s\n' "$surface" "$compose_relative" "$details" \
        >> "$temporary"
    done <<< "$identifiers"
  done <<'SURFACES'
core|docker-compose.yml
ingress|stack/ingress.yml
SURFACES

  [[ -s "$temporary" ]] || return 1
  mv -f -- "$temporary" "$output"
}

atlas_deployment_verify_runtime() {
  local record="$1"
  local surface
  local compose_relative
  local project
  local service
  local container_name
  local image_reference
  local expected_image
  local actual_image

  [[ -s "$record/images.tsv" ]] || return 1

  while IFS='|' read -r \
    surface compose_relative project service container_name image_reference expected_image
  do
    [[ -n "$container_name" && -n "$expected_image" ]] || return 1
    actual_image="$(docker inspect --format '{{.Image}}' "$container_name")" || return 1
    [[ "$actual_image" == "$expected_image" ]] || {
      printf 'ERROR: runtime drift detected for %s (%s).\n' \
        "$service" "$container_name" >&2
      return 1
    }
  done < "$record/images.tsv"
}

atlas_deployment_create_source_pair() {
  local record="$1"
  local commit="$2"
  atlas_deployment_archive_source "$commit" "$record/core-source.tar.gz" || return 1
  cp -- "$record/core-source.tar.gz" "$record/ingress-source.tar.gz"
}

atlas_deployment_require_current_record() {
  local identifier
  local record
  identifier="$(atlas_deployment_current_id)" || {
    echo 'ERROR: no verified production deployment baseline exists.' >&2
    return 1
  }
  record="$(atlas_deployment_record_dir "$identifier")" || return 1
  [[ -f "$record/status" && "$(<"$record/status")" == 'verified' ]] || {
    echo 'ERROR: current deployment baseline is not verified.' >&2
    return 1
  }
  [[ -s "$record/core-source.tar.gz" ]] || return 1
  [[ -s "$record/ingress-source.tar.gz" ]] || return 1
  [[ -s "$record/images.tsv" ]] || return 1
  printf '%s\n' "$record"
}

atlas_deployment_new_id() {
  local kind="$1"
  printf '%s-%s-%s\n' "$kind" "$(date -u +%Y%m%dT%H%M%SZ)" "$$"
}

atlas_deployment_baseline() {
  local identifier
  local record
  local commit

  atlas_deployment_validate_source || return 1

  echo 'Baseline doctor:'
  atlas_command_doctor || return 1
  echo 'Baseline verify:'
  atlas_command_verify || return 1
  echo 'Baseline ingress verification:'
  "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh" || return 1

  identifier="$(atlas_deployment_new_id baseline)"
  record="$(atlas_deployment_record_dir "$identifier")"
  mkdir -p "$record"
  commit="$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)"

  cat > "$record/metadata" <<EOF
type=baseline
deployment_id=$identifier
source_commit=$commit
core_commit=$commit
ingress_commit=$commit
scope=all
migration=none
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  atlas_deployment_create_source_pair "$record" "$commit" || return 1
  atlas_deployment_capture_images "$record" || return 1
  atlas_deployment_verify_runtime "$record" || return 1
  atlas_deployment_set_status "$record" verified
  atlas_deployment_set_current "$identifier"

  printf 'Verified production baseline: %s\n' "$identifier"
}

atlas_deployment_prepare_update() {
  local identifier="$1"
  local scope="$2"
  local previous_record="$3"
  local record
  local target_commit
  local previous_id
  local core_commit
  local ingress_commit

  record="$(atlas_deployment_record_dir "$identifier")" || return 1
  mkdir -p "$record"
  target_commit="$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)"
  previous_id="$(basename "$previous_record")"
  core_commit="$(atlas_deployment_record_value "$previous_record" core_commit)"
  ingress_commit="$(atlas_deployment_record_value "$previous_record" ingress_commit)"

  case "$scope" in
    core)
      core_commit="$target_commit"
      ;;
    ingress)
      ingress_commit="$target_commit"
      ;;
    all)
      core_commit="$target_commit"
      ingress_commit="$target_commit"
      ;;
  esac

  cat > "$record/metadata" <<EOF
type=update
deployment_id=$identifier
previous_baseline=$previous_id
target_commit=$target_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
scope=$scope
migration=none
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  cp -- "$previous_record/images.tsv" "$record/pre-images.tsv"

  if [[ "$scope" == 'core' || "$scope" == 'all' ]]; then
    atlas_deployment_archive_source "$target_commit" "$record/core-source.tar.gz" || return 1
  else
    cp -- "$previous_record/core-source.tar.gz" "$record/core-source.tar.gz"
  fi

  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    atlas_deployment_archive_source "$target_commit" "$record/ingress-source.tar.gz" || return 1
  else
    cp -- "$previous_record/ingress-source.tar.gz" "$record/ingress-source.tar.gz"
  fi

  atlas_deployment_set_status "$record" prepared
}

atlas_deployment_record_backup() {
  local identifier="$1"
  local backup_file="$2"
  local record
  record="$(atlas_deployment_record_dir "$identifier")" || return 1
  [[ -f "$backup_file" ]] || return 1
  tar -tzf "$backup_file" >/dev/null 2>&1 || return 1
  printf '%s\n' "$backup_file" > "$record/backup_file"
}

atlas_deployment_complete_update() {
  local identifier="$1"
  local record
  record="$(atlas_deployment_record_dir "$identifier")" || return 1
  atlas_deployment_capture_images "$record" || return 1
  atlas_deployment_verify_runtime "$record" || return 1
  atlas_deployment_set_status "$record" verified
  atlas_deployment_set_current "$identifier"
}

atlas_deployment_status() {
  local identifier
  local record
  if ! identifier="$(atlas_deployment_current_id)"; then
    echo 'Verified production baseline: none'
    return 0
  fi
  record="$(atlas_deployment_record_dir "$identifier")"
  printf 'Verified production baseline: %s\n' "$identifier"
  printf 'Status: %s\n' "$(<"$record/status")"
  printf 'Core source: %s\n' "$(atlas_deployment_record_value "$record" core_commit)"
  printf 'Ingress source: %s\n' "$(atlas_deployment_record_value "$record" ingress_commit)"
}

atlas_deployment_restore_surface() {
  local baseline="$1"
  local transaction="$2"
  local surface="$3"
  local recovery
  local archive="$baseline/${surface}-source.tar.gz"
  local row
  local compose_relative
  local project
  local service
  local container_name
  local image_reference
  local image_id

  [[ -s "$archive" ]] || return 1
  recovery="$(mktemp -d "$transaction/recovery-${surface}.XXXXXX")"
  tar -xzf "$archive" -C "$recovery" || return 1

  if [[ -f "$ATLAS_PROJECT_DIR/.env" && ! -e "$recovery/.env" ]]; then
    ln -s -- "$ATLAS_PROJECT_DIR/.env" "$recovery/.env"
  fi

  while IFS='|' read -r \
    row compose_relative project service container_name image_reference image_id
  do
    [[ "$row" == "$surface" ]] || continue
    docker image inspect "$image_id" >/dev/null 2>&1 || return 1
    docker image tag "$image_id" "$image_reference" || return 1
  done < "$baseline/images.tsv"

  compose_relative="$(awk -F'|' -v surface="$surface" '$1 == surface {print $2; exit}' "$baseline/images.tsv")"
  project="$(awk -F'|' -v surface="$surface" '$1 == surface {print $3; exit}' "$baseline/images.tsv")"
  [[ -n "$compose_relative" && -n "$project" ]] || return 1

  (
    cd "$recovery"
    docker compose \
      --project-name "$project" \
      -f "$recovery/$compose_relative" \
      up -d --no-build --pull never
  )
}

atlas_deployment_rollback() {
  local identifier="$1"
  local transaction
  local previous_id
  local baseline
  local scope
  local migration
  local status
  local current_id
  local backup_file
  local acquired=false

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid deployment identifier.' >&2
    return 2
  }
  atlas_deployment_validate_source || return 1
  transaction="$(atlas_deployment_record_dir "$identifier")" || return 1
  [[ -d "$transaction" && -f "$transaction/metadata" && -f "$transaction/status" ]] || return 1

  status="$(<"$transaction/status")"
  [[ "$status" == 'failed' || "$status" == 'verified' ]] || {
    printf 'ERROR: deployment %s is not rollback-eligible (%s).\n' "$identifier" "$status" >&2
    return 1
  }

  migration="$(atlas_deployment_record_value "$transaction" migration)"
  [[ "$migration" == 'none' ]] || {
    echo 'ERROR: automatic rollback is blocked for state-changing migrations.' >&2
    return 1
  }

  previous_id="$(atlas_deployment_record_value "$transaction" previous_baseline)"
  baseline="$(atlas_deployment_record_dir "$previous_id")" || return 1
  [[ -f "$baseline/status" && "$(<"$baseline/status")" == 'verified' ]] || return 1

  current_id="$(atlas_deployment_current_id)" || return 1
  if [[ "$status" == 'verified' && "$current_id" != "$identifier" ]]; then
    echo 'ERROR: refusing to rollback a deployment that is no longer current.' >&2
    return 1
  fi
  if [[ "$status" == 'failed' && "$current_id" != "$previous_id" ]]; then
    echo 'ERROR: failed deployment no longer points at the current baseline.' >&2
    return 1
  fi

  [[ -f "$transaction/backup_file" ]] || {
    echo 'ERROR: rollback requires the recorded pre-update backup.' >&2
    return 1
  }
  IFS= read -r backup_file < "$transaction/backup_file"
  [[ -f "$backup_file" ]] && tar -tzf "$backup_file" >/dev/null 2>&1 || {
    echo 'ERROR: recorded pre-update backup is unavailable or invalid.' >&2
    return 1
  }

  while IFS='|' read -r _ _ _ _ _ _ image_id; do
    docker image inspect "$image_id" >/dev/null 2>&1 || {
      printf 'ERROR: rollback image unavailable: %s\n' "$image_id" >&2
      return 1
    }
  done < "$baseline/images.tsv"

  if [[ -d "$(atlas_deployment_lock_dir)" ]]; then
    atlas_deployment_lock_matches "$identifier" || {
      echo 'ERROR: another deployment owns the active lock.' >&2
      return 1
    }
  else
    atlas_deployment_acquire_lock "$identifier" || return 1
    acquired=true
  fi

  if ! atlas_command_maintenance enable; then
    [[ "$acquired" == true ]] && atlas_deployment_release_lock "$identifier"
    return 1
  fi

  scope="$(atlas_deployment_record_value "$transaction" scope)"
  case "$scope" in
    core)
      atlas_deployment_restore_surface "$baseline" "$transaction" core || return 1
      ;;
    ingress)
      atlas_deployment_restore_surface "$baseline" "$transaction" ingress || return 1
      ;;
    all)
      atlas_deployment_restore_surface "$baseline" "$transaction" core || return 1
      atlas_deployment_restore_surface "$baseline" "$transaction" ingress || return 1
      ;;
    *)
      return 1
      ;;
  esac

  atlas_command_doctor || return 1
  atlas_command_verify || return 1
  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh" || return 1
  fi

  atlas_deployment_set_current "$previous_id" || return 1
  atlas_deployment_set_status "$transaction" rolled_back || return 1
  atlas_command_maintenance disable || return 1
  atlas_deployment_release_lock "$identifier" || return 1

  printf 'Rollback complete: %s -> %s\n' "$identifier" "$previous_id"
}

atlas_command_deployment() {
  local action="${1:-status}"
  case "$action" in
    status)
      atlas_deployment_status
      ;;
    baseline)
      atlas_deployment_baseline
      ;;
    rollback)
      [[ -n "${2:-}" ]] || {
        echo 'Usage: atlas deployment rollback <deployment-id>' >&2
        return 2
      }
      atlas_deployment_rollback "$2"
      ;;
    help|-h|--help)
      cat <<'HELP'
Usage:
  atlas deployment status
  atlas deployment baseline
  atlas deployment rollback <deployment-id>

Baseline creation records verified production source archives and exact running
image identities. Rollback restores only a directly related known-good baseline.
HELP
      ;;
    *)
      printf 'Unknown deployment action: %s\n' "$action" >&2
      return 2
      ;;
  esac
}
