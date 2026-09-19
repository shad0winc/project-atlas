from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"
COMMIT = "a" * 40
IMAGE = "sha256:" + "b" * 64
ROW = "|".join((
    "notifications",
    "modules/notifications/docker-compose.yml",
    "notifications",
    "atlas-notifications-worker",
    "/atlas-notifications-worker",
    "worker:test",
    IMAGE,
))


def make_archive(path: Path, marker: bytes) -> None:
    with tarfile.open(path, "w:gz") as archive:
        item = tarfile.TarInfo("source-marker")
        item.size = len(marker)
        archive.addfile(item, io.BytesIO(marker))


def invoke(tmp_path: Path, scenario: str):
    root = tmp_path / "deployment"
    root.mkdir()
    previous = root / "previous"
    previous.mkdir()
    checkout = root / "historical"
    checkout.mkdir()

    (root / "current").write_text("previous\n", encoding="utf-8")
    (previous / "status").write_text("verified\n", encoding="utf-8")
    (previous / "metadata").write_text(
        "type=baseline\n"
        "deployment_id=previous\n"
        f"source_commit={COMMIT}\n"
        f"core_commit={COMMIT}\n"
        f"ingress_commit={COMMIT}\n"
        f"sports_commit={COMMIT}\n"
        "notifications_commit=\n",
        encoding="utf-8",
    )
    for name in (
        "core-source.tar.gz",
        "ingress-source.tar.gz",
        "sports-source.tar.gz",
    ):
        make_archive(previous / name, name.encode())

    (previous / "images.tsv").write_text(
        "core|docker-compose.yml|core|core-service|/core-service|"
        f"core:test|{IMAGE}\n",
        encoding="utf-8",
    )

    script = r"""
set -euo pipefail
source "$ATLAS_TEST_DEPLOYMENT"

event() { printf '%s\n' "$1" >> "$ATLAS_TEST_EVENTS"; }

atlas_deployment_new_id() { printf '%s\n' baseline-test-new; }
atlas_deployment_current_id() { cat "$ATLAS_TEST_ROOT/current"; }
atlas_deployment_record_dir() {
  printf '%s/%s\n' "$ATLAS_TEST_ROOT" "$1"
}
atlas_deployment_require_current_record() {
  [[ "$(<"$ATLAS_TEST_ROOT/current")" == previous ]] || return 1
  [[ "$(<"$ATLAS_TEST_ROOT/previous/status")" == verified ]] || return 1
  printf '%s\n' "$ATLAS_TEST_ROOT/previous"
}
atlas_deployment_acquire_lock() {
  event acquire
  mkdir "$ATLAS_TEST_ROOT/lock" || return 1
  printf '%s\n' "$1" > "$ATLAS_TEST_ROOT/lock/owner"
}
atlas_deployment_release_lock() {
  event release
  [[ "$(<"$ATLAS_TEST_ROOT/lock/owner")" == "$1" ]] || return 1
  rm -- "$ATLAS_TEST_ROOT/lock/owner"
  rmdir -- "$ATLAS_TEST_ROOT/lock"
}
atlas_deployment_verify_runtime() {
  if [[ "$1" == "$ATLAS_TEST_ROOT/previous" ]]; then
    event verify-previous
    [[ "$(<"$1/status")" == verified ]]
  else
    event verify-new
    [[ -s "$1/notifications-source.tar.gz" ]] || return 1
    [[ -s "$1/rollback-images.tsv" ]] || return 1
    [[ "$(grep -c '^notifications|' "$1/images.tsv")" == 1 ]]
  fi
}
atlas_deployment_notifications_live_worker_row() {
  event attest
  [[ "$1" == "$ATLAS_TEST_CHECKOUT" ]] || return 1
  [[ "$2" == "$ATLAS_TEST_COMMIT" ]] || return 1
  printf '%s\n' "$ATLAS_TEST_ROW"
}
atlas_deployment_capture_notifications_adoption_evidence() {
  event capture
  [[ "$1" == "$ATLAS_TEST_ROOT/baseline-test-new" ]] || return 1
  [[ "$2" == "$ATLAS_TEST_CHECKOUT" ]] || return 1
  [[ "$3" == "$ATLAS_TEST_COMMIT" ]] || return 1
  cp -- "$ATLAS_TEST_ROOT/previous/core-source.tar.gz" \
    "$1/notifications-source.tar.gz"
  printf '%s\n' "$ATLAS_TEST_ROW" > "$1/notifications-image.tsv"
  printf '%s\n' "$3" > "$1/notifications-source-commit"
}
atlas_deployment_preserve_rollback_images() {
  event preserve-image
  [[ "$1" == "$2" ]] || return 1
  [[ "$(grep -c '^notifications|' "$1/images.tsv")" == 1 ]] || return 1
  if [[ "$ATLAS_TEST_SCENARIO" == image-fails ]]; then
    return 93
  fi
  printf '%s|atlas-rollback:test\n' "$ATLAS_TEST_IMAGE" \
    > "$2/rollback-images.tsv"
}
atlas_deployment_set_status() {
  event status-verified
  printf '%s\n' "$2" > "$1/status"
}
atlas_deployment_set_current() {
  event publish
  [[ "$(<"$ATLAS_TEST_ROOT/baseline-test-new/status")" == verified ]] \
    || return 1
  if [[ "$ATLAS_TEST_SCENARIO" == publish-fails ]]; then
    return 94
  fi
  printf '%s\n' "$1" > "$ATLAS_TEST_ROOT/current"
}

atlas_deployment_adopt_notifications \
  "$ATLAS_TEST_CHECKOUT" "$ATLAS_TEST_COMMIT"
"""

    events = root / "events"
    env = {
        **os.environ,
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_ROOT": str(root),
        "ATLAS_TEST_EVENTS": str(events),
        "ATLAS_TEST_CHECKOUT": str(checkout),
        "ATLAS_TEST_COMMIT": COMMIT,
        "ATLAS_TEST_IMAGE": IMAGE,
        "ATLAS_TEST_ROW": ROW,
        "ATLAS_TEST_SCENARIO": scenario,
    }
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    observed = events.read_text(encoding="utf-8").splitlines() \
        if events.exists() else []
    return result, root, observed


