from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"
COMMIT = "c" * 40
CORE_IMAGE = "sha256:" + "a" * 64


def run_rollback(
    tmp_path: Path,
    *,
    adopted: bool = True,
    fail_on: int = 0,
    invalid_commit: bool = False,
):
    root = tmp_path / "deployments"
    records = root / "records"
    records.mkdir(parents=True)

    baseline = records / "baseline-test"
    transaction = records / "update-test"
    baseline.mkdir()
    transaction.mkdir()

    commit = (
        "invalid" if invalid_commit else COMMIT
    ) if adopted else ""

    (baseline / "metadata").write_text(
        "type=baseline\n"
        "deployment_id=baseline-test\n"
        + (
            f"notifications_commit={commit}\n"
            if adopted else ""
        ),
        encoding="utf-8",
    )
    (baseline / "status").write_text(
        "verified\n", encoding="utf-8"
    )
    (baseline / "images.tsv").write_text(
        "core|docker-compose.yml|atlas|api|/atlas-api|"
        f"atlas-api:test|{CORE_IMAGE}\n",
        encoding="utf-8",
    )

    (transaction / "metadata").write_text(
        "type=update\n"
        "deployment_id=update-test\n"
        "previous_baseline=baseline-test\n"
        "scope=core\n"
        "migration=none\n",
        encoding="utf-8",
    )
    (transaction / "status").write_text(
        "verified\n", encoding="utf-8"
    )

    backup = tmp_path / "pre-update-backup.tar.gz"
    with tarfile.open(backup, "w:gz") as archive:
        payload = b"test-backup\n"
        member = tarfile.TarInfo("proof.txt")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))

    (transaction / "backup_file").write_text(
        str(backup) + "\n", encoding="utf-8"
    )

    (root / "current").write_text(
        "update-test\n", encoding="utf-8"
    )

    # An existing transaction-owned lock avoids testing lock
    # acquisition and keeps this gate focused on finalization.
    lock = root / "update.lock"
    lock.mkdir()
    (lock / "owner").write_text(
        "deployment_id=update-test\n",
        encoding="utf-8",
    )

    maintenance = tmp_path / "maintenance.enabled"
    event_log = tmp_path / "events.log"

    # The real rollback_locked and rollback verifier run against
    # tmp_path. Every runtime-changing or external boundary is mocked.
    script = r'''
set -euo pipefail
source "$DEPLOYMENT_FILE"

atlas_deployment_validate_source() {
  return 0
}

atlas_deployment_lock_dir() {
  printf '%s/update.lock\n' "$ATLAS_DEPLOYMENT_DIR"
}

atlas_deployment_current_id() {
  cat "$ATLAS_DEPLOYMENT_DIR/current"
}

atlas_command_doctor() {
  printf 'doctor\n' >> "$EVENT_LOG"
}

atlas_command_verify() {
  printf 'atlas-verify\n' >> "$EVENT_LOG"
}

docker() {
  [[ "$#" -eq 3 &&
    "$1" == image &&
    "$2" == inspect ]] || return 1

  [[ "$3" == "$EXPECTED_CORE_IMAGE" ]]
}

atlas_deployment_restore_surface() {
  [[ "$#" -eq 3 &&
    "$1" == "$BASELINE_RECORD" &&
    "$2" == "$TRANSACTION_RECORD" &&
    "$3" == core ]] || return 1

  printf 'restore:core\n' >> "$EVENT_LOG"
}

atlas_deployment_verify_runtime() {
  [[ "$1" == "$BASELINE_RECORD" ]] || return 1

  ATTEST_COUNT=$((ATTEST_COUNT + 1))
  printf 'notifications-attest:%s\n' \
    "$ATTEST_COUNT" >> "$EVENT_LOG"

  [[ "$ATTEST_COUNT" -ne "$FAIL_ON" ]]
}

atlas_command_maintenance() {
  printf 'maintenance:%s\n' "$1" >> "$EVENT_LOG"

  case "$1" in
    enable)
      printf 'enabled\n' > "$MAINTENANCE_FLAG"
      ;;
    disable)
      rm -f -- "$MAINTENANCE_FLAG"
      ;;
    *)
      return 2
      ;;
  esac
}

atlas_deployment_set_current() {
  [[ "$1" == baseline-test ]] || return 1

  printf 'set-current:%s\n' "$1" >> "$EVENT_LOG"
  printf '%s\n' "$1" > "$ATLAS_DEPLOYMENT_DIR/current"
}

atlas_deployment_release_lock() {
  [[ "$1" == update-test ]] || return 1
  atlas_deployment_lock_matches "$1" || return 1

  printf 'release:%s\n' "$1" >> "$EVENT_LOG"
  rm -f -- "$(atlas_deployment_lock_dir)/owner"
  rmdir -- "$(atlas_deployment_lock_dir)"
}

ATTEST_COUNT=0

atlas_deployment_rollback_locked update-test
'''

    environment = os.environ.copy()
    environment.update({
        "ATLAS_DEPLOYMENT_DIR": str(root),
        "ATLAS_RUNTIME_CONFIG_DIR": str(
            tmp_path / "runtime-config"
        ),
        "ATLAS_PROJECT_DIR": str(ROOT),
        "DEPLOYMENT_FILE": str(DEPLOYMENT),
        "BASELINE_RECORD": str(baseline),
        "TRANSACTION_RECORD": str(transaction),
        "EXPECTED_CORE_IMAGE": CORE_IMAGE,
        "MAINTENANCE_FLAG": str(maintenance),
        "EVENT_LOG": str(event_log),
        "FAIL_ON": str(fail_on),
    })

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    result.events = (
        event_log.read_text(encoding="utf-8")
        if event_log.exists()
        else ""
    )
    result.current_id = (
        root / "current"
    ).read_text(encoding="utf-8").strip()
    result.transaction_status = (
        transaction / "status"
    ).read_text(encoding="utf-8").strip()
    result.baseline_status = (
        baseline / "status"
    ).read_text(encoding="utf-8").strip()
    result.lock_exists = lock.is_dir()
    result.maintenance_exists = maintenance.is_file()

    return result


