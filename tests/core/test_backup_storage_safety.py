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
