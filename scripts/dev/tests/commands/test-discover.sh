#!/usr/bin/env bash
set -Eeuo pipefail

ATLAS_DEV_COMMAND_TEST_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
        pwd
)"

# shellcheck source=/dev/null
source "$ATLAS_DEV_COMMAND_TEST_DIR/../lib/atlas-test-common.sh"

cd "$ATLAS_PROJECT_DIR"

ATLAS_DISCOVER_REPORT_DIR="$ATLAS_PROJECT_DIR/reports/discovery"
ATLAS_DISCOVER_BASELINE_REPORTS="$(mktemp)"
ATLAS_DISCOVER_CURRENT_REPORTS="$(mktemp)"
ATLAS_DISCOVER_STDERR="$(mktemp)"

atlas_discover_list_reports() {
    local output_file="$1"

    if [[ ! -d "$ATLAS_DISCOVER_REPORT_DIR" ]]; then
        : > "$output_file"
        return 0
    fi

    find "$ATLAS_DISCOVER_REPORT_DIR" \
        -maxdepth 1 \
        -type f \
        -print |
        LC_ALL=C sort > "$output_file"
}

atlas_discover_cleanup() {
    local report_path

    atlas_discover_list_reports "$ATLAS_DISCOVER_CURRENT_REPORTS"

    while IFS= read -r report_path; do
        [[ -n "$report_path" ]] || continue
        rm -f -- "$report_path"
    done < <(
        comm -13 \
            "$ATLAS_DISCOVER_BASELINE_REPORTS" \
            "$ATLAS_DISCOVER_CURRENT_REPORTS"
    )

    rm -f \
        "$ATLAS_DISCOVER_BASELINE_REPORTS" \
        "$ATLAS_DISCOVER_CURRENT_REPORTS" \
        "$ATLAS_DISCOVER_STDERR"
}

trap atlas_discover_cleanup EXIT

atlas_discover_list_reports "$ATLAS_DISCOVER_BASELINE_REPORTS"

atlas_test_begin "discover command contract"

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

discover_status=0
discover_output="$(
    "$ATLAS_DEV_DIR/atlas-dev" discover
)" || discover_status=$?

atlas_assert_equals \
    0 \
    "$discover_status" \
    "The discover command returns status 0."

atlas_assert_stdout_contains \
    "Atlas engineering discovery completed successfully." \
    "The discover command reports successful completion." \
    printf '%s\n' "$discover_output"

atlas_assert_stdout_contains \
    "Discovery report:" \
    "The discover command reports the generated report path." \
    printf '%s\n' "$discover_output"

report_path="$(
    printf '%s\n' "$discover_output" |
        sed -n 's/^.*Discovery report: //p' |
        tail -n 1
)"

atlas_assert_command_succeeds \
    "The discover command creates the reported discovery artifact." \
    test -f "$ATLAS_PROJECT_DIR/$report_path"

help_status=0
help_output="$(
    "$ATLAS_DEV_DIR/atlas-dev" discover --help
)" || help_status=$?

atlas_assert_equals \
    0 \
    "$help_status" \
    "The discover help interface returns status 0."

atlas_assert_stdout_contains \
    "Project Atlas Engineering Toolkit — Discover" \
    "The discover help interface prints its command title." \
    printf '%s\n' "$help_output"

atlas_assert_stdout_contains \
    "scripts/dev/atlas-dev discover --help" \
    "The discover help interface documents the supported help form." \
    printf '%s\n' "$help_output"

unexpected_status=0

"$ATLAS_DEV_DIR/atlas-dev" discover unexpected \
    >/dev/null \
    2>"$ATLAS_DISCOVER_STDERR" ||
    unexpected_status=$?

atlas_assert_equals \
    2 \
    "$unexpected_status" \
    "The discover command rejects unexpected arguments with status 2."

atlas_assert_stdout_contains \
    "Unexpected discover argument: unexpected" \
    "The discover command identifies the rejected argument." \
    cat "$ATLAS_DISCOVER_STDERR"

atlas_assert_stdout_contains \
    "Project Atlas Engineering Toolkit — Discover" \
    "The discover command prints help after argument misuse." \
    cat "$ATLAS_DISCOVER_STDERR"

worktree_after="$(
    git diff --binary --no-ext-diff |
        sha256sum |
        awk '{print $1}'
)"

index_after="$(
    git diff --cached --binary --no-ext-diff |
        sha256sum |
        awk '{print $1}'
)"

atlas_assert_equals \
    "$worktree_before" \
    "$worktree_after" \
    "The discover command does not modify tracked working-tree content."

atlas_assert_equals \
    "$index_before" \
    "$index_after" \
    "The discover command does not modify staged repository content."

atlas_test_end
