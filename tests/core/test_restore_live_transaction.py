from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESTORE_COMMAND = PROJECT_ROOT / "scripts" / "commands" / "restore.sh"


def _run(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        cwd=PROJECT_ROOT,
        env={**os.environ, **env, "RESTORE_COMMAND": str(RESTORE_COMMAND)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _base(tmp_path: Path, extra: str = "") -> tuple[str, dict[str, str]]:
    runtime = tmp_path / "atlas"
    runtime.mkdir()
    stage = Path("/tmp") / f"project-atlas-restore.tx-{os.getpid()}-{tmp_path.name}"
    stage.mkdir(mode=0o700)
    baseline = tmp_path / "baseline-verified"
    baseline.mkdir()
    backup = tmp_path / "atlas-pre-restore.tar.gz"
    backup.write_bytes(b"stub-backup")
    events = tmp_path / "events"

    script = r'''
source "$RESTORE_COMMAND"
atlas_restore_require_production_preflight() { printf '%s\n' "$BASELINE"; }
atlas_restore_load_recovery_library() { :; }
atlas_backup_recovery_staged_state_digest() { echo staged-digest; }
atlas_deployment_new_id() { echo restore-test; }
atlas_deployment_valid_id() { :; }
atlas_deployment_acquire_lock() { echo lock:acquire >> "$EVENTS"; }
atlas_deployment_release_lock() { echo lock:release >> "$EVENTS"; }
atlas_maintenance_enable() { echo maintenance:enable >> "$EVENTS"; }
atlas_maintenance_disable() { echo maintenance:disable >> "$EVENTS"; }
atlas_restore_stop_writers() { echo writers:stop >> "$EVENTS"; }
atlas_restore_start_writers() { echo writers:start >> "$EVENTS"; }
atlas_restore_wait_for_writers() { echo writers:ready >> "$EVENTS"; }
atlas_restore_create_pre_restore_recovery_point() {
  echo backup:create >> "$EVENTS"
  ATLAS_RESTORE_RECOVERY_POINT="$BACKUP"
  export ATLAS_RESTORE_RECOVERY_POINT
}
atlas_backup_recovery_validate_archive() { :; }
atlas_backup_recovery_apply_staged_state() {
  echo state:apply >> "$EVENTS"
  mkdir -p "$2"
  echo applied-awaiting-verification > "$2/status"
  mkdir -p "$2/live-rollback"
}
atlas_backup_recovery_revert_applied_state() {
  echo state:revert >> "$EVENTS"
  echo reverted > "$1/status"
}
atlas_backup_recovery_finalize_applied_state() {
  echo state:finalize >> "$EVENTS"
  echo verified > "$1/status"
}
atlas_restore_validate_live_consumers() { echo consumers:live >> "$EVENTS"; }
atlas_restore_verify_runtime_boundary() { echo runtime:verify >> "$EVENTS"; }
atlas_restore_verify_maintenance_isolation() { echo maintenance:verify >> "$EVENTS"; }
'''
    script += extra
    environment = {
        "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
        "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
        "STAGE": str(stage),
        "BASELINE": str(baseline),
        "BACKUP": str(backup),
        "EVENTS": str(events),
    }
    return script, environment


def _cleanup_stage(env: dict[str, str]) -> None:
    stage = Path(env["STAGE"])
    if stage.exists():
        stage.rmdir()


def test_successful_apply_orders_safety_boundaries(tmp_path: Path) -> None:
    script, env = _base(tmp_path)
    script += r'''
atlas_restore_apply_live "$STAGE"
'''
    try:
        result = _run(script, env)
    finally:
        _cleanup_stage(env)

    assert result.returncode == 0, result.stderr
    events = Path(env["EVENTS"]).read_text(encoding="utf-8").splitlines()
    assert events == [
        "lock:acquire",
        "maintenance:enable",
        "maintenance:verify",
        "writers:stop",
        "backup:create",
        "state:apply",
        "consumers:live",
        "writers:start",
        "writers:ready",
        "runtime:verify",
        "maintenance:disable",
        "runtime:verify",
        "state:finalize",
        "lock:release",
    ]
    transaction = Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "restores/restore-test"
    assert (transaction / "status").read_text().strip() == "verified"
    assert (transaction / "pre-restore-backup").read_text().strip() == env["BACKUP"]
    assert (transaction / "restore-metadata").is_file()


def test_backup_failure_restores_normal_operation_before_mutation(tmp_path: Path) -> None:
    override = r'''
atlas_restore_create_pre_restore_recovery_point() {
  echo backup:fail >> "$EVENTS"
  return 1
}
'''
    script, env = _base(tmp_path, override)
    script += 'atlas_restore_apply_live "$STAGE"\n'
    try:
        result = _run(script, env)
    finally:
        _cleanup_stage(env)

    assert result.returncode != 0
    events = Path(env["EVENTS"]).read_text(encoding="utf-8").splitlines()
    assert "state:apply" not in events
    assert events[-4:] == [
        "writers:start",
        "writers:ready",
        "maintenance:disable",
        "lock:release",
    ]


def test_application_failure_retains_maintenance_and_lock(tmp_path: Path) -> None:
    override = r'''
atlas_backup_recovery_apply_staged_state() {
  echo state:apply-fail >> "$EVENTS"
  mkdir -p "$2"
  echo reverted > "$2/status"
  return 1
}
'''
    script, env = _base(tmp_path, override)
    script += 'atlas_restore_apply_live "$STAGE"\n'
    try:
        result = _run(script, env)
    finally:
        _cleanup_stage(env)

    assert result.returncode != 0
    events = Path(env["EVENTS"]).read_text(encoding="utf-8").splitlines()
    assert "state:apply-fail" in events
    assert "lock:release" not in events
    assert "maintenance:disable" not in events
    assert "Maintenance: retained" in result.stderr


def test_live_consumer_failure_reverts_while_writers_are_quiesced(tmp_path: Path) -> None:
    override = r'''
atlas_restore_validate_live_consumers() {
  echo consumers:fail >> "$EVENTS"
  return 1
}
'''
    script, env = _base(tmp_path, override)
    script += 'atlas_restore_apply_live "$STAGE"\n'
    try:
        result = _run(script, env)
    finally:
        _cleanup_stage(env)

    assert result.returncode != 0
    events = Path(env["EVENTS"]).read_text(encoding="utf-8").splitlines()
    assert events.index("state:apply") < events.index("consumers:fail")
    assert events.index("consumers:fail") < events.index("state:revert")
    assert events.index("state:revert") < events.index("writers:start")
    assert "lock:release" not in events
    assert "maintenance:disable" not in events


def test_public_verification_failure_reenables_maintenance_and_keeps_lock(tmp_path: Path) -> None:
    override = r'''
VERIFY_COUNT=0
atlas_restore_verify_runtime_boundary() {
  VERIFY_COUNT=$((VERIFY_COUNT + 1))
  echo "runtime:verify:$VERIFY_COUNT" >> "$EVENTS"
  [[ "$VERIFY_COUNT" -eq 1 ]]
}
'''
    script, env = _base(tmp_path, override)
    script += 'atlas_restore_apply_live "$STAGE"\n'
    try:
        result = _run(script, env)
    finally:
        _cleanup_stage(env)

    assert result.returncode != 0
    events = Path(env["EVENTS"]).read_text(encoding="utf-8").splitlines()
    disable = events.index("maintenance:disable")
    assert "maintenance:enable" in events[disable + 1 :]
    assert "lock:release" not in events
    assert "state:finalize" not in events


def _held_environment(tmp_path: Path, status: str) -> tuple[str, dict[str, str], Path]:
    runtime = tmp_path / "atlas"
    transaction = runtime / "restores/restore-held"
    transaction.mkdir(parents=True)
    (transaction / "status").write_text(status + "\n", encoding="utf-8")
    backup = tmp_path / "pre-restore.tar.gz"
    backup.write_bytes(b"stub")
    (transaction / "pre-restore-backup").write_text(str(backup) + "\n", encoding="utf-8")
    events = tmp_path / "events"

    script = r'''
source "$RESTORE_COMMAND"
atlas_deployment_valid_id() { :; }
atlas_deployment_validate_source() { :; }
atlas_deployment_lock_matches() { :; }
atlas_maintenance_flag() { printf '%s\n' "$MAINTENANCE_FLAG"; }
atlas_restore_load_recovery_library() { :; }
atlas_backup_recovery_validate_archive() { :; }
atlas_restore_stop_writers() { echo writers:stop >> "$EVENTS"; }
atlas_restore_start_writers() { echo writers:start >> "$EVENTS"; }
atlas_restore_wait_for_writers() { echo writers:ready >> "$EVENTS"; }
atlas_restore_validate_live_consumers() { echo consumers:live >> "$EVENTS"; }
atlas_restore_verify_runtime_boundary() { echo runtime:verify >> "$EVENTS"; }
atlas_maintenance_disable() { echo maintenance:disable >> "$EVENTS"; }
atlas_maintenance_enable() { echo maintenance:enable >> "$EVENTS"; }
atlas_deployment_release_lock() { echo lock:release >> "$EVENTS"; }
atlas_backup_recovery_revert_applied_state() {
  echo state:revert >> "$EVENTS"
  echo reverted > "$1/status"
}
atlas_backup_recovery_finalize_applied_state() {
  echo state:finalize >> "$EVENTS"
  echo verified > "$1/status"
}
'''
    environment = {
        "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
        "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
        "MAINTENANCE_FLAG": str(tmp_path / "enabled"),
        "EVENTS": str(events),
    }
    Path(environment["MAINTENANCE_FLAG"]).write_text("", encoding="utf-8")
    return script, environment, transaction


def test_abort_reverts_applied_state_before_reopening(tmp_path: Path) -> None:
    script, env, transaction = _held_environment(
        tmp_path, "applied-awaiting-verification"
    )
    script += 'atlas_restore_abort_live restore-held\n'
    result = _run(script, env)

    assert result.returncode == 0, result.stderr
    events = Path(env["EVENTS"]).read_text(encoding="utf-8").splitlines()
    assert events.index("writers:stop") < events.index("state:revert")
    assert events.index("state:revert") < events.index("consumers:live")
    assert events[-2:] == ["runtime:verify", "lock:release"]
    assert transaction.joinpath("status").read_text().strip() == "aborted"


def test_resume_validates_live_state_then_finalizes(tmp_path: Path) -> None:
    script, env, transaction = _held_environment(
        tmp_path, "applied-awaiting-verification"
    )
    script += 'atlas_restore_resume_live restore-held\n'
    result = _run(script, env)

    assert result.returncode == 0, result.stderr
    events = Path(env["EVENTS"]).read_text(encoding="utf-8").splitlines()
    assert events.index("writers:stop") < events.index("consumers:live")
    assert "state:revert" not in events
    assert events[-2:] == ["state:finalize", "lock:release"]
    assert transaction.joinpath("status").read_text().strip() == "verified"


def test_cli_requires_explicit_live_confirmation() -> None:
    result = subprocess.run(
        ["bash", "-c", r'''
set -euo pipefail
atlas_print_header() { :; }
source "$RESTORE_COMMAND"
atlas_command_restore apply /tmp/project-atlas-restore.example
'''],
        cwd=PROJECT_ROOT,
        env={**os.environ, "RESTORE_COMMAND": str(RESTORE_COMMAND)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--confirm-live" in result.stderr
