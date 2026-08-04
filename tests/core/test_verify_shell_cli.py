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

COMPOSE_SERVICES = (
    "dozzle",
    "flaresolverr",
    "gluetun",
    "qbittorrent",
    "sonarr",
    "jellyfin",
    "radarr",
    "maintainerr",
    "tautulli",
    "jellyseerr",
    "sonarr-anime",
    "bazarr",
    "homepage",
    "prowlarr",
    "radarr-anime",
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
        backup_dir,
        config_root,
        runtime_config_dir,
        project_dir / "scripts",
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

    (project_dir / "docker-compose.yml").write_text(
        "services: {}\n",
        encoding="utf-8",
    )

    write_executable(
        project_dir / "scripts" / "verify-ingress.sh",
        """
        #!/usr/bin/env bash

        printf '%s\n' "${ATLAS_TEST_INGRESS_OUTPUT:-Atlas Ingress Status: PASS}"
        exit "${ATLAS_TEST_INGRESS_STATUS:-0}"
        """,
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

        if [[ "${1:-}" == "compose" ]]; then
          arguments=" $* "

          if [[ "$arguments" == *" config --services "* ]]; then
            if [[ "${ATLAS_TEST_COMPOSE_CONFIG_STATUS:-0}" != "0" ]]; then
              exit "${ATLAS_TEST_COMPOSE_CONFIG_STATUS}"
            fi

            printf '%s\n' "${ATLAS_TEST_COMPOSE_SERVICES:-}"
            exit 0
          fi

          if [[ "$arguments" == *" ps --status running --services "* ]]; then
            if [[ "${ATLAS_TEST_COMPOSE_PS_STATUS:-0}" != "0" ]]; then
              exit "${ATLAS_TEST_COMPOSE_PS_STATUS}"
            fi

            printf '%s\n' "${ATLAS_TEST_RUNNING_SERVICES:-}"
            exit 0
          fi
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
            "ATLAS_TEST_COMPOSE_SERVICES": "\n".join(
                COMPOSE_SERVICES
            ),
            "ATLAS_TEST_RUNNING_SERVICES": "\n".join(
                COMPOSE_SERVICES
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

    atlas_command_scheduler() {
      if [[ "${ATLAS_TEST_SCHEDULER_STATUS:-0}" != "0" ]]; then
        printf '%s\n' "${ATLAS_TEST_SCHEDULER_OUTPUT:-Scheduler unavailable}"
        return "${ATLAS_TEST_SCHEDULER_STATUS}"
      fi

      printf '%s\n' "${ATLAS_TEST_SCHEDULER_OUTPUT:-operations.collect true 300 healthy false -}"
    }

    atlas_module_list() {
      printf '%s\n' "${ATLAS_TEST_MODULES:-notifications
sports}"
    }

    atlas_module_enabled() {
      local module="$1"
      local enabled_modules="${ATLAS_TEST_ENABLED_MODULES-notifications
sports}"

      grep -Fxq -- "$module" <<<"$enabled_modules"
    }

    atlas_command_module() {
      local subcommand="${1:-}"
      local module="${2:-}"

      if [[ "$subcommand" != "verify" ]]; then
        return 1
      fi

      printf '%s\n' "$module module verifier output"

      if [[ "$module" == "${ATLAS_TEST_FAIL_MODULE:-}" ]]; then
        return 1
      fi

      return 0
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
    assert "Runtime Filesystem" in result.stdout
    assert "Infrastructure" in result.stdout
    assert "Compose Services" in result.stdout
    assert "Storage Paths" in result.stdout
    assert "Project Files" in result.stdout
    assert "VPN" in result.stdout
    assert "Specialized Verifiers" in result.stdout
    assert "OK   Ingress verification" in result.stdout
    assert "OK   Scheduler registry readiness" in result.stdout
    assert "OK   notifications module verification" in result.stdout
    assert "OK   sports module verification" in result.stdout
    assert "OK   Docker Engine" in result.stdout
    assert "OK   dozzle running" in result.stdout
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


def test_verify_reports_missing_compose_service(
    tmp_path: Path,
) -> None:
    """A configured service that is not running must fail verification."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_RUNNING_SERVICES"] = "\n".join(
        service
        for service in COMPOSE_SERVICES
        if service != "dozzle"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert "FAIL dozzle running" in result.stdout
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


def test_verify_reports_missing_required_runtime_directory(
    tmp_path: Path,
) -> None:
    """A missing foundational runtime directory must fail verification."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    backup_dir = Path(
        environment["ATLAS_BACKUP_DIR"]
    )

    backup_dir.rmdir()

    result = run_verify(environment)

    assert result.returncode == 1
    assert (
        "FAIL ATLAS_BACKUP_DIR directory present"
        in result.stdout
    )
    assert (
        "FAIL ATLAS_BACKUP_DIR directory writable"
        in result.stdout
    )
    assert "Infrastructure" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_rejects_runtime_path_that_is_not_a_directory(
    tmp_path: Path,
) -> None:
    """A configured runtime path must resolve to a directory."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    runtime_config_dir = Path(
        environment["ATLAS_RUNTIME_CONFIG_DIR"]
    )

    runtime_config_dir.rmdir()
    runtime_config_dir.write_text(
        "not a directory\n",
        encoding="utf-8",
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert (
        "FAIL ATLAS_RUNTIME_CONFIG_DIR directory present"
        in result.stdout
    )
    assert (
        "FAIL ATLAS_RUNTIME_CONFIG_DIR directory writable"
        in result.stdout
    )
    assert "Overall Status: FAIL" in result.stdout


def test_verify_does_not_require_lazy_subsystem_directories(
    tmp_path: Path,
) -> None:
    """Subsystem-owned state directories may be absent before initialization."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    for variable in (
        "ATLAS_USERS_DIR",
        "ATLAS_IDENTITY_DIR",
        "ATLAS_ARI_DIR",
        "ATLAS_ARI_SNAPSHOT_DIR",
        "ATLAS_SCHEDULER_DIR",
    ):
        assert not Path(
            environment[variable]
        ).exists()

    result = run_verify(environment)

    assert result.returncode == 0
    assert "Overall Status: PASS" in result.stdout
    assert (
        "ATLAS_USERS_DIR directory present"
        not in result.stdout
    )
    assert (
        "ATLAS_SCHEDULER_DIR directory present"
        not in result.stdout
    )


