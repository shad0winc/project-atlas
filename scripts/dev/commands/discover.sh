#!/usr/bin/env bash
set -Eeuo pipefail

ATLAS_DEV_DISCOVER_COMMAND_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

ATLAS_DEV_DISCOVER_DEV_DIR="$(
    cd "$ATLAS_DEV_DISCOVER_COMMAND_DIR/.." &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_DISCOVER_DEV_DIR/lib/atlas-command.sh"

atlas_dev_command_initialize "${BASH_SOURCE[0]}"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_DEV_DIR/lib/atlas-discovery.sh"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_DEV_DIR/lib/atlas-report.sh"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_DEV_DIR/lib/atlas-validation.sh"

atlas_dev_discover_print_help() {
    cat <<'HELP'
Project Atlas Engineering Toolkit — Discover

Usage:
  scripts/dev/atlas-dev discover
  scripts/dev/atlas-dev discover help
  scripts/dev/atlas-dev discover --help

Description:
  Validate the Project Atlas repository and generate a standardized
  engineering discovery report.

Report location:
  reports/discovery/

The report contains:
  - repository and Git metadata
  - Engineering Toolkit file inventory
  - toolkit TODO and FIXME references
  - complete atlas-inventory output

Discovery is read-only. It does not modify tracked repository files.
HELP
}

atlas_dev_discover_parse_arguments() {
    atlas_dev_command_parse_standard_help \
        discover \
        atlas_dev_discover_print_help \
        "$@"
}

atlas_dev_discover_summary() {
    atlas_discovery_section "ENGINEERING TOOLKIT SNAPSHOT"

    atlas_discovery_command \
        "Git working tree status" \
        git status --short

    atlas_discovery_note "Engineering Toolkit files"
    atlas_discovery_find_files scripts/dev

    atlas_discovery_search \
        "Toolkit TODO and FIXME references" \
        'TODO|FIXME' \
        100 \
        scripts/dev
}

atlas_dev_discover_run() {
    local report_path
    local inventory_status=0

    atlas_dev_info "Starting Atlas engineering discovery."

    atlas_dev_validate_repository_basics
    atlas_dev_guard_file "scripts/dev/atlas-inventory"

    atlas_dev_report_prepare_directory discovery >/dev/null

    report_path="$(
        atlas_dev_report_path \
            discovery \
            "Engineering Toolkit Discovery"
    )"

    atlas_dev_report_write_header \
        "$report_path" \
        "Project Atlas Engineering Discovery Report" \
        "discovery"

    atlas_dev_discover_summary |
        atlas_dev_report_append_section \
            "$report_path" \
            "Engineering Toolkit Discovery"

    set +e
    atlas_dev_report_append_command \
        "$report_path" \
        "Repository Contract Inventory" \
        scripts/dev/atlas-inventory --stdout
    inventory_status=$?
    set -e

    if [[ "$inventory_status" -ne 0 ]]; then
        printf '%s\n' \
            "The repository inventory command returned status $inventory_status." |
            atlas_dev_report_append_section \
                "$report_path" \
                "Discovery Warning"
    fi

    atlas_dev_report_finalize "$report_path"

    if [[ "$inventory_status" -ne 0 ]]; then
        atlas_dev_error \
            "Discovery report was preserved, but inventory collection failed."
        atlas_dev_error "Report: $report_path"
        return "$inventory_status"
    fi

    atlas_dev_success "Atlas engineering discovery completed successfully."
    atlas_dev_success "Discovery report: $report_path"
}

main() {
    atlas_dev_command_execute \
        atlas_dev_discover_parse_arguments \
        atlas_dev_discover_run \
        "$@"
}

main "$@"