def test_success_preserves_previous_evidence_then_publishes(
    tmp_path: Path,
) -> None:
    result, root, events = invoke(tmp_path, "success")
    assert result.returncode == 0, result.stderr

    record = root / "baseline-test-new"
    assert (root / "current").read_text().strip() == record.name
    assert (record / "status").read_text().strip() == "verified"
    assert (record / "notifications-source-commit").read_text().strip() \
        == COMMIT

    for name in (
        "core-source.tar.gz",
        "ingress-source.tar.gz",
        "sports-source.tar.gz",
    ):
        assert (record / name).read_bytes() == (
            root / "previous" / name
        ).read_bytes()

    manifest = (record / "images.tsv").read_text().splitlines()
    assert len(manifest) == 2
    assert manifest[1] == ROW
    assert (record / "rollback-images.tsv").read_text().strip() \
        == f"{IMAGE}|atlas-rollback:test"

    assert events == [
        "acquire",
        "verify-previous",
        "attest",
        "capture",
        "preserve-image",
        "verify-new",
        "attest",
        "status-verified",
        "publish",
        "release",
    ]
    assert not (root / "lock").exists()


@pytest.mark.parametrize("scenario,failed_event", [
    ("image-fails", "preserve-image"),
    ("publish-fails", "publish"),
])
def test_failure_preserves_record_and_lock_without_changing_current(
    tmp_path: Path,
    scenario: str,
    failed_event: str,
) -> None:
    result, root, events = invoke(tmp_path, scenario)
    assert result.returncode != 0

    record = root / "baseline-test-new"
    assert record.is_dir()
    assert (record / "notifications-source.tar.gz").is_file()
    assert (record / "notifications-image.tsv").is_file()
    assert events[-1] == failed_event
    assert (root / "lock/owner").read_text().strip() == record.name
    assert (root / "current").read_text().strip() == "previous"
    assert (
        root / "previous" / "status"
    ).read_text().strip() == "verified"
