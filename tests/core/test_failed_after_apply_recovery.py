from __future__ import annotations

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"
HELP = PROJECT_ROOT / "scripts" / "commands" / "help.sh"

COMMAND = "recover-failed-after-apply"
FUNCTION = "atlas_deployment_recover_failed_after_apply"


def recovery_section() -> str:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    marker = f"{FUNCTION}() {{"

    assert marker in content, (
        "failed-after-apply recovery function is not implemented yet: "
        f"{FUNCTION}"
    )

    start = content.index(marker)
    tail = content[start + len(marker) :]

    next_function = re.search(
        r"\n[a-zA-Z_][a-zA-Z0-9_]*\(\)[ \t]*\{",
        tail,
    )

    assert next_function is not None, (
        "failed-after-apply recovery function has no following "
        "shell-function boundary"
    )

    end = start + len(marker) + next_function.start() + 1
    return content[start:end]


def test_cli_exposes_failed_after_apply_recovery() -> None:
    deployment = DEPLOYMENT.read_text(encoding="utf-8")
    help_text = HELP.read_text(encoding="utf-8")

    usage = f"atlas deployment {COMMAND} <deployment-id>"

    assert usage in deployment
    assert usage in help_text
    assert f"{COMMAND})" in deployment
    assert FUNCTION in deployment


def test_recovery_requires_original_transaction_to_remain_failed() -> None:
    section = recovery_section()

    assert "status" in section
    assert "failed" in section
    assert "not failed-after-apply recovery eligible" in section

    # The original failed deployment is immutable failure evidence.
    forbidden = (
        'atlas_deployment_set_status "$transaction" verified',
        'atlas_deployment_set_status "$transaction" recovered',
        'atlas_deployment_set_status "$transaction" rolled_back',
        'atlas_deployment_set_current "$identifier"',
    )

    for phrase in forbidden:
        assert phrase not in section


def test_recovery_requires_recorded_preupdate_backup() -> None:
    section = recovery_section()

    assert "backup_file" in section
    assert "recorded pre-update backup" in section

    # This path is specifically for a transaction that entered the
    # maintenance/apply portion of the canonical update transaction.
    assert '[[ -f "$transaction/backup_file" ]]' in section


def test_recovery_requires_previous_verified_baseline_still_current() -> None:
    section = recovery_section()

    assert "previous_baseline" in section
    assert "atlas_deployment_current_id" in section
    assert "verified" in section


def test_recovery_requires_original_lock_owner_and_maintenance() -> None:
    section = recovery_section()

    assert "atlas_deployment_lock_matches" in section
    assert "another deployment owns the active lock" in section

    assert "atlas_maintenance_flag" in section
    assert "maintenance" in section.lower()

    # Recovery resumes the deliberately held transaction. It must not
    # manufacture a replacement lock or a maintenance window.
    assert "atlas_deployment_acquire_lock" not in section

    first_verify = section.index("atlas_deployment_verify_runtime")
    prefix = section[:first_verify]

    assert "atlas_command_maintenance enable" not in prefix


def test_recovery_verifies_applied_target_before_public_reopen() -> None:
    section = recovery_section()

    first_verify = section.index("atlas_deployment_verify_runtime")
    disable = section.index("atlas_command_maintenance disable")

    assert first_verify < disable


def test_recovery_reverifies_public_runtime_after_reopen() -> None:
    section = recovery_section()

    disable = section.index("atlas_command_maintenance disable")

    assert section.count("atlas_deployment_verify_runtime") >= 2

    second_verify = section.index(
        "atlas_deployment_verify_runtime",
        disable,
    )

    assert disable < second_verify

    # Public release readiness must also pass normal Atlas verification.
    tail = section[disable:]

    assert "atlas_command_doctor" in tail
    assert "atlas_command_verify" in tail


def test_public_verification_failure_restores_maintenance() -> None:
    section = recovery_section()

    disable = section.index("atlas_command_maintenance disable")
    tail = section[disable:]

    assert "atlas_command_maintenance enable" in tail


def test_recovery_does_not_repeat_runtime_apply_or_restore() -> None:
    section = recovery_section()

    forbidden = (
        "atlas_update_apply_scope",
        "atlas_deployment_restore_surface",
        "docker compose",
        "docker restart",
        "docker pull",
        "docker build",
        "docker image tag",
    )

    for phrase in forbidden:
        assert phrase not in section


