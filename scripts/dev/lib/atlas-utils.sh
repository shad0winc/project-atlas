#!/usr/bin/env bash

# Shared utility functions for the Project Atlas Engineering Toolkit.
#
# This file is intended to be sourced by developer commands and libraries.
# It must not execute workflows directly.

if [[ -n "${ATLAS_DEV_UTILS_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi

readonly ATLAS_DEV_UTILS_LOADED=1

atlas_dev_timestamp() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
}

atlas_dev_timestamp_compact() {
    date -u '+%Y%m%dT%H%M%SZ'
}

atlas_dev_log() {
    local level="${1:?Log level is required.}"
    shift

    printf '[%s] [%s] %s\n' \
        "$(atlas_dev_timestamp)" \
        "$level" \
        "$*"
}

atlas_dev_info() {
    atlas_dev_log "INFO" "$@"
}

atlas_dev_success() {
    atlas_dev_log "PASS" "$@"
}

atlas_dev_warn() {
    atlas_dev_log "WARN" "$@" >&2
}

atlas_dev_error() {
    atlas_dev_log "ERROR" "$@" >&2
}

atlas_dev_die() {
    local exit_status=1

    if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
        exit_status="$1"
        shift
    fi

    atlas_dev_error "$@"
    return "$exit_status"
}

atlas_dev_command_exists() {
    local command_name="${1:?Command name is required.}"

    command -v "$command_name" >/dev/null 2>&1
}

atlas_dev_require_command() {
    local command_name="${1:?Command name is required.}"

    if ! atlas_dev_command_exists "$command_name"; then
        atlas_dev_die 1 "Required command is unavailable: $command_name"
        return 1
    fi
}

atlas_dev_require_file() {
    local file_path="${1:?File path is required.}"

    if [[ ! -f "$file_path" ]]; then
        atlas_dev_die 1 "Required file does not exist: $file_path"
        return 1
    fi
}

atlas_dev_require_directory() {
    local directory_path="${1:?Directory path is required.}"

    if [[ ! -d "$directory_path" ]]; then
        atlas_dev_die 1 "Required directory does not exist: $directory_path"
        return 1
    fi
}

atlas_dev_require_executable() {
    local executable_path="${1:?Executable path is required.}"

    if [[ ! -x "$executable_path" ]]; then
        atlas_dev_die 1 "Required executable is not executable: $executable_path"
        return 1
    fi
}

atlas_dev_absolute_path() {
    local target_path="${1:?Path is required.}"
    local parent_directory
    local base_name

    if [[ -d "$target_path" ]]; then
        (
            cd "$target_path" &&
                pwd
        )
        return
    fi

    parent_directory="$(dirname "$target_path")"
    base_name="$(basename "$target_path")"

    (
        cd "$parent_directory" &&
            printf '%s/%s\n' "$(pwd)" "$base_name"
    )
}

atlas_dev_join_path() {
    local base_path="${1:?Base path is required.}"
    local child_path="${2:?Child path is required.}"

    printf '%s/%s\n' \
        "${base_path%/}" \
        "${child_path#/}"
}

atlas_dev_is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

if ! atlas_dev_is_sourced; then
    atlas_dev_error \
        "atlas-utils.sh is a library and must be sourced, not executed."
    exit 2
fi
