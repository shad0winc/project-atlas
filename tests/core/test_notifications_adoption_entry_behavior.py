from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"
COMMIT = "a" * 40


def run_entry(
    tmp_path: Path,
    scenario: str,
):
    source = DEPLOYMENT.read_text(encoding="utf-8")

    start = source.index(
        "atlas_deployment_adopt_notifications_guarded() {"
    )
    end = source.index(
        "atlas_deployment_adopt_sports() {",
        start,
    )
    wrapper = source[start:end]

    # Assert the actual production constants before making a
    # temporary test-only copy with isolated checkout paths.
    canonical_literal = "'/opt/project-atlas-v1-main'"
    checkout_literal = "local checkout='/opt/project-atlas'"

    assert wrapper.count(canonical_literal) == 1
    assert wrapper.count(checkout_literal) == 1
    assert "atlas_deployment_validate_source || return 1" in wrapper

    canonical = tmp_path / "canonical"
    alternate = tmp_path / "alternate"
    historical = tmp_path / "historical"
    canonical.mkdir()
    alternate.mkdir()
    historical.mkdir()

    wrapper = wrapper.replace(
        canonical_literal,
        "'" + str(canonical) + "'",
        1,
    ).replace(
        checkout_literal,
        "local checkout='" + str(historical) + "'",
        1,
    )

    # This file lives exclusively inside pytest's temporary
    # directory. The repository implementation is not rewritten.
    test_wrapper = tmp_path / "isolated-entry.sh"
    test_wrapper.write_text(wrapper, encoding="utf-8")

    events = tmp_path / "events"

    script = r"""
set -euo pipefail

source "$ATLAS_TEST_DEPLOYMENT"
source "$ATLAS_TEST_WRAPPER"

atlas_deployment_validate_source() {
  printf 'validate\n' >> "$ATLAS_TEST_EVENTS"
  [[ "$ATLAS_TEST_SCENARIO" != source-rejected ]]
}

git() {
  printf 'git\n' >> "$ATLAS_TEST_EVENTS"

  [[ "$#" -eq 4 &&
     "$1" == -C &&
     "$2" == "$ATLAS_TEST_HISTORICAL" &&
     "$3" == rev-parse &&
     "$4" == HEAD ]] || return 90

  if [[ "$ATLAS_TEST_SCENARIO" == invalid-commit ]]; then
    printf 'invalid\n'
  else
    printf '%s\n' "$ATLAS_TEST_COMMIT"
  fi
}

atlas_execution_exclusion_acquire() {
  printf 'exclusion-acquire\n' >> "$ATLAS_TEST_EVENTS"

  [[ "$ATLAS_TEST_SCENARIO" != exclusion-held ]] || return 91

  printf -v "$1" '%s' 99
}

atlas_execution_exclusion_release() {
  printf 'exclusion-release:%s\n' "$1" >> "$ATLAS_TEST_EVENTS"
  [[ "$ATLAS_TEST_SCENARIO" != release-failed ]]
}

atlas_deployment_adopt_notifications() {
  printf 'adopt\n' >> "$ATLAS_TEST_EVENTS"

  [[ "$#" -eq 2 &&
     "$1" == "$ATLAS_TEST_HISTORICAL" &&
     "$2" == "$ATLAS_TEST_COMMIT" ]] || return 92

  [[ "$ATLAS_TEST_SCENARIO" != adopt-failed ]]
}

case "$ATLAS_TEST_SCENARIO" in
  extra-argument)
    atlas_deployment_adopt_notifications_guarded unexpected
    ;;
  *)
    atlas_deployment_adopt_notifications_guarded
    ;;
esac
"""

    environment = os.environ.copy()
    environment.update({
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_WRAPPER": str(test_wrapper),
        "ATLAS_TEST_EVENTS": str(events),
        "ATLAS_TEST_SCENARIO": scenario,
        "ATLAS_TEST_HISTORICAL": str(historical),
        "ATLAS_TEST_COMMIT": COMMIT,
        "ATLAS_PROJECT_DIR": str(
            alternate if scenario == "alternate-checkout"
            else canonical
        ),
    })

    if scenario == "missing-historical":
        historical.rmdir()

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    event_lines = (
        events.read_text(encoding="utf-8").splitlines()
        if events.exists()
        else []
    )

    return result, event_lines


@pytest.mark.parametrize(
    ("scenario", "expected_events"),
    [
        ("extra-argument", []),
        ("alternate-checkout", []),
        ("source-rejected", ["validate"]),
        ("missing-historical", ["validate"]),
        ("invalid-commit", ["validate", "git"]),
        (
            "exclusion-held",
            ["validate", "git", "exclusion-acquire"],
        ),
    ],
)
def test_rejects_before_adoption(
    tmp_path: Path,
    scenario: str,
    expected_events: list[str],
):
    result, events = run_entry(tmp_path, scenario)

    assert result.returncode != 0, result.stderr
    assert events == expected_events
    assert "adopt" not in events
    assert not any(
        item.startswith("exclusion-release:")
        for item in events
    )


@pytest.mark.parametrize(
    ("scenario", "expected_returncode"),
    [
        ("success", 0),
        ("adopt-failed", 1),
        ("release-failed", 1),
    ],
)
def test_exclusion_is_released_after_adoption_attempt(
    tmp_path: Path,
    scenario: str,
    expected_returncode: int,
):
    result, events = run_entry(tmp_path, scenario)

    assert result.returncode == expected_returncode, (
        result.stderr
    )
    assert events == [
        "validate",
        "git",
        "exclusion-acquire",
        "adopt",
        "exclusion-release:99",
    ]

def test_historical_adoption_boundary_is_documented() -> None:
    source = DEPLOYMENT.read_text(encoding="utf-8")

    internal_start = source.index(
        "atlas_deployment_adopt_notifications() {"
    )
    guarded_start = source.index(
        "atlas_deployment_adopt_notifications_guarded() {",
        internal_start,
    )
    sports_start = source.index(
        "atlas_deployment_adopt_sports() {",
        guarded_start,
    )

    internal = source[internal_start:guarded_start]
    guarded = source[guarded_start:sports_start]

    for body in (internal, guarded):
        assert "docker compose" not in body
        assert "docker restart" not in body
        assert "docker run" not in body
        assert "atlas_update_apply_scope" not in body
        assert "atlas_deployment_restore_surface" not in body

    assert (
        "Historical-worker adoption only: record and attest"
        in source
    )
    assert (
        "Notifications adoption records and attests "
        "the existing historical worker."
        in source
    )
    assert (
        "Notifications deployment requires a separate "
        "verified lifecycle contract."
        in source
    )