def test_verify_reports_compose_discovery_failure(
    tmp_path: Path,
) -> None:
    """A failed Compose model query must fail verification cleanly."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_COMPOSE_CONFIG_STATUS"] = "1"

    result = run_verify(environment)

    assert result.returncode == 1
    assert "FAIL Compose service discovery" in result.stdout
    assert "Compose runtime query" not in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_reports_empty_compose_service_model(
    tmp_path: Path,
) -> None:
    """An empty active Compose model must fail verification."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_COMPOSE_SERVICES"] = ""

    result = run_verify(environment)

    assert result.returncode == 1
    assert "FAIL Compose service discovery" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_checks_newly_discovered_compose_service(
    tmp_path: Path,
) -> None:
    """New active Compose services must be verified without code changes."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_COMPOSE_SERVICES"] = (
        environment["ATLAS_TEST_COMPOSE_SERVICES"]
        + "\nnew-service"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert "FAIL new-service running" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_reports_compose_runtime_query_failure(
    tmp_path: Path,
) -> None:
    """A failed running-service query must fail verification cleanly."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_COMPOSE_PS_STATUS"] = "1"

    result = run_verify(environment)

    assert result.returncode == 1
    assert "OK   Compose service discovery" in result.stdout
    assert "FAIL Compose runtime query" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_reports_ingress_verifier_failure(
    tmp_path: Path,
) -> None:
    """Ingress failure must be aggregated without stopping later checks."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_INGRESS_STATUS"] = "1"
    environment["ATLAS_TEST_INGRESS_OUTPUT"] = (
        "Atlas Ingress Status: FAIL"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert "Atlas Ingress Status: FAIL" in result.stdout
    assert "FAIL Ingress verification" in result.stdout
    assert "OK   Scheduler registry readiness" in result.stdout
    assert "OK   sports module verification" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_reports_scheduler_command_failure(
    tmp_path: Path,
) -> None:
    """A failing Scheduler CLI must fail readiness verification."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_SCHEDULER_STATUS"] = "1"
    environment["ATLAS_TEST_SCHEDULER_OUTPUT"] = (
        "Scheduler registry unavailable"
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert "Scheduler registry unavailable" in result.stdout
    assert "FAIL Scheduler registry readiness" in result.stdout
    assert "OK   notifications module verification" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_rejects_empty_scheduler_registry(
    tmp_path: Path,
) -> None:
    """A successful but empty Scheduler registry is not ready."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_SCHEDULER_OUTPUT"] = (
        "No scheduler tasks registered."
    )

    result = run_verify(environment)

    assert result.returncode == 1
    assert "No scheduler tasks registered." in result.stdout
    assert "FAIL Scheduler registry readiness" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_runs_only_enabled_module_verifiers(
    tmp_path: Path,
) -> None:
    """Disabled modules must not participate in root verification."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_ENABLED_MODULES"] = "sports"

    result = run_verify(environment)

    assert result.returncode == 0
    assert "OK   sports module verification" in result.stdout
    assert "notifications module verifier output" not in result.stdout
    assert (
        "notifications module verification"
        not in result.stdout
    )
    assert "Overall Status: PASS" in result.stdout


def test_verify_aggregates_enabled_module_failure(
    tmp_path: Path,
) -> None:
    """One enabled module failure must not suppress remaining modules."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_FAIL_MODULE"] = "notifications"

    result = run_verify(environment)

    assert result.returncode == 1
    assert "FAIL notifications module verification" in result.stdout
    assert "OK   sports module verification" in result.stdout
    assert "Overall Status: FAIL" in result.stdout


def test_verify_handles_no_enabled_modules(
    tmp_path: Path,
) -> None:
    """A system with no enabled optional modules remains valid."""

    environment = dict(
        prepare_runtime(tmp_path)
    )

    environment["ATLAS_TEST_ENABLED_MODULES"] = ""

    result = run_verify(environment)

    assert result.returncode == 0
    assert (
        "OK   No enabled modules require verification"
        in result.stdout
    )
    assert "module verifier output" not in result.stdout
    assert "Overall Status: PASS" in result.stdout
