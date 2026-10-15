#!/usr/bin/env bash

ATLAS_REQUESTS_RUNTIME_UID="${ATLAS_REQUESTS_RUNTIME_UID:-0}"
ATLAS_REQUESTS_RUNTIME_GID="${ATLAS_REQUESTS_RUNTIME_GID:-20000}"
ATLAS_REQUESTS_RUNTIME_MODE="${ATLAS_REQUESTS_RUNTIME_MODE:-2770}"
ATLAS_REQUESTS_RUNTIME_API_UID="${ATLAS_REQUESTS_RUNTIME_API_UID:-}"
ATLAS_REQUESTS_RUNTIME_FILE_GID="${ATLAS_REQUESTS_RUNTIME_FILE_GID:-20000}"
ATLAS_REQUESTS_RUNTIME_FILE_MODE="${ATLAS_REQUESTS_RUNTIME_FILE_MODE:-0640}"

atlas_requests_runtime_dir() {
  local runtime_root

  runtime_root="$(
    printf '%s\n' \
      "${ATLAS_RUNTIME_CONFIG_DIR:-/mnt/storage/configs/atlas}"
  )"

  printf '%s/runtime/requests\n' "${runtime_root%/}"
}

atlas_requests_runtime_registry_file() {
  local requests_dir

  requests_dir="$(atlas_requests_runtime_dir)" || return 1
  printf '%s/requests.json\n' "${requests_dir%/}"
}

atlas_requests_runtime_lock_file() {
  local requests_dir

  requests_dir="$(atlas_requests_runtime_dir)" || return 1
  printf '%s/requests.lock\n' "${requests_dir%/}"
}

