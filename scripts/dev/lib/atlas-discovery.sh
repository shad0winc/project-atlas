#!/usr/bin/env bash

# Project Atlas discovery helper library.
#
# This library is sourced by milestone-specific discovery scripts. It provides:
#
# - consistent report sections,
# - safe and bounded file inspection,
# - vendor-aware repository searching,
# - deterministic file ordering,
# - optional-command handling,
# - output truncation without broken pipes.
#
# Generated discovery reports belong under reports/, which is intentionally
# excluded from source control.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf '%s\n' \
        "This file is a shell library and must be sourced by a discovery script." >&2
    exit 1
fi

atlas_discovery_section() {
    local title="$1"

    printf '\n\n============================================================\n'
    printf '%s\n' "$title"
    printf '============================================================\n'
}

atlas_discovery_note() {
    local title="$1"

    printf '\n--- %s ---\n' "$title"
}

atlas_discovery_file() {
    local file="$1"
    local start_line="${2:-1}"
    local end_line="${3:-320}"

    if [[ ! -f "$file" ]]; then
        printf '[missing file: %s]\n' "$file"
        return 0
    fi

    printf '\n--- %s ---\n' "$file"
    sed -n "${start_line},${end_line}p" "$file"
}

atlas_discovery_files() {
    local file

    for file in "$@"; do
        atlas_discovery_file "$file"
    done
}

atlas_discovery_find_files() {
    local root="$1"
    shift || true

    if [[ ! -d "$root" ]]; then
        printf '[missing directory: %s]\n' "$root"
        return 0
    fi

    find "$root" \
        \( \
            -type d \
            \( \
                -name .git \
                -o -name node_modules \
                -o -name .next \
                -o -name .venv \
                -o -name venv \
                -o -name dist \
                -o -name build \
                -o -name coverage \
                -o -name reports \
                -o -name .atlas-backups \
                -o -name .pytest_cache \
                -o -name __pycache__ \
                -o -name .mypy_cache \
                -o -name .ruff_cache \
            \) \
            -prune \
        \) \
        -o \
        -type f \
        "$@" \
        -print |
        LC_ALL=C sort
}

atlas_discovery_search() {
    local description="$1"
    local pattern="$2"
    local limit="$3"
    shift 3

    local -a requested_paths=("$@")
    local -a existing_paths=()
    local path
    local temp_file
    local search_status
    local total_lines

    atlas_discovery_note "$description"

    for path in "${requested_paths[@]}"; do
        if [[ -e "$path" ]]; then
            existing_paths+=("$path")
        else
            printf '[skipping missing path: %s]\n' "$path"
        fi
    done

    if [[ "${#existing_paths[@]}" -eq 0 ]]; then
        printf '[no searchable paths]\n'
        return 0
    fi

    temp_file="$(mktemp)"

    if command -v rg >/dev/null 2>&1; then
        set +e
        rg \
            --line-number \
            --no-heading \
            --color never \
            --hidden \
            --glob '!.git/**' \
            --glob '!node_modules/**' \
            --glob '!**/node_modules/**' \
            --glob '!.next/**' \
            --glob '!**/.next/**' \
            --glob '!.venv/**' \
            --glob '!**/.venv/**' \
            --glob '!venv/**' \
            --glob '!**/venv/**' \
            --glob '!dist/**' \
            --glob '!**/dist/**' \
            --glob '!build/**' \
            --glob '!**/build/**' \
            --glob '!coverage/**' \
            --glob '!**/coverage/**' \
            --glob '!reports/**' \
            --glob '!**/reports/**' \
            --glob '!.atlas-backups/**' \
            --glob '!**/.atlas-backups/**' \
            --glob '!.pytest_cache/**' \
            --glob '!**/.pytest_cache/**' \
            --glob '!**/__pycache__/**' \
            --glob '!**/*.pyc' \
            --glob '!.mypy_cache/**' \
            --glob '!**/.mypy_cache/**' \
            --glob '!.ruff_cache/**' \
            --glob '!**/.ruff_cache/**' \
            -- "$pattern" \
            "${existing_paths[@]}" > "$temp_file" 2>&1
        search_status=$?
        set -e
    else
        set +e
        grep \
            -RInE \
            --exclude='*.pyc' \
            --exclude-dir=.git \
            --exclude-dir=node_modules \
            --exclude-dir=.next \
            --exclude-dir=.venv \
            --exclude-dir=venv \
            --exclude-dir=dist \
            --exclude-dir=build \
            --exclude-dir=coverage \
            --exclude-dir=reports \
            --exclude-dir=.atlas-backups \
            --exclude-dir=.pytest_cache \
            --exclude-dir=__pycache__ \
            --exclude-dir=.mypy_cache \
            --exclude-dir=.ruff_cache \
            -- "$pattern" \
            "${existing_paths[@]}" > "$temp_file" 2>&1
        search_status=$?
        set -e
    fi

    if [[ "$search_status" -gt 1 ]]; then
        printf '[search returned status %s]\n' "$search_status"
        sed -n '1,80p' "$temp_file"
        rm -f "$temp_file"
        return 0
    fi

    if [[ ! -s "$temp_file" ]]; then
        printf '[no matches]\n'
        rm -f "$temp_file"
        return 0
    fi

    total_lines="$(wc -l < "$temp_file" | tr -d '[:space:]')"

    # sed reads the complete input and does not close the pipeline early.
    # This prevents the SIGPIPE behavior caused by grep | head.
    sed -n "1,${limit}p" "$temp_file"

    if (( total_lines > limit )); then
        printf '\n[output truncated: showing %s of %s matching lines]\n' \
            "$limit" \
            "$total_lines"
    fi

    rm -f "$temp_file"
}

atlas_discovery_command() {
    local description="$1"
    shift

    local command_status

    atlas_discovery_note "$description"

    set +e
    "$@"
    command_status=$?
    set -e

    if [[ "$command_status" -ne 0 ]]; then
        printf '[command returned status %s]\n' "$command_status"
    fi

    return 0
}
