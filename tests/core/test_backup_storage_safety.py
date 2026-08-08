from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_COMMAND = PROJECT_ROOT / "scripts" / "commands" / "backup.sh"


def _make_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    backups = tmp_path / "backups"

    project.mkdir()
    backups.mkdir()

    for directory in ("config", "docs", "modules", "scripts"):
        (project / directory).mkdir()
        (project / directory / ".keep").write_text("keep\n", encoding="utf-8")

    files = {
        "docker-compose.yml": "services: {}\n",
        "docker-compose.sports.yml": "services: {}\n",
        ".env.example": "ATLAS_TEST=1\n",
        "VERSION": "1.0.0-test\n",
        "CHARTER.md": "# Charter\n",
        "ROADMAP.md": "# Roadmap\n",
        "CHANGELOG.md": "# Changelog\n",
    }

    for name, content in files.items():
        (project / name).write_text(content, encoding="utf-8")

    _write_recovery_state(project)
    return project, backups


def _run_backup(
    project: Path,
    backups: Path,
    *,
    path_prefix: Path | None = None,
    list_only: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = """
set -euo pipefail
atlas_print_header() { :; }
source "$BACKUP_COMMAND"
atlas_command_backup "$@"
"""

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_PROJECT_DIR": str(project),
            "ATLAS_BACKUP_DIR": str(backups),
            "BACKUP_COMMAND": str(BACKUP_COMMAND),
        }
    )

    environment.update(_recovery_environment(project))

    if path_prefix is not None:
        environment["PATH"] = f"{path_prefix}:{environment['PATH']}"

    arguments = ["--list"] if list_only else ["--notes", "storage-test"]

    return subprocess.run(
        ["bash", "-c", command, "atlas-backup-test", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_successful_backup_publishes_only_valid_final_archive(
    tmp_path: Path,
) -> None:
    project, backups = _make_project(tmp_path)

    result = _run_backup(project, backups)

    assert result.returncode == 0, result.stderr
    final_archives = list(backups.glob("atlas-*.tar.gz"))
    partial_archives = list(backups.glob("*.partial"))
    assert len(final_archives) == 1
    assert partial_archives == []
    assert "Available backup storage:" in result.stdout
    assert "Status:\n  SUCCESS" in result.stdout

    listing = subprocess.run(
        ["tar", "-tzf", str(final_archives[0])],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert listing.returncode == 0
    assert "BACKUP_INFO.txt" in listing.stdout.splitlines()


def test_archive_creation_failure_removes_partial_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    project, backups = _make_project(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()

    _write_executable(
        fake_bin / "tar",
        """#!/usr/bin/env bash
set -euo pipefail
output=''
while (($#)); do
  if [[ "$1" == '-czf' ]]; then
    output="$2"
    break
  fi
  shift
done
[[ -n "$output" ]]
printf 'partial archive' > "$output"
exit 28
""",
    )

    result = _run_backup(project, backups, path_prefix=fake_bin)

    assert result.returncode != 0
    assert list(backups.glob("atlas-*.tar.gz")) == []
    assert list(backups.glob("*.partial")) == []
    assert not (project / ".atlas-backup-manifest.tmp").exists()
    assert "backup archive creation failed" in result.stderr


def test_publication_failure_removes_partial_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    project, backups = _make_project(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()

    real_tar = subprocess.run(
        ["bash", "-c", "command -v tar"],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()

    _write_executable(
        fake_bin / "tar",
        f"#!/usr/bin/env bash\nexec {real_tar!r} \"$@\"\n",
    )
    _write_executable(
        fake_bin / "mv",
        """#!/usr/bin/env bash
exit 1
""",
    )

    result = _run_backup(project, backups, path_prefix=fake_bin)

    assert result.returncode != 0
    assert list(backups.glob("atlas-*.tar.gz")) == []
    assert list(backups.glob("*.partial")) == []
    assert not (project / ".atlas-backup-manifest.tmp").exists()
    assert "backup publication failed" in result.stderr


def test_backup_listing_ignores_partial_artifacts(
    tmp_path: Path,
) -> None:
    project, backups = _make_project(tmp_path)
    (backups / "atlas-20260807-000000-000.tar.gz.partial").write_text(
        "partial",
        encoding="utf-8",
    )

    result = _run_backup(project, backups, list_only=True)

    assert result.returncode == 0
    assert "No backups found." in result.stdout
    assert ".partial" not in result.stdout


# M-023.25.2 recovery metadata / CLI safety contracts

def _run_backup_arguments(
    project: Path,
    backups: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    command = """
set -euo pipefail
atlas_print_header() { :; }
source "$BACKUP_COMMAND"
atlas_command_backup "$@"
"""

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_PROJECT_DIR": str(project),
            "ATLAS_BACKUP_DIR": str(backups),
            "BACKUP_COMMAND": str(BACKUP_COMMAND),
        }
    )

    environment.update(_recovery_environment(project))

    return subprocess.run(
        ["bash", "-c", command, "atlas-backup-test", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_backup_help_is_read_only(tmp_path: Path) -> None:
    project, backups = _make_project(tmp_path)

    result = _run_backup_arguments(project, backups, "--help")

    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout
    assert "atlas backup --help" in result.stdout
    assert list(backups.glob("atlas-*.tar.gz")) == []
    assert list(backups.glob("*.partial")) == []


def test_unknown_backup_argument_fails_without_mutation(tmp_path: Path) -> None:
    project, backups = _make_project(tmp_path)

    existing = []
    for index in range(11):
        path = backups / f"atlas-20260808-000000-{index:03d}.tar.gz"
        path.write_text("historical\n", encoding="utf-8")
        existing.append(path)

    result = _run_backup_arguments(project, backups, "--unknown")

    assert result.returncode == 2
    assert "unknown backup option" in result.stderr
    assert all(path.exists() for path in existing)
    assert len(list(backups.glob("atlas-*.tar.gz"))) == 11
    assert list(backups.glob("*.partial")) == []


def test_backup_rejects_extra_arguments_without_mutation(tmp_path: Path) -> None:
    project, backups = _make_project(tmp_path)

    result = _run_backup_arguments(
        project,
        backups,
        "--notes",
        "expected note",
        "unexpected",
    )

    assert result.returncode == 2
    assert list(backups.glob("atlas-*.tar.gz")) == []
    assert list(backups.glob("*.partial")) == []


def test_successful_backup_is_owner_only_and_declares_recovery_metadata(
    tmp_path: Path,
) -> None:
    project, backups = _make_project(tmp_path)

    result = _run_backup_arguments(
        project,
        backups,
        "--notes",
        "recovery-contract-test",
    )

    assert result.returncode == 0, result.stderr

    archives = list(backups.glob("atlas-*.tar.gz"))
    assert len(archives) == 1
    archive = archives[0]

    assert archive.stat().st_mode & 0o777 == 0o600

    members = subprocess.run(
        ["tar", "-tzf", str(archive)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert "BACKUP_INFO.txt" in members
    assert "RECOVERY_FORMAT" in members
    assert "RECOVERY_MANIFEST.tsv" in members
    assert "SHA256SUMS" in members

    recovery_format = subprocess.run(
        ["tar", "-xOzf", str(archive), "RECOVERY_FORMAT"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout

    assert recovery_format == "1\n"

    recovery_manifest = subprocess.run(
        ["tar", "-xOzf", str(archive), "RECOVERY_MANIFEST.tsv"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout

    assert (
        "surface\tarchive_path\trequirement\tpolicy\n"
        in recovery_manifest
    )
    assert (
        "project-configuration\t.\trequired\tconfiguration-only\n"
        in recovery_manifest
    )

    backup_info = subprocess.run(
        ["tar", "-xOzf", str(archive), "BACKUP_INFO.txt"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout

    assert "Recovery format: 1" in backup_info
    assert "Recovery state: state-complete" in backup_info
    assert "Recovery capability: restore-unverified" in backup_info
    assert "Format 1 (state-complete; restore-unverified)" in result.stdout

    for temporary in (
        ".atlas-backup-manifest.tmp",
        ".atlas-backup-recovery-format.tmp",
        ".atlas-backup-recovery-manifest.tmp",
        ".atlas-backup-recovery-checksums.tmp",
    ):
        assert not (project / temporary).exists()


# M-023.25.3.2 state-snapshot fixtures

def _recovery_environment(project: Path) -> dict[str, str]:
    state = project / "recovery-state"
    runtime = state / "atlas"
    return {
        "ATLAS_CONFIG_ROOT": str(state),
        "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
        "ATLAS_USERS_DIR": str(runtime / "users"),
        "ATLAS_IDENTITY_DIR": str(runtime / "identity"),
        "ATLAS_REQUESTS_DIR": str(runtime / "requests"),
        "ATLAS_SCHEDULER_STATE_FILE": str(runtime / "scheduler" / "tasks.json"),
        "ATLAS_ARI_DIR": str(runtime / "ari"),
        "SPORTS_CONFIG_DIR": str(state / "sportyfin"),
    }


def _write_recovery_state(project: Path) -> None:
    env = _recovery_environment(project)

    files = {
        Path(env["ATLAS_USERS_DIR"]) / "users.json": '{"users": []}\n',
        Path(env["ATLAS_IDENTITY_DIR"]) / "favorites" / "favorites.json": '{}\n',
        Path(env["ATLAS_SCHEDULER_STATE_FILE"]): '{"tasks": []}\n',
        Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "runtime" / "events.jsonl": "",
        Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "runtime" / "subscribers" / "test.cursor": "0\n",
        Path(env["ATLAS_ARI_DIR"]) / "state.json": '{}\n',
        Path(env["SPORTS_CONFIG_DIR"]) / "state" / "subscriptions.json": '[]\n',
        Path(env["SPORTS_CONFIG_DIR"]) / "recordings" / "recordings.json": '[]\n',
        Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "runtime" / "scheduler" / "sports.json": '{}\n',
    }

    for state_path, state_content in files.items():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(state_content, encoding="utf-8")
