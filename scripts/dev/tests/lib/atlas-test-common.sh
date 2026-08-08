#!/usr/bin/env bash

# Shared bootstrap and repository path resolution for Project Atlas
# Engineering Toolkit contract tests.
#
# This file is intended to be sourced.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf '%s\n' \
        "ERROR: atlas-test-common.sh is a library and must be sourced, not executed." \
        >&2
    exit 2
fi

if [[ -n "${ATLAS_DEV_TEST_COMMON_LOADED:-}" ]]; then
    return 0
fi

readonly ATLAS_DEV_TEST_COMMON_LOADED=1

ATLAS_DEV_TEST_COMMON_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

ATLAS_DEV_TESTS_DIR="$(
    cd "$ATLAS_DEV_TEST_COMMON_DIR/.." &&
        pwd
)"

ATLAS_DEV_DIR="$(
    cd "$ATLAS_DEV_TESTS_DIR/.." &&
        pwd
)"

ATLAS_PROJECT_DIR="$(
    cd "$ATLAS_DEV_DIR/../.." &&
        pwd
)"

readonly ATLAS_DEV_TEST_COMMON_DIR
readonly ATLAS_DEV_TESTS_DIR
readonly ATLAS_DEV_DIR
readonly ATLAS_PROJECT_DIR

ATLAS_DEV_TEST_RUNTIME="$ATLAS_DEV_DIR/lib/atlas-test.sh"
readonly ATLAS_DEV_TEST_RUNTIME

if [[ ! -f "$ATLAS_DEV_TEST_RUNTIME" ]]; then
    printf 'ERROR: Required test runtime does not exist: %s\n' \
        "$ATLAS_DEV_TEST_RUNTIME" >&2
    return 2
fi

# shellcheck source=/dev/null
source "$ATLAS_DEV_TEST_RUNTIME"
