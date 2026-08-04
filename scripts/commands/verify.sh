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
