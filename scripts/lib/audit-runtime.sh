#!/usr/bin/env bash

ATLAS_AUDIT_RUNTIME_DIR="${ATLAS_AUDIT_RUNTIME_DIR:-/mnt/storage/configs/atlas/runtime}"
ATLAS_AUDIT_JOURNAL="${ATLAS_AUDIT_JOURNAL:-$ATLAS_AUDIT_RUNTIME_DIR/events.jsonl}"

ATLAS_AUDIT_JOURNAL_UID='0'
ATLAS_AUDIT_JOURNAL_GID='20000'
ATLAS_AUDIT_JOURNAL_MODE='660'

atlas_audit_runtime_require_directory() {
  local runtime_dir="$ATLAS_AUDIT_RUNTIME_DIR"

  if [[ -L "$runtime_dir" ]]; then
    printf 'ERROR: audit runtime directory must not be a symbolic link: %s\n' \
      "$runtime_dir" >&2
    return 1
  fi

  if [[ -e "$runtime_dir" && ! -d "$runtime_dir" ]]; then
    printf 'ERROR: audit runtime path is not a directory: %s\n' \
      "$runtime_dir" >&2
    return 1
  fi

  if [[ ! -e "$runtime_dir" ]]; then
    install \
      -d \
      -m 0755 \
      -o 0 \
      -g 0 \
      "$runtime_dir" ||
      return 1
  fi
}

atlas_audit_runtime_require_journal_shape() {
  local journal="$ATLAS_AUDIT_JOURNAL"

  if [[ -L "$journal" ]]; then
    printf 'ERROR: audit journal must not be a symbolic link: %s\n' \
      "$journal" >&2
    return 1
  fi

  if [[ -e "$journal" && ! -f "$journal" ]]; then
    printf 'ERROR: audit journal must be a regular file: %s\n' \
      "$journal" >&2
    return 1
  fi
}

atlas_audit_runtime_provision() {
  local journal="$ATLAS_AUDIT_JOURNAL"

  atlas_audit_runtime_require_directory || return 1
  atlas_audit_runtime_require_journal_shape || return 1

  if [[ ! -e "$journal" ]]; then
    install \
      -m "$ATLAS_AUDIT_JOURNAL_MODE" \
      -o "$ATLAS_AUDIT_JOURNAL_UID" \
      -g "$ATLAS_AUDIT_JOURNAL_GID" \
      /dev/null \
      "$journal" ||
      return 1
  else
    chown \
      "$ATLAS_AUDIT_JOURNAL_UID:$ATLAS_AUDIT_JOURNAL_GID" \
      "$journal" ||
      return 1

    chmod \
      "$ATLAS_AUDIT_JOURNAL_MODE" \
      "$journal" ||
      return 1
  fi

  atlas_audit_runtime_verify
}

atlas_audit_runtime_verify() {
  local journal="$ATLAS_AUDIT_JOURNAL"
  local uid
  local gid
  local mode

  atlas_audit_runtime_require_directory || return 1
  atlas_audit_runtime_require_journal_shape || return 1

  [[ -f "$journal" ]] || {
    printf 'ERROR: audit journal is missing: %s\n' "$journal" >&2
    return 1
  }

  uid="$(stat -c '%u' "$journal")" || return 1
  gid="$(stat -c '%g' "$journal")" || return 1
  mode="$(stat -c '%a' "$journal")" || return 1

  [[ "$uid" == "$ATLAS_AUDIT_JOURNAL_UID" ]] || {
    printf 'ERROR: audit journal owner mismatch (expected=%s actual=%s).\n' \
      "$ATLAS_AUDIT_JOURNAL_UID" "$uid" >&2
    return 1
  }

  [[ "$gid" == "$ATLAS_AUDIT_JOURNAL_GID" ]] || {
    printf 'ERROR: audit journal group mismatch (expected=%s actual=%s).\n' \
      "$ATLAS_AUDIT_JOURNAL_GID" "$gid" >&2
    return 1
  }

  [[ "$mode" == "$ATLAS_AUDIT_JOURNAL_MODE" ]] || {
    printf 'ERROR: audit journal mode mismatch (expected=%s actual=%s).\n' \
      "$ATLAS_AUDIT_JOURNAL_MODE" "$mode" >&2
    return 1
  }
}
