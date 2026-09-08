#!/usr/bin/env bash

ATLAS_SPORTS_RUNTIME_DIR="${ATLAS_SPORTS_RUNTIME_DIR:-/mnt/storage/configs/atlas/runtime/sports}"
ATLAS_SPORTS_RUNTIME_UID="${ATLAS_SPORTS_RUNTIME_UID:-0}"
ATLAS_SPORTS_RUNTIME_GID="${ATLAS_SPORTS_RUNTIME_GID:-20000}"
ATLAS_SPORTS_RUNTIME_MODE="${ATLAS_SPORTS_RUNTIME_MODE:-2770}"
ATLAS_SPORTS_RUNTIME_FILE_GID="${ATLAS_SPORTS_RUNTIME_FILE_GID:-20000}"
ATLAS_SPORTS_RUNTIME_FILE_MODE="${ATLAS_SPORTS_RUNTIME_FILE_MODE:-0660}"

atlas_sports_runtime_resource_pool_file() {
  printf '%s/resource-pool.json\n' "${ATLAS_SPORTS_RUNTIME_DIR%/}"
}

atlas_sports_runtime_resource_pool_lock_file() {
  local resource_pool_file

  resource_pool_file="$(atlas_sports_runtime_resource_pool_file)" || return 1

  printf '%s.lock\n' "$resource_pool_file"
}

