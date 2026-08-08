#!/usr/bin/env bash

atlas_backup_usage() {
  cat <<'HELP'
Usage:
  atlas backup
  atlas backup --notes "description"
  atlas backup --list
  atlas backup --help

Creates an atomic Project Atlas backup with consistency-checked authoritative
state. State completeness and content integrity are validated before publication;
restore verification remains a separate recovery milestone.
HELP
}

atlas_command_backup() {
  atlas_print_header

  local backup_dir="$ATLAS_BACKUP_DIR"
  local option="${1:-}"
  local notes=''

  case "$option" in
    '')
      [[ "$#" -eq 0 ]] || {
        echo 'ERROR: unexpected backup arguments.' >&2
        atlas_backup_usage >&2
        return 2
      }
      ;;
    --notes)
      [[ "$#" -eq 2 && -n "${2:-}" ]] || {
        echo 'ERROR: --notes requires exactly one non-empty description.' >&2
        atlas_backup_usage >&2
        return 2
      }
      notes="$2"
      ;;
    --list)
      [[ "$#" -eq 1 ]] || {
        echo 'ERROR: --list does not accept additional arguments.' >&2
        atlas_backup_usage >&2
        return 2
      }

      echo 'Atlas Backups'
      echo

      if ! compgen -G "$backup_dir/atlas-*.tar.gz" >/dev/null; then
        echo 'No backups found.'
        return 0
      fi

      local file
      while IFS= read -r file; do
        echo "$(basename "$file")"
        tar -xOzf "$file" BACKUP_INFO.txt 2>/dev/null |
          sed 's/^/  /' ||
          echo '  No manifest found'
        echo
      done < <(ls -1t "$backup_dir"/atlas-*.tar.gz)

      return 0
      ;;
    --help|-h)
      [[ "$#" -eq 1 ]] || {
        echo 'ERROR: backup help does not accept additional arguments.' >&2
        atlas_backup_usage >&2
        return 2
      }
      atlas_backup_usage
      return 0
      ;;
    *)
      printf 'ERROR: unknown backup option: %s\n' "$option" >&2
      atlas_backup_usage >&2
      return 2
      ;;
  esac

  # Resolve and validate the canonical recovery-state registry before any
  # backup artifact is created.
  local recovery_library
  recovery_library="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
  )/lib/backup-recovery.sh"
  source "$recovery_library"
  atlas_backup_recovery_validate_registry || return 1

  # Recovery archives can contain identity/configuration information. Protect
  # every subsequently created temporary/final artifact from group/other read.
  local previous_umask
  previous_umask="$(umask)"
  umask 077

  mkdir -p "$backup_dir"

  local snapshot_root
  snapshot_root="$(
    mktemp -d "$backup_dir/.atlas-state-snapshot.XXXXXX"
  )" || {
    echo 'ERROR: unable to create private recovery snapshot directory.' >&2
    return 1
  }
  chmod 0700 "$snapshot_root" || {
    rm -rf -- "$snapshot_root"
    echo 'ERROR: unable to protect recovery snapshot directory.' >&2
    return 1
  }

  local timestamp
  timestamp="$(date +%Y%m%d-%H%M%S-%3N)"

  local backup_file="${backup_dir}/atlas-${timestamp}.tar.gz"
  local partial_file="${backup_file}.partial"
  local manifest="$ATLAS_PROJECT_DIR/.atlas-backup-manifest.tmp"
  local recovery_format="$ATLAS_PROJECT_DIR/.atlas-backup-recovery-format.tmp"
  local recovery_manifest="$ATLAS_PROJECT_DIR/.atlas-backup-recovery-manifest.tmp"
  local recovery_checksums="$ATLAS_PROJECT_DIR/.atlas-backup-recovery-checksums.tmp"
  local cleanup_command

  printf -v cleanup_command \
    'rm -f -- %q %q %q %q %q; rm -rf -- %q; umask %q; trap - RETURN' \
    "$manifest" \
    "$recovery_format" \
    "$recovery_manifest" \
    "$recovery_checksums" \
    "$partial_file" \
    "$snapshot_root" \
    "$previous_umask"
  trap "$cleanup_command" RETURN

  cat > "$manifest" <<EOF_MANIFEST
