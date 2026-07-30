#!/usr/bin/env bash

# Contract tests for the dependency-free Engineering Toolkit test runtime.

set -euo pipefail

TEST_FILE="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)/$(basename "${BASH_SOURCE[0]}")"

TEST_DIR="$(dirname "$TEST_FILE")"

# shellcheck source=/dev/null
source "$TEST_DIR/../lib/atlas-test-common.sh"

atlas_test_begin "atlas-test runtime contract"

atlas_assert_equals \
    "1" \
    "$ATLAS_DEV_TEST_RUNTIME_LOADED" \
    "The test runtime records its loaded state."

atlas_assert_equals \
    "1" \
    "$ATLAS_DEV_TEST_ACTIVE" \
    "The outer contract test is active."

atlas_assert_equals \
    "atlas-test runtime contract" \
    "$ATLAS_DEV_TEST_NAME" \
    "The active test name is retained."

atlas_assert_command_succeeds \
    "Repeated sourcing succeeds without replacing the active context." \
    bash -c "
        set -euo pipefail

        source '$ATLAS_DEV_TEST_RUNTIME'

        source '$ATLAS_DEV_TEST_RUNTIME'

        [[ \"\$ATLAS_DEV_TEST_RUNTIME_LOADED\" -eq 1 ]]
        [[ \"\$ATLAS_DEV_TEST_ACTIVE\" -eq 0 ]]
        [[ -z \"\$ATLAS_DEV_TEST_NAME\" ]]
        [[ \"\$ATLAS_DEV_TEST_ASSERTIONS\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_PASSED\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_FAILED\" -eq 0 ]]
        [[ \"\${#ATLAS_DEV_TEST_FAILURES[@]}\" -eq 0 ]]
    "

atlas_assert_command_succeeds \
    "Assertions without an active test return status 2." \
    bash -c "
        set -u

        source '$ATLAS_DEV_TEST_RUNTIME'

        status=0
        atlas_assert_equals expected actual >/dev/null 2>&1 ||
            status=\$?

        [[ \"\$status\" -eq 2 ]]
        [[ \"\$ATLAS_DEV_TEST_ASSERTIONS\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_FAILED\" -eq 0 ]]
    "

atlas_assert_command_succeeds \
    "Nested test contexts are rejected without replacing active state." \
    bash -c "
        set -euo pipefail

        source '$ATLAS_DEV_TEST_RUNTIME'

        atlas_test_begin first >/dev/null

        status=0
        atlas_test_begin second >/dev/null 2>&1 ||
            status=\$?

        [[ \"\$status\" -eq 2 ]]
        [[ \"\$ATLAS_DEV_TEST_ACTIVE\" -eq 1 ]]
        [[ \"\$ATLAS_DEV_TEST_NAME\" == first ]]
    "

atlas_assert_command_succeeds \
    "A passing child test returns zero and resets its state." \
    bash -c "
        set -euo pipefail

        source '$ATLAS_DEV_TEST_RUNTIME'

        atlas_test_begin passing >/dev/null

        atlas_assert_equals atlas atlas >/dev/null
        atlas_assert_not_equals atlas other >/dev/null
        atlas_assert_file_exists '$ATLAS_DEV_DIR/atlas-dev' >/dev/null
        atlas_assert_directory_exists '$ATLAS_DEV_DIR/lib' >/dev/null
        atlas_assert_command_succeeds success true >/dev/null
        atlas_assert_command_fails failure false >/dev/null

        atlas_test_end >/dev/null

        [[ \"\$ATLAS_DEV_TEST_ACTIVE\" -eq 0 ]]
        [[ -z \"\$ATLAS_DEV_TEST_NAME\" ]]
        [[ \"\$ATLAS_DEV_TEST_ASSERTIONS\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_PASSED\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_FAILED\" -eq 0 ]]
        [[ \"\${#ATLAS_DEV_TEST_FAILURES[@]}\" -eq 0 ]]
    "

atlas_assert_command_succeeds \
    "Failed assertions continue under set -e and aggregate at test end." \
    bash -c "
        set -euo pipefail

        source '$ATLAS_DEV_TEST_RUNTIME'

        atlas_test_begin failing >/dev/null

        atlas_assert_equals expected actual >/dev/null 2>&1
        atlas_assert_not_equals same same >/dev/null 2>&1
        atlas_assert_file_exists missing.file >/dev/null 2>&1
        atlas_assert_directory_exists missing.directory >/dev/null 2>&1
        atlas_assert_command_succeeds command-failure false >/dev/null 2>&1
        atlas_assert_command_fails command-success true >/dev/null 2>&1

        [[ \"\$ATLAS_DEV_TEST_ASSERTIONS\" -eq 6 ]]
        [[ \"\$ATLAS_DEV_TEST_PASSED\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_FAILED\" -eq 6 ]]
        [[ \"\${#ATLAS_DEV_TEST_FAILURES[@]}\" -eq 6 ]]

        status=0
        atlas_test_end >/dev/null 2>&1 ||
            status=\$?

        [[ \"\$status\" -eq 1 ]]
        [[ \"\$ATLAS_DEV_TEST_ACTIVE\" -eq 0 ]]
        [[ -z \"\$ATLAS_DEV_TEST_NAME\" ]]
        [[ \"\$ATLAS_DEV_TEST_ASSERTIONS\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_PASSED\" -eq 0 ]]
        [[ \"\$ATLAS_DEV_TEST_FAILED\" -eq 0 ]]
        [[ \"\${#ATLAS_DEV_TEST_FAILURES[@]}\" -eq 0 ]]
    "

atlas_assert_command_succeeds \
    "The resolved repository root contains the Atlas runtime CLI." \
    test -f "$ATLAS_PROJECT_DIR/scripts/atlas"

atlas_test_end
