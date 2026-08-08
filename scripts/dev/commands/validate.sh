#!/usr/bin/env bash
set -Eeuo pipefail

ATLAS_DEV_VALIDATE_COMMAND_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

ATLAS_DEV_VALIDATE_DEV_DIR="$(
    cd "$ATLAS_DEV_VALIDATE_COMMAND_DIR/.." &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_VALIDATE_DEV_DIR/lib/atlas-command.sh"

atlas_dev_command_initialize "${BASH_SOURCE[0]}"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_DEV_DIR/lib/atlas-validation.sh"

atlas_dev_validate_print_help() {
    cat <<'HELP'
Project Atlas Engineering Toolkit — Validate

Usage:
  scripts/dev/atlas-dev validate
  scripts/dev/atlas-dev validate help
  scripts/dev/atlas-dev validate --help

Description:
  Run foundational repository validation for the Atlas Engineering Toolkit.

Checks:
  - Atlas repository identity
  - Git diff formatting
  - Bash syntax for toolkit files

The validation workflow does not require a clean working tree.
HELP
}

atlas_dev_validate_parse_arguments() {
    atlas_dev_command_parse_standard_help \
        validate \
        atlas_dev_validate_print_help \
        "$@"
}

atlas_dev_validate_run() {
    atlas_dev_info "Starting Atlas engineering validation."

    atlas_dev_validate_repository_basics

    atlas_dev_success "Atlas engineering validation completed successfully."
}

main() {
    atlas_dev_command_execute \
        atlas_dev_validate_parse_arguments \
        atlas_dev_validate_run \
        "$@"
}

main "$@"
