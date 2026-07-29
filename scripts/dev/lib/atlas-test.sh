#!/usr/bin/env bash

# Dependency-free contract testing helpers for the Project Atlas
# Engineering Toolkit.
#
# This library provides focused test lifecycle and assertion primitives.
# It does not discover or execute test files.
#
# Test contract:
#
#   1. Source this library.
#   2. Call atlas_test_begin with a descriptive test name.
#   3. Execute one or more atlas_assert_* functions.
#   4. Call atlas_test_end and use its return status.
#
# Assertions collect failures instead of stopping at the first failure.
# Only one test context may be active at a time.
#
# This file is intended to be sourced.

if [[ -n "${ATLAS_DEV_TEST_RUNTIME_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi

readonly ATLAS_DEV_TEST_RUNTIME_LOADED=1

ATLAS_DEV_TEST_LIBRARY_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_TEST_LIBRARY_DIR/atlas-utils.sh"

ATLAS_DEV_TEST_ACTIVE=0
ATLAS_DEV_TEST_NAME=""
ATLAS_DEV_TEST_ASSERTIONS=0
ATLAS_DEV_TEST_PASSED=0
ATLAS_DEV_TEST_FAILED=0
ATLAS_DEV_TEST_FAILURES=()

atlas_test_reset() {
    ATLAS_DEV_TEST_ACTIVE=0
    ATLAS_DEV_TEST_NAME=""
    ATLAS_DEV_TEST_ASSERTIONS=0
    ATLAS_DEV_TEST_PASSED=0
    ATLAS_DEV_TEST_FAILED=0
    ATLAS_DEV_TEST_FAILURES=()
}

atlas_test_require_active() {
    if [[ "$ATLAS_DEV_TEST_ACTIVE" -ne 1 ]]; then
        atlas_dev_error \
            "No active test. Call atlas_test_begin before using assertions."
        return 2
    fi
}

atlas_test_record_pass() {
    local message="${1:?Assertion message is required.}"

    ATLAS_DEV_TEST_ASSERTIONS=$((ATLAS_DEV_TEST_ASSERTIONS + 1))
    ATLAS_DEV_TEST_PASSED=$((ATLAS_DEV_TEST_PASSED + 1))

    atlas_dev_success "$message"
}

atlas_test_record_failure() {
    local message="${1:?Assertion failure message is required.}"

    ATLAS_DEV_TEST_ASSERTIONS=$((ATLAS_DEV_TEST_ASSERTIONS + 1))
    ATLAS_DEV_TEST_FAILED=$((ATLAS_DEV_TEST_FAILED + 1))
    ATLAS_DEV_TEST_FAILURES+=("$message")

    atlas_dev_error "$message"
}

atlas_test_begin() {
    local test_name="${1:?Test name is required.}"

    if [[ "$ATLAS_DEV_TEST_ACTIVE" -eq 1 ]]; then
        atlas_dev_error \
            "A test is already active: $ATLAS_DEV_TEST_NAME"
        return 2
    fi

    atlas_test_reset

    ATLAS_DEV_TEST_ACTIVE=1
    ATLAS_DEV_TEST_NAME="$test_name"

    atlas_dev_info "TEST: $ATLAS_DEV_TEST_NAME"
}

atlas_assert_true() {
    local description="${1:-Expected command to succeed.}"
    local command_status=0

    atlas_test_require_active || return $?

    shift || true

    if [[ "$#" -eq 0 ]]; then
        atlas_dev_error "atlas_assert_true requires a command."
        return 2
    fi

    "$@" || command_status=$?

    if [[ "$command_status" -eq 0 ]]; then
        atlas_test_record_pass "$description"
        return 0
    fi

    atlas_test_record_failure \
        "$description (exit status: $command_status)"
    return 0
}

atlas_assert_false() {
    local description="${1:-Expected command to fail.}"
    local command_status=0

    atlas_test_require_active || return $?

    shift || true

    if [[ "$#" -eq 0 ]]; then
        atlas_dev_error "atlas_assert_false requires a command."
        return 2
    fi

    "$@" || command_status=$?

    if [[ "$command_status" -ne 0 ]]; then
        atlas_test_record_pass "$description"
        return 0
    fi

    atlas_test_record_failure \
        "$description (command unexpectedly succeeded)"
    return 0
}

atlas_assert_equals() {
    local expected="${1-}"
    local actual="${2-}"
    local description="${3:-Expected values to be equal.}"

    atlas_test_require_active || return $?

    if [[ "$expected" == "$actual" ]]; then
        atlas_test_record_pass "$description"
        return 0
    fi

    atlas_test_record_failure \
        "$description Expected: [$expected] Actual: [$actual]"
    return 0
}

atlas_assert_not_equals() {
    local unexpected="${1-}"
    local actual="${2-}"
    local description="${3:-Expected values to differ.}"

    atlas_test_require_active || return $?

    if [[ "$unexpected" != "$actual" ]]; then
        atlas_test_record_pass "$description"
        return 0
    fi

    atlas_test_record_failure \
        "$description Unexpected value: [$unexpected]"
    return 0
}

atlas_assert_file_exists() {
    local file_path="${1:?File path is required.}"
    local description="${2:-Expected file to exist: $file_path}"

    atlas_test_require_active || return $?

    if [[ -f "$file_path" ]]; then
        atlas_test_record_pass "$description"
        return 0
    fi

    atlas_test_record_failure "$description"
    return 0
}

atlas_assert_directory_exists() {
    local directory_path="${1:?Directory path is required.}"
    local description="${2:-Expected directory to exist: $directory_path}"

    atlas_test_require_active || return $?

    if [[ -d "$directory_path" ]]; then
        atlas_test_record_pass "$description"
        return 0
    fi

    atlas_test_record_failure "$description"
    return 0
}

atlas_assert_command_succeeds() {
    local description="${1:-Expected command to succeed.}"

    shift || true

    atlas_assert_true "$description" "$@"
}

atlas_assert_command_fails() {
    local description="${1:-Expected command to fail.}"

    shift || true

    atlas_assert_false "$description" "$@"
}

atlas_test_end() {
    local failure
    local test_status=0

    atlas_test_require_active || return $?

    printf '\n'
    printf 'Test: %s\n' "$ATLAS_DEV_TEST_NAME"
    printf 'Assertions: %s\n' "$ATLAS_DEV_TEST_ASSERTIONS"
    printf 'Passed: %s\n' "$ATLAS_DEV_TEST_PASSED"
    printf 'Failed: %s\n' "$ATLAS_DEV_TEST_FAILED"

    if [[ "$ATLAS_DEV_TEST_FAILED" -gt 0 ]]; then
        printf '\nFailures:\n'

        for failure in "${ATLAS_DEV_TEST_FAILURES[@]}"; do
            printf '  - %s\n' "$failure"
        done

        atlas_dev_error "Test failed: $ATLAS_DEV_TEST_NAME"
        test_status=1
    else
        atlas_dev_success "Test passed: $ATLAS_DEV_TEST_NAME"
    fi

    atlas_test_reset

    return "$test_status"
}

atlas_dev_is_sourced() {
    [[ "${BASH_SOURCE[0]}" != "$0" ]]
}

if ! atlas_dev_is_sourced; then
    atlas_dev_error \
        "atlas-test.sh is a library and must be sourced, not executed."
    exit 2
fi
