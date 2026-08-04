"""Shell-level regression tests for the root Atlas Verify command."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = (
    PROJECT_ROOT
    / "scripts"
    / "commands"
    / "verify.sh"
)

CORE_SERVICES = (
    "jellyfin",
    "jellyseerr",
    "prowlarr",
    "sonarr",
    "sonarr-anime",
    "radarr",
    "radarr-anime",
    "gluetun",
    "qbittorrent",
    "homepage",
)

REQUIRED_PROJECT_FILES = (
    "VERSION",
    "CHARTER.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "docs/BUILD_LOG.md",
    "docs/MATURITY.md",
    "docs/INDEXERS.md",
)


def write_executable(
    path: Path,
    content: str,
) -> None:
    """Write one executable test command."""

    path.write_text(
        textwrap.dedent(content).lstrip(),
        encoding="utf-8",
    )

    path.chmod(0o755)


def prepare_runtime(
    tmp_path: Path,
) -> Mapping[str, str]:
    """Create a minimal deterministic Atlas runtime."""

    project_dir = tmp_path / "project-atlas"
    storage_root = tmp_path / "storage"
    media_root = storage_root / "media"
    downloads_root = storage_root / "downloads"
    backup_dir = storage_root / "backups" / "atlas"
    config_root = storage_root / "configs"
    runtime_config_dir = config_root / "atlas"
    users_dir = runtime_config_dir / "users"
    identity_dir = runtime_config_dir / "identity"
    ari_dir = runtime_config_dir / "ari"
    ari_snapshot_dir = ari_dir / "snapshots"
    scheduler_dir = runtime_config_dir / "scheduler"
    gpu_device = tmp_path / "renderD128"
    bin_directory = tmp_path / "bin"

    for path in (
        project_dir,
        media_root / "Movies",
        media_root / "TV",
        media_root / "Anime Movies",
        media_root / "Anime TV",
        downloads_root,
        bin_directory,
    ):
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

    gpu_device.touch()

    for relative_path in REQUIRED_PROJECT_FILES:
        path = project_dir / relative_path

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            "test\n",
            encoding="utf-8",
        )

    write_executable(
        bin_directory / "docker",
        r"""
        #!/usr/bin/env bash

        set -euo pipefail

        if [[ "${1:-}" == "info" ]]; then
          if [[ "${ATLAS_TEST_DOCKER_INFO_STATUS:-0}" != "0" ]]; then
            exit "${ATLAS_TEST_DOCKER_INFO_STATUS}"
          fi

          exit 0
        fi

        if [[ "${1:-}" == "compose" && "${2:-}" == "version" ]]; then
          exit 0
        fi

        if [[ "${1:-}" == "ps" ]]; then
          printf '%s\n' "${ATLAS_TEST_RUNNING_SERVICES:-}"
          exit 0
        fi

        if [[ "${1:-}" == "exec" && "${2:-}" == "qbittorrent" ]]; then
          exit "${ATLAS_TEST_VPN_STATUS:-0}"
        fi

        exit 0
        """,
    )

    environment = os.environ.copy()

    environment.update(
        {
            "PATH": (
                str(bin_directory)
                + os.pathsep
                + environment["PATH"]
            ),
            "ATLAS_PROJECT_DIR": str(project_dir),
            "ATLAS_STORAGE_ROOT": str(storage_root),
            "ATLAS_MEDIA_ROOT": str(media_root),
            "ATLAS_DOWNLOADS_ROOT": str(downloads_root),
            "ATLAS_BACKUP_DIR": str(backup_dir),
            "ATLAS_CONFIG_ROOT": str(config_root),
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime_config_dir),
            "ATLAS_USERS_DIR": str(users_dir),
            "ATLAS_IDENTITY_DIR": str(identity_dir),
            "ATLAS_BASE_URL": "http://atlas.local",
            "ATLAS_INVITE_EXPIRATION_DAYS": "7",
            "ATLAS_ARI_DIR": str(ari_dir),
            "ATLAS_ARI_SNAPSHOT_DIR": str(ari_snapshot_dir),
            "ATLAS_ARI_LATEST_FILE": str(ari_dir / "latest.json"),
            "ATLAS_JELLYFIN_URL": "http://127.0.0.1:8096",
            "ATLAS_JELLYFIN_MOVIES_PATH": "/media/Movies",
            "ATLAS_JELLYFIN_TV_PATH": "/media/TV",
            "ATLAS_JELLYFIN_ANIME_MOVIES_PATH": "/media/Anime Movies",
            "ATLAS_JELLYFIN_ANIME_TV_PATH": "/media/Anime TV",
            "ATLAS_SCHEDULER_DIR": str(scheduler_dir),
            "ATLAS_SCHEDULER_STATE_FILE": str(
                scheduler_dir / "tasks.json"
            ),
            "ATLAS_SCHEDULER_LOCK_FILE": str(
                scheduler_dir / "scheduler.lock"
            ),
            "ATLAS_VERIFY_GPU_DEVICE": str(gpu_device),
            "ATLAS_TEST_RUNNING_SERVICES": "\n".join(
                CORE_SERVICES
            ),
        }
    )

    return environment


def run_verify(
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    """Source and run the root Verify command."""

    harness = r"""
    set -u

    source "$ATLAS_TEST_VERIFY_SCRIPT"

    atlas_print_header() {
      echo "Project Atlas"
      echo "Simplicity Meets Ingenuity"
      echo
    }

    atlas_section() {
      echo "$1"
      printf '%*s\n' "${#1}" '' | tr ' ' '-'
    }

    atlas_ok() {
      echo "OK   $*"
    }

    atlas_fail() {
      echo "FAIL $*"
    }

    atlas_command_verify
    """

    resolved_environment = dict(environment)
    resolved_environment["ATLAS_TEST_VERIFY_SCRIPT"] = str(
        VERIFY_SCRIPT
    )

    return subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=resolved_environment,
    )


def test_verify_reports_pass_for_valid_runtime(
    tmp_path: Path,
) -> None:
    """A valid runtime must produce a successful result."""

    result = run_verify(
        prepare_runtime(tmp_path)
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Atlas Verification" in result.stdout
    assert "Configuration" in result.stdout
    assert "Infrastructure" in result.stdout
    assert "Core Services" in result.stdout
    assert "Storage Paths" in result.stdout
    assert "Project Files" in result.stdout
    assert "VPN" in result.stdout
    assert "OK   Docker Engine" in result.stdout
    assert "OK   homepage running" in result.stdout
    assert "Overall Status: PASS" in result.stdout
    assert "Overall Status: FAIL" not in result.stdout


def test_verify_aggregates_infrastructure_failures(
    tmp_path: Path,
) -> None:
    """Multiple failed checks must be reported before exiting."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_DOCKER_INFO_STATUS"] = "1"
    environment["ATLAS_VERIFY_GPU_DEVICE"] = str(
        tmp_path / "missing-render-device"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert "FAIL Docker Engine" in result.stdout
    assert "FAIL Intel GPU Available" in result.stdout
    assert "OK   Docker Compose" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_reports_missing_core_service(
    tmp_path: Path,
) -> None:
    """A missing required service must fail verification."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_RUNNING_SERVICES"] = "\n".join(
        service
        for service in CORE_SERVICES
        if service != "homepage"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert "FAIL homepage running" in result.stdout
    assert "OK   jellyfin running" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_reports_missing_configuration_value(
    tmp_path: Path,
) -> None:
    """A missing required variable must fail configuration verification."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment.pop(
        "ATLAS_BACKUP_DIR"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert (
        "FAIL ATLAS_BACKUP_DIR absolute path"
        in result.stdout
    )
    assert "Infrastructure" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_rejects_blank_url_configuration(
    tmp_path: Path,
) -> None:
    """Required URLs must reject blank values."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_BASE_URL"] = "   "

    result = run_verify(environment)

    assert result.returncode == 1
    assert (
        "FAIL ATLAS_BASE_URL HTTP URL"
        in result.stdout
    )
    assert "Overall Status: FAIL" in result.stdout


def test_verify_rejects_relative_path_configuration(
    tmp_path: Path,
) -> None:
    """Path contracts must require absolute values."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_USERS_DIR"] = "users"

    result = run_verify(environment)

    assert result.returncode == 1
    assert (
        "FAIL ATLAS_USERS_DIR absolute path"
        in result.stdout
    )
    assert (
        "FAIL ATLAS_USERS_DIR within "
        "ATLAS_RUNTIME_CONFIG_DIR"
        in result.stdout
    )


def test_verify_rejects_invalid_positive_integer(
    tmp_path: Path,
) -> None:
    """Invitation expiry must be a positive integer."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment[
        "ATLAS_INVITE_EXPIRATION_DAYS"
    ] = "0"

    result = run_verify(environment)

    assert result.returncode == 1
    assert (
        "FAIL ATLAS_INVITE_EXPIRATION_DAYS "
        "positive integer"
        in result.stdout
    )


def test_verify_rejects_inconsistent_path_relationship(
    tmp_path: Path,
) -> None:
    """Derived paths must remain beneath their canonical parent."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_SCHEDULER_STATE_FILE"] = (
        "/tmp/tasks.json"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert (
        "OK   ATLAS_SCHEDULER_STATE_FILE absolute path"
        in result.stdout
    )
    assert (
        "FAIL ATLAS_SCHEDULER_STATE_FILE within "
        "ATLAS_SCHEDULER_DIR"
        in result.stdout
    )
