#!/usr/bin/env bash

atlas_restore_usage() {
  cat <<'HELP'
Usage:
  atlas restore inspect <archive>
  atlas restore verify <archive>
  atlas restore --help

Read-only recovery commands. `inspect` reports archive metadata without
claiming recovery validity. `verify` requires the state-complete recovery
contract, manifest, and checksums to pass. Live restore/apply is intentionally
unavailable until the staged restore transaction is implemented and tested.
HELP
}

atlas_restore_require_archive() {
  local archive="$1"

  [[ -n "$archive" ]] || {
    echo 'ERROR: restore archive path is required.' >&2
    return 2
  }

  [[ -f "$archive" && ! -L "$archive" ]] || {
    printf 'ERROR: restore archive is not a regular file: %s\n' \
      "$archive" >&2
    return 1
  }
}

atlas_restore_inspect() {
  local archive="$1"
  local backup_info recovery_format manifest

  atlas_restore_require_archive "$archive" || return $?

  tar -tzf "$archive" >/dev/null 2>&1 || {
    echo 'ERROR: restore archive is unreadable.' >&2
    return 1
  }

  echo 'Atlas Restore Inspection'
  echo
  printf 'Archive: %s\n' "$archive"
  printf 'Size: %s\n' "$(du -h "$archive" | awk '{print $1}')"
  echo

  if backup_info="$(tar -xOzf "$archive" BACKUP_INFO.txt 2>/dev/null)"; then
    echo 'Backup information:'
    printf '%s\n' "$backup_info" | sed 's/^/  /'
  else
    echo 'Backup information: unavailable'
  fi

  echo

  if recovery_format="$(tar -xOzf "$archive" RECOVERY_FORMAT 2>/dev/null)"; then
    printf 'Recovery format: %s\n' "$recovery_format"
  else
    echo 'Recovery format: legacy/undeclared'
    echo 'Recovery state: configuration-only historical archive'
    echo 'Restore verification: unavailable'
    return 0
  fi

  if manifest="$(tar -xOzf "$archive" RECOVERY_MANIFEST.tsv 2>/dev/null)"; then
    echo
    echo 'Recovery manifest:'
    printf '%s\n' "$manifest" | sed 's/^/  /'
  else
    echo 'Recovery manifest: unavailable'
  fi

  echo
  echo 'Inspection only: archive validity has not been asserted.'
}

atlas_restore_verify() {
  local archive="$1"

  atlas_restore_require_archive "$archive" || return $?

  atlas_backup_recovery_validate_archive "$archive" || {
    echo 'Atlas Restore Verification: FAIL' >&2
    return 1
  }

  echo 'Atlas Restore Verification'
  echo
  printf 'Archive: %s\n' "$archive"
  echo 'Recovery state: state-complete'
  echo 'Restore capability: unverified'
  echo 'Integrity: PASS'
  echo
  echo 'Atlas Restore Verification: PASS'
}

atlas_restore_load_recovery_library() {
  local recovery_library

  if declare -F atlas_backup_recovery_validate_archive >/dev/null; then
    return 0
  fi

  recovery_library="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
  )/lib/backup-recovery.sh"
  source "$recovery_library"
}

atlas_command_restore() {
  atlas_print_header

  local command="${1:-}"

  case "$command" in
    inspect)
      [[ "$#" -eq 2 ]] || {
        echo 'ERROR: restore inspect requires exactly one archive.' >&2
        atlas_restore_usage >&2
        return 2
      }
      atlas_restore_inspect "$2"
      ;;
    verify)
      [[ "$#" -eq 2 ]] || {
        echo 'ERROR: restore verify requires exactly one archive.' >&2
        atlas_restore_usage >&2
        return 2
      }
      atlas_restore_load_recovery_library
      atlas_restore_verify "$2"
      ;;
    --help|-h|help)
      [[ "$#" -eq 1 ]] || {
        echo 'ERROR: restore help does not accept additional arguments.' >&2
        return 2
      }
      atlas_restore_usage
      ;;
    apply)
      echo 'ERROR: live restore apply is not implemented or authorized.' >&2
      echo 'Use: atlas restore inspect <archive>' >&2
      echo '     atlas restore verify <archive>' >&2
      return 2
      ;;
    '')
      atlas_restore_usage >&2
      return 2
      ;;
    *)
      printf 'ERROR: unknown restore command: %s\n' "$command" >&2
      atlas_restore_usage >&2
      return 2
      ;;
  esac
}
