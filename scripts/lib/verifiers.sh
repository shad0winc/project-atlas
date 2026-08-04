#!/usr/bin/env bash

atlas_verify_specialized_command() {
  local label="$1"
  shift

  if "$@"; then
    atlas_ok "$label"
    return 0
  fi

  atlas_fail "$label"
  ATLAS_VERIFY_PASS=false
  return 1
}

atlas_verify_specialized_output_command() {
  local label="$1"
  local empty_message="$2"
  shift 2

  local output
  local status=0

  output="$("$@" 2>&1)" || status=$?

  if [[ -n "$output" ]]; then
    printf '%s\n' "$output"
  fi

  if [[ "$status" -ne 0 ]]; then
    atlas_fail "$label"
    ATLAS_VERIFY_PASS=false
    return 1
  fi

  if [[ -z "${output//[[:space:]]/}" ]]; then
    atlas_fail "$label"
    ATLAS_VERIFY_PASS=false
    return 1
  fi

  if grep -Fqx -- "$empty_message" <<<"$output"; then
    atlas_fail "$label"
    ATLAS_VERIFY_PASS=false
    return 1
  fi

  atlas_ok "$label"
}
