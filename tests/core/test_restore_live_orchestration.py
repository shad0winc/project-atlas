from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESTORE_COMMAND = PROJECT_ROOT / "scripts" / "commands" / "restore.sh"


def _bash(script: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        cwd=PROJECT_ROOT,
        env={**os.environ, **(env or {}), "RESTORE_COMMAND": str(RESTORE_COMMAND)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_writer_set_is_exact_and_bounded() -> None:
    result = _bash('source "$RESTORE_COMMAND"; atlas_restore_writer_containers')

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "atlas-api",
        "atlas-sports-controller",
        "atlas-notifications-worker",
    ]


def test_writer_preflight_requires_every_writer_ready(tmp_path: Path) -> None:
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${@: -1}\" == atlas-sports-controller ]]; then\n"
        "  echo stopped\n"
        "else\n"
        "  echo healthy\n"
        "fi\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)

    result = _bash(
        'source "$RESTORE_COMMAND"; atlas_restore_require_writers_running',
        {"PATH": f"{tmp_path}:{os.environ['PATH']}"},
    )

    assert result.returncode != 0
    assert "atlas-sports-controller (stopped)" in result.stderr


def test_stop_and_start_target_only_declared_writers(tmp_path: Path) -> None:
    events = tmp_path / "events"
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "echo \"$*\" >> \"$EVENTS\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "EVENTS": str(events),
    }

    result = _bash(
        'source "$RESTORE_COMMAND"; '
        'atlas_restore_stop_writers; atlas_restore_start_writers',
        environment,
    )

    assert result.returncode == 0, result.stderr
    assert events.read_text(encoding="utf-8").splitlines() == [
        "stop --time 30 atlas-api",
        "stop --time 30 atlas-sports-controller",
        "stop --time 30 atlas-notifications-worker",
        "start atlas-api",
        "start atlas-sports-controller",
        "start atlas-notifications-worker",
    ]


def test_preflight_runs_certified_source_and_stage_contracts(tmp_path: Path) -> None:
    stage = tmp_path / "project-atlas-restore.test"
    stage.mkdir()
    record = tmp_path / "baseline"
    record.mkdir()
    marker = tmp_path / "events"

    script = r'''
source "$RESTORE_COMMAND"
atlas_deployment_validate_source() { echo source >> "$EVENTS"; }
atlas_deployment_require_current_record() { echo baseline >> "$EVENTS"; printf '%s\n' "$RECORD"; }
atlas_maintenance_flag() { printf '%s\n' "$MAINTENANCE_FLAG"; }
atlas_deployment_lock_dir() { printf '%s\n' "$LOCK_DIR"; }
atlas_restore_load_recovery_library() { :; }
atlas_backup_recovery_validate_staged_restore() { echo staged >> "$EVENTS"; }
atlas_backup_recovery_staged_state_digest() { echo digest; }
atlas_backup_recovery_validate_staged_consumers() { echo consumers >> "$EVENTS"; }
atlas_restore_require_writers_running() { echo writers >> "$EVENTS"; }
atlas_restore_require_production_preflight "$STAGE"
'''
    # Production preflight intentionally requires the canonical /tmp staging
    # namespace. Create an equivalent path there for this contract test.
    canonical = Path("/tmp") / f"project-atlas-restore.pytest-{os.getpid()}-{tmp_path.name}"
    canonical.mkdir(mode=0o700)
    try:
        result = _bash(
            script,
            {
                "EVENTS": str(marker),
                "RECORD": str(record),
                "MAINTENANCE_FLAG": str(tmp_path / "maintenance-enabled"),
                "LOCK_DIR": str(tmp_path / "update.lock"),
                "STAGE": str(canonical),
            },
        )
    finally:
        canonical.rmdir()

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(record)
    assert marker.read_text(encoding="utf-8").splitlines() == [
        "source",
        "baseline",
        "staged",
        "consumers",
        "writers",
    ]


def test_preflight_rejects_existing_shared_lock(tmp_path: Path) -> None:
    stage = Path("/tmp") / f"project-atlas-restore.lock-{os.getpid()}-{tmp_path.name}"
    stage.mkdir(mode=0o700)
    record = tmp_path / "baseline"
    record.mkdir()
    lock = tmp_path / "update.lock"
    lock.mkdir()
    try:
        result = _bash(
            r'''
source "$RESTORE_COMMAND"
atlas_deployment_validate_source() { :; }
atlas_deployment_require_current_record() { printf '%s\n' "$RECORD"; }
atlas_maintenance_flag() { printf '%s\n' "$MAINTENANCE_FLAG"; }
atlas_deployment_lock_dir() { printf '%s\n' "$LOCK_DIR"; }
atlas_restore_require_production_preflight "$STAGE"
''',
            {
                "RECORD": str(record),
                "MAINTENANCE_FLAG": str(tmp_path / "maintenance-enabled"),
                "LOCK_DIR": str(lock),
                "STAGE": str(stage),
            },
        )
    finally:
        stage.rmdir()

    assert result.returncode != 0
    assert "shared deployment lock to be free" in result.stderr


