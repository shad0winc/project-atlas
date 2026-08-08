#!/usr/bin/env bash

# Run Project Atlas Engineering Toolkit contract tests.

set -Eeuo pipefail

ATLAS_DEV_TEST_COMMAND_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

ATLAS_DEV_TEST_SCRIPT_DIR="$(
    cd "$ATLAS_DEV_TEST_COMMAND_DIR/.." &&
        pwd
)"

ATLAS_DEV_TEST_RUNNER="$ATLAS_DEV_TEST_SCRIPT_DIR/tests/run-tests"

if [[ "$#" -ne 0 ]]; then
    printf 'ERROR: atlas-dev test does not accept arguments.\n' >&2
    exit 2
fi

if [[ ! -f "$ATLAS_DEV_TEST_RUNNER" ]]; then
    printf 'ERROR: Contract-test runner was not found: %s\n' \
        "$ATLAS_DEV_TEST_RUNNER" >&2
    exit 1
fi

if [[ ! -x "$ATLAS_DEV_TEST_RUNNER" ]]; then
    printf 'ERROR: Contract-test runner is not executable: %s\n' \
        "$ATLAS_DEV_TEST_RUNNER" >&2
    exit 1
fi

"$ATLAS_DEV_TEST_RUNNER"