def test_recovery_publishes_separate_verified_baseline() -> None:
    section = recovery_section()

    # The failed transaction remains immutable evidence. Recovery therefore
    # publishes a separately named verified description of the live target.
    assert "reconciliation" in section.lower()
    assert "atlas_deployment_capture_images" in section
    assert "atlas_deployment_verify_runtime" in section
    assert "atlas_deployment_set_current" in section
    assert "verified" in section

    assert 'atlas_deployment_set_current "$identifier"' not in section
    assert 'atlas_deployment_set_status "$transaction"' not in section


def test_recovery_finalizes_before_releasing_original_lock() -> None:
    section = recovery_section()

    set_current = section.index("atlas_deployment_set_current")

    release = section.index(
        'atlas_deployment_release_lock "$identifier"',
        set_current,
    )

    assert set_current < release


def test_recovery_source_contract_is_target_not_previous_runtime() -> None:
    section = recovery_section()

    # This is not rollback reconciliation. The new verified baseline must
    # describe the already-applied target transaction.
    assert "target_commit" in section
    assert "core_commit" in section
    assert "ingress_commit" in section
    assert "sports_commit" in section

    # Target source archives were already captured in the failed transaction.
    assert "core-source.tar.gz" in section
    assert "ingress-source.tar.gz" in section
    assert "sports-source.tar.gz" in section