def test_preflight_rejects_existing_maintenance(tmp_path: Path) -> None:
    stage = Path("/tmp") / f"project-atlas-restore.maintenance-{os.getpid()}-{tmp_path.name}"
    stage.mkdir(mode=0o700)
    record = tmp_path / "baseline"
    record.mkdir()
    maintenance = tmp_path / "enabled"
    maintenance.write_text("", encoding="utf-8")
    try:
        result = _bash(
            r'''
source "$RESTORE_COMMAND"
atlas_deployment_validate_source() { :; }
atlas_deployment_require_current_record() { printf '%s\n' "$RECORD"; }
atlas_maintenance_flag() { printf '%s\n' "$MAINTENANCE_FLAG"; }
atlas_deployment_lock_dir() { printf '%s\n' "$LOCK_DIR"; }
atlas_restore_require_production_preflight "$STAGE"
''',
            {
                "RECORD": str(record),
                "MAINTENANCE_FLAG": str(maintenance),
                "LOCK_DIR": str(tmp_path / "update.lock"),
                "STAGE": str(stage),
            },
        )
    finally:
        stage.rmdir()

    assert result.returncode != 0
    assert "maintenance mode to be disabled" in result.stderr


def test_recovery_point_must_be_published_and_validated(tmp_path: Path) -> None:
    archive = tmp_path / "atlas-pre-restore.tar.gz"
    archive.write_bytes(b"validated-by-stub")
    result = _bash(
        r'''
source "$RESTORE_COMMAND"
atlas_deployment_valid_id() { :; }
atlas_command_backup() {
  printf 'Backup complete\n\nFile:\n  %s\n' "$ARCHIVE"
}
atlas_restore_load_recovery_library() { :; }
atlas_backup_recovery_validate_archive() { [[ "$1" == "$ARCHIVE" ]]; }
atlas_restore_create_pre_restore_recovery_point restore-test
printf 'RECOVERY_POINT=%s\n' "$ATLAS_RESTORE_RECOVERY_POINT"
''',
        {"ARCHIVE": str(archive)},
    )

    assert result.returncode == 0, result.stderr
    assert f"RECOVERY_POINT={archive}" in result.stdout


def test_recovery_point_rejects_unvalidated_backup(tmp_path: Path) -> None:
    archive = tmp_path / "atlas-pre-restore.tar.gz"
    archive.write_bytes(b"invalid")
    result = _bash(
        r'''
source "$RESTORE_COMMAND"
atlas_deployment_valid_id() { :; }
atlas_command_backup() { printf 'File:\n  %s\n' "$ARCHIVE"; }
atlas_restore_load_recovery_library() { :; }
atlas_backup_recovery_validate_archive() { return 1; }
atlas_restore_create_pre_restore_recovery_point restore-test
''',
        {"ARCHIVE": str(archive)},
    )

    assert result.returncode != 0
    assert "failed validation" in result.stderr


def test_live_consumer_validation_uses_fresh_snapshot(tmp_path: Path) -> None:
    marker = tmp_path / "events"
    result = _bash(
        r'''
source "$RESTORE_COMMAND"
atlas_restore_load_recovery_library() { :; }
atlas_backup_recovery_snapshot_state() {
  mkdir -p "$1/state"
  echo snapshot >> "$EVENTS"
  printf 'users\tstate/users\trequired\tcaptured\n'
}
atlas_backup_recovery_validate_staged_consumers() {
  [[ -f "$1/RECOVERY_MANIFEST.tsv" ]]
  echo consumers >> "$EVENTS"
}
atlas_restore_validate_live_consumers
''',
        {"EVENTS": str(marker)},
    )

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8").splitlines() == [
        "snapshot",
        "consumers",
    ]


def test_cli_apply_requires_explicit_confirmation_after_orchestration_checkpoint() -> None:
    content = RESTORE_COMMAND.read_text(encoding="utf-8")

    assert "restore apply requires <staging-root> --confirm-live" in content
    assert "atlas_restore_require_production_preflight()" in content
    assert "atlas_restore_validate_live_consumers()" in content
    assert "atlas_restore_apply_live()" in content
