#!/usr/bin/env bash

atlas_verify_command_directory="$(
  cd "$(dirname "${BASH_SOURCE[0]}")"
  pwd
)"

# shellcheck disable=SC1091
source "$atlas_verify_command_directory/../lib/verifiers.sh"

unset atlas_verify_command_directory

atlas_verify_check() {
  local label="$1"
  shift

  if "$@" >/dev/null 2>&1; then
    atlas_ok "$label"
  else
    atlas_fail "$label"
    ATLAS_VERIFY_PASS=false
  fi
}

atlas_verify_has_value() {
  local variable="$1"
  local value

  if [[ ! -v "$variable" ]]; then
    return 1
  fi

  value="${!variable}"

  [[ -n "${value//[[:space:]]/}" ]]
}

atlas_verify_is_absolute_path() {
  local variable="$1"
  local value

  atlas_verify_has_value "$variable" || return 1

  value="${!variable}"

  [[ "$value" == /* ]]
}

atlas_verify_is_http_url() {
  local variable="$1"
  local value

  atlas_verify_has_value "$variable" || return 1

  value="${!variable}"

  [[ "$value" =~ ^https?://[^[:space:]]+$ ]]
}

atlas_verify_is_positive_integer() {
  local variable="$1"
  local value

  atlas_verify_has_value "$variable" || return 1

  value="${!variable}"

  [[ "$value" =~ ^[1-9][0-9]*$ ]]
}

atlas_verify_path_within() {
  local child_variable="$1"
  local parent_variable="$2"
  local child
  local parent

  atlas_verify_is_absolute_path "$child_variable" || return 1
  atlas_verify_is_absolute_path "$parent_variable" || return 1

  child="${!child_variable}"
  parent="${!parent_variable}"

  [[ "$child" == "$parent" || "$child" == "$parent/"* ]]
}

atlas_verify_directory_exists() {
  local variable="$1"

  atlas_verify_is_absolute_path "$variable" || return 1

  test -d "${!variable}"
}

atlas_verify_directory_writable() {
  local variable="$1"
  local directory
  local probe

  atlas_verify_directory_exists "$variable" || return 1

  directory="${!variable}"

  probe="$(
    mktemp "$directory/.atlas-verify.XXXXXX"
  )" || return 1

  rm -f "$probe"
}

atlas_verify_line_list_contains() {
  local expected="$1"
  local values="$2"

  grep -Fxq -- "$expected" <<<"$values"
}

atlas_verify_configuration() {
  local variable

  atlas_section "Configuration"

  for variable in \
    ATLAS_PROJECT_DIR \
    ATLAS_STORAGE_ROOT \
    ATLAS_MEDIA_ROOT \
    ATLAS_DOWNLOADS_ROOT \
    ATLAS_BACKUP_DIR \
    ATLAS_CONFIG_ROOT \
    ATLAS_RUNTIME_CONFIG_DIR \
    ATLAS_USERS_DIR \
    ATLAS_IDENTITY_DIR \
    ATLAS_ARI_DIR \
    ATLAS_ARI_SNAPSHOT_DIR \
    ATLAS_ARI_LATEST_FILE \
    ATLAS_JELLYFIN_MOVIES_PATH \
    ATLAS_JELLYFIN_TV_PATH \
    ATLAS_JELLYFIN_ANIME_MOVIES_PATH \
    ATLAS_JELLYFIN_ANIME_TV_PATH \
    ATLAS_SCHEDULER_DIR \
    ATLAS_SCHEDULER_STATE_FILE \
    ATLAS_SCHEDULER_LOCK_FILE
  do
    atlas_verify_check \
      "$variable absolute path" \
      atlas_verify_is_absolute_path \
      "$variable"
  done

  for variable in \
    ATLAS_BASE_URL \
    ATLAS_JELLYFIN_URL
  do
    atlas_verify_check \
      "$variable HTTP URL" \
      atlas_verify_is_http_url \
      "$variable"
  done

  atlas_verify_check \
    "ATLAS_INVITE_EXPIRATION_DAYS positive integer" \
    atlas_verify_is_positive_integer \
    ATLAS_INVITE_EXPIRATION_DAYS

  atlas_verify_check \
    "ATLAS_MEDIA_ROOT within ATLAS_STORAGE_ROOT" \
    atlas_verify_path_within \
    ATLAS_MEDIA_ROOT \
    ATLAS_STORAGE_ROOT

  atlas_verify_check \
    "ATLAS_DOWNLOADS_ROOT within ATLAS_STORAGE_ROOT" \
    atlas_verify_path_within \
    ATLAS_DOWNLOADS_ROOT \
    ATLAS_STORAGE_ROOT

  atlas_verify_check \
    "ATLAS_BACKUP_DIR within ATLAS_STORAGE_ROOT" \
    atlas_verify_path_within \
    ATLAS_BACKUP_DIR \
    ATLAS_STORAGE_ROOT

  atlas_verify_check \
    "ATLAS_CONFIG_ROOT within ATLAS_STORAGE_ROOT" \
    atlas_verify_path_within \
    ATLAS_CONFIG_ROOT \
    ATLAS_STORAGE_ROOT

  atlas_verify_check \
    "ATLAS_RUNTIME_CONFIG_DIR within ATLAS_CONFIG_ROOT" \
    atlas_verify_path_within \
    ATLAS_RUNTIME_CONFIG_DIR \
    ATLAS_CONFIG_ROOT

  atlas_verify_check \
    "ATLAS_USERS_DIR within ATLAS_RUNTIME_CONFIG_DIR" \
    atlas_verify_path_within \
    ATLAS_USERS_DIR \
    ATLAS_RUNTIME_CONFIG_DIR

  atlas_verify_check \
    "ATLAS_IDENTITY_DIR within ATLAS_RUNTIME_CONFIG_DIR" \
    atlas_verify_path_within \
    ATLAS_IDENTITY_DIR \
    ATLAS_RUNTIME_CONFIG_DIR

  atlas_verify_check \
    "ATLAS_ARI_DIR within ATLAS_RUNTIME_CONFIG_DIR" \
    atlas_verify_path_within \
    ATLAS_ARI_DIR \
    ATLAS_RUNTIME_CONFIG_DIR

  atlas_verify_check \
    "ATLAS_ARI_SNAPSHOT_DIR within ATLAS_ARI_DIR" \
    atlas_verify_path_within \
    ATLAS_ARI_SNAPSHOT_DIR \
    ATLAS_ARI_DIR

  atlas_verify_check \
    "ATLAS_ARI_LATEST_FILE within ATLAS_ARI_DIR" \
    atlas_verify_path_within \
    ATLAS_ARI_LATEST_FILE \
    ATLAS_ARI_DIR

  atlas_verify_check \
    "ATLAS_SCHEDULER_DIR within ATLAS_RUNTIME_CONFIG_DIR" \
    atlas_verify_path_within \
    ATLAS_SCHEDULER_DIR \
    ATLAS_RUNTIME_CONFIG_DIR

  atlas_verify_check \
    "ATLAS_SCHEDULER_STATE_FILE within ATLAS_SCHEDULER_DIR" \
    atlas_verify_path_within \
    ATLAS_SCHEDULER_STATE_FILE \
    ATLAS_SCHEDULER_DIR

  atlas_verify_check \
    "ATLAS_SCHEDULER_LOCK_FILE within ATLAS_SCHEDULER_DIR" \
    atlas_verify_path_within \
    ATLAS_SCHEDULER_LOCK_FILE \
    ATLAS_SCHEDULER_DIR
}

atlas_verify_runtime_filesystem() {
  local variable

  atlas_section "Runtime Filesystem"

  atlas_verify_check \
    "ATLAS_PROJECT_DIR directory present" \
    atlas_verify_directory_exists \
    ATLAS_PROJECT_DIR

  for variable in \
    ATLAS_STORAGE_ROOT \
    ATLAS_MEDIA_ROOT \
    ATLAS_DOWNLOADS_ROOT \
    ATLAS_BACKUP_DIR \
    ATLAS_CONFIG_ROOT \
    ATLAS_RUNTIME_CONFIG_DIR
  do
    atlas_verify_check \
      "$variable directory present" \
      atlas_verify_directory_exists \
      "$variable"

    atlas_verify_check \
      "$variable directory writable" \
      atlas_verify_directory_writable \
      "$variable"
  done
}

atlas_verify_infrastructure() {
  local gpu_device="${ATLAS_VERIFY_GPU_DEVICE:-/dev/dri/renderD128}"

  atlas_section "Infrastructure"

  atlas_verify_check \
    "Docker Engine" \
    docker info

  atlas_verify_check \
    "Docker Compose" \
    docker compose version

  atlas_verify_check \
    "Intel GPU Available" \
    test -e "$gpu_device"
}

atlas_verify_compose_services() {
  local compose_file
  local configured_services
  local running_services
  local service

  compose_file="${ATLAS_VERIFY_COMPOSE_FILE:-$ATLAS_PROJECT_DIR/docker-compose.yml}"

  atlas_section "Compose Services"

  atlas_verify_check \
    "Compose file present" \
    test -f "$compose_file"

  if ! configured_services="$(
    docker compose \
      -f "$compose_file" \
      config \
      --services
  )"; then
    atlas_fail "Compose service discovery"
    ATLAS_VERIFY_PASS=false
    return
  fi

  if [[ -z "${configured_services//[[:space:]]/}" ]]; then
    atlas_fail "Compose service discovery"
    ATLAS_VERIFY_PASS=false
    return
  fi

  atlas_ok "Compose service discovery"

  if ! running_services="$(
    docker compose \
      -f "$compose_file" \
      ps \
      --status running \
      --services
  )"; then
    atlas_fail "Compose runtime query"
    ATLAS_VERIFY_PASS=false
    return
  fi

  atlas_ok "Compose runtime query"

  while IFS= read -r service; do
    [[ -n "$service" ]] || continue

    atlas_verify_check \
      "$service running" \
      atlas_verify_line_list_contains \
      "$service" \
      "$running_services"
  done <<<"$configured_services"
}

atlas_verify_storage_paths() {
  local path

  atlas_section "Storage Paths"

  for path in \
    "$ATLAS_MEDIA_ROOT/Movies" \
    "$ATLAS_MEDIA_ROOT/TV" \
    "$ATLAS_MEDIA_ROOT/Anime Movies" \
    "$ATLAS_MEDIA_ROOT/Anime TV" \
    "$ATLAS_DOWNLOADS_ROOT"
  do
    atlas_verify_check \
      "$path writable" \
      sh -c \
      "touch '$path/.atlas-test' && rm '$path/.atlas-test'"
  done
}

atlas_verify_project_files() {
  local file

  atlas_section "Project Files"

  for file in \
    VERSION \
    CHARTER.md \
    ROADMAP.md \
    CHANGELOG.md \
    docs/BUILD_LOG.md \
    docs/MATURITY.md \
    docs/INDEXERS.md
  do
    atlas_verify_check \
      "$file present" \
      test -e "$ATLAS_PROJECT_DIR/$file"
  done
}

atlas_verify_ingress() {
  local verifier

  verifier="${ATLAS_VERIFY_INGRESS_VERIFIER:-$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh}"

  atlas_verify_specialized_command \
    "Ingress verification" \
    "$verifier" || true
}

atlas_verify_scheduler() {
  atlas_verify_specialized_output_command \
    "Scheduler registry readiness" \
    "No scheduler tasks registered." \
    atlas_command_scheduler \
    list || true
}

atlas_verify_enabled_modules() {
  local module
  local enabled_count=0

  while IFS= read -r module; do
    [[ -n "$module" ]] || continue

    if ! atlas_module_enabled "$module"; then
      continue
    fi

    enabled_count=$((enabled_count + 1))

    atlas_verify_specialized_command \
      "$module module verification" \
      atlas_command_module \
      verify \
      "$module" || true
  done < <(atlas_module_list)

  if [[ "$enabled_count" -eq 0 ]]; then
    atlas_ok "No enabled modules require verification"
  fi
}

atlas_verify_specialized_verifiers() {
  atlas_section "Specialized Verifiers"

  atlas_verify_ingress

  echo
  atlas_verify_scheduler

  echo
  atlas_verify_enabled_modules
}

atlas_verify_vpn() {
  atlas_section "VPN"

  atlas_verify_check \
    "Gluetun running" \
    sh -c \
    "docker ps --format '{{.Names}}' | grep -qx gluetun"

  atlas_verify_check \
    "qBittorrent reachable through VPN namespace" \
    docker exec \
      qbittorrent \
      sh -c \
      "curl -s ifconfig.io || wget -qO- ifconfig.io"
}

atlas_command_verify() {
  atlas_print_header
  echo "Atlas Verification"
  echo

  ATLAS_VERIFY_PASS=true

  atlas_verify_configuration

  echo
  atlas_verify_runtime_filesystem

  echo
  atlas_verify_infrastructure

  echo
  atlas_verify_compose_services

  echo
  atlas_verify_storage_paths

  echo
  atlas_verify_project_files

  echo
  atlas_verify_vpn

  echo
  atlas_verify_specialized_verifiers

  echo

  if [[ "$ATLAS_VERIFY_PASS" == true ]]; then
    echo "Overall Status: PASS"
    return 0
  fi

  echo "Overall Status: FAIL"
  return 1
}
