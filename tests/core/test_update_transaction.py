from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPDATE = PROJECT_ROOT / "scripts" / "commands" / "update.sh"
DEPLOYMENT = PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"
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

        args=" $* "

        if [[ "$args" == *" compose "* && "$args" == *" config --images "* ]]; then
          if [[ "$args" == *" stack/ingress.yml "* ]]; then
            printf '%s\\n' \
              'atlas-api:test' \
              'atlas-portal:test' \
              'caddy:test'
          else
            printf '%s\\n' \
              'core:test' \
              'dependency:test'
          fi
          exit 0
        fi

        if [[ "$args" == *" image inspect "* ]]; then
          image="${@: -1}"

          if [[ -n "${ATLAS_TEST_MISSING_IMAGE:-}" ]] &&
             [[ "$image" == "$ATLAS_TEST_MISSING_IMAGE" ]]
          then
            exit 1
          fi

          exit 0
        fi

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
    deployment_root = runtime / "deployments"
    baseline = deployment_root / "records" / "baseline-test"
    baseline.mkdir(parents=True)
    (deployment_root / "current").write_text("baseline-test\n", encoding="utf-8")
    (baseline / "status").write_text("verified\n", encoding="utf-8")
    (baseline / "metadata").write_text(
        "type=baseline\ndeployment_id=baseline-test\n"
        "source_commit=abc123\ncore_commit=abc123\n"
        "ingress_commit=abc123\nscope=all\nmigration=none\n",
        encoding="utf-8",
    )
    (baseline / "images.tsv").write_text(
        "core|docker-compose.yml|atlas|core|core-container|core:test|sha256:core\n"
        "ingress|stack/ingress.yml|atlas-ingress|caddy|atlas-caddy|caddy:test|sha256:caddy\n",
        encoding="utf-8",
    )
    (baseline / "core-source.tar.gz").write_bytes(b"archive")
    (baseline / "ingress-source.tar.gz").write_bytes(b"archive")
    return environment


def run_update(
    environment: dict[str, str],
    scope: str = "core",
) -> subprocess.CompletedProcess[str]:
    harness = r"""
    set -u
    source "$ATLAS_TEST_DEPLOYMENT"
    source "$ATLAS_TEST_UPDATE"

    atlas_print_header() { :; }
    atlas_command_doctor() {
      echo doctor >> "$ATLAS_TEST_EVENTS"
      return "${ATLAS_TEST_DOCTOR_STATUS:-0}"
    }
    atlas_command_verify() {
      echo verify >> "$ATLAS_TEST_EVENTS"
      if [[ "${ATLAS_TEST_VERIFY_FAIL_AFTER_DISABLE:-0}" == "1" ]] &&
        grep -Fxq 'maintenance:disable' "$ATLAS_TEST_EVENTS"
      then
        return 1
      fi
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

    atlas_deployment_archive_source() {
      cp "$ATLAS_TEST_ARCHIVE" "$2"
    }
    atlas_deployment_preserve_rollback_images() {
      echo preserve-rollback-images >> "$ATLAS_TEST_EVENTS"
      return 0
    }
    atlas_deployment_verify_runtime() { return 0; }
    atlas_deployment_capture_images() {
      cp "$ATLAS_TEST_IMAGES" "$1/images.tsv"
    }
    atlas_deployment_record_backup() {
      printf "%s\n" "$2" > "$(atlas_deployment_record_dir "$1")/backup_file"
    }
    atlas_update_latest_backup() { printf "%s\n" "$ATLAS_TEST_BACKUP_FILE"; }
    atlas_command_update "$1" --migration none
    """
    baseline = Path(environment["ATLAS_RUNTIME_CONFIG_DIR"]) / "deployments" / "records" / "baseline-test"
    environment = dict(environment)
    environment["ATLAS_TEST_DEPLOYMENT"] = str(DEPLOYMENT)
    environment["ATLAS_TEST_ARCHIVE"] = str(baseline / "core-source.tar.gz")
    environment["ATLAS_TEST_IMAGES"] = str(baseline / "images.tsv")
    backup = Path(environment["ATLAS_RUNTIME_CONFIG_DIR"]) / "test-backup.tar.gz"
    backup.write_bytes(b"backup")
    environment["ATLAS_TEST_BACKUP_FILE"] = str(backup)
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


