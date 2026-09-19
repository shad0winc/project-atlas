from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"
COMMIT = "a" * 40


def invoke(tmp_path: Path, scenario: str) -> subprocess.CompletedProcess[str]:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    record = sandbox / "previous"
    record.mkdir()
    (record / "metadata").write_text(
        "type=baseline\n"
        "deployment_id=previous\n"
        "core_commit=" + COMMIT + "\n"
        "ingress_commit=" + COMMIT + "\n"
        "sports_commit=\n"
        "notifications_commit=" + (
            COMMIT if scenario == "already-adopted" else ""
        ) + "\n",
        encoding="utf-8",
    )
    (record / "status").write_text("verified\n", encoding="utf-8")

    checkout = sandbox / "historical"
    checkout.mkdir()
    events = sandbox / "events"
    current = sandbox / "current"
    current.write_text("previous\n", encoding="utf-8")

    script = r"""
set -euo pipefail
source "$ATLAS_TEST_DEPLOYMENT"

atlas_deployment_new_id() {
  printf '%s\n' 'baseline-test-new'
}

atlas_deployment_require_current_record() {
  printf '%s\n' "$ATLAS_TEST_PREVIOUS"
}

atlas_deployment_current_id() {
  cat "$ATLAS_TEST_CURRENT"
}

atlas_deployment_record_dir() {
  printf '%s/%s\n' "$ATLAS_TEST_ROOT" "$1"
}

atlas_deployment_acquire_lock() {
  printf '%s\n' acquire >> "$ATLAS_TEST_EVENTS"
  if [[ "$ATLAS_TEST_SCENARIO" == lock-held ]]; then
    return 1
  fi
  mkdir "$ATLAS_TEST_ROOT/lock"
  printf '%s\n' "$1" > "$ATLAS_TEST_ROOT/lock/owner"
}

atlas_deployment_release_lock() {
  printf '%s\n' release >> "$ATLAS_TEST_EVENTS"
  [[ -f "$ATLAS_TEST_ROOT/lock/owner" ]] || return 1
  [[ "$(<"$ATLAS_TEST_ROOT/lock/owner")" == "$1" ]] || return 1
  rm -- "$ATLAS_TEST_ROOT/lock/owner"
  rmdir -- "$ATLAS_TEST_ROOT/lock"
}

atlas_deployment_verify_runtime() {
  printf '%s\n' verify >> "$ATLAS_TEST_EVENTS"
}

atlas_deployment_notifications_live_worker_row() {
  printf '%s\n' attest >> "$ATLAS_TEST_EVENTS"
  if [[ "$ATLAS_TEST_SCENARIO" == metadata-fails ]]; then
    printf '%s\n' 'notifications|modules/notifications/docker-compose.yml|notifications|atlas-notifications-worker|/atlas-notifications-worker|worker:test|sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    return 0
  fi
  return 91
}

atlas_deployment_capture_notifications_adoption_evidence() {
  printf '%s\n' capture >> "$ATLAS_TEST_EVENTS"
  return 92
}

atlas_deployment_record_value() {
  if [[ "$ATLAS_TEST_SCENARIO" == metadata-fails &&
        "$2" == core_commit ]]; then
    return 95
  fi
  awk -F= -v key="$2" \
    '$1 == key {sub(/^[^=]*=/, ""); print; exit}' \
    "$1/metadata"
}

atlas_deployment_preserve_rollback_images() {
  printf '%s\n' preserve-image >> "$ATLAS_TEST_EVENTS"
  return 93
}

atlas_deployment_set_current() {
  printf '%s\n' publish >> "$ATLAS_TEST_EVENTS"
  return 94
}

atlas_deployment_adopt_notifications \
  "$ATLAS_TEST_CHECKOUT" \
  "$ATLAS_TEST_COMMIT"
"""

    env = {
        **os.environ,
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_ROOT": str(sandbox),
        "ATLAS_TEST_PREVIOUS": str(record),
        "ATLAS_TEST_CURRENT": str(current),
        "ATLAS_TEST_EVENTS": str(events),
        "ATLAS_TEST_CHECKOUT": str(checkout),
        "ATLAS_TEST_COMMIT": COMMIT,
        "ATLAS_TEST_SCENARIO": scenario,
    }

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=sandbox,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    result.atlas_events = (
        events.read_text(encoding="utf-8").splitlines()
        if events.exists()
        else []
    )
    result.atlas_sandbox = sandbox
    return result


def test_lock_contention_rejects_adoption_before_any_work(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "lock-held")

    assert result.returncode != 0
    assert result.atlas_events == ["acquire"]
    assert not (result.atlas_sandbox / "baseline-test-new").exists()
    assert (
        result.atlas_sandbox / "current"
    ).read_text(encoding="utf-8") == "previous\n"


def test_already_adopted_baseline_is_not_republished(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "already-adopted")

    assert result.returncode != 0
    assert result.atlas_events == ["acquire", "release"], (
        "An already-adopted baseline must be rejected under the "
        "deployment lock, with no recovery capture or publication"
    )
    assert "capture" not in result.atlas_events
    assert "preserve-image" not in result.atlas_events
    assert "publish" not in result.atlas_events
    assert not (result.atlas_sandbox / "baseline-test-new").exists()
    assert (
        result.atlas_sandbox / "current"
    ).read_text(encoding="utf-8") == "previous\n"


def test_failed_worker_attestation_does_not_publish_baseline(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "attestation-fails")

    assert result.returncode != 0
    assert "attest" in result.atlas_events
    assert "publish" not in result.atlas_events
    assert (
        result.atlas_sandbox / "current"
    ).read_text(encoding="utf-8") == "previous\n"


def test_pre_record_metadata_failure_releases_owned_lock(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "metadata-fails")

    assert result.returncode != 0
    assert result.atlas_events == [
        "acquire",
        "verify",
        "attest",
        "release",
    ], result.stderr
    assert not (result.atlas_sandbox / "lock").exists()
    assert not (result.atlas_sandbox / "baseline-test-new").exists()
    assert (
        result.atlas_sandbox / "current"
    ).read_text(encoding="utf-8") == "previous\n"
