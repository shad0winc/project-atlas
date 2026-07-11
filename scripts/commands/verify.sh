#!/usr/bin/env bash

atlas_command_verify() {
  atlas_print_header
  echo "Atlas Verification"
  echo

  local pass=true

  check() {
    local label="$1"
    shift

    if "$@" >/dev/null 2>&1; then
      atlas_ok "$label"
    else
      atlas_fail "$label"
      pass=false
    fi
  }

  atlas_section "Infrastructure"
  check "Docker Engine" docker info
  check "Docker Compose" docker compose version
  check "Project Directory" test -d "$ATLAS_PROJECT_DIR"
  check "Storage Mounted" test -d "$ATLAS_STORAGE_ROOT"
  check "Intel GPU Available" test -e /dev/dri/renderD128

  echo
  atlas_section "Core Services"

  local service
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
    check "$service running" \
      sh -c "docker ps --format '{{.Names}}' | grep -qx '$service'"
  done

  echo
  atlas_section "Storage Paths"

  local path
  for path in \
    "$ATLAS_MEDIA_ROOT/Movies" \
    "$ATLAS_MEDIA_ROOT/TV" \
    "$ATLAS_MEDIA_ROOT/Anime Movies" \
    "$ATLAS_MEDIA_ROOT/Anime TV" \
    "$ATLAS_DOWNLOADS_ROOT"
  do
    check "$path writable" \
      sh -c "touch '$path/.atlas-test' && rm '$path/.atlas-test'"
  done

  echo
  atlas_section "Project Files"

  local file
  for file in \
    VERSION \
    CHARTER.md \
    ROADMAP.md \
    CHANGELOG.md \
    docs/BUILD_LOG.md \
    docs/MATURITY.md \
    docs/INDEXERS.md
  do
    check "$file present" test -e "$ATLAS_PROJECT_DIR/$file"
  done

  echo
  atlas_section "VPN"

  check "Gluetun running" \
    sh -c "docker ps --format '{{.Names}}' | grep -qx gluetun"

  check "qBittorrent reachable through VPN namespace" \
    docker exec qbittorrent sh -c \
      "curl -s ifconfig.io || wget -qO- ifconfig.io"

  echo

  if [[ "$pass" == true ]]; then
    echo "Overall Status: PASS"
  else
    echo "Overall Status: FAIL"
    return 1
  fi
}