atlas_sports_runtime_normalize_directory() {
  local path="$1"
  local uid="$2"
  local gid="$3"
  local mode="$4"

  [[ -n "$path" ]] || return 1

  [[ "$path" == /* ]] || {
    printf \
      'ERROR: Sports runtime path must be absolute: %s\n' \
      "$path" >&2
    return 1
  }

  if [[ -L "$path" ]]; then
    printf \
      'ERROR: Sports runtime path must not be a symlink: %s\n' \
      "$path" >&2
    return 1
  fi

  if [[ -e "$path" && ! -d "$path" ]]; then
    printf \
      'ERROR: Sports runtime path is not a directory: %s\n' \
      "$path" >&2
    return 1
  fi

  install -d \
    -o "$uid" \
    -g "$gid" \
    -m "$mode" \
    "$path" || return 1

  chown \
    "$uid:$gid" \
    "$path" || return 1

  chmod \
    "$mode" \
    "$path" || return 1
}

atlas_sports_runtime_normalize_file() {
  local path="$1"

  [[ -n "$path" ]] || return 1

  [[ "$path" == /* ]] || {
    printf \
      'ERROR: Sports runtime file path must be absolute: %s\n' \
      "$path" >&2
    return 1
  }

  if [[ -L "$path" ]]; then
    printf \
      'ERROR: Sports runtime file must not be a symlink: %s\n' \
      "$path" >&2
    return 1
  fi

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  [[ -f "$path" ]] || {
    printf \
      'ERROR: Sports runtime file path is not a file: %s\n' \
      "$path" >&2
    return 1
  }

  # Preserve the current owner. The API may legitimately replace these files
  # as its non-root runtime user. The stable cross-process contract is the
  # Atlas Sports runtime group plus the exact private group-writable mode.
  chgrp \
    "$ATLAS_SPORTS_RUNTIME_FILE_GID" \
    "$path" || return 1

  chmod \
    "$ATLAS_SPORTS_RUNTIME_FILE_MODE" \
    "$path" || return 1
}

atlas_sports_runtime_verify_directory() {
  local path="$1"
  local expected_uid="$2"
  local expected_gid="$3"
  local expected_mode="$4"
  local actual_uid
  local actual_gid
  local actual_mode

  [[ -d "$path" && ! -L "$path" ]] || {
    printf \
      'ERROR: Sports runtime directory is unavailable: %s\n' \
      "$path" >&2
    return 1
  }

  actual_uid="$(stat -c '%u' "$path")" || return 1
  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1

  [[ "$actual_uid" == "$expected_uid" ]] || {
    printf \
      'ERROR: Sports runtime uid mismatch for %s: expected %s, got %s.\n' \
      "$path" "$expected_uid" "$actual_uid" >&2
    return 1
  }

  [[ "$actual_gid" == "$expected_gid" ]] || {
    printf \
      'ERROR: Sports runtime gid mismatch for %s: expected %s, got %s.\n' \
      "$path" "$expected_gid" "$actual_gid" >&2
    return 1
  }

  [[ "$actual_mode" == "$expected_mode" ]] || {
    printf \
      'ERROR: Sports runtime mode mismatch for %s: expected %s, got %s.\n' \
      "$path" "$expected_mode" "$actual_mode" >&2
    return 1
  }
}

atlas_sports_runtime_verify_file() {
  local path="$1"
  local expected_gid="$2"
  local expected_mode="$3"
  local actual_gid
  local actual_mode
  local normalized_expected_mode

  if [[ -L "$path" ]]; then
    printf \
      'ERROR: Sports runtime file must not be a symlink: %s\n' \
      "$path" >&2
    return 1
  fi

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  [[ -f "$path" ]] || {
    printf \
      'ERROR: Sports runtime file path is not a file: %s\n' \
      "$path" >&2
    return 1
  }

  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1

  normalized_expected_mode="$(
    printf '%o\n' "$((8#$expected_mode))"
  )" || return 1

  [[ "$actual_gid" == "$expected_gid" ]] || {
    printf \
      'ERROR: Sports runtime file gid mismatch for %s: expected %s, got %s.\n' \
      "$path" "$expected_gid" "$actual_gid" >&2
    return 1
  }

  [[ "$actual_mode" == "$normalized_expected_mode" ]] || {
    printf \
      'ERROR: Sports runtime file mode mismatch for %s: expected %s, got %s.\n' \
      "$path" "$normalized_expected_mode" "$actual_mode" >&2
    return 1
  }
}

atlas_sports_runtime_verify() {
  local resource_pool_file
  local resource_pool_lock_file

  resource_pool_file="$(atlas_sports_runtime_resource_pool_file)" || return 1
  resource_pool_lock_file="$(atlas_sports_runtime_resource_pool_lock_file)" || return 1

  atlas_sports_runtime_verify_directory \
    "$ATLAS_SPORTS_RUNTIME_DIR" \
    "$ATLAS_SPORTS_RUNTIME_UID" \
    "$ATLAS_SPORTS_RUNTIME_GID" \
    "$ATLAS_SPORTS_RUNTIME_MODE" || return 1

  atlas_sports_runtime_verify_file \
    "$resource_pool_file" \
    "$ATLAS_SPORTS_RUNTIME_FILE_GID" \
    "$ATLAS_SPORTS_RUNTIME_FILE_MODE" || return 1

  atlas_sports_runtime_verify_file \
    "$resource_pool_lock_file" \
    "$ATLAS_SPORTS_RUNTIME_FILE_GID" \
    "$ATLAS_SPORTS_RUNTIME_FILE_MODE"
}

atlas_sports_runtime_provision() {
  local resource_pool_file
  local resource_pool_lock_file

  resource_pool_file="$(atlas_sports_runtime_resource_pool_file)" || return 1
  resource_pool_lock_file="$(atlas_sports_runtime_resource_pool_lock_file)" || return 1

  atlas_sports_runtime_normalize_directory \
    "$ATLAS_SPORTS_RUNTIME_DIR" \
    "$ATLAS_SPORTS_RUNTIME_UID" \
    "$ATLAS_SPORTS_RUNTIME_GID" \
    "$ATLAS_SPORTS_RUNTIME_MODE" || return 1

  atlas_sports_runtime_normalize_file \
    "$resource_pool_file" || return 1

  atlas_sports_runtime_normalize_file \
    "$resource_pool_lock_file" || return 1

  atlas_sports_runtime_verify
}
