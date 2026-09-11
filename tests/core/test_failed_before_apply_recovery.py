from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"
HELP = PROJECT_ROOT / "scripts" / "commands" / "help.sh"


def recovery_section() -> str:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    return content.split(
        "atlas_deployment_recover_failed_before_apply() {", 1
    )[1].split(
        "atlas_command_deployment() {", 1
    )[0]


def test_deployment_cli_exposes_failed_before_apply_recovery() -> None:
    deployment = DEPLOYMENT.read_text(encoding="utf-8")
    help_text = HELP.read_text(encoding="utf-8")

    assert "atlas deployment recover-failed-before-apply <deployment-id>" in deployment
    assert "atlas deployment recover-failed-before-apply <deployment-id>" in help_text
    assert "recover-failed-before-apply)" in deployment


def test_recovery_requires_failed_transaction() -> None:
    section = recovery_section()

    assert "status" in section
    assert "failed" in section
    assert "not failed-before-apply recovery eligible" in section


def test_recovery_requires_no_recorded_backup() -> None:
    section = recovery_section()

    assert "backup_file" in section
    assert "recorded pre-update backup" in section


def test_recovery_requires_previous_baseline_still_current_and_verified() -> None:
    section = recovery_section()

    assert "previous_baseline" in section
    assert "atlas_deployment_current_id" in section
    assert "verified" in section
    assert "atlas_deployment_verify_runtime" in section


def test_recovery_requires_matching_lock_owner() -> None:
    section = recovery_section()

    assert "atlas_deployment_lock_matches" in section
    assert "another deployment owns the active lock" in section


def test_recovery_verifies_runtime_before_disabling_maintenance() -> None:
    section = recovery_section()

    verify_index = section.index("atlas_deployment_verify_runtime")
    disable_index = section.index("atlas_command_maintenance disable")

    assert verify_index < disable_index


def test_recovery_reverifies_baseline_after_public_reopen() -> None:
    section = recovery_section()

    assert section.count("atlas_deployment_verify_runtime") >= 2
    assert section.count("atlas_command_doctor") >= 2

    # Failed-before-apply recovery certifies the recorded previous
    # baseline. Current-main release readiness can legitimately require
    # services that did not exist in that baseline.
    assert "atlas_command_verify" not in section
    assert "verify-ingress.sh" not in section


def test_recovery_reenables_maintenance_if_public_verification_fails() -> None:
    section = recovery_section()

    disable_index = section.index("atlas_command_maintenance disable")
    tail = section[disable_index:]

    assert "atlas_command_maintenance enable" in tail


def test_recovery_marks_transaction_recovered_before_releasing_lock() -> None:
    section = recovery_section()

    status_index = section.index(
        'atlas_deployment_set_status "$transaction" recovered_pre_apply'
    )
    release_index = section.index(
        'atlas_deployment_release_lock "$identifier"'
    )

    assert status_index < release_index


def test_recovery_does_not_restore_or_apply_runtime() -> None:
    section = recovery_section()

    assert "atlas_deployment_restore_surface" not in section
    assert "atlas_update_apply_scope" not in section
    assert "docker compose" not in section
    assert "docker restart" not in section


