#!/usr/bin/env bash

# Contract test for the Engineering Toolkit test command.

set -Eeuo pipefail

ATLAS_DEV_COMMAND_TEST_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_TEST_DIR/../lib/atlas-test-common.sh"

cd "$ATLAS_PROJECT_DIR"

atlas_test_begin "Engineering Toolkit test command"

worktree_before="$(
    git diff --binary --no-ext-diff |
        sha256sum |
        awk '{print $1}'
)"

index_before="$(
    git diff --cached --binary --no-ext-diff |
        sha256sum |
        awk '{print $1}'
)"

stderr_file="$(mktemp)"
trap 'rm -f "$stderr_file"' EXIT

unexpected_status=0

"$ATLAS_DEV_DIR/atlas-dev" test unexpected \
    >/dev/null \
    2>"$stderr_file" || unexpected_status=$?

atlas_assert_equals \
    2 \
    "$unexpected_status" \
    "The test command rejects unexpected arguments with status 2."

atlas_assert_stdout_contains \
    "ERROR: atlas-dev test does not accept arguments." \
    "The test command reports argument validation errors." \
    cat "$stderr_file"

atlas_assert_worktree_unchanged \
    "$worktree_before" \
    "The test command does not modify tracked working-tree content."

atlas_assert_index_unchanged \
    "$index_before" \
    "The test command does not modify staged repository content."

atlas_test_end
