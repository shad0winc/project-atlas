#!/usr/bin/env bash

ATLAS_PASSWORD_RECOVERY_RUNTIME_UID="${ATLAS_PASSWORD_RECOVERY_RUNTIME_UID:-0}"
ATLAS_PASSWORD_RECOVERY_RUNTIME_GID="${ATLAS_PASSWORD_RECOVERY_RUNTIME_GID:-20000}"
ATLAS_PASSWORD_RECOVERY_RUNTIME_MODE="${ATLAS_PASSWORD_RECOVERY_RUNTIME_MODE:-2770}"
ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_GID="${ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_GID:-20000}"
ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_MODE="${ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_MODE:-0640}"

atlas_password_recovery_runtime_dir() {
  local identity_root

  identity_root="$(
    printf '%s\n' \
      "${ATLAS_IDENTITY_DIR:-/mnt/storage/configs/atlas/identity}"
  )"

  printf '%s/password-recovery\n' "${identity_root%/}"
}

atlas_password_recovery_runtime_registry_file() {
  local recovery_dir

  recovery_dir="$(atlas_password_recovery_runtime_dir)" || return 1

  printf '%s/password-recovery.json\n' "${recovery_dir%/}"
}

atlas_password_recovery_runtime_normalize_directory() {
  local path="$1"
  local uid="$2"
  local gid="$3"
  local mode="$4"

  [[ -n "$path" ]] || return 1

  [[ "$path" == /* ]] || {
    printf \
      'ERROR: password recovery runtime path must be absolute: %s\n' \
      "$path" >&2
    return 1
  }

  if [[ -e "$path" && ! -d "$path" ]]; then
    printf \
      'ERROR: password recovery runtime path is not a directory: %s\n' \
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

atlas_password_recovery_runtime_normalize_file() {
  local path="$1"

  [[ -n "$path" ]] || return 1

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  [[ -f "$path" ]] || {
    printf \
      'ERROR: password recovery runtime file path is not a file: %s\n' \
      "$path" >&2
    return 1
  }

  # Preserve the API-created owner while enforcing the canonical Atlas
  # persistence group and private group-readable mode.
  chgrp \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_GID" \
    "$path" || return 1

  chmod \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_MODE" \
    "$path" || return 1
}

atlas_password_recovery_runtime_normalize_state_files() {
  local recovery_dir
  local state_dir
  local state_file
  local nullglob_was_set=0
  local -a state_files=()

  recovery_dir="$(atlas_password_recovery_runtime_dir)" || return 1

  if shopt -q nullglob; then
    nullglob_was_set=1
  fi

  shopt -s nullglob

  for state_dir in active completed revoked; do
    state_files=("$recovery_dir/$state_dir"/*.json)

    for state_file in "${state_files[@]}"; do
      atlas_password_recovery_runtime_normalize_file \
        "$state_file" || return 1
    done
  done

  if (( ! nullglob_was_set )); then
    shopt -u nullglob
  fi
}

atlas_password_recovery_runtime_verify_directory() {
  local path="$1"
  local expected_uid="$2"
  local expected_gid="$3"
  local expected_mode="$4"

  local actual_uid
  local actual_gid
  local actual_mode

  [[ -d "$path" ]] || {
    printf \
      'ERROR: password recovery runtime directory missing: %s\n' \
      "$path" >&2
    return 1
  }

  actual_uid="$(stat -c '%u' "$path")" || return 1
  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1

  [[ "$actual_uid" == "$expected_uid" ]] || {
    printf \
      'ERROR: password recovery runtime UID mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_uid" \
      "$actual_uid" >&2
    return 1
  }

  [[ "$actual_gid" == "$expected_gid" ]] || {
    printf \
      'ERROR: password recovery runtime GID mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_gid" \
      "$actual_gid" >&2
    return 1
  }

  [[ "$actual_mode" == "$expected_mode" ]] || {
    printf \
      'ERROR: password recovery runtime mode mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_mode" \
      "$actual_mode" >&2
    return 1
  }
}

atlas_password_recovery_runtime_verify_file_access() {
  local path="$1"
  local expected_gid="$2"

  local actual_gid
  local actual_mode

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  [[ -f "$path" ]] || {
    printf \
      'ERROR: password recovery runtime file path is not a file: %s\n' \
      "$path" >&2
    return 1
  }

  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1

  [[ "$actual_gid" == "$expected_gid" ]] || {
    printf \
      'ERROR: password recovery runtime file GID mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_gid" \
      "$actual_gid" >&2
    return 1
  }

  local expected_mode

  expected_mode="$(
    printf '%o\n'       "$((8#$ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_MODE))"
  )"

  [[ "$actual_mode" == "$expected_mode" ]] || {
    printf \
      'ERROR: password recovery runtime file mode mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_mode" \
      "$actual_mode" >&2
    return 1
  }
}

atlas_password_recovery_runtime_verify_state_files() {
  local recovery_dir
  local state_dir
  local state_file
  local nullglob_was_set=0
  local -a state_files=()

  recovery_dir="$(atlas_password_recovery_runtime_dir)" || return 1

  if shopt -q nullglob; then
    nullglob_was_set=1
  fi

  shopt -s nullglob

  for state_dir in active completed revoked; do
    state_files=("$recovery_dir/$state_dir"/*.json)

    for state_file in "${state_files[@]}"; do
      atlas_password_recovery_runtime_verify_file_access \
        "$state_file" \
        "$ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_GID" || return 1
    done
  done

  if (( ! nullglob_was_set )); then
    shopt -u nullglob
  fi
}

atlas_password_recovery_runtime_verify() {
  local recovery_dir
  local registry_file
  local state_dir

  recovery_dir="$(atlas_password_recovery_runtime_dir)" || return 1
  registry_file="$(atlas_password_recovery_runtime_registry_file)" || return 1

  atlas_password_recovery_runtime_verify_directory \
    "$recovery_dir" \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_UID" \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_GID" \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_MODE" || return 1

  for state_dir in active completed revoked; do
    atlas_password_recovery_runtime_verify_directory \
      "$recovery_dir/$state_dir" \
      "$ATLAS_PASSWORD_RECOVERY_RUNTIME_UID" \
      "$ATLAS_PASSWORD_RECOVERY_RUNTIME_GID" \
      "$ATLAS_PASSWORD_RECOVERY_RUNTIME_MODE" || return 1
  done

  atlas_password_recovery_runtime_verify_file_access \
    "$registry_file" \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_GID" || return 1

  atlas_password_recovery_runtime_verify_state_files
}

atlas_password_recovery_runtime_provision() {
  local recovery_dir
  local registry_file
  local state_dir

  recovery_dir="$(atlas_password_recovery_runtime_dir)" || return 1
  registry_file="$(atlas_password_recovery_runtime_registry_file)" || return 1

  # Normalize only the explicit password-recovery subtree. Never recursively
  # alter the wider Atlas identity tree.
  atlas_password_recovery_runtime_normalize_directory \
    "$recovery_dir" \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_UID" \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_GID" \
    "$ATLAS_PASSWORD_RECOVERY_RUNTIME_MODE" || return 1

  for state_dir in active completed revoked; do
    atlas_password_recovery_runtime_normalize_directory \
      "$recovery_dir/$state_dir" \
      "$ATLAS_PASSWORD_RECOVERY_RUNTIME_UID" \
      "$ATLAS_PASSWORD_RECOVERY_RUNTIME_GID" \
      "$ATLAS_PASSWORD_RECOVERY_RUNTIME_MODE" || return 1
  done

  atlas_password_recovery_runtime_normalize_file \
    "$registry_file" || return 1

  atlas_password_recovery_runtime_normalize_state_files || return 1

  atlas_password_recovery_runtime_verify
}