def _run_recovery_behavior(
    tmp_path: Path,
    *,
    transaction_status: str = "failed",
    backup_present: bool = False,
    current_baseline: str = "baseline-test",
    lock_owner: str = "update-test",
    maintenance_present: bool = True,
    verify_runtime_result: int = 0,
    post_verify_result: int = 0,
) -> tuple["subprocess.CompletedProcess[str]", list[str], Path]:
    import os
    import subprocess
    import textwrap

    deployment_root = tmp_path / "deployments"
    records = deployment_root / "records"
    transaction = records / "update-test"
    baseline = records / "baseline-test"
    lock = deployment_root / "update.lock"
    maintenance = tmp_path / "maintenance.flag"
    events = tmp_path / "events"
    project = tmp_path / "project"
    scripts = project / "scripts"

    transaction.mkdir(parents=True)
    baseline.mkdir(parents=True)
    lock.mkdir(parents=True)
    scripts.mkdir(parents=True)

    (transaction / "status").write_text(
        transaction_status + "\n",
        encoding="utf-8",
    )
    (transaction / "metadata").write_text(
        "\n".join(
            (
                "type=update",
                "deployment_id=update-test",
                "previous_baseline=baseline-test",
                "scope=ingress",
                "migration=none",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    (baseline / "status").write_text(
        "verified\n",
        encoding="utf-8",
    )
    (baseline / "metadata").write_text(
        "\n".join(
            (
                "type=baseline",
                "deployment_id=baseline-test",
                "scope=all",
                "migration=none",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    (deployment_root / "current").write_text(
        current_baseline + "\n",
        encoding="utf-8",
    )

    (lock / "owner").write_text(
        f"deployment_id={lock_owner}\n",
        encoding="utf-8",
    )

    if maintenance_present:
        maintenance.write_text("enabled\n", encoding="utf-8")

    if backup_present:
        (transaction / "backup_file").write_text(
            "/tmp/not-used.tar.gz\n",
            encoding="utf-8",
        )

    verify_ingress = scripts / "verify-ingress.sh"
    verify_ingress.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' 'CURRENT_RELEASE_INGRESS_VERIFIER_CALLED' >> "$ATLAS_TEST_EVENTS"
exit 97
""",
        encoding="utf-8",
    )
    verify_ingress.chmod(0o755)

    harness = r"""
    set -euo pipefail

    source "$ATLAS_TEST_DEPLOYMENT"

    atlas_deployment_valid_id() {
      [[ -n "${1:-}" ]]
    }

    atlas_deployment_validate_source() {
      return 0
    }

    atlas_deployment_root() {
      printf '%s\n' "$ATLAS_TEST_ROOT"
    }

    atlas_deployment_record_dir() {
      printf '%s/records/%s\n' "$ATLAS_TEST_ROOT" "$1"
    }

    atlas_deployment_record_value() {
      local record="$1"
      local key="$2"

      awk -F= -v key="$key" '
        $1 == key {
          sub(/^[^=]*=/, "")
          print
          exit
        }
      ' "$record/metadata"
    }

    atlas_deployment_current_id() {
      cat "$ATLAS_TEST_ROOT/current"
    }

    atlas_deployment_lock_dir() {
      printf '%s/update.lock\n' "$ATLAS_TEST_ROOT"
    }

    atlas_deployment_lock_matches() {
      local expected="$1"
      local actual

      actual="$(
        awk -F= '
          $1 == "deployment_id" {
            print $2
            exit
          }
        ' "$ATLAS_TEST_ROOT/update.lock/owner"
      )"

      [[ "$actual" == "$expected" ]]
    }

    atlas_maintenance_flag() {
      printf '%s\n' "$ATLAS_TEST_MAINTENANCE"
    }

    verify_count=0

    atlas_deployment_verify_runtime() {
      verify_count=$((verify_count + 1))
      printf 'runtime:%s\n' "$verify_count" >> "$ATLAS_TEST_EVENTS"

      if [[ "$verify_count" -eq 1 ]]; then
        return "$ATLAS_TEST_VERIFY_RUNTIME_RESULT"
      fi

      return 0
    }

    atlas_command_doctor() {
      printf '%s\n' 'doctor' >> "$ATLAS_TEST_EVENTS"
      return 0
    }

    atlas_command_verify() {
      printf '%s\n' 'CURRENT_RELEASE_VERIFY_CALLED' >> "$ATLAS_TEST_EVENTS"
      return 96
    }

    atlas_command_maintenance() {
      local action="$1"

      printf 'maintenance:%s\n' "$action" >> "$ATLAS_TEST_EVENTS"

      case "$action" in
        disable)
          rm -f -- "$ATLAS_TEST_MAINTENANCE"
          ;;
        enable)
          printf '%s\n' enabled > "$ATLAS_TEST_MAINTENANCE"
          ;;
        *)
          return 91
          ;;
      esac
    }

    atlas_deployment_set_status() {
      local transaction="$1"
      local status="$2"

      printf 'status:%s\n' "$status" >> "$ATLAS_TEST_EVENTS"
      printf '%s\n' "$status" > "$transaction/status"
    }

    atlas_deployment_release_lock() {
      local identifier="$1"

      atlas_deployment_lock_matches "$identifier" || return 1

      printf '%s\n' 'release' >> "$ATLAS_TEST_EVENTS"
      rm -rf -- "$ATLAS_TEST_ROOT/update.lock"
    }

    atlas_deployment_recover_failed_before_apply update-test
    """

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
            "ATLAS_TEST_ROOT": str(deployment_root),
            "ATLAS_TEST_MAINTENANCE": str(maintenance),
            "ATLAS_TEST_EVENTS": str(events),
            "ATLAS_TEST_VERIFY_RUNTIME_RESULT": str(
                verify_runtime_result
            ),
            "ATLAS_TEST_POST_VERIFY_RESULT": str(
                post_verify_result
            ),
            "ATLAS_PROJECT_DIR": str(project),
        }
    )

    result = subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    recorded_events: list[str] = []

    if events.exists():
        recorded_events = events.read_text(
            encoding="utf-8"
        ).splitlines()

    return result, recorded_events, deployment_root


def test_recovery_behavior_rejects_nonfailed_transaction(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(
        tmp_path,
        transaction_status="prepared",
    )

    assert result.returncode != 0
    assert events == []
    assert (root / "update.lock").is_dir()
    assert (tmp_path / "maintenance.flag").is_file()


def test_recovery_behavior_rejects_recorded_backup(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(
        tmp_path,
        backup_present=True,
    )

    assert result.returncode != 0
    assert events == []
    assert (root / "update.lock").is_dir()
    assert (tmp_path / "maintenance.flag").is_file()


def test_recovery_behavior_rejects_current_baseline_mismatch(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(
        tmp_path,
        current_baseline="baseline-other",
    )

    assert result.returncode != 0
    assert events == []
    assert (root / "update.lock").is_dir()
    assert (tmp_path / "maintenance.flag").is_file()


def test_recovery_behavior_rejects_wrong_lock_owner(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(
        tmp_path,
        lock_owner="update-other",
    )

    assert result.returncode != 0
    assert events == []
    assert (root / "update.lock").is_dir()
    assert (tmp_path / "maintenance.flag").is_file()


def test_recovery_behavior_rejects_missing_maintenance(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(
        tmp_path,
        maintenance_present=False,
    )

    assert result.returncode != 0
    assert events == []
    assert (root / "update.lock").is_dir()
    assert not (tmp_path / "maintenance.flag").exists()


def test_recovery_behavior_runtime_failure_keeps_maintenance_and_lock(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(
        tmp_path,
        verify_runtime_result=1,
    )

    assert result.returncode != 0
    assert events == ["runtime:1"]
    assert (root / "update.lock").is_dir()
    assert (tmp_path / "maintenance.flag").is_file()
    assert (
        root / "records" / "update-test" / "status"
    ).read_text(encoding="utf-8").strip() == "failed"


def test_recovery_behavior_ignores_current_release_readiness(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(tmp_path)

    assert result.returncode == 0, result.stderr

    assert "CURRENT_RELEASE_VERIFY_CALLED" not in events
    assert "CURRENT_RELEASE_INGRESS_VERIFIER_CALLED" not in events

    assert not (root / "update.lock").exists()
    assert not (tmp_path / "maintenance.flag").exists()

    assert (
        root / "records" / "update-test" / "status"
    ).read_text(encoding="utf-8").strip() == "recovered_pre_apply"


def test_recovery_behavior_success_orders_reopen_finalize_and_release(
    tmp_path: Path,
) -> None:
    result, events, root = _run_recovery_behavior(tmp_path)

    assert result.returncode == 0, result.stderr

    assert events == [
        "runtime:1",
        "doctor",
        "maintenance:disable",
        "doctor",
        "runtime:2",
        "status:recovered_pre_apply",
        "release",
    ]

    assert not (root / "update.lock").exists()
    assert not (tmp_path / "maintenance.flag").exists()

    assert (
        root / "records" / "update-test" / "status"
    ).read_text(encoding="utf-8").strip() == "recovered_pre_apply"