def test_core_update_preflights_artifacts_before_maintenance_and_reopens_on_success(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "core")

    assert result.returncode == 0, result.stderr
    events = event_lines(environment)

    preserve = events.index("preserve-rollback-images")
    doctor = events.index("doctor")
    pull = next(
        index
        for index, event in enumerate(events)
        if "docker compose" in event and event.endswith(" pull")
    )
    render = next(
        index
        for index, event in enumerate(events)
        if "docker compose" in event and "config --images" in event
    )
    inspections = [
        index
        for index, event in enumerate(events)
        if event.startswith("docker image inspect ")
    ]
    maintenance = events.index("maintenance:enable")
    backup = events.index("backup")
    apply = next(
        index
        for index, event in enumerate(events)
        if "docker compose" in event
        and "up -d" in event
        and "--no-build" in event
        and "--pull never" in event
    )

    assert inspections
    assert preserve < doctor < pull < render
    assert all(render < inspection < maintenance for inspection in inspections)
    assert maintenance < backup < apply

    assert events[-3:] == ["maintenance:disable", "doctor", "verify"]
    assert not lock_path(environment).exists()
    assert not any("image prune" in event for event in events)


def test_backup_failure_keeps_maintenance_and_lock(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_BACKUP_STATUS"] = "1"

    result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    assert events[0] == "preserve-rollback-images"
    assert events[1] == "doctor"
    assert any(event.endswith(" pull") for event in events)
    assert any("config --images" in event for event in events)
    assert any(event.startswith("docker image inspect ") for event in events)

    maintenance = events.index("maintenance:enable")
    backup = events.index("backup")

    assert maintenance < backup
    assert backup == len(events) - 1
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


def test_ingress_scope_prepares_builds_and_applies_without_network_in_maintenance(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    pull = next(
        index for index, event in enumerate(events) if "pull caddy" in event
    )
    build = next(
        index for index, event in enumerate(events) if "build portal api" in event
    )
    render = next(
        index for index, event in enumerate(events) if "config --images" in event
    )
    maintenance = events.index("maintenance:enable")
    apply = next(
        index
        for index, event in enumerate(events)
        if "up -d" in event
        and "--no-build" in event
        and "--pull never" in event
    )

    assert pull < build < render < maintenance < apply

    assert events.count("ingress-verify") == 2

    disable = events.index("maintenance:disable")

    assert events.index("ingress-verify") < disable
    assert events.index("ingress-verify", disable + 1) > disable


def test_update_preserves_rollback_images_before_runtime_mutation(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr
    events = event_lines(environment)
    preserve = events.index("preserve-rollback-images")
    first_compose = next(
        index for index, event in enumerate(events) if event.startswith("docker compose")
    )
    assert preserve < first_compose


def test_failed_public_reopen_reenables_maintenance_and_keeps_lock(tmp_path: Path) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_VERIFY_STATUS"] = "0"
    environment["ATLAS_TEST_VERIFY_FAIL_AFTER_DISABLE"] = "1"

    result = run_update(environment, "ingress")

    assert result.returncode != 0
    events = event_lines(environment)
    disable = events.index("maintenance:disable")
    assert "verify" in events[disable + 1 :]
    assert "maintenance:enable" in events[disable + 1 :]
    assert lock_path(environment).is_dir()
    current = (
        Path(environment["ATLAS_RUNTIME_CONFIG_DIR"]) / "deployments" / "current"
    ).read_text(encoding="utf-8")
    assert current == "baseline-test\n"
    assert "public post-maintenance verification failed" in result.stderr


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


def test_missing_target_image_aborts_before_maintenance_or_apply(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_MISSING_IMAGE"] = "dependency:test"

    result = run_update(environment, "core")

    assert result.returncode != 0

    events = event_lines(environment)

    assert events[0] == "preserve-rollback-images"
    assert events[1] == "doctor"
    assert any(event.endswith(" pull") for event in events)
    assert any("config --images" in event for event in events)
    assert "docker image inspect dependency:test" in events

    assert "maintenance:enable" not in events
    assert "backup" not in events
    assert not any(
        "up -d" in event
        for event in events
        if event.startswith("docker compose")
    )

    assert not lock_path(environment).exists()
    assert (
        "target image completeness verification failed before maintenance"
        in result.stderr
    )
