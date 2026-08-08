from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPDATE = PROJECT_ROOT / "scripts" / "commands" / "update.sh"
STANDALONE = PROJECT_ROOT / "scripts" / "update.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def prepare_runtime(tmp_path: Path, *, branch: str = "main") -> dict[str, str]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    bin_dir = tmp_path / "bin"
    events = tmp_path / "events"

    project.mkdir()
    runtime.mkdir()
    bin_dir.mkdir()
    (project / "scripts").mkdir()
    (project / "stack").mkdir()
    (project / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (project / "stack" / "ingress.yml").write_text("services: {}\n", encoding="utf-8")

    write_executable(
        project / "scripts" / "verify-ingress.sh",
        """
        #!/usr/bin/env bash
        echo ingress-verify >> "$ATLAS_TEST_EVENTS"
        exit "${ATLAS_TEST_INGRESS_STATUS:-0}"
        """,
    )

    write_executable(
        bin_dir / "git",
        f"""
        #!/usr/bin/env bash
        set -euo pipefail
        args=" $* "
        if [[ "$args" == *" branch --show-current "* ]]; then
          printf '%s\\n' {branch!r}
        elif [[ "$args" == *" status --porcelain "* ]]; then
          printf '%s' "${{ATLAS_TEST_GIT_STATUS:-}}"
        elif [[ "$args" == *" rev-parse origin/main "* ]]; then
          printf '%s\\n' "${{ATLAS_TEST_ORIGIN_MAIN:-abc123}}"
        elif [[ "$args" == *" rev-parse HEAD "* ]]; then
          printf '%s\\n' "${{ATLAS_TEST_HEAD:-abc123}}"
        else
          exit 1
        fi
        """,
    )

    write_executable(
        bin_dir / "docker",
        """
        #!/usr/bin/env bash
        set -euo pipefail
        echo "docker $*" >> "$ATLAS_TEST_EVENTS"
        exit "${ATLAS_TEST_DOCKER_STATUS:-0}"
        """,
    )

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment['PATH']}",
            "ATLAS_PROJECT_DIR": str(project),
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_TEST_EVENTS": str(events),
            "ATLAS_TEST_UPDATE": str(UPDATE),
        }
    )
    return environment


def run_update(
    environment: dict[str, str],
    scope: str = "core",
) -> subprocess.CompletedProcess[str]:
    harness = r"""
    set -u
    source "$ATLAS_TEST_UPDATE"

    atlas_print_header() { :; }
    atlas_command_doctor() {
      echo doctor >> "$ATLAS_TEST_EVENTS"
      return "${ATLAS_TEST_DOCTOR_STATUS:-0}"
    }
    atlas_command_verify() {
      echo verify >> "$ATLAS_TEST_EVENTS"
      return "${ATLAS_TEST_VERIFY_STATUS:-0}"
    }
    atlas_command_maintenance() {
      echo "maintenance:$1" >> "$ATLAS_TEST_EVENTS"
      return "${ATLAS_TEST_MAINTENANCE_STATUS:-0}"
    }
    atlas_command_backup() {
      echo backup >> "$ATLAS_TEST_EVENTS"
      return "${ATLAS_TEST_BACKUP_STATUS:-0}"
    }

    atlas_command_update "$1"
    """
    return subprocess.run(
        ["bash", "-c", textwrap.dedent(harness), "atlas-update-test", scope],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def event_lines(environment: dict[str, str]) -> list[str]:
    path = Path(environment["ATLAS_TEST_EVENTS"])
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def lock_path(environment: dict[str, str]) -> Path:
    return Path(environment["ATLAS_RUNTIME_CONFIG_DIR"]) / "deployments" / "update.lock"


def test_feature_branch_is_rejected_before_runtime_mutation(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path, branch="feature/example")

    result = run_update(environment)

    assert result.returncode != 0
    assert event_lines(environment) == []
    assert not lock_path(environment).exists()
    assert "require main" in result.stderr


def test_dirty_main_is_rejected_before_runtime_mutation(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_GIT_STATUS"] = " M file\n"

    result = run_update(environment)

    assert result.returncode != 0
    assert event_lines(environment) == []
    assert not lock_path(environment).exists()


def test_diverged_main_is_rejected_before_runtime_mutation(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_ORIGIN_MAIN"] = "different"

    result = run_update(environment)

    assert result.returncode != 0
    assert event_lines(environment) == []
    assert not lock_path(environment).exists()


def test_core_update_orders_backup_before_apply_and_reopens_on_success(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "core")

    assert result.returncode == 0, result.stderr
    events = event_lines(environment)
    assert events[0:3] == ["doctor", "maintenance:enable", "backup"]
    assert events[3].startswith("docker compose")
    assert events[4].startswith("docker compose")
    assert events[-3:] == ["doctor", "verify", "maintenance:disable"]
    assert not lock_path(environment).exists()
    assert not any("image prune" in event for event in events)


def test_backup_failure_keeps_maintenance_and_lock(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_BACKUP_STATUS"] = "1"

    result = run_update(environment)

    assert result.returncode != 0
    assert event_lines(environment) == ["doctor", "maintenance:enable", "backup"]
    assert lock_path(environment).is_dir()
    assert "Maintenance mode remains enabled" in result.stderr


def test_post_verify_failure_keeps_maintenance_and_lock(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_VERIFY_STATUS"] = "1"

    result = run_update(environment)

    assert result.returncode != 0
    events = event_lines(environment)
    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()


def test_ingress_scope_builds_ingress_and_runs_ingress_verifier(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr
    events = event_lines(environment)
    assert any("pull caddy" in event for event in events)
    assert any("build portal api" in event for event in events)
    assert any("up -d" in event for event in events)
    assert "ingress-verify" in events
    assert events[-1] == "maintenance:disable"


def test_unknown_scope_is_rejected_before_runtime_mutation(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "everything")

    assert result.returncode == 2
    assert event_lines(environment) == []
    assert not lock_path(environment).exists()


def test_existing_deployment_lock_fails_closed(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)
    lock_path(environment).mkdir(parents=True)

    result = run_update(environment)

    assert result.returncode != 0
    assert event_lines(environment) == []
    assert lock_path(environment).is_dir()


def test_standalone_update_delegates_to_canonical_atlas_cli() -> None:
    content = STANDALONE.read_text(encoding="utf-8")

    assert 'exec "$project_dir/scripts/atlas" update "$@"' in content
    assert "docker compose" not in content
    assert "docker image prune" not in content
