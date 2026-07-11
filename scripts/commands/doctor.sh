#!/usr/bin/env bash

atlas_command_doctor() {
  atlas_print_header

  echo "Docker:"
  if docker info >/dev/null 2>&1; then
    echo "  OK Docker is running"
  else
    echo "  FAIL Docker is not running"
  fi

  echo
  echo "Git:"
  if git -C "$ATLAS_PROJECT_DIR" diff --quiet &&
     git -C "$ATLAS_PROJECT_DIR" diff --cached --quiet; then
    echo "  OK Working tree clean"
  else
    echo "  WARN Working tree has changes"
  fi

  echo
  echo "VPN:"
  if docker ps --format '{{.Names}}' | grep -qx gluetun; then
    echo "  OK Gluetun container running"
  else
    echo "  FAIL Gluetun container not running"
  fi

  echo
  echo "qBittorrent VPN IP:"
  docker exec qbittorrent sh -c \
    "curl -s ifconfig.io || wget -qO- ifconfig.io" \
    2>/dev/null || echo "  WARN Could not check qBittorrent public IP"

  echo
  echo "Storage writable:"

  local path
  for path in \
    "$ATLAS_MEDIA_ROOT/Movies" \
    "$ATLAS_MEDIA_ROOT/TV" \
    "$ATLAS_MEDIA_ROOT/Anime Movies" \
    "$ATLAS_MEDIA_ROOT/Anime TV" \
    "$ATLAS_DOWNLOADS_ROOT"
  do
    if touch "$path/.atlas-write-test" 2>/dev/null; then
      rm -f "$path/.atlas-write-test"
      echo "  OK $path"
    else
      echo "  FAIL $path"
    fi
  done

  echo
  echo "Project Files:"

  local file
  for file in \
    VERSION \
    CHARTER.md \
    ROADMAP.md \
    CHANGELOG.md \
    docs/BUILD_LOG.md \
    docs/MATURITY.md
  do
    if [[ -e "$ATLAS_PROJECT_DIR/$file" ]]; then
      echo "  OK $file"
    else
      echo "  FAIL $file"
    fi
  done

  local dir
  for dir in \
    docs \
    docs/ADR \
    docs/EDR
  do
    if [[ -d "$ATLAS_PROJECT_DIR/$dir" ]]; then
      echo "  OK $dir"
    else
      echo "  FAIL $dir"
    fi
  done

  echo
  echo "Container status:"
  docker ps --format "  {{.Names}} - {{.Status}}"

  echo
  echo "Modules:"

  local module
  while IFS= read -r module; do
    [[ -n "$module" ]] || continue

    if atlas_module_enabled "$module"; then
      echo "  OK $module enabled"
    else
      echo "  WARN $module disabled"
    fi
  done < <(atlas_module_list)
}