def assert_attestation_failure_preserves_state(result):
    assert result.returncode != 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        f"events:\n{result.events}"
    )
    assert result.current_id == "update-test"
    assert result.transaction_status == "verified"
    assert result.baseline_status == "verified"
    assert result.lock_exists is True
    assert result.maintenance_exists is True
    assert "set-current:" not in result.events
    assert "release:" not in result.events


def test_private_attestation_failure_prevents_public_reopen(
    tmp_path: Path,
):
    result = run_rollback(tmp_path, fail_on=1)

    assert_attestation_failure_preserves_state(result)
    assert result.events.splitlines() == [
        "maintenance:enable",
        "restore:core",
        "doctor",
        "atlas-verify",
        "notifications-attest:1",
    ]


def test_public_attestation_failure_restores_maintenance(
    tmp_path: Path,
):
    result = run_rollback(tmp_path, fail_on=2)

    assert_attestation_failure_preserves_state(result)
    assert result.events.splitlines() == [
        "maintenance:enable",
        "restore:core",
        "doctor",
        "atlas-verify",
        "notifications-attest:1",
        "maintenance:disable",
        "doctor",
        "atlas-verify",
        "notifications-attest:2",
        "maintenance:enable",
    ]


def test_invalid_adopted_identity_prevents_public_reopen(
    tmp_path: Path,
):
    result = run_rollback(
        tmp_path, invalid_commit=True
    )

    assert_attestation_failure_preserves_state(result)
    assert "notifications-attest:" not in result.events
    assert "maintenance:disable" not in result.events


@pytest.mark.parametrize("adopted", (False, True))
def test_matching_or_historical_baseline_finalizes_in_order(
    tmp_path: Path,
    adopted: bool,
):
    result = run_rollback(tmp_path, adopted=adopted)

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        f"events:\n{result.events}"
    )
    assert result.current_id == "baseline-test"
    assert result.transaction_status == "rolled_back"
    assert result.baseline_status == "verified"
    assert result.lock_exists is False
    assert result.maintenance_exists is False

    events = result.events.splitlines()

    assert events.count("maintenance:disable") == 1
    assert events.count("set-current:baseline-test") == 1
    assert events.count("release:update-test") == 1

    assert events.index(
        "set-current:baseline-test"
    ) < events.index("release:update-test")

    if adopted:
        assert events.count("notifications-attest:1") == 1
        assert events.count("notifications-attest:2") == 1
        assert events.index(
            "notifications-attest:2"
        ) < events.index("set-current:baseline-test")
    else:
        assert not any(
            event.startswith("notifications-attest:")
            for event in events
        )
