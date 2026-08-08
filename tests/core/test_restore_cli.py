from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESTORE_COMMAND = PROJECT_ROOT / "scripts" / "commands" / "restore.sh"


def _run_restore(
    *arguments: str,
    validator: str | None = None,
) -> subprocess.CompletedProcess[str]:
    override = validator or ""
    command = f'''
set -euo pipefail
atlas_print_header() {{ :; }}
source "$RESTORE_COMMAND"
{override}
atlas_command_restore "$@"
'''
    environment = {**os.environ, "RESTORE_COMMAND": str(RESTORE_COMMAND)}
    return subprocess.run(
        ["bash", "-c", command, "atlas-restore-test", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _write_tar_member(
    archive: tarfile.TarFile,
    name: str,
    content: str,
) -> None:
    payload = content.encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o600
    archive.addfile(info, io.BytesIO(payload))


def _legacy_archive(tmp_path: Path) -> Path:
    archive_path = tmp_path / "legacy.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        _write_tar_member(
            archive,
            "BACKUP_INFO.txt",
            "Project Atlas Backup\nVersion: historical\n",
        )
    return archive_path


def test_restore_help_is_read_only(tmp_path: Path) -> None:
    marker = tmp_path / "marker"

    result = _run_restore("--help")

    assert result.returncode == 0, result.stderr
    assert "atlas restore inspect <archive>" in result.stdout
    assert "atlas restore verify <archive>" in result.stdout
    assert "atlas restore stage <archive>" in result.stdout
    assert not marker.exists()


def test_restore_inspect_accepts_historical_configuration_archive(
    tmp_path: Path,
) -> None:
    archive = _legacy_archive(tmp_path)

    result = _run_restore("inspect", str(archive))

    assert result.returncode == 0, result.stderr
    assert "Atlas Restore Inspection" in result.stdout
    assert "Recovery format: legacy/undeclared" in result.stdout
    assert "configuration-only historical archive" in result.stdout
    assert "archive validity has not been asserted" not in result.stdout


def test_restore_verify_delegates_to_state_complete_validator(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "candidate.tar.gz"
    archive.write_bytes(b"validator-test")

    validator = r'''
atlas_backup_recovery_validate_archive() {
  [[ "$1" == "$EXPECTED_ARCHIVE" ]]
  echo 'VALIDATOR_CALLED' >&2
}
'''
    environment_archive = str(archive)
    command = f'''
set -euo pipefail
export EXPECTED_ARCHIVE={environment_archive!r}
atlas_print_header() {{ :; }}
source "$RESTORE_COMMAND"
{validator}
atlas_command_restore verify "$EXPECTED_ARCHIVE"
'''
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=PROJECT_ROOT,
        env={**os.environ, "RESTORE_COMMAND": str(RESTORE_COMMAND)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "VALIDATOR_CALLED" in result.stderr
    assert "Atlas Restore Verification: PASS" in result.stdout
    assert "Restore capability: unverified" in result.stdout


def test_restore_verify_rejects_invalid_archive(tmp_path: Path) -> None:
    archive = tmp_path / "invalid.tar.gz"
    archive.write_text("not a recovery archive\n", encoding="utf-8")

    result = _run_restore("verify", str(archive))

    assert result.returncode != 0
    assert "Atlas Restore Verification: FAIL" in result.stderr


def test_restore_apply_fails_closed_without_mutation(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"

    result = _run_restore("apply", str(marker))

    assert result.returncode == 2
    assert "live restore apply is not implemented or authorized" in result.stderr
    assert not marker.exists()


def test_restore_unknown_command_fails_closed() -> None:
    result = _run_restore("unexpected")

    assert result.returncode == 2
    assert "unknown restore command" in result.stderr


def test_restore_rejects_symbolic_link_archive(tmp_path: Path) -> None:
    target = _legacy_archive(tmp_path)
    link = tmp_path / "linked.tar.gz"
    link.symlink_to(target)

    result = _run_restore("inspect", str(link))

    assert result.returncode != 0
    assert "restore archive is not a regular file" in result.stderr
