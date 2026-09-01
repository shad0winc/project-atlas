#!/usr/bin/env bash

ATLAS_FAVORITES_RUNTIME_UID="${ATLAS_FAVORITES_RUNTIME_UID:-0}"
ATLAS_FAVORITES_RUNTIME_GID="${ATLAS_FAVORITES_RUNTIME_GID:-20000}"
ATLAS_FAVORITES_RUNTIME_MODE="${ATLAS_FAVORITES_RUNTIME_MODE:-2770}"
ATLAS_FAVORITES_RUNTIME_FILE_GID="${ATLAS_FAVORITES_RUNTIME_FILE_GID:-20000}"
ATLAS_FAVORITES_RUNTIME_FILE_MODE="${ATLAS_FAVORITES_RUNTIME_FILE_MODE:-0640}"

atlas_favorites_runtime_dir() {
  local identity_root

  identity_root="$(
    printf '%s\n' \
      "${ATLAS_IDENTITY_DIR:-/mnt/storage/configs/atlas/identity}"
  )"

  printf '%s/favorites\n' "${identity_root%/}"
}

atlas_favorites_runtime_records_dir() {
  local favorites_dir

  favorites_dir="$(atlas_favorites_runtime_dir)" || return 1

  printf '%s/records\n' "${favorites_dir%/}"
}

atlas_favorites_runtime_registry_file() {
  local favorites_dir

  favorites_dir="$(atlas_favorites_runtime_dir)" || return 1

  printf '%s/favorites.json\n' "${favorites_dir%/}"
}

