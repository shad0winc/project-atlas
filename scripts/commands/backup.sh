#!/usr/bin/env bash

atlas_command_backup() {
  atlas_print_header

  local backup_dir="$ATLAS_BACKUP_DIR"
  local option="${1:-}"
  local notes="${2:-}"

  mkdir -p "$backup_dir"

  if [[ "$option" == "--list" ]]; then
    echo "Atlas Backups"
    echo

    if ! compgen -G "$backup_dir/atlas-*.tar.gz" >/dev/null; then
      echo "No backups found."
      return 0
    fi

    local file
    while IFS= read -r file; do
      echo "$(basename "$file")"
      tar -xOzf "$file" BACKUP_INFO.txt 2>/dev/null |
        sed 's/^/  /' ||
        echo "  No manifest found"
      echo
    done < <(ls -1t "$backup_dir"/atlas-*.tar.gz)

    return 0
  fi

  if [[ "$option" == "--notes" && -z "$notes" ]]; then
    echo "Usage: atlas backup --notes \"description\""
    return 1
  fi

  local timestamp
  timestamp="$(date +%Y%m%d-%H%M%S-%3N)"

  local backup_file="${backup_dir}/atlas-${timestamp}.tar.gz"
  local partial_file="${backup_file}.partial"
  local manifest
  manifest="$ATLAS_PROJECT_DIR/.atlas-backup-manifest.tmp"

  trap 'rm -f "$manifest" "$partial_file"' RETURN

  cat > "$manifest" <<EOF_MANIFEST
Project Atlas Backup

Created: $(date)
Version: $(cat "$ATLAS_PROJECT_DIR/VERSION")
Branch: $(git -C "$ATLAS_PROJECT_DIR" branch --show-current)
Commit: $(git -C "$ATLAS_PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)

Notes:
${notes:-None}

EOF_MANIFEST

  echo "Creating Atlas backup..."
  echo

  local available_kib

  if available_kib="$(
    df -Pk "$backup_dir" 2>/dev/null |
      awk 'NR == 2 {print $4}'
  )" && [[ "$available_kib" =~ ^[0-9]+$ ]]; then
    echo "Available backup storage: ${available_kib} KiB"
  else
    echo "Available backup storage: unknown"
  fi

  echo

  if ! tar \
    --exclude='.git' \
    --exclude='backups' \
    --transform='s|\.atlas-backup-manifest\.tmp|BACKUP_INFO.txt|' \
    -czf "$partial_file" \
    -C "$ATLAS_PROJECT_DIR" \
    docker-compose.yml \
    docker-compose.sports.yml \
    .env.example \
    VERSION \
    CHARTER.md \
    ROADMAP.md \
    CHANGELOG.md \
    config \
    docs \
    modules \
    scripts \
    .atlas-backup-manifest.tmp
  then
    echo "ERROR: backup archive creation failed; partial artifact removed." >&2
    return 1
  fi

  if ! tar -tzf "$partial_file" >/dev/null 2>&1; then
    echo "ERROR: backup archive validation failed; partial artifact removed." >&2
    return 1
  fi

  if ! mv -- "$partial_file" "$backup_file"; then
    echo "ERROR: backup publication failed; partial artifact removed." >&2
    return 1
  fi

  echo "Backup complete"
  echo
  echo "File:"
  echo "  $backup_file"
  echo
  echo "Size:"
  echo "  $(du -h "$backup_file" | awk '{print $1}')"
  echo
  echo "Retention:"
  echo "  Keeping newest 10 backups"

  ls -1t "$backup_dir"/atlas-*.tar.gz 2>/dev/null |
    tail -n +11 |
    xargs -r rm -f

  echo
  echo "Status:"
  echo "  SUCCESS"
}