atlas_requests_runtime_normalize_directory() {
  local path="$1"

  [[ -n "$path" && "$path" == /* ]] || return 1

  if [[ -L "$path" ]]; then
    echo "ERROR: Request runtime directory must not be a symlink: $path" >&2
    return 1
  fi

  if [[ -e "$path" && ! -d "$path" ]]; then
    echo "ERROR: Request runtime path is not a directory: $path" >&2
    return 1
  fi

  install -d \
    -o "$ATLAS_REQUESTS_RUNTIME_UID" \
    -g "$ATLAS_REQUESTS_RUNTIME_GID" \
    -m "$ATLAS_REQUESTS_RUNTIME_MODE" \
    "$path" || return 1

  chown \
    "$ATLAS_REQUESTS_RUNTIME_UID:$ATLAS_REQUESTS_RUNTIME_GID" \
    "$path" || return 1

  chmod "$ATLAS_REQUESTS_RUNTIME_MODE" "$path" || return 1
}

atlas_requests_runtime_resolve_api_uid() {
  local configured="${ATLAS_REQUESTS_RUNTIME_API_UID:-}"
  local resolved

  if [[ -n "$configured" ]]; then
    if [[ ! "$configured" =~ ^[0-9]+$ ]]; then
      echo "ERROR: invalid configured Request API UID: $configured" >&2
      return 1
    fi

    printf '%s\n' "$configured"
    return 0
  fi

  command -v docker >/dev/null 2>&1 || {
    echo "ERROR: cannot resolve Request API UID: docker unavailable." >&2
    return 1
  }

  docker inspect atlas-api >/dev/null 2>&1 || {
    echo "ERROR: cannot resolve Request API UID: atlas-api unavailable." >&2
    return 1
  }

  resolved="$(docker exec atlas-api id -u 2>/dev/null)" || {
    echo "ERROR: cannot resolve Request API UID from atlas-api." >&2
    return 1
  }

  if [[ ! "$resolved" =~ ^[0-9]+$ ]]; then
    echo "ERROR: invalid Request API UID resolved from atlas-api." >&2
    return 1
  fi

  printf '%s\n' "$resolved"
}

atlas_requests_runtime_normalize_file() {
  local path="$1"
  local api_uid

  [[ -n "$path" && "$path" == /* ]] || return 1

  if [[ -L "$path" ]]; then
    echo "ERROR: Request runtime file must not be a symlink: $path" >&2
    return 1
  fi

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  if [[ ! -f "$path" ]]; then
    echo "ERROR: Request runtime path is not a file: $path" >&2
    return 1
  fi

  api_uid="$(atlas_requests_runtime_resolve_api_uid)" || return 1

  # requests.json and requests.lock are mutable API-owned state. A
  # privileged deployment may repair legacy root-owned files, after which
  # repository atomic replacement preserves the API-compatible owner.
  chown \
    "$api_uid:$ATLAS_REQUESTS_RUNTIME_FILE_GID" \
    "$path" || return 1

  chmod "$ATLAS_REQUESTS_RUNTIME_FILE_MODE" "$path" || return 1
}

atlas_requests_runtime_verify_directory() {
  local path="$1"
  local actual_uid
  local actual_gid
  local actual_mode
  local expected_mode

  [[ -d "$path" && ! -L "$path" ]] || return 1

  actual_uid="$(stat -c '%u' "$path")" || return 1
  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1
  expected_mode="$(
    printf '%o\n' "$((8#$ATLAS_REQUESTS_RUNTIME_MODE))"
  )"

  [[ "$actual_uid" == "$ATLAS_REQUESTS_RUNTIME_UID" ]] || return 1
  [[ "$actual_gid" == "$ATLAS_REQUESTS_RUNTIME_GID" ]] || return 1
  [[ "$actual_mode" == "$expected_mode" ]] || return 1
}

atlas_requests_runtime_verify_file() {
  local path="$1"
  local api_uid
  local actual_uid
  local actual_gid
  local actual_mode
  local expected_mode

  if [[ ! -e "$path" ]]; then
    return 0
  fi

  [[ -f "$path" && ! -L "$path" ]] || return 1

  actual_uid="$(stat -c '%u' "$path")" || return 1
  actual_gid="$(stat -c '%g' "$path")" || return 1
  actual_mode="$(stat -c '%a' "$path")" || return 1
  expected_mode="$(
    printf '%o\n' "$((8#$ATLAS_REQUESTS_RUNTIME_FILE_MODE))"
  )"

  api_uid="$(atlas_requests_runtime_resolve_api_uid)" || return 1

  [[ "$actual_uid" == "$api_uid" ]] || return 1
  [[ "$actual_gid" == "$ATLAS_REQUESTS_RUNTIME_FILE_GID" ]] || return 1
  [[ "$actual_mode" == "$expected_mode" ]] || return 1
}

atlas_requests_runtime_verify() {
  local requests_dir
  local registry_file
  local lock_file

  requests_dir="$(atlas_requests_runtime_dir)" || return 1
  registry_file="$(atlas_requests_runtime_registry_file)" || return 1
  lock_file="$(atlas_requests_runtime_lock_file)" || return 1

  atlas_requests_runtime_verify_directory \
    "$requests_dir" || return 1

  atlas_requests_runtime_verify_file \
    "$registry_file" || return 1

  atlas_requests_runtime_verify_file \
    "$lock_file" || return 1
}

atlas_requests_runtime_provision() {
  local requests_dir
  local registry_file
  local lock_file

  requests_dir="$(atlas_requests_runtime_dir)" || return 1
  registry_file="$(atlas_requests_runtime_registry_file)" || return 1
  lock_file="$(atlas_requests_runtime_lock_file)" || return 1

  # Normalize only the mutable Request-state boundary. Reviewed routing
  # configuration in this directory is deliberately outside this contract.
  atlas_requests_runtime_normalize_directory \
    "$requests_dir" || return 1

  atlas_requests_runtime_normalize_file \
    "$registry_file" || return 1

  atlas_requests_runtime_normalize_file \
    "$lock_file" || return 1

  atlas_requests_runtime_verify
}
