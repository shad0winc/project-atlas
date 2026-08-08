#!/usr/bin/env bash

# Guard helpers for the Project Atlas Engineering Toolkit.
# This file is intended to be sourced.

if [[ -n "${ATLAS_DEV_GUARDS_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi

readonly ATLAS_DEV_GUARDS_LOADED=1

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/atlas-utils.sh"

atlas_dev_guard_git_repository() {
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
        atlas_dev_die 1 "Current directory is not inside a Git repository."
}

atlas_dev_guard_project_root() {
    atlas_dev_guard_git_repository

    local root

    root="$(git rev-parse --show-toplevel)"

    if [[ ! -f "$root/scripts/atlas" ]]; then
        atlas_dev_die 1 "Atlas project root could not be verified."
    fi
}

atlas_dev_guard_clean_worktree() {
    atlas_dev_guard_git_repository

    if [[ -n "$(git status --porcelain)" ]]; then
        atlas_dev_die 1 "Working tree contains uncommitted changes."
    fi
}

atlas_dev_guard_command() {
    atlas_dev_require_command "$1"
}

atlas_dev_guard_directory() {
    atlas_dev_require_directory "$1"
}

atlas_dev_guard_file() {
    atlas_dev_require_file "$1"
}

atlas_dev_guard_virtualenv() {
    if [[ ! -x ".venv/bin/python" ]]; then
        atlas_dev_die 1 \
            "Python virtual environment not found at .venv/bin/python."
    fi
}

atlas_dev_guard_python() {
    atlas_dev_guard_virtualenv
    .venv/bin/python --version >/dev/null
}

atlas_dev_guard_docker() {
    atlas_dev_require_command docker
}

atlas_dev_guard_bash() {
    atlas_dev_require_command bash
}

atlas_dev_guard_git() {
    atlas_dev_require_command git
}

atlas_dev_is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

if ! atlas_dev_is_sourced; then
    atlas_dev_error \
        "atlas-guards.sh is a library and must be sourced, not executed."
    exit 2
fi
