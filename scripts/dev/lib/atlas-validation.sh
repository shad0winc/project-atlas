#!/usr/bin/env bash

# Reusable validation helpers for the Project Atlas Engineering Toolkit.
#
# This library exposes focused validation functions. It does not define or
# execute a complete validation workflow when sourced.

if [[ -n "${ATLAS_DEV_VALIDATION_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi

readonly ATLAS_DEV_VALIDATION_LOADED=1

ATLAS_DEV_VALIDATION_LIB_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_VALIDATION_LIB_DIR/atlas-utils.sh"

# shellcheck source=/dev/null
source "$ATLAS_DEV_VALIDATION_LIB_DIR/atlas-guards.sh"

atlas_dev_validate_git_diff() {
    atlas_dev_guard_git

    atlas_dev_info "Checking Git diff formatting."

    if ! git diff --check; then
        atlas_dev_error "Git diff formatting validation failed."
        return 1
    fi

    atlas_dev_success "Git diff formatting validation passed."
}

atlas_dev_validate_bash_file() {
    local file_path="${1:?Bash file path is required.}"

    atlas_dev_guard_bash
    atlas_dev_guard_file "$file_path"

    atlas_dev_info "Checking Bash syntax: $file_path"

    if ! bash -n "$file_path"; then
        atlas_dev_error "Bash syntax validation failed: $file_path"
        return 1
    fi

    atlas_dev_success "Bash syntax validation passed: $file_path"
}

atlas_dev_validate_bash_files() {
    local file_path
    local status=0

    if [[ "$#" -eq 0 ]]; then
        atlas_dev_error "At least one Bash file is required."
        return 2
    fi

    for file_path in "$@"; do
        if ! atlas_dev_validate_bash_file "$file_path"; then
            status=1
        fi
    done

    return "$status"
}

atlas_dev_validation_collect_bash_files() {
    local root_script
    local search_directory

    for root_script in \
        scripts/dev/atlas-dev \
        scripts/dev/atlas-inventory
    do
        atlas_dev_guard_file "$root_script"
        printf '%s\0' "$root_script"
    done

    for search_directory in \
        scripts/dev/commands \
        scripts/dev/lib
    do
        if [[ ! -d "$search_directory" ]]; then
            atlas_dev_error \
                "Required toolkit directory does not exist: $search_directory"
            return 1
        fi

        find "$search_directory" \
            -maxdepth 1 \
            -type f \
            -name '*.sh' \
            -print0
    done
}

atlas_dev_validate_toolkit_bash() {
    local -a bash_files=()

    mapfile -d '' -t bash_files < <(
        atlas_dev_validation_collect_bash_files |
            sort -z
    )

    if [[ "${#bash_files[@]}" -eq 0 ]]; then
        atlas_dev_error "No Engineering Toolkit Bash files were discovered."
        return 1
    fi

    atlas_dev_info \
        "Discovered ${#bash_files[@]} Engineering Toolkit Bash files."

    atlas_dev_validate_bash_files "${bash_files[@]}"
}

atlas_dev_validate_python_file() {
    local file_path="${1:?Python file path is required.}"

    atlas_dev_guard_python
    atlas_dev_guard_file "$file_path"

    atlas_dev_info "Compiling Python file: $file_path"

    if ! .venv/bin/python -m py_compile "$file_path"; then
        atlas_dev_error "Python compilation failed: $file_path"
        return 1
    fi

    atlas_dev_success "Python compilation passed: $file_path"
}

atlas_dev_validate_python_files() {
    local file_path
    local status=0

    if [[ "$#" -eq 0 ]]; then
        atlas_dev_error "At least one Python file is required."
        return 2
    fi

    for file_path in "$@"; do
        if ! atlas_dev_validate_python_file "$file_path"; then
            status=1
        fi
    done

    return "$status"
}

atlas_dev_validate_pytest() {
    atlas_dev_guard_python

    atlas_dev_info "Running pytest: $*"

    if ! .venv/bin/python -m pytest "$@"; then
        atlas_dev_error "Pytest validation failed."
        return 1
    fi

    atlas_dev_success "Pytest validation passed."
}

atlas_dev_validate_repository_basics() {
    atlas_dev_guard_project_root

    atlas_dev_validate_git_diff
    atlas_dev_validate_toolkit_bash
}

atlas_dev_is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

if ! atlas_dev_is_sourced; then
    atlas_dev_error \
        "atlas-validation.sh is a library and must be sourced, not executed."
    exit 2
fi
