#!/usr/bin/env bash

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
    "Project Directory" \
    test -d "$ATLAS_PROJECT_DIR"

  atlas_verify_check \
    "Storage Mounted" \
    test -d "$ATLAS_STORAGE_ROOT"

  atlas_verify_check \
    "Intel GPU Available" \
    test -e "$gpu_device"
}

atlas_verify_core_services() {
  local service

  atlas_section "Core Services"

  for service in \
    jellyfin \
    jellyseerr \
    prowlarr \
    sonarr \
    sonarr-anime \
    radarr \
    radarr-anime \
    gluetun \
    qbittorrent \
    homepage
  do
    atlas_verify_check \
      "$service running" \
      sh -c \
      "docker ps --format '{{.Names}}' | grep -qx '$service'"
  done
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
  atlas_verify_infrastructure

  echo
  atlas_verify_core_services

  echo
  atlas_verify_storage_paths

  echo
  atlas_verify_project_files

  echo
  atlas_verify_vpn

  echo

  if [[ "$ATLAS_VERIFY_PASS" == true ]]; then
    echo "Overall Status: PASS"
    return 0
  fi

  echo "Overall Status: FAIL"
  return 1
}
