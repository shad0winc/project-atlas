#!/usr/bin/env bash

ATLAS_IDENTITY_WRITER_USERS_UID="${ATLAS_IDENTITY_WRITER_USERS_UID:-0}"
ATLAS_IDENTITY_WRITER_USERS_GID="${ATLAS_IDENTITY_WRITER_USERS_GID:-20000}"
ATLAS_IDENTITY_WRITER_USERS_MODE="${ATLAS_IDENTITY_WRITER_USERS_MODE:-2770}"

ATLAS_IDENTITY_WRITER_INVITATIONS_UID="${ATLAS_IDENTITY_WRITER_INVITATIONS_UID:-0}"
ATLAS_IDENTITY_WRITER_INVITATIONS_GID="${ATLAS_IDENTITY_WRITER_INVITATIONS_GID:-20001}"
ATLAS_IDENTITY_WRITER_INVITATIONS_MODE="${ATLAS_IDENTITY_WRITER_INVITATIONS_MODE:-2770}"

atlas_identity_writer_runtime_users_dir() {
  printf '%s\n' \
    "${ATLAS_USERS_DIR:-/mnt/storage/configs/atlas/users}"
}

atlas_identity_writer_runtime_profiles_dir() {
  local users_dir
  users_dir="$(atlas_identity_writer_runtime_users_dir)" || return 1
  printf '%s/profiles\n' "${users_dir%/}"
}

atlas_identity_writer_runtime_custom_roles_dir() {
  local identity_root
  identity_root="${ATLAS_IDENTITY_DIR:-/mnt/storage/configs/atlas/identity}"
  printf '%s/custom_roles\n' "${identity_root%/}"
}


atlas_identity_writer_runtime_invitations_dir() {
  local identity_root
  identity_root="$(
    printf '%s\n' \
      "${ATLAS_IDENTITY_DIR:-/mnt/storage/configs/atlas/identity}"
  )"

  printf '%s/invitations\n' "${identity_root%/}"
}