def _write_failed_after_apply_fixture(
    tmp_path: Path,
    *,
    transaction_status: str = "failed",
    migration: str = "none",
    backup_present: bool = True,
    backup_valid: bool = True,
    previous_status: str = "verified",
    current_id: str = "baseline-test",
    lock_present: bool = True,
    lock_owner: str = "update-test",
    maintenance_present: bool = True,
    target_commit: str = "a" * 40,
    source_commit: str = "",
    core_commit: str = "a" * 40,
    ingress_commit: str = "a" * 40,
    sports_commit: str = "a" * 40,
    core_archive: bool = True,
    ingress_archive: bool = True,
    sports_archive: bool = True,
) -> dict[str, object]:
    import io
    import tarfile

    deployment_root = tmp_path / "deployments"
    records = deployment_root / "records"
    records.mkdir(parents=True)

    previous_id = "baseline-test"
    failed_id = "update-test"
    reconciliation_id = "baseline-reconciliation-test"

    previous = records / previous_id
    failed = records / failed_id

    previous.mkdir()
    failed.mkdir()

    (previous / "status").write_text(
        previous_status + "\n",
        encoding="utf-8",
    )

    (previous / "metadata").write_text(
        "\n".join(
            (
                "type=baseline",
                f"deployment_id={previous_id}",
                f"target_commit={'b' * 40}",
                f"source_commit={'b' * 40}",
                f"core_commit={'b' * 40}",
                f"ingress_commit={'b' * 40}",
                f"sports_commit={'b' * 40}",
                "scope=all",
                "migration=none",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    metadata = [
        "type=update",
        f"deployment_id={failed_id}",
        f"previous_baseline={previous_id}",
        f"target_commit={target_commit}",
    ]

    if source_commit:
        metadata.append(f"source_commit={source_commit}")

    metadata.extend(
        (
            f"core_commit={core_commit}",
            f"ingress_commit={ingress_commit}",
            f"sports_commit={sports_commit}",
            "scope=all",
            f"migration={migration}",
        )
    )

    (failed / "status").write_text(
        transaction_status + "\n",
        encoding="utf-8",
    )

    (failed / "metadata").write_text(
        "\n".join(metadata) + "\n",
        encoding="utf-8",
    )

    if core_archive:
        (failed / "core-source.tar.gz").write_bytes(
            b"core-target-source\n"
        )

    if ingress_archive:
        (failed / "ingress-source.tar.gz").write_bytes(
            b"ingress-target-source\n"
        )

    if sports_archive:
        (failed / "sports-source.tar.gz").write_bytes(
            b"sports-target-source\n"
        )

    backup = tmp_path / "pre-update-backup.tar.gz"

    if backup_present:
        if backup_valid:
            with tarfile.open(backup, "w:gz") as archive:
                payload = b"backup\n"
                info = tarfile.TarInfo("proof.txt")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
        else:
            backup.write_text(
                "not a tar archive\n",
                encoding="utf-8",
            )

        (failed / "backup_file").write_text(
            str(backup) + "\n",
            encoding="utf-8",
        )

    (deployment_root / "current").write_text(
        current_id + "\n",
        encoding="utf-8",
    )

    lock = deployment_root / "update.lock"

    if lock_present:
        lock.mkdir()
        (lock / "owner").write_text(
            f"deployment_id={lock_owner}\n",
            encoding="utf-8",
        )

    maintenance_flag = tmp_path / "maintenance.enabled"

    if maintenance_present:
        maintenance_flag.write_text(
            "enabled\n",
            encoding="utf-8",
        )

    return {
        "deployment_root": deployment_root,
        "records": records,
        "previous_id": previous_id,
        "failed_id": failed_id,
        "reconciliation_id": reconciliation_id,
        "previous": previous,
        "failed": failed,
        "lock": lock,
        "maintenance_flag": maintenance_flag,
    }


def _run_failed_after_apply_recovery(
    tmp_path: Path,
    *,
    transaction_status: str = "failed",
    migration: str = "none",
    backup_present: bool = True,
    backup_valid: bool = True,
    previous_status: str = "verified",
    current_id: str = "baseline-test",
    lock_present: bool = True,
    lock_owner: str = "update-test",
    maintenance_present: bool = True,
    target_commit: str = "a" * 40,
    source_commit: str = "",
    core_commit: str = "a" * 40,
    ingress_commit: str = "a" * 40,
    sports_commit: str = "a" * 40,
    core_archive: bool = True,
    ingress_archive: bool = True,
    sports_archive: bool = True,
    capture_fails: bool = False,
    private_runtime_fails: bool = False,
    private_doctor_fails: bool = False,
    private_atlas_verify_fails: bool = False,
    public_runtime_fails: bool = False,
    public_doctor_fails: bool = False,
    public_atlas_verify_fails: bool = False,
) -> "subprocess.CompletedProcess[str]":
    import os
    import subprocess

    fixture = _write_failed_after_apply_fixture(
        tmp_path,
        transaction_status=transaction_status,
        migration=migration,
        backup_present=backup_present,
        backup_valid=backup_valid,
        previous_status=previous_status,
        current_id=current_id,
        lock_present=lock_present,
        lock_owner=lock_owner,
        maintenance_present=maintenance_present,
        target_commit=target_commit,
        source_commit=source_commit,
        core_commit=core_commit,
        ingress_commit=ingress_commit,
        sports_commit=sports_commit,
        core_archive=core_archive,
        ingress_archive=ingress_archive,
        sports_archive=sports_archive,
    )

    event_log = tmp_path / "events.log"

    script = r'''
set -euo pipefail

source "$DEPLOYMENT_FILE"

atlas_deployment_validate_source() {
  return 0
}

atlas_deployment_new_id() {
  test "$1" = baseline-reconciliation
  printf '%s\n' "$RECONCILIATION_ID"
}

atlas_maintenance_flag() {
  printf '%s\n' "$MAINTENANCE_FLAG"
}

atlas_deployment_capture_images() {
  local record="$1"

  printf 'capture\n' >> "$EVENT_LOG"

  if [[ "$CAPTURE_FAILS" == true ]]; then
    return 1
  fi

  printf '%s\n' \
    'core|docker-compose.yml|project-atlas|core|/core|core:test|sha256:core' \
    'ingress|stack/ingress.yml|atlas-ingress|api|/atlas-api|api:test|sha256:api' \
    'sports|modules/sports/docker-compose.yml|sports|atlas-sports-controller|/atlas-sports-controller|sports:test|sha256:sports' \
    > "$record/images.tsv"
}

atlas_deployment_verify_runtime() {
  VERIFY_RUNTIME_COUNT=$((VERIFY_RUNTIME_COUNT + 1))

  printf \
    'runtime-verify:%s\n' \
    "$VERIFY_RUNTIME_COUNT" \
    >> "$EVENT_LOG"

  if [[ "$VERIFY_RUNTIME_COUNT" -eq 1 && "$PRIVATE_RUNTIME_FAILS" == true ]]; then
    return 1
  fi

  if [[ "$VERIFY_RUNTIME_COUNT" -eq 2 && "$PUBLIC_RUNTIME_FAILS" == true ]]; then
    return 1
  fi
}

atlas_command_doctor() {
  DOCTOR_COUNT=$((DOCTOR_COUNT + 1))

  printf \
    'doctor:%s\n' \
    "$DOCTOR_COUNT" \
    >> "$EVENT_LOG"

  if [[ "$DOCTOR_COUNT" -eq 1 && "$PRIVATE_DOCTOR_FAILS" == true ]]; then
    return 1
  fi

  if [[ "$DOCTOR_COUNT" -eq 2 && "$PUBLIC_DOCTOR_FAILS" == true ]]; then
    return 1
  fi
}

atlas_command_verify() {
  ATLAS_VERIFY_COUNT=$((ATLAS_VERIFY_COUNT + 1))

  printf \
    'atlas-verify:%s\n' \
    "$ATLAS_VERIFY_COUNT" \
    >> "$EVENT_LOG"

  if [[ "$ATLAS_VERIFY_COUNT" -eq 1 && "$PRIVATE_ATLAS_VERIFY_FAILS" == true ]]; then
    return 1
  fi

  if [[ "$ATLAS_VERIFY_COUNT" -eq 2 && "$PUBLIC_ATLAS_VERIFY_FAILS" == true ]]; then
    return 1
  fi
}

atlas_command_maintenance() {
  local action="$1"

  printf \
    'maintenance:%s\n' \
    "$action" \
    >> "$EVENT_LOG"

  case "$action" in
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

atlas_deployment_set_status() {
  local record="$1"
  local status="$2"

  printf \
    'set-status:%s\n' \
    "$status" \
    >> "$EVENT_LOG"

  printf '%s\n' "$status" > "$record/status"
}

atlas_deployment_set_current() {
  local identifier="$1"

  printf \
    'set-current:%s\n' \
    "$identifier" \
    >> "$EVENT_LOG"

  printf '%s\n' "$identifier" > "$ATLAS_DEPLOYMENT_DIR/current"
}

atlas_deployment_release_lock() {
  local identifier="$1"

  printf \
    'release:%s\n' \
    "$identifier" \
    >> "$EVENT_LOG"

  atlas_deployment_lock_matches "$identifier"

  rm -f -- "$FAKE_LOCK_DIR/owner"
  rmdir -- "$FAKE_LOCK_DIR"
}

VERIFY_RUNTIME_COUNT=0
DOCTOR_COUNT=0
ATLAS_VERIFY_COUNT=0

atlas_deployment_recover_failed_after_apply "$FAILED_ID"
'''

    env = os.environ.copy()
    env.update(
        {
            "ATLAS_DEPLOYMENT_DIR": str(
                fixture["deployment_root"]
            ),
            "ATLAS_RUNTIME_CONFIG_DIR": str(
                tmp_path / "runtime-config"
            ),
            "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
            "DEPLOYMENT_FILE": str(DEPLOYMENT),
            "FAILED_ID": str(fixture["failed_id"]),
            "PREVIOUS_ID": str(fixture["previous_id"]),
            "RECONCILIATION_ID": str(
                fixture["reconciliation_id"]
            ),
            "FAKE_LOCK_DIR": str(fixture["lock"]),
            "MAINTENANCE_FLAG": str(
                fixture["maintenance_flag"]
            ),
            "EVENT_LOG": str(event_log),
            "CAPTURE_FAILS": (
                "true" if capture_fails else "false"
            ),
            "PRIVATE_RUNTIME_FAILS": (
                "true" if private_runtime_fails else "false"
            ),
            "PRIVATE_DOCTOR_FAILS": (
                "true" if private_doctor_fails else "false"
            ),
            "PRIVATE_ATLAS_VERIFY_FAILS": (
                "true"
                if private_atlas_verify_fails
                else "false"
            ),
            "PUBLIC_RUNTIME_FAILS": (
                "true" if public_runtime_fails else "false"
            ),
            "PUBLIC_DOCTOR_FAILS": (
                "true" if public_doctor_fails else "false"
            ),
            "PUBLIC_ATLAS_VERIFY_FAILS": (
                "true"
                if public_atlas_verify_fails
                else "false"
            ),
        }
    )

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    events = (
        event_log.read_text(encoding="utf-8")
        if event_log.exists()
        else ""
    )

    current = (
        fixture["deployment_root"] / "current"
    ).read_text(encoding="utf-8").strip()

    result.events = events  # type: ignore[attr-defined]
    result.current_id = current  # type: ignore[attr-defined]
    result.maintenance_exists = fixture[
        "maintenance_flag"
    ].exists()  # type: ignore[attr-defined]
    result.lock_exists = fixture[
        "lock"
    ].exists()  # type: ignore[attr-defined]
    result.failed_status = (
        fixture["failed"] / "status"
    ).read_text(
        encoding="utf-8"
    ).strip()  # type: ignore[attr-defined]

    reconciliation = (
        fixture["records"] / fixture["reconciliation_id"]
    )

    result.reconciliation = reconciliation  # type: ignore[attr-defined]

    return result


def test_behavior_rejects_nonfailed_transaction(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        transaction_status="verified",
    )

    assert result.returncode != 0
    assert "not failed-after-apply recovery eligible" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"
    assert result.lock_exists is True


def test_behavior_rejects_state_changing_migration(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        migration="required",
    )

    assert result.returncode != 0
    assert "requires migration=none" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"
    assert result.lock_exists is True


def test_behavior_requires_recorded_backup(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        backup_present=False,
    )

    assert result.returncode != 0
    assert "recorded pre-update backup" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_rejects_invalid_recorded_backup(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        backup_valid=False,
    )

    assert result.returncode != 0
    assert "unavailable or invalid" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_requires_previous_verified_baseline(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        previous_status="failed",
    )

    assert result.returncode != 0
    assert "previous deployment baseline is not verified" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_requires_previous_baseline_still_current(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        current_id="another-baseline",
    )

    assert result.returncode != 0
    assert "no longer points at the current baseline" in result.stderr
    assert result.events == ""
    assert result.current_id == "another-baseline"


def test_behavior_requires_original_lock(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        lock_present=False,
    )

    assert result.returncode != 0
    assert "requires the original deployment lock" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_requires_matching_original_lock_owner(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        lock_owner="different-update",
    )

    assert result.returncode != 0
    assert "another deployment owns the active lock" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"
    assert result.lock_exists is True


def test_behavior_requires_existing_maintenance_window(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        maintenance_present=False,
    )

    assert result.returncode != 0
    assert "maintenance mode to remain enabled" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"
    assert result.lock_exists is True


def test_behavior_rejects_invalid_target_identity(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        target_commit="not-a-sha",
    )

    assert result.returncode != 0
    assert "target source identity is invalid" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_rejects_invalid_sports_identity(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        sports_commit="not-a-sha",
    )

    assert result.returncode != 0
    assert "Sports source identity is invalid" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_requires_target_core_archive(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        core_archive=False,
    )

    assert result.returncode != 0
    assert "Core source archive is unavailable" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_requires_target_ingress_archive(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        ingress_archive=False,
    )

    assert result.returncode != 0
    assert "Ingress source archive is unavailable" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_requires_target_sports_archive_when_managed(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        sports_archive=False,
    )

    assert result.returncode != 0
    assert "Sports source archive is unavailable" in result.stderr
    assert result.events == ""
    assert result.current_id == "baseline-test"


def test_behavior_capture_failure_never_reopens_or_publishes(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        capture_fails=True,
    )

    assert result.returncode != 0
    assert result.events.splitlines() == ["capture"]
    assert result.current_id == "baseline-test"
    assert result.maintenance_exists is True
    assert result.lock_exists is True
    assert result.failed_status == "failed"


def test_behavior_private_runtime_failure_never_reopens(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        private_runtime_fails=True,
    )

    assert result.returncode != 0
    assert result.events.splitlines() == [
        "capture",
        "runtime-verify:1",
    ]
    assert result.current_id == "baseline-test"
    assert result.maintenance_exists is True
    assert result.lock_exists is True
    assert result.failed_status == "failed"


def test_behavior_private_doctor_failure_never_reopens(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        private_doctor_fails=True,
    )

    assert result.returncode != 0
    assert result.events.splitlines() == [
        "capture",
        "runtime-verify:1",
        "doctor:1",
    ]
    assert result.current_id == "baseline-test"
    assert result.maintenance_exists is True
    assert result.lock_exists is True


def test_behavior_private_atlas_verify_failure_never_reopens(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        private_atlas_verify_fails=True,
    )

    assert result.returncode != 0
    assert result.events.splitlines() == [
        "capture",
        "runtime-verify:1",
        "doctor:1",
        "atlas-verify:1",
    ]
    assert result.current_id == "baseline-test"
    assert result.maintenance_exists is True
    assert result.lock_exists is True


def test_behavior_public_runtime_failure_restores_maintenance(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        public_runtime_fails=True,
    )

    assert result.returncode != 0

    assert result.events.splitlines() == [
        "capture",
        "runtime-verify:1",
        "doctor:1",
        "atlas-verify:1",
        "maintenance:disable",
        "runtime-verify:2",
        "maintenance:enable",
    ]

    assert result.current_id == "baseline-test"
    assert result.maintenance_exists is True
    assert result.lock_exists is True
    assert result.failed_status == "failed"
    assert result.reconciliation.exists() is False


def test_behavior_public_doctor_failure_restores_maintenance(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        public_doctor_fails=True,
    )

    assert result.returncode != 0

    assert result.events.splitlines() == [
        "capture",
        "runtime-verify:1",
        "doctor:1",
        "atlas-verify:1",
        "maintenance:disable",
        "runtime-verify:2",
        "doctor:2",
        "maintenance:enable",
    ]

    assert result.current_id == "baseline-test"
    assert result.maintenance_exists is True
    assert result.lock_exists is True
    assert result.failed_status == "failed"
    assert result.reconciliation.exists() is False


def test_behavior_public_atlas_verify_failure_restores_maintenance(
    tmp_path: Path,
) -> None:
    result = _run_failed_after_apply_recovery(
        tmp_path,
        public_atlas_verify_fails=True,
    )

    assert result.returncode != 0

    assert result.events.splitlines() == [
        "capture",
        "runtime-verify:1",
        "doctor:1",
        "atlas-verify:1",
        "maintenance:disable",
        "runtime-verify:2",
        "doctor:2",
        "atlas-verify:2",
        "maintenance:enable",
    ]

    assert result.current_id == "baseline-test"
    assert result.maintenance_exists is True
    assert result.lock_exists is True
    assert result.failed_status == "failed"
    assert result.reconciliation.exists() is False


def test_behavior_success_publishes_verified_target_reconciliation(
    tmp_path: Path,
) -> None:
    import subprocess

    result = _run_failed_after_apply_recovery(tmp_path)

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        f"events:\n{result.events}"
    )

    assert result.events.splitlines() == [
        "capture",
        "runtime-verify:1",
        "doctor:1",
        "atlas-verify:1",
        "maintenance:disable",
        "runtime-verify:2",
        "doctor:2",
        "atlas-verify:2",
        "set-status:verified",
        "set-current:baseline-reconciliation-test",
        "release:update-test",
    ]

    assert result.current_id == "baseline-reconciliation-test"
    assert result.maintenance_exists is False
    assert result.lock_exists is False

    # The original failed deployment is immutable evidence.
    assert result.failed_status == "failed"

    record = result.reconciliation

    assert record.is_dir()
    assert (record / "status").read_text(
        encoding="utf-8"
    ).strip() == "verified"

    metadata = (record / "metadata").read_text(
        encoding="utf-8"
    )

    assert "type=baseline\n" in metadata
    assert (
        "baseline_kind=failed-after-apply-reconciliation\n"
        in metadata
    )
    assert "previous_baseline=baseline-test\n" in metadata
    assert "failed_deployment=update-test\n" in metadata
    assert f"target_commit={'a' * 40}\n" in metadata
    assert f"source_commit={'a' * 40}\n" in metadata
    assert f"core_commit={'a' * 40}\n" in metadata
    assert f"ingress_commit={'a' * 40}\n" in metadata
    assert f"sports_commit={'a' * 40}\n" in metadata
    assert "reason=failed-after-apply-recovery\n" in metadata
    assert (
        "source_claim=verified-already-applied-target\n"
        in metadata
    )

    assert (record / "images.tsv").is_file()
    assert (record / "provenance").is_file()
    assert (record / "core-source.tar.gz").is_file()
    assert (record / "ingress-source.tar.gz").is_file()
    assert (record / "sports-source.tar.gz").is_file()
    assert (record / "MANIFEST.sha256").is_file()

    subprocess.run(
        ["sha256sum", "-c", "MANIFEST.sha256"],
        cwd=record,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert "Failed-after-apply recovery complete" in result.stdout
