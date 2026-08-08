#!/usr/bin/env bash

# Standardized report helpers for the Project Atlas Engineering Toolkit.
#
# This library owns report locations, filenames, headers, section formatting,
# and finalization. It does not execute discovery or validation workflows.

if [[ -n "${ATLAS_DEV_REPORT_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi

readonly ATLAS_DEV_REPORT_LOADED=1

ATLAS_DEV_REPORT_LIB_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_REPORT_LIB_DIR/atlas-utils.sh"

# shellcheck source=/dev/null
source "$ATLAS_DEV_REPORT_LIB_DIR/atlas-guards.sh"

readonly ATLAS_DEV_REPORT_ROOT="reports"

atlas_dev_report_type_directory() {
    local report_type="${1:?Report type is required.}"

    case "$report_type" in
        discovery|validation|releases|benchmarks|diagnostics)
            printf '%s/%s\n' "$ATLAS_DEV_REPORT_ROOT" "$report_type"
            ;;
        *)
            atlas_dev_error "Unsupported report type: $report_type"
            return 2
            ;;
    esac
}

atlas_dev_report_slug() {
    local value="${1:?Report name is required.}"

    printf '%s\n' "$value" |
        tr '[:upper:]' '[:lower:]' |
        sed -E \
            -e 's/[^a-z0-9]+/-/g' \
            -e 's/^-+//' \
            -e 's/-+$//'
}

atlas_dev_report_path() {
    local report_type="${1:?Report type is required.}"
    local report_name="${2:?Report name is required.}"
    local directory
    local slug
    local timestamp

    directory="$(atlas_dev_report_type_directory "$report_type")"
    slug="$(atlas_dev_report_slug "$report_name")"
    timestamp="$(atlas_dev_timestamp_compact)"

    if [[ -z "$slug" ]]; then
        atlas_dev_error "Report name did not produce a valid filename."
        return 2
    fi

    printf '%s/%s-%s.md\n' "$directory" "$timestamp" "$slug"
}

atlas_dev_report_prepare_directory() {
    local report_type="${1:?Report type is required.}"
    local directory

    directory="$(atlas_dev_report_type_directory "$report_type")"

    mkdir -p "$directory"

    printf '%s\n' "$directory"
}

atlas_dev_report_write_header() {
    local report_path="${1:?Report path is required.}"
    local report_title="${2:?Report title is required.}"
    local report_type="${3:?Report type is required.}"
    local branch
    local commit

    atlas_dev_guard_git_repository

    branch="$(git branch --show-current)"
    commit="$(git rev-parse HEAD)"

    cat > "$report_path" <<HEADER
# $report_title

- Report type: \`$report_type\`
- Generated: \`$(atlas_dev_timestamp)\`
- Branch: \`$branch\`
- Commit: \`$commit\`

HEADER
}

atlas_dev_report_append_section() {
    local report_path="${1:?Report path is required.}"
    local section_title="${2:?Section title is required.}"

    {
        printf '## %s\n\n' "$section_title"
        cat
        printf '\n'
    } >> "$report_path"
}

atlas_dev_report_append_command() {
    local report_path="${1:?Report path is required.}"
    local section_title="${2:?Section title is required.}"
    shift 2

    if [[ "$#" -eq 0 ]]; then
        atlas_dev_error "A report command is required."
        return 2
    fi

    {
        printf '## %s\n\n' "$section_title"
        printf '```text\n'
        printf '$'
        printf ' %q' "$@"
        printf '\n\n'

        "$@" 2>&1
        local command_status=$?

        printf '\n[exit status: %s]\n' "$command_status"
        printf '```\n\n'

        return "$command_status"
    } >> "$report_path"
}

atlas_dev_report_finalize() {
    local report_path="${1:?Report path is required.}"

    atlas_dev_guard_file "$report_path"

    {
        printf '%s\n' '---'
        printf '\n'
        printf 'Report completed at `%s`.\n' "$(atlas_dev_timestamp)"
    } >> "$report_path"

    atlas_dev_success "Report written: $report_path"
}

atlas_dev_is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

if ! atlas_dev_is_sourced; then
    atlas_dev_error \
        "atlas-report.sh is a library and must be sourced, not executed."
    exit 2
fi
