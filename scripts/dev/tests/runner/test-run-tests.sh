#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$SCRIPT_DIR/../lib/atlas-test-common.sh"

atlas_test_begin "run-tests contract"

read -r worktree_before index_before \
    < <(atlas_capture_repository_state)

runner="$ATLAS_DEV_TESTS_DIR/run-tests"

#
# Single contract
#

single_status=
single_stdout=
single_stderr=

atlas_capture_command \
    single_status \
    single_stdout \
    single_stderr \
    -- \
    "$runner" runtime/test-atlas-test.sh

atlas_assert_equals \
    0 \
    "$single_status" \
    "The runner succeeds for a single contract."

atlas_assert_stdout_contains \
    "Discovered: 1" \
    "The runner discovers one requested contract." \
    printf '%s\n' "$single_stdout"

atlas_assert_stdout_contains \
    "Passed: 1" \
    "The runner reports one passing contract." \
    printf '%s\n' "$single_stdout"

atlas_assert_stdout_contains \
    "Failed: 0" \
    "The runner reports zero failures." \
    printf '%s\n' "$single_stdout"

#
# Multiple contracts
#

multiple_status=
multiple_stdout=
multiple_stderr=

atlas_capture_command \
    multiple_status \
    multiple_stdout \
    multiple_stderr \
    -- \
    "$runner" \
        runtime/test-atlas-test.sh \
        commands/test-validate.sh

atlas_assert_equals \
    0 \
    "$multiple_status" \
    "The runner succeeds for multiple contracts."

atlas_assert_stdout_contains \
    "Discovered: 2" \
    "The runner discovers both requested contracts." \
    printf '%s\n' "$multiple_stdout"

atlas_assert_stdout_contains \
    "Passed: 2" \
    "The runner reports two passing contracts." \
    printf '%s\n' "$multiple_stdout"

atlas_assert_stdout_contains \
    "Failed: 0" \
    "The runner reports zero failures." \
    printf '%s\n' "$multiple_stdout"

#
# Missing contract
#

missing_status=
missing_stdout=
missing_stderr=

atlas_capture_command \
    missing_status \
    missing_stdout \
    missing_stderr \
    -- \
    "$runner" does/not/exist.sh

atlas_assert_equals \
    2 \
    "$missing_status" \
    "Missing contracts return status 2."

atlas_assert_stdout_contains \
    "Contract test not found" \
    "Missing contracts produce a helpful error." \
    printf '%s\n' "$missing_stderr"

read -r worktree_after index_after \
    < <(atlas_capture_repository_state)

atlas_assert_equals \
    "$worktree_before" \
    "$worktree_after" \
    "The runner does not modify tracked working-tree content."

atlas_assert_equals \
    "$index_before" \
    "$index_after" \
    "The runner does not modify staged repository content."

atlas_test_end
