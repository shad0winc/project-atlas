from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"
COMMIT = "c" * 40


def run_recovery(
    tmp_path: Path,
    *,
    adopted: bool = True,
    fail_on: int = 0,
    invalid_commit: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    deployment_root = tmp_path / "deployments"
    records = deployment_root / "records"
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
    (transaction / "metadata").write_text(
        "type=update\n"
        "deployment_id=update-test\n"
        "previous_baseline=baseline-test\n"
        "migration=none\n"
        "scope=core\n",
        encoding="utf-8",
    )
    (transaction / "status").write_text(
        "failed\n", encoding="utf-8"
    )
    (deployment_root / "current").write_text(
        "baseline-test\n", encoding="utf-8"
    )

    lock = deployment_root / "update.lock"
    lock.mkdir()
    (lock / "owner").write_text(
        "deployment_id=update-test\n",
        encoding="utf-8",
    )

    maintenance = tmp_path / "maintenance.enabled"
    maintenance.write_text(
        "enabled\n", encoding="utf-8"
    )
    events = tmp_path / "events.log"

    # Both real orchestration and rollback verification are invoked.
    # Only external checks and publication are replaced. The mocked
    # runtime boundary models first/second Notifications attestation.
    script = r'''
set -euo pipefail
source "$DEPLOYMENT_FILE"

atlas_deployment_validate_source() {
  return 0
}

atlas_deployment_current_id() {
  cat "$ATLAS_DEPLOYMENT_DIR/current"
}

atlas_maintenance_flag() {
  printf '%s\n' "$MAINTENANCE_FLAG"
}

atlas_command_doctor() {
  printf 'doctor\n' >> "$EVENT_LOG"
}

atlas_command_verify() {
  printf 'atlas-verify\n' >> "$EVENT_LOG"
}

atlas_deployment_verify_runtime() {
  test "$1" = "$BASELINE_RECORD" || return 1
  ATTEST_COUNT=$((ATTEST_COUNT + 1))
  printf 'notifications-attest:%s\n' \
    "$ATTEST_COUNT" >> "$EVENT_LOG"

  if [[ "$ATTEST_COUNT" -eq "$FAIL_ON" ]]; then
    return 1
  fi
}

atlas_command_maintenance() {
  printf 'maintenance:%s\n' "$1" >> "$EVENT_LOG"
  case "$1" in
    disable)
      rm -f -- "$MAINTENANCE_FLAG"
      ;;
    enable)
      printf 'enabled\n' > "$MAINTENANCE_FLAG"
      ;;
    *)
      return 2
      ;;
  esac
}

atlas_deployment_publish_reconciliation_baseline() {
  printf 'publish\n' >> "$EVENT_LOG"
  return 1
}

atlas_deployment_set_current() {
  printf 'set-current:%s\n' "$1" >> "$EVENT_LOG"
  return 1
}

atlas_deployment_release_lock() {
  printf 'release:%s\n' "$1" >> "$EVENT_LOG"
  return 1
}

ATTEST_COUNT=0
atlas_deployment_recover_failed_rollback update-test
'''

    env = os.environ.copy()
    env.update({
        "ATLAS_DEPLOYMENT_DIR": str(deployment_root),
        "ATLAS_RUNTIME_CONFIG_DIR": str(
            tmp_path / "runtime-config"
        ),
        "ATLAS_PROJECT_DIR": str(ROOT),
        "DEPLOYMENT_FILE": str(DEPLOYMENT),
        "BASELINE_RECORD": str(baseline),
        "MAINTENANCE_FLAG": str(maintenance),
        "EVENT_LOG": str(events),
        "FAIL_ON": str(fail_on),
    })

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    result.events = (
        events.read_text(encoding="utf-8")
        if events.exists() else ""
    )
    result.current_id = (
        deployment_root / "current"
    ).read_text(encoding="utf-8").strip()
    result.lock_exists = lock.is_dir()
    result.maintenance_exists = maintenance.is_file()
    result.transaction_status = (
        transaction / "status"
    ).read_text(encoding="utf-8").strip()
    result.reconciliation_exists = (
        records / "baseline-reconciliation-test"
    ).exists()

    return result, baseline


def assert_failure_preserves_state(
    result, *, publication_attempted: bool = False
) -> None:
    assert result.returncode != 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        f"events:\n{result.events}"
    )
    assert result.current_id == "baseline-test"
    assert result.transaction_status == "failed"
    assert result.lock_exists is True
    assert result.maintenance_exists is True
    assert result.reconciliation_exists is False
    assert ("publish\n" in result.events) is publication_attempted
    assert "set-current:" not in result.events
    assert "release:" not in result.events


def test_private_notifications_attestation_blocks_reopen(
    tmp_path: Path,
) -> None:
    result, _ = run_recovery(tmp_path, fail_on=1)
    assert_failure_preserves_state(result)
    assert result.events.splitlines() == [
        "doctor",
        "atlas-verify",
        "notifications-attest:1",
    ]


def test_public_notifications_attestation_restores_maintenance(
    tmp_path: Path,
) -> None:
    result, _ = run_recovery(tmp_path, fail_on=2)
    assert_failure_preserves_state(result)
    assert result.events.splitlines() == [
        "doctor",
        "atlas-verify",
        "notifications-attest:1",
        "maintenance:disable",
        "doctor",
        "atlas-verify",
        "notifications-attest:2",
        "maintenance:enable",
    ]


def test_invalid_adopted_identity_blocks_private_reopen(
    tmp_path: Path,
) -> None:
    result, _ = run_recovery(
        tmp_path, invalid_commit=True
    )
    assert_failure_preserves_state(result)
    assert "notifications-attest:" not in result.events
    assert "maintenance:disable" not in result.events


def test_historical_baseline_bypasses_notifications_attestation(
    tmp_path: Path,
) -> None:
    # The publisher is deliberately mocked to fail so the test
    # cannot finalize a transaction even on a successful verify.
    result, _ = run_recovery(tmp_path, adopted=False)
    assert_failure_preserves_state(
        result, publication_attempted=True
    )
    assert "notifications-attest:" not in result.events
    assert result.events.splitlines() == [
        "doctor",
        "atlas-verify",
        "maintenance:disable",
        "doctor",
        "atlas-verify",
        "publish",
        "maintenance:enable",
    ]
