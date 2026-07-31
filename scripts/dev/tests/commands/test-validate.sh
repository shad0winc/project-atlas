#!/usr/bin/env bash

# Contract test for the Engineering Toolkit validate command.

set -Eeuo pipefail

ATLAS_DEV_COMMAND_TEST_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_TEST_DIR/../lib/atlas-test-common.sh"

cd "$ATLAS_PROJECT_DIR"

atlas_test_begin "validate command contract"

read -r worktree_before index_before \
    < <(atlas_capture_repository_state)

validate_status=
validate_stdout=
validate_stderr=

atlas_capture_command \
    validate_status \
    validate_stdout \
    validate_stderr \
    -- \
    "$ATLAS_DEV_DIR/atlas-dev" validate

atlas_assert_equals \
    0 \
    "$validate_status" \
    "The validate command returns status 0."

atlas_assert_stdout_contains \
    "Starting Atlas engineering validation." \
    "The validate command reports validation startup." \
    printf '%s\n' "$validate_stdout"

atlas_assert_stdout_contains \
    "Atlas engineering validation completed successfully." \
    "The validate command reports successful completion." \
    printf '%s\n' "$validate_stdout"

help_status=
help_stdout=
help_stderr=

atlas_capture_command \
    help_status \
    help_stdout \
    help_stderr \
    -- \
    "$ATLAS_DEV_DIR/atlas-dev" validate --help

atlas_assert_equals \
    0 \
    "$help_status" \
    "The validate help interface returns status 0."

atlas_assert_stdout_contains \
    "Project Atlas Engineering Toolkit — Validate" \
    "The validate help interface prints its command title." \
    printf '%s\n' "$help_stdout"

atlas_assert_stdout_contains \
    "scripts/dev/atlas-dev validate --help" \
    "The validate help interface documents the supported help form." \
    printf '%s\n' "$help_stdout"

unexpected_status=
unexpected_stdout=
unexpected_stderr=

atlas_capture_command \
    unexpected_status \
    unexpected_stdout \
    unexpected_stderr \
    -- \
    "$ATLAS_DEV_DIR/atlas-dev" validate unexpected

atlas_assert_equals \
    2 \
    "$unexpected_status" \
    "The validate command rejects unexpected arguments with status 2."

atlas_assert_stdout_contains \
    "Unexpected validate argument: unexpected" \
    "The validate command identifies the rejected argument." \
    printf '%s\n' "$unexpected_stderr"

atlas_assert_stdout_contains \
    "Project Atlas Engineering Toolkit — Validate" \
    "The validate command prints help after argument misuse." \
    printf '%s\n' "$unexpected_stderr"

read -r worktree_after index_after \
    < <(atlas_capture_repository_state)

atlas_assert_equals \
    "$worktree_before" \
    "$worktree_after" \
    "The validate command does not modify tracked working-tree content."

atlas_assert_equals \
    "$index_before" \
    "$index_after" \
    "The validate command does not modify staged repository content."

atlas_test_end