atlas_identity_writer_runtime_normalize_directory() {
  local path="$1"
  local uid="$2"
  local gid="$3"
  local mode="$4"

  [[ -n "$path" ]] || return 1
  [[ "$path" == /* ]] || {
    printf 'ERROR: identity writer runtime path must be absolute: %s\n' \
      "$path" >&2
    return 1
  }

  if [[ -e "$path" && ! -d "$path" ]]; then
    printf 'ERROR: identity writer runtime path is not a directory: %s\n' \
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

atlas_identity_writer_runtime_verify_directory() {
  local path="$1"
  local expected_uid="$2"
  local expected_gid="$3"
  local expected_mode="$4"

  local actual_uid
  local actual_gid
  local actual_mode

  [[ -d "$path" ]] || {
    printf 'ERROR: identity writer runtime directory missing: %s\n' \
      "$path" >&2
    return 1
  }

  actual_uid="$(stat -c '%u' "$path")" || return 1
  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1

  [[ "$actual_uid" == "$expected_uid" ]] || {
    printf \
      'ERROR: identity writer runtime UID mismatch for %s: expected %s, got %s.\n' \
      "$path" "$expected_uid" "$actual_uid" >&2
    return 1
  }

  [[ "$actual_gid" == "$expected_gid" ]] || {
    printf \
      'ERROR: identity writer runtime GID mismatch for %s: expected %s, got %s.\n' \
      "$path" "$expected_gid" "$actual_gid" >&2
    return 1
  }

  [[ "$actual_mode" == "$expected_mode" ]] || {
    printf \
      'ERROR: identity writer runtime mode mismatch for %s: expected %s, got %s.\n' \
      "$path" "$expected_mode" "$actual_mode" >&2
    return 1
  }
}

atlas_identity_writer_runtime_verify() {
  local users_dir
  local profiles_dir
  local invitations_dir
  local custom_roles_dir
  local lifecycle_dir
  local profile_dir

  users_dir="$(atlas_identity_writer_runtime_users_dir)" || return 1
  profiles_dir="$(atlas_identity_writer_runtime_profiles_dir)" || return 1
  invitations_dir="$(
    atlas_identity_writer_runtime_invitations_dir
  )" || return 1
  custom_roles_dir="$(atlas_identity_writer_runtime_custom_roles_dir)" || return 1

  atlas_identity_writer_runtime_verify_directory \
    "$users_dir" \
    "$ATLAS_IDENTITY_WRITER_USERS_UID" \
    "$ATLAS_IDENTITY_WRITER_USERS_GID" \
    "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1

  atlas_identity_writer_runtime_verify_directory \
    "$profiles_dir" \
    "$ATLAS_IDENTITY_WRITER_USERS_UID" \
    "$ATLAS_IDENTITY_WRITER_USERS_GID" \
    "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1

  local nullglob_was_set=0
  local -a profile_dirs=()

  if shopt -q nullglob; then
    nullglob_was_set=1
  fi
  shopt -s nullglob
  profile_dirs=("$profiles_dir"/usr_*)
  if (( ! nullglob_was_set )); then
    shopt -u nullglob
  fi

  for profile_dir in "${profile_dirs[@]}"; do
    atlas_identity_writer_runtime_verify_directory \
      "$profile_dir" \
      "$ATLAS_IDENTITY_WRITER_USERS_UID" \
      "$ATLAS_IDENTITY_WRITER_USERS_GID" \
      "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1
  done

  atlas_identity_writer_runtime_verify_directory \
    "$custom_roles_dir" \
    "$ATLAS_IDENTITY_WRITER_USERS_UID" \
    "$ATLAS_IDENTITY_WRITER_USERS_GID" \
    "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1

  atlas_identity_writer_runtime_verify_directory \
    "$invitations_dir" \
    "$ATLAS_IDENTITY_WRITER_INVITATIONS_UID" \
    "$ATLAS_IDENTITY_WRITER_INVITATIONS_GID" \
    "$ATLAS_IDENTITY_WRITER_INVITATIONS_MODE" || return 1

  for lifecycle_dir in active completed revoked; do
    atlas_identity_writer_runtime_verify_directory \
      "$invitations_dir/$lifecycle_dir" \
      "$ATLAS_IDENTITY_WRITER_INVITATIONS_UID" \
      "$ATLAS_IDENTITY_WRITER_INVITATIONS_GID" \
      "$ATLAS_IDENTITY_WRITER_INVITATIONS_MODE" || return 1
  done
}

atlas_identity_writer_runtime_provision() {
  local users_dir
  local profiles_dir
  local invitations_dir
  local custom_roles_dir
  local lifecycle_dir
  local profile_dir

  users_dir="$(atlas_identity_writer_runtime_users_dir)" || return 1
  profiles_dir="$(atlas_identity_writer_runtime_profiles_dir)" || return 1
  invitations_dir="$(
    atlas_identity_writer_runtime_invitations_dir
  )" || return 1
  custom_roles_dir="$(atlas_identity_writer_runtime_custom_roles_dir)" || return 1

  atlas_identity_writer_runtime_normalize_directory \
    "$users_dir" \
    "$ATLAS_IDENTITY_WRITER_USERS_UID" \
    "$ATLAS_IDENTITY_WRITER_USERS_GID" \
    "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1

  atlas_identity_writer_runtime_normalize_directory \
    "$profiles_dir" \
    "$ATLAS_IDENTITY_WRITER_USERS_UID" \
    "$ATLAS_IDENTITY_WRITER_USERS_GID" \
    "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1

  local nullglob_was_set=0
  local -a profile_dirs=()

  if shopt -q nullglob; then
    nullglob_was_set=1
  fi
  shopt -s nullglob
  profile_dirs=("$profiles_dir"/usr_*)
  if (( ! nullglob_was_set )); then
    shopt -u nullglob
  fi

  for profile_dir in "${profile_dirs[@]}"; do
    atlas_identity_writer_runtime_normalize_directory \
      "$profile_dir" \
      "$ATLAS_IDENTITY_WRITER_USERS_UID" \
      "$ATLAS_IDENTITY_WRITER_USERS_GID" \
      "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1
  done

  atlas_identity_writer_runtime_normalize_directory \
    "$custom_roles_dir" \
    "$ATLAS_IDENTITY_WRITER_USERS_UID" \
    "$ATLAS_IDENTITY_WRITER_USERS_GID" \
    "$ATLAS_IDENTITY_WRITER_USERS_MODE" || return 1

  atlas_identity_writer_runtime_normalize_directory \
    "$invitations_dir" \
    "$ATLAS_IDENTITY_WRITER_INVITATIONS_UID" \
    "$ATLAS_IDENTITY_WRITER_INVITATIONS_GID" \
    "$ATLAS_IDENTITY_WRITER_INVITATIONS_MODE" || return 1

  for lifecycle_dir in active completed revoked; do
    atlas_identity_writer_runtime_normalize_directory \
      "$invitations_dir/$lifecycle_dir" \
      "$ATLAS_IDENTITY_WRITER_INVITATIONS_UID" \
      "$ATLAS_IDENTITY_WRITER_INVITATIONS_GID" \
      "$ATLAS_IDENTITY_WRITER_INVITATIONS_MODE" || return 1
  done

  atlas_identity_writer_runtime_verify
}