Project Atlas Backup

Created: $(date)
Version: $(cat "$ATLAS_PROJECT_DIR/VERSION")
Branch: $(git -C "$ATLAS_PROJECT_DIR" branch --show-current)
Commit: $(git -C "$ATLAS_PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)
Recovery format: 1
Recovery state: state-complete
Recovery capability: restore-unverified

Notes:
${notes:-None}

EOF_MANIFEST

  printf '%s\n' '1' > "$recovery_format"

  printf '%s\t%s\t%s\t%s\n' \
    'surface' 'archive_path' 'requirement' 'policy' \
    > "$recovery_manifest"
  printf '%s\t%s\t%s\t%s\n' \
    'project-configuration' '.' 'required' 'configuration-only' \
    >> "$recovery_manifest"

  echo 'Capturing authoritative recovery state...'
  if ! atlas_backup_recovery_snapshot_state "$snapshot_root" \
    >> "$recovery_manifest"
  then
    echo 'ERROR: authoritative recovery-state snapshot failed.' >&2
    return 1
  fi

  atlas_backup_recovery_write_snapshot_checksums \
    "$snapshot_root" "$recovery_checksums" || {
      echo 'ERROR: recovery-state checksum generation failed.' >&2
      return 1
    }

  echo 'Creating Atlas backup...'
  echo

  local available_kib

  if available_kib="$(
    df -Pk "$backup_dir" 2>/dev/null |
      awk 'NR == 2 {print $4}'
  )" && [[ "$available_kib" =~ ^[0-9]+$ ]]; then
    echo "Available backup storage: ${available_kib} KiB"
  else
    echo 'Available backup storage: unknown'
  fi

  echo

  if ! tar \
    --exclude='.git' \
    --exclude='backups' \
    --transform='s|\.atlas-backup-manifest\.tmp|BACKUP_INFO.txt|' \
    --transform='s|\.atlas-backup-recovery-format\.tmp|RECOVERY_FORMAT|' \
    --transform='s|\.atlas-backup-recovery-manifest\.tmp|RECOVERY_MANIFEST.tsv|' \
    --transform='s|\.atlas-backup-recovery-checksums\.tmp|SHA256SUMS|' \
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
    .atlas-backup-manifest.tmp \
    .atlas-backup-recovery-format.tmp \
    .atlas-backup-recovery-manifest.tmp \
    .atlas-backup-recovery-checksums.tmp \
    -C "$snapshot_root" \
    state
  then
    echo 'ERROR: backup archive creation failed; partial artifact removed.' >&2
    return 1
  fi

  chmod 0600 "$partial_file" || {
    echo 'ERROR: unable to protect partial backup artifact.' >&2
    return 1
  }

  if ! tar -tzf "$partial_file" >/dev/null 2>&1; then
    echo 'ERROR: backup archive validation failed; partial artifact removed.' >&2
    return 1
  fi

  if ! atlas_backup_recovery_validate_archive "$partial_file"; then
    echo 'ERROR: state-complete recovery archive validation failed.' >&2
    return 1
  fi

  if ! mv -- "$partial_file" "$backup_file"; then
    echo 'ERROR: backup publication failed; partial artifact removed.' >&2
    return 1
  fi

  chmod 0600 "$backup_file" || {
    rm -f -- "$backup_file"
    echo 'ERROR: unable to protect published backup artifact.' >&2
    return 1
  }

  echo 'Backup complete'
  echo
  echo 'File:'
  echo "  $backup_file"
  echo
  echo 'Size:'
  echo "  $(du -h "$backup_file" | awk '{print $1}')"
  echo
  echo 'Recovery:'
  echo '  Format 1 (state-complete; restore-unverified)'
  echo
  echo 'Retention:'
  echo '  Keeping newest 10 backups'

  ls -1t "$backup_dir"/atlas-*.tar.gz 2>/dev/null |
    tail -n +11 |
    xargs -r rm -f

  echo
  echo 'Status:'
  echo '  SUCCESS'
}
