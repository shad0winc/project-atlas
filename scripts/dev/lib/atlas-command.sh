#!/usr/bin/env bash

# Shared command runtime for the Project Atlas Engineering Toolkit.
#
# This library provides common command bootstrap, standard help parsing,
# and command lifecycle execution. Command-specific help and workflows
# remain owned by each command implementation.
#
# Runtime contract:
#
#   1. Source this library.
#   2. Call atlas_dev_command_initialize once with the command file.
#   3. Call atlas_dev_command_execute with parser and workflow callbacks.
#
# Reinitialization with the same command file is safe. Reinitialization with
# a different command file is rejected.
#
# This file is intended to be sourced.

if [[ -n "${ATLAS_DEV_COMMAND_RUNTIME_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi

readonly ATLAS_DEV_COMMAND_RUNTIME_LOADED=1

ATLAS_DEV_COMMAND_LIBRARY_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_LIBRARY_DIR/atlas-utils.sh"

readonly ATLAS_DEV_COMMAND_HELP_STATUS=10

ATLAS_DEV_COMMAND_FILE=""
ATLAS_DEV_COMMAND_DIR=""
ATLAS_DEV_COMMAND_DEV_DIR=""
ATLAS_DEV_COMMAND_PROJECT_DIR=""

atlas_dev_command_resolve_directory() {
    local directory_path="${1:?Directory path is required.}"
    local description="${2:-directory}"
    local resolved_directory

    if [[ ! -d "$directory_path" ]]; then
        atlas_dev_error \
            "Unable to resolve $description; directory does not exist: $directory_path"
        return 1
    fi

    if ! resolved_directory="$(
        cd "$directory_path" &&
            pwd
    )"; then
        atlas_dev_error \
            "Unable to resolve $description: $directory_path"
        return 1
    fi

    printf '%s\n' "$resolved_directory"
}

atlas_dev_command_initialize() {
    local command_file="${1:?Command file is required.}"
    local resolved_command_file
    local resolved_command_dir
    local resolved_dev_dir
    local resolved_project_dir

    if [[ ! -f "$command_file" ]]; then
        atlas_dev_die 1 "Command file does not exist: $command_file"
        return 1
    fi

    resolved_command_file="$(atlas_dev_absolute_path "$command_file")"

    if [[ -n "$ATLAS_DEV_COMMAND_FILE" ]]; then
        if [[ "$ATLAS_DEV_COMMAND_FILE" == "$resolved_command_file" ]]; then
            return 0
        fi

        atlas_dev_die 1 \
            "Command runtime is already initialized for $ATLAS_DEV_COMMAND_FILE."
        return 1
    fi

    if ! resolved_command_dir="$(
        atlas_dev_command_resolve_directory \
            "$(dirname "$resolved_command_file")" \
            "command directory"
    )"; then
        return 1
    fi

    if ! resolved_dev_dir="$(
        atlas_dev_command_resolve_directory \
            "$resolved_command_dir/.." \
            "Engineering Toolkit directory"
    )"; then
        return 1
    fi

    if ! resolved_project_dir="$(
        atlas_dev_command_resolve_directory \
            "$resolved_dev_dir/../.." \
            "Project Atlas repository root"
    )"; then
        return 1
    fi

    if [[ ! -d "$resolved_project_dir/.git" ]]; then
        atlas_dev_die 1 \
            "Repository metadata was not found at $resolved_project_dir/.git."
        return 1
    fi

    if [[ ! -f "$resolved_project_dir/scripts/atlas" ]]; then
        atlas_dev_die 1 \
            "Atlas runtime CLI was not found at $resolved_project_dir/scripts/atlas."
        return 1
    fi

    ATLAS_DEV_COMMAND_FILE="$resolved_command_file"
    ATLAS_DEV_COMMAND_DIR="$resolved_command_dir"
    ATLAS_DEV_COMMAND_DEV_DIR="$resolved_dev_dir"
    ATLAS_DEV_COMMAND_PROJECT_DIR="$resolved_project_dir"
}

atlas_dev_command_parse_standard_help() {
    local command_name="${1:?Command name is required.}"
    local help_function="${2:?Help function is required.}"

    shift 2

    if ! declare -F "$help_function" >/dev/null 2>&1; then
        atlas_dev_die 1 \
            "Command help function is unavailable: $help_function"
        return 1
    fi

    if [[ "$#" -eq 0 ]]; then
        return 0
    fi

    case "$1" in
        help|-h|--help)
            if [[ "$#" -ne 1 ]]; then
                atlas_dev_error \
                    "The $command_name help option does not accept additional arguments."
                return 2
            fi

            "$help_function"
            return "$ATLAS_DEV_COMMAND_HELP_STATUS"
            ;;
        *)
            atlas_dev_error "Unexpected $command_name argument: $1"
            printf '\n' >&2
            "$help_function" >&2
            return 2
            ;;
    esac
}

atlas_dev_command_execute() {
    local parse_function="${1:?Argument parser function is required.}"
    local run_function="${2:?Command workflow function is required.}"
    local argument_status=0
    local workflow_status=0

    shift 2

    if [[ -z "$ATLAS_DEV_COMMAND_PROJECT_DIR" ]]; then
        atlas_dev_die 1 \
            "Command runtime has not been initialized."
        return 1
    fi

    if ! declare -F "$parse_function" >/dev/null 2>&1; then
        atlas_dev_die 1 \
            "Command argument parser is unavailable: $parse_function"
        return 1
    fi

    if ! declare -F "$run_function" >/dev/null 2>&1; then
        atlas_dev_die 1 \
            "Command workflow function is unavailable: $run_function"
        return 1
    fi

    if ! cd "$ATLAS_DEV_COMMAND_PROJECT_DIR"; then
        atlas_dev_die 1 \
            "Unable to change directory to project root: $ATLAS_DEV_COMMAND_PROJECT_DIR"
        return 1
    fi

    "$parse_function" "$@" || argument_status=$?

    case "$argument_status" in
        0)
            "$run_function" || workflow_status=$?
            return "$workflow_status"
            ;;
        "$ATLAS_DEV_COMMAND_HELP_STATUS")
            return 0
            ;;
        *)
            return "$argument_status"
            ;;
    esac
}

atlas_dev_is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

if ! atlas_dev_is_sourced; then
    atlas_dev_error \
        "atlas-command.sh is a library and must be sourced, not executed."
    exit 2
fi
