from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts/commands/deployment.sh"
CORE_IMAGE = "sha256:" + "a" * 64
NOTIFICATIONS_IMAGE = "sha256:" + "b" * 64
TRANSACTION_ID = "baseline-test-new"


def invoke(tmp_path: Path, scenario: str):
    baseline = tmp_path / "baseline"
    transaction = tmp_path / TRANSACTION_ID
    baseline.mkdir()
    transaction.mkdir()

    (baseline / "images.tsv").write_text(
        "core|docker-compose.yml|core|core-service|/core-service|"
        f"core:test|{CORE_IMAGE}\n"
        "notifications|modules/notifications/docker-compose.yml|"
        "notifications|atlas-notifications-worker|"
        f"/atlas-notifications-worker|worker:test|{NOTIFICATIONS_IMAGE}\n",
        encoding="utf-8",
    )

    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"

    # Every Docker operation is intercepted by this fixture executable.
    # No real Docker executable is called.
    docker.write_text(
        r'''#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$*" >> "$ATLAS_TEST_DOCKER_EVENTS"

[[ "${1:-}" == image ]] || exit 90
shift

case "${1:-}" in
  inspect)
    shift

    if [[ "${1:-}" == --format ]]; then
      [[ "$#" -eq 3 ]] || exit 91
      [[ "$2" == '{{.Id}}' ]] || exit 92
      tag="$3"
      case "$tag" in
        atlas-rollback:baseline-test-new-1)
          printf '%s\n' "$ATLAS_TEST_CORE_IMAGE"
          ;;
        atlas-rollback:baseline-test-new-2)
          printf '%s\n' "$ATLAS_TEST_NOTIFICATIONS_IMAGE"
          ;;
        *)
          exit 93
          ;;
      esac
    else
      [[ "$#" -eq 1 ]] || exit 94
      case "$1" in
        "$ATLAS_TEST_CORE_IMAGE"|"$ATLAS_TEST_NOTIFICATIONS_IMAGE")
          exit 0
          ;;
        *)
          exit 95
          ;;
      esac
    fi
    ;;

  tag)
    [[ "$#" -eq 3 ]] || exit 96

    if [[ "$ATLAS_TEST_SCENARIO" == second-tag-fails &&
          "$2" == "$ATLAS_TEST_NOTIFICATIONS_IMAGE" ]]; then
      exit 97
    fi

    case "$2|$3" in
      "$ATLAS_TEST_CORE_IMAGE|atlas-rollback:baseline-test-new-1"|"$ATLAS_TEST_NOTIFICATIONS_IMAGE|atlas-rollback:baseline-test-new-2")
        exit 0
        ;;
      *)
        exit 98
        ;;
    esac
    ;;

  *)
    exit 99
    ;;
esac
''',
        encoding="utf-8",
    )
    docker.chmod(0o755)

    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_DOCKER_EVENTS": str(tmp_path / "docker-events"),
        "ATLAS_TEST_CORE_IMAGE": CORE_IMAGE,
        "ATLAS_TEST_NOTIFICATIONS_IMAGE": NOTIFICATIONS_IMAGE,
        "ATLAS_TEST_SCENARIO": scenario,
    }

    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; '
            'source "$ATLAS_TEST_DEPLOYMENT"; '
            'atlas_deployment_preserve_rollback_images "$1" "$2"',
            "preservation-test",
            str(baseline),
            str(transaction),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    log = tmp_path / "docker-events"
    events = (
        log.read_text(encoding="utf-8").splitlines()
        if log.exists() else []
    )
    return result, transaction, events


def test_preserves_core_and_notifications_images(
    tmp_path: Path,
) -> None:
    result, transaction, events = invoke(tmp_path, "success")

    assert result.returncode == 0, result.stderr
    assert (
        transaction / "rollback-images.tsv"
    ).read_text(encoding="utf-8").splitlines() == [
        f"{CORE_IMAGE}|atlas-rollback:{TRANSACTION_ID}-1",
        f"{NOTIFICATIONS_IMAGE}|atlas-rollback:{TRANSACTION_ID}-2",
    ]

    assert (
        f"image tag {CORE_IMAGE} "
        f"atlas-rollback:{TRANSACTION_ID}-1"
    ) in events
    assert (
        f"image tag {NOTIFICATIONS_IMAGE} "
        f"atlas-rollback:{TRANSACTION_ID}-2"
    ) in events

    assert (
        "image inspect --format {{.Id}} "
        f"atlas-rollback:{TRANSACTION_ID}-2"
    ) in events


def test_second_image_tag_failure_does_not_publish_manifest(
    tmp_path: Path,
) -> None:
    result, transaction, events = invoke(
        tmp_path, "second-tag-fails"
    )

    assert result.returncode != 0
    assert not (transaction / "rollback-images.tsv").exists()
    assert (
        f"image tag {NOTIFICATIONS_IMAGE} "
        f"atlas-rollback:{TRANSACTION_ID}-2"
    ) in events


@pytest.mark.parametrize("scenario", ["success", "second-tag-fails"])
def test_preservation_fixture_never_invokes_compose(
    tmp_path: Path,
    scenario: str,
) -> None:
    _, _, events = invoke(tmp_path, scenario)
    assert events
    assert all(event.startswith("image ") for event in events)