atlas_favorites_runtime_normalize_directory() {
  local path="$1"
  local uid="$2"
  local gid="$3"
  local mode="$4"

  [[ -n "$path" ]] || return 1

  [[ "$path" == /* ]] || {
    printf \
      'ERROR: Favorites runtime path must be absolute: %s\n' \
      "$path" >&2
    return 1
  }

  if [[ -e "$path" && ! -d "$path" ]]; then
    printf \
      'ERROR: Favorites runtime path is not a directory: %s\n' \
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

atlas_favorites_runtime_normalize_file() {
  local path="$1"

  [[ -n "$path" ]] || return 1

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  [[ -f "$path" ]] || {
    printf \
      'ERROR: Favorites runtime file path is not a file: %s\n' \
      "$path" >&2
    return 1
  }

  # Preserve the existing file owner. FavoriteStore may legitimately replace
  # these files as the non-root API process. The canonical access requirement
  # is the Atlas runtime group plus a group-readable file mode.
  chgrp \
    "$ATLAS_FAVORITES_RUNTIME_FILE_GID" \
    "$path" || return 1

  chmod \
    "$ATLAS_FAVORITES_RUNTIME_FILE_MODE" \
    "$path" || return 1
}

atlas_favorites_runtime_normalize_record_files() {
  local records_dir
  local nullglob_was_set=0
  local -a record_files=()
  local record_file

  records_dir="$(atlas_favorites_runtime_records_dir)" || return 1

  if shopt -q nullglob; then
    nullglob_was_set=1
  fi

  shopt -s nullglob
  record_files=("$records_dir"/fav_*.json)

  if (( ! nullglob_was_set )); then
    shopt -u nullglob
  fi

  for record_file in "${record_files[@]}"; do
    atlas_favorites_runtime_normalize_file \
      "$record_file" || return 1
  done
}

atlas_favorites_runtime_verify_directory() {
  local path="$1"
  local expected_uid="$2"
  local expected_gid="$3"
  local expected_mode="$4"

  local actual_uid
  local actual_gid
  local actual_mode

  [[ -d "$path" ]] || {
    printf \
      'ERROR: Favorites runtime directory missing: %s\n' \
      "$path" >&2
    return 1
  }

  actual_uid="$(stat -c '%u' "$path")" || return 1
  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1

  [[ "$actual_uid" == "$expected_uid" ]] || {
    printf \
      'ERROR: Favorites runtime UID mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_uid" \
      "$actual_uid" >&2
    return 1
  }

  [[ "$actual_gid" == "$expected_gid" ]] || {
    printf \
      'ERROR: Favorites runtime GID mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_gid" \
      "$actual_gid" >&2
    return 1
  }

  [[ "$actual_mode" == "$expected_mode" ]] || {
    printf \
      'ERROR: Favorites runtime mode mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_mode" \
      "$actual_mode" >&2
    return 1
  }
}

atlas_favorites_runtime_verify_file_access() {
  local path="$1"
  local expected_gid="$2"

  local actual_gid
  local actual_mode
  local group_digit

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  [[ -f "$path" ]] || {
    printf \
      'ERROR: Favorites runtime file path is not a file: %s\n' \
      "$path" >&2
    return 1
  }

  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1

  [[ "$actual_gid" == "$expected_gid" ]] || {
    printf \
      'ERROR: Favorites runtime file GID mismatch for %s: expected %s, got %s.\n' \
      "$path" \
      "$expected_gid" \
      "$actual_gid" >&2
    return 1
  }

  # The API must retain group-read access even after FavoriteStore atomically
  # replaces a file and its process umask determines the exact final mode.
  group_digit="${actual_mode: -2:1}"

  case "$group_digit" in
    4|5|6|7)
      ;;
    *)
      printf \
        'ERROR: Favorites runtime file is not group-readable: %s (mode=%s).\n' \
        "$path" \
        "$actual_mode" >&2
      return 1
      ;;
  esac
}

atlas_favorites_runtime_verify_record_files() {
  local records_dir
  local nullglob_was_set=0
  local -a record_files=()
  local record_file

  records_dir="$(atlas_favorites_runtime_records_dir)" || return 1

  if shopt -q nullglob; then
    nullglob_was_set=1
  fi

  shopt -s nullglob
  record_files=("$records_dir"/fav_*.json)

  if (( ! nullglob_was_set )); then
    shopt -u nullglob
  fi

  for record_file in "${record_files[@]}"; do
    atlas_favorites_runtime_verify_file_access \
      "$record_file" \
      "$ATLAS_FAVORITES_RUNTIME_FILE_GID" || return 1
  done
}

atlas_favorites_runtime_verify() {
  local favorites_dir
  local records_dir
  local registry_file

  favorites_dir="$(atlas_favorites_runtime_dir)" || return 1
  records_dir="$(atlas_favorites_runtime_records_dir)" || return 1
  registry_file="$(atlas_favorites_runtime_registry_file)" || return 1

  atlas_favorites_runtime_verify_directory \
    "$favorites_dir" \
    "$ATLAS_FAVORITES_RUNTIME_UID" \
    "$ATLAS_FAVORITES_RUNTIME_GID" \
    "$ATLAS_FAVORITES_RUNTIME_MODE" || return 1

  atlas_favorites_runtime_verify_directory \
    "$records_dir" \
    "$ATLAS_FAVORITES_RUNTIME_UID" \
    "$ATLAS_FAVORITES_RUNTIME_GID" \
    "$ATLAS_FAVORITES_RUNTIME_MODE" || return 1

  atlas_favorites_runtime_verify_file_access \
    "$registry_file" \
    "$ATLAS_FAVORITES_RUNTIME_FILE_GID" || return 1

  atlas_favorites_runtime_verify_record_files
}

atlas_favorites_runtime_provision() {
  local favorites_dir
  local records_dir
  local registry_file

  favorites_dir="$(atlas_favorites_runtime_dir)" || return 1
  records_dir="$(atlas_favorites_runtime_records_dir)" || return 1
  registry_file="$(atlas_favorites_runtime_registry_file)" || return 1

  # Normalize only explicit canonical Favorites paths. Never recursively
  # rewrite the Atlas identity tree.
  atlas_favorites_runtime_normalize_directory \
    "$favorites_dir" \
    "$ATLAS_FAVORITES_RUNTIME_UID" \
    "$ATLAS_FAVORITES_RUNTIME_GID" \
    "$ATLAS_FAVORITES_RUNTIME_MODE" || return 1

  atlas_favorites_runtime_normalize_directory \
    "$records_dir" \
    "$ATLAS_FAVORITES_RUNTIME_UID" \
    "$ATLAS_FAVORITES_RUNTIME_GID" \
    "$ATLAS_FAVORITES_RUNTIME_MODE" || return 1

  atlas_favorites_runtime_normalize_file \
    "$registry_file" || return 1

  atlas_favorites_runtime_normalize_record_files || return 1

  atlas_favorites_runtime_verify
}
