from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import tarfile
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPDATE = PROJECT_ROOT / "scripts" / "commands" / "update.sh"
DEPLOYMENT = PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"
STANDALONE = PROJECT_ROOT / "scripts" / "update.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def write_runtime_source_archive(path: Path) -> None:
    members = {
        "VERSION": (b"1.0.0-rc.1\n", 0o644),
        "scripts/atlas": (
            b"#!/usr/bin/env bash\nexit 0\n",
            0o755,
        ),
        "scripts/commands/scheduler.sh": (
            b"#!/usr/bin/env bash\n",
            0o644,
        ),
        "atlas/scheduler.py": (
            b"# scheduler fixture\n",
            0o644,
        ),
        "atlas/scheduler_cli.py": (
            b"# scheduler CLI fixture\n",
            0o644,
        ),
    }

    with tarfile.open(path, "w:gz") as archive:
        for name, (payload, mode) in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = mode
            info.mtime = 0

            archive.addfile(
                info,
                io.BytesIO(payload),
            )


def prepare_runtime(tmp_path: Path, *, branch: str = "main") -> dict[str, str]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    bin_dir = tmp_path / "bin"
    events = tmp_path / "events"

    project.mkdir()
    runtime.mkdir()
    bin_dir.mkdir()
    (project / "scripts").mkdir()
    (project / "scripts" / "lib").mkdir()
    (project / "stack").mkdir()
    (project / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (project / "stack" / "ingress.yml").write_text("services: {}\n", encoding="utf-8")

    tracked_build_files = (
        project / "apps" / "api" / "pyproject.toml",
        project / "apps" / "api" / "atlas_api" / "main.py",
        project / "atlas" / "example.py",
        project / "apps" / "portal" / "package.json",
    )

    for tracked in tracked_build_files:
        tracked.parent.mkdir(parents=True, exist_ok=True)
        tracked.write_text("fixture\n", encoding="utf-8")
        tracked.chmod(0o644)

    write_executable(
        project / "scripts" / "atlas-dashboard-runtime.sh",
        """
        #!/usr/bin/env bash
        set -euo pipefail
        echo "dashboard-runtime:${1:-}" >> "$ATLAS_TEST_EVENTS"
        exit "${ATLAS_TEST_DASHBOARD_RUNTIME_STATUS:-0}"
        """,
    )

    write_executable(
        project / "scripts" / "verify-ingress.sh",
        """
        #!/usr/bin/env bash
        echo ingress-verify >> "$ATLAS_TEST_EVENTS"
        exit "${ATLAS_TEST_INGRESS_STATUS:-0}"
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "audit-runtime.sh",
        """
        #!/usr/bin/env bash
        atlas_audit_runtime_provision() {
          echo audit-runtime:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_AUDIT_RUNTIME_STATUS:-0}"
        }
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "identity-writer-runtime.sh",
        """
        #!/usr/bin/env bash
        atlas_identity_writer_runtime_provision() {
          echo identity-writer-runtime:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_IDENTITY_WRITER_RUNTIME_STATUS:-0}"
        }
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "favorites-runtime.sh",
        """
        #!/usr/bin/env bash
        atlas_favorites_runtime_provision() {
          echo favorites-runtime:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_FAVORITES_RUNTIME_STATUS:-0}"
        }
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "dislikes-runtime.sh",
        """
        #!/usr/bin/env bash
        atlas_dislikes_runtime_provision() {
          echo dislikes-runtime:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_DISLIKES_RUNTIME_STATUS:-0}"
        }
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "password-recovery-runtime.sh",
        """
        #!/usr/bin/env bash
        atlas_password_recovery_runtime_provision() {
          echo password-recovery-runtime:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_PASSWORD_RECOVERY_RUNTIME_STATUS:-0}"
        }
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "sports-runtime.sh",
        """
        #!/usr/bin/env bash
        atlas_sports_runtime_provision() {
          echo sports-runtime:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_SPORTS_RUNTIME_STATUS:-0}"
        }
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "sports-live-source-bootstrap.sh",
        """
        #!/usr/bin/env bash
        atlas_sports_live_source_bootstrap_provision() {
          echo sports-live-source-bootstrap:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_SPORTS_LIVE_SOURCE_BOOTSTRAP_STATUS:-0}"
        }
        """,
    )

    write_executable(
        project / "scripts" / "lib" / "sports-dispatcharr-binding-bootstrap.sh",
        """
        #!/usr/bin/env bash
        atlas_sports_dispatcharr_binding_bootstrap_provision() {
          echo sports-dispatcharr-binding-bootstrap:provision >> "$ATLAS_TEST_EVENTS"
          return "${ATLAS_TEST_SPORTS_DISPATCHARR_BINDING_BOOTSTRAP_STATUS:-0}"
        }
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
        elif [[ "$args" == *" ls-files -z "* ]]; then
          printf '%s\\0' \
            'apps/api/pyproject.toml' \
            'apps/api/atlas_api/main.py' \
            'atlas/example.py' \
            'apps/portal/package.json'
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
    write_runtime_source_archive(
        baseline / "core-source.tar.gz"
    )
    write_runtime_source_archive(
        baseline / "ingress-source.tar.gz"
    )
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
      local call=1
      local count_file="${ATLAS_TEST_DOCTOR_COUNT_FILE:-}"

      if [[ -n "$count_file" ]]; then
        if [[ -f "$count_file" ]]; then
          call="$(( $(cat "$count_file") + 1 ))"
        fi
        printf '%s\n' "$call" > "$count_file"
      fi

      echo doctor >> "$ATLAS_TEST_EVENTS"

      case ",${ATLAS_TEST_DOCTOR_FAIL_CALLS:-}," in
        *",$call,"*)
          return 1
          ;;
      esac

      return "${ATLAS_TEST_DOCTOR_STATUS:-0}"
    }

    atlas_health_python() {
      local payload="${ATLAS_TEST_HEALTH_JSON:-}"

      echo health-json >> "$ATLAS_TEST_EVENTS"

      if [[ -z "$payload" ]]; then
        payload='{"status":"healthy","score":100,"checks":[]}'
      fi

      printf '%s\n' "$payload"
      return "${ATLAS_TEST_HEALTH_STATUS:-0}"
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

    atlas_update_ingress_container_state() {
      local container="$1"
      local status="running"
      local health="healthy"

      if [[ -n "${ATLAS_TEST_READINESS_FAIL_CONTAINER:-}" ]] &&
         [[ "$container" == "$ATLAS_TEST_READINESS_FAIL_CONTAINER" ]]
      then
        status="${ATLAS_TEST_READINESS_FAIL_STATUS:-running}"
        health="${ATLAS_TEST_READINESS_FAIL_HEALTH:-healthy}"
      fi

      if [[ "$container" == "atlas-caddy" ]] &&
         [[ "${ATLAS_TEST_CADDY_STARTING_ONCE:-0}" == "1" ]]
      then
        if [[ ! -e "$ATLAS_TEST_CADDY_READY_MARKER" ]]; then
          touch "$ATLAS_TEST_CADDY_READY_MARKER"
          health="starting"
        fi
      fi

      if [[ "$container" == "atlas-caddy" ]] &&
         [[ "${ATLAS_TEST_CADDY_ALWAYS_STARTING:-0}" == "1" ]]
      then
        health="starting"
      fi

      echo "readiness-probe:$container:$status:$health" \
        >> "$ATLAS_TEST_EVENTS"

      printf '%s|%s\n' "$status" "$health"
    }

    atlas_update_readiness_sleep() {
      echo "readiness-sleep:${1:-}" >> "$ATLAS_TEST_EVENTS"
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
      printf 'capture-images:%s\n' "$1" >> "$ATLAS_TEST_EVENTS"
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


def test_ingress_unreadable_tracked_file_fails_before_network_or_maintenance(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    project = Path(environment["ATLAS_PROJECT_DIR"])
    blocked = project / "atlas" / "example.py"
    blocked.chmod(0o600)

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    events = event_lines(environment)

    assert events == [
        "preserve-rollback-images",
        "doctor",
    ]
    assert "maintenance:enable" not in events
    assert "backup" not in events
    assert not any(
        event.startswith("docker compose")
        for event in events
    )
    assert not lock_path(environment).exists()

    assert (
        "tracked build-context file is not readable by "
        "container runtime user: atlas/example.py (mode=600)"
        in result.stderr
    )
    assert (
        "ingress build-context permission validation failed"
        in result.stderr
    )


def test_ingress_untraversable_tracked_directory_fails_before_network_or_maintenance(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    project = Path(environment["ATLAS_PROJECT_DIR"])
    blocked = project / "atlas"
    blocked.chmod(0o700)

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    events = event_lines(environment)

    assert events == [
        "preserve-rollback-images",
        "doctor",
    ]
    assert "maintenance:enable" not in events
    assert "backup" not in events
    assert not any(
        event.startswith("docker compose")
        for event in events
    )
    assert not lock_path(environment).exists()

    assert (
        "tracked build-context directory is not traversable by "
        "container runtime user: atlas (mode=700)"
        in result.stderr
    )
    assert (
        "ingress build-context permission validation failed"
        in result.stderr
    )


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
        index for index, event in enumerate(events) if "build portal api sports-writer" in event
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


def test_dashboard_runtime_publication_failure_keeps_maintenance_and_lock(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_DASHBOARD_RUNTIME_STATUS"] = "1"

    result = run_update(environment, "ingress")

    assert result.returncode != 0
    events = event_lines(environment)

    assert "dashboard-runtime:publish-all" in events
    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert "Dashboard runtime publication failed." in result.stderr


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



def deployment_record(
    environment: dict[str, str],
) -> Path:
    captures = [
        event
        for event in event_lines(environment)
        if event.startswith("capture-images:")
    ]

    assert len(captures) == 1

    record = Path(
        captures[0].split(":", 1)[1]
    )

    expected_records = (
        Path(environment["ATLAS_RUNTIME_CONFIG_DIR"])
        / "deployments"
        / "records"
    )

    assert record.parent == expected_records
    assert record.name.startswith("update-")

    return record


def test_update_captures_applied_target_images_before_private_post_verify(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment)

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    apply = next(
        index
        for index, event in enumerate(events)
        if event.startswith("docker compose ")
        and " up " in f" {event} "
        and "--no-build" in event
        and "--pull never" in event
    )

    capture = next(
        index
        for index, event in enumerate(events)
        if event.startswith("capture-images:")
    )

    private_doctor = events.index("doctor", apply + 1)

    assert apply < capture < private_doctor

    images = deployment_record(environment) / "images.tsv"
    assert images.is_file()
    baseline_images = (
        Path(environment["ATLAS_RUNTIME_CONFIG_DIR"])
        / "deployments"
        / "records"
        / "baseline-test"
        / "images.tsv"
    )

    assert images.read_bytes() == baseline_images.read_bytes()


def test_private_post_apply_failure_preserves_target_image_attestation(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    # Call 1 is the pre-update doctor.
    # Call 2 is the first private post-apply doctor.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        '{"schema_version":1,"status":"critical","score":90,'
        '"checks":['
        '{"category":"services",'
        '"name":"jellyfin",'
        '"status":"critical",'
        '"message":"jellyfin container is not running",'
        '"details":{"returncode":1}}'
        ']}'
    )

    result = run_update(environment)

    assert result.returncode != 0

    record = deployment_record(environment)
    images = record / "images.tsv"

    # Failed-after-apply evidence must already exist even though
    # final baseline completion was never reached.
    assert images.is_file()
    baseline_images = (
        Path(environment["ATLAS_RUNTIME_CONFIG_DIR"])
        / "deployments"
        / "records"
        / "baseline-test"
        / "images.tsv"
    )

    assert images.read_bytes() == baseline_images.read_bytes()

    events = event_lines(environment)

    apply = next(
        index
        for index, event in enumerate(events)
        if event.startswith("docker compose ")
        and " up " in f" {event} "
        and "--no-build" in event
        and "--pull never" in event
    )

    capture = next(
        index
        for index, event in enumerate(events)
        if event.startswith("capture-images:")
    )

    failed_doctor = events.index("doctor", apply + 1)

    assert apply < capture < failed_doctor
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()


def readiness_events(environment: dict[str, str]) -> list[str]:
    return [
        event
        for event in event_lines(environment)
        if event.startswith("readiness-")
    ]


def test_readiness_already_healthy_succeeds_immediately(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr

    events = readiness_events(environment)

    assert events == [
        "readiness-probe:atlas-api:running:healthy",
        "readiness-probe:atlas-portal:running:healthy",
        "readiness-probe:atlas-caddy:running:healthy",
        "readiness-probe:atlas-sports-writer:running:healthy",
        "readiness-probe:atlas-jellyfin-writer:running:healthy",
        "readiness-probe:atlas-api:running:healthy",
        "readiness-probe:atlas-portal:running:healthy",
        "readiness-probe:atlas-caddy:running:healthy",
        "readiness-probe:atlas-sports-writer:running:healthy",
        "readiness-probe:atlas-jellyfin-writer:running:healthy",
    ]

    assert not any(
        event.startswith("readiness-sleep:")
        for event in events
    )


def test_readiness_starting_then_healthy_retries_and_succeeds(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_STARTING_ONCE"] = "1"
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr

    events = readiness_events(environment)

    first_caddy = events.index(
        "readiness-probe:atlas-caddy:running:starting"
    )
    sleep = next(
        index
        for index, event in enumerate(events)
        if event.startswith("readiness-sleep:")
    )
    healthy_caddy = events.index(
        "readiness-probe:atlas-caddy:running:healthy",
        sleep + 1,
    )

    assert first_caddy < sleep < healthy_caddy


def test_readiness_unhealthy_fails_immediately(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )
    environment["ATLAS_TEST_READINESS_FAIL_CONTAINER"] = "atlas-caddy"
    environment["ATLAS_TEST_READINESS_FAIL_HEALTH"] = "unhealthy"

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    events = readiness_events(environment)

    assert (
        "readiness-probe:atlas-caddy:running:unhealthy"
        in events
    )

    assert not any(
        event.startswith("readiness-sleep:")
        for event in events
    )

    assert "maintenance:enable" in event_lines(environment)
    assert "maintenance:disable" not in event_lines(environment)
    assert lock_path(environment).is_dir()

    assert "ingress readiness failed" in result.stderr.lower()


def test_readiness_non_running_container_fails_immediately(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )
    environment["ATLAS_TEST_READINESS_FAIL_CONTAINER"] = "atlas-portal"
    environment["ATLAS_TEST_READINESS_FAIL_STATUS"] = "exited"
    environment["ATLAS_TEST_READINESS_FAIL_HEALTH"] = "healthy"

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    assert (
        "readiness-probe:atlas-portal:exited:healthy"
        in readiness_events(environment)
    )

    assert "maintenance:disable" not in event_lines(environment)
    assert lock_path(environment).is_dir()


def test_readiness_missing_health_contract_fails_immediately(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )
    environment["ATLAS_TEST_READINESS_FAIL_CONTAINER"] = "atlas-api"
    environment["ATLAS_TEST_READINESS_FAIL_HEALTH"] = "missing"

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    assert (
        "readiness-probe:atlas-api:running:missing"
        in readiness_events(environment)
    )

    assert "maintenance:disable" not in event_lines(environment)
    assert lock_path(environment).is_dir()


def test_readiness_starting_timeout_fails_closed(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_ALWAYS_STARTING"] = "1"
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )
    environment["ATLAS_UPDATE_READINESS_ATTEMPTS"] = "3"
    environment["ATLAS_UPDATE_READINESS_INTERVAL_SECONDS"] = "0"

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    events = readiness_events(environment)

    caddy_starting = [
        event
        for event in events
        if event == "readiness-probe:atlas-caddy:running:starting"
    ]

    assert len(caddy_starting) == 3
    assert "maintenance:disable" not in event_lines(environment)
    assert lock_path(environment).is_dir()

    assert "readiness timed out" in result.stderr.lower()


def test_core_scope_does_not_invoke_ingress_readiness(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )

    result = run_update(environment, "core")

    assert result.returncode == 0, result.stderr
    assert readiness_events(environment) == []


def test_ingress_readiness_occurs_after_apply_before_verification(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    apply = next(
        index
        for index, event in enumerate(events)
        if event.startswith("docker compose")
        and "up -d" in event
        and "--no-build" in event
        and "--pull never" in event
    )

    readiness = events.index(
        "readiness-probe:atlas-api:running:healthy"
    )

    doctor_after_apply = events.index("doctor", apply + 1)

    assert apply < readiness < doctor_after_apply


def test_readiness_failure_preserves_maintenance_and_lock(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )
    environment["ATLAS_TEST_READINESS_FAIL_CONTAINER"] = "atlas-caddy"
    environment["ATLAS_TEST_READINESS_FAIL_HEALTH"] = "unhealthy"

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    events = event_lines(environment)

    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()
    assert "Recovery command: atlas deployment rollback" in result.stderr


def test_readiness_waiter_is_inspection_only() -> None:
    content = UPDATE.read_text(encoding="utf-8")

    assert "atlas_update_wait_for_ingress_readiness() {" in content

    section = content.split(
        "atlas_update_wait_for_ingress_readiness() {",
        1,
    )[1].split(
        "atlas_update_core_apply() {",
        1,
    )[0]

    assert "docker inspect" in section

    forbidden = (
        "docker restart",
        "docker stop",
        "docker start",
        "docker compose",
        " up -d",
        "docker pull",
        "docker build",
        "maintenance",
        "deployment_set_status",
        "release_lock",
    )

    for item in forbidden:
        assert item not in section


def test_identity_writer_runtime_provisioning_failure_aborts_before_ingress_apply(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_IDENTITY_WRITER_RUNTIME_STATUS"] = "1"

    result = run_update(environment, "ingress")

    assert result.returncode != 0
    assert "identity writer runtime provisioning failed" in result.stderr

    events = event_lines(environment)

    assert "audit-runtime:provision" in events
    assert "identity-writer-runtime:provision" in events

    identity_provision = events.index(
        "identity-writer-runtime:provision"
    )

    compose_up_events = [
        event
        for event in events
        if event.startswith("docker compose ")
        and " up " in f" {event} "
    ]

    assert compose_up_events == []
    assert "maintenance:disable" not in events

    audit_provision = events.index("audit-runtime:provision")
    assert audit_provision < identity_provision



def test_sports_writer_unhealthy_blocks_ingress_verification(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )
    environment["ATLAS_TEST_READINESS_FAIL_CONTAINER"] = (
        "atlas-sports-writer"
    )
    environment["ATLAS_TEST_READINESS_FAIL_HEALTH"] = "unhealthy"

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    events = readiness_events(environment)

    assert (
        "readiness-probe:atlas-sports-writer:running:unhealthy"
        in events
    )
    assert "maintenance:disable" not in event_lines(environment)
    assert lock_path(environment).is_dir()


def test_sports_writer_not_running_blocks_ingress_verification(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_CADDY_READY_MARKER"] = str(
        tmp_path / "caddy-ready"
    )
    environment["ATLAS_TEST_READINESS_FAIL_CONTAINER"] = (
        "atlas-sports-writer"
    )
    environment["ATLAS_TEST_READINESS_FAIL_STATUS"] = "exited"

    result = run_update(environment, "ingress")

    assert result.returncode != 0

    events = readiness_events(environment)

    assert (
        "readiness-probe:atlas-sports-writer:exited:healthy"
        in events
    )
    assert "maintenance:disable" not in event_lines(environment)
    assert lock_path(environment).is_dir()



def test_sports_runtime_provisioning_failure_aborts_before_ingress_apply(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_SPORTS_RUNTIME_STATUS"] = "1"

    result = run_update(environment, "ingress")

    assert result.returncode != 0
    assert "Sports runtime provisioning failed" in result.stderr

    events = event_lines(environment)

    expected_apply_provisioners = (
        "audit-runtime:provision",
        "identity-writer-runtime:provision",
        "favorites-runtime:provision",
        "dislikes-runtime:provision",
        "password-recovery-runtime:provision",
        "sports-runtime:provision",
    )

    for event in expected_apply_provisioners:
        assert event in events

    assert events.count("dislikes-runtime:provision") == 2

    audit_position = events.index("audit-runtime:provision")

    positions = [
        (
            events.index(event, audit_position)
            if event == "dislikes-runtime:provision"
            else events.index(event)
        )
        for event in expected_apply_provisioners
    ]

    assert positions == sorted(positions)

    compose_up_events = [
        event
        for event in events
        if event.startswith("docker compose ")
        and " up " in f" {event} "
    ]

    assert compose_up_events == []
    assert "maintenance:disable" not in events



def test_sports_live_source_bootstrap_failure_aborts_before_maintenance(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_SPORTS_LIVE_SOURCE_BOOTSTRAP_STATUS"] = "1"

    result = run_update(environment, "ingress")

    assert result.returncode != 0
    assert (
        "Sports live-source bootstrap failed before maintenance"
        in result.stderr
    )

    events = event_lines(environment)

    assert "sports-live-source-bootstrap:provision" in events
    assert "maintenance:enable" not in events
    assert "backup" not in events

    assert not lock_path(environment).exists()


def test_ingress_live_source_bootstrap_precedes_maintenance_and_backup(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    bootstrap = events.index(
        "sports-live-source-bootstrap:provision"
    )
    maintenance = events.index("maintenance:enable")
    backup = events.index("backup")

    assert bootstrap < maintenance < backup


def test_core_update_does_not_run_sports_live_source_bootstrap(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "core")

    assert result.returncode == 0, result.stderr

    assert (
        "sports-live-source-bootstrap:provision"
        not in event_lines(environment)
    )


def test_sports_dispatcharr_binding_bootstrap_failure_aborts_before_maintenance(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment[
        "ATLAS_TEST_SPORTS_DISPATCHARR_BINDING_BOOTSTRAP_STATUS"
    ] = "1"

    result = run_update(environment, "ingress")

    assert result.returncode != 0
    assert (
        "Sports Dispatcharr binding bootstrap failed before maintenance"
        in result.stderr
    )

    events = event_lines(environment)

    assert "sports-live-source-bootstrap:provision" in events
    assert "sports-dispatcharr-binding-bootstrap:provision" in events
    assert "maintenance:enable" not in events
    assert "backup" not in events
    assert not lock_path(environment).exists()


def test_ingress_dispatcharr_binding_bootstrap_precedes_maintenance_and_backup(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    live_source = events.index(
        "sports-live-source-bootstrap:provision"
    )
    binding = events.index(
        "sports-dispatcharr-binding-bootstrap:provision"
    )
    maintenance = events.index("maintenance:enable")
    backup = events.index("backup")

    assert live_source < binding < maintenance < backup


def test_core_update_does_not_run_sports_dispatcharr_binding_bootstrap(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "core")

    assert result.returncode == 0, result.stderr

    assert (
        "sports-dispatcharr-binding-bootstrap:provision"
        not in event_lines(environment)
    )



def test_dislikes_prebackup_bootstrap_failure_aborts_before_maintenance(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)
    environment["ATLAS_TEST_DISLIKES_RUNTIME_STATUS"] = "1"

    result = run_update(environment, "ingress")

    assert result.returncode != 0
    assert (
        "Dislikes runtime bootstrap failed before maintenance"
        in result.stderr
    )

    events = event_lines(environment)

    assert events.count("dislikes-runtime:provision") == 1
    assert "maintenance:enable" not in events
    assert "backup" not in events
    assert not lock_path(environment).exists()


def test_ingress_dislikes_prebackup_bootstrap_precedes_maintenance_and_backup(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "ingress")

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    dislikes_positions = [
        index
        for index, event in enumerate(events)
        if event == "dislikes-runtime:provision"
    ]

    assert len(dislikes_positions) == 2

    bootstrap, apply_provision = dislikes_positions
    maintenance = events.index("maintenance:enable")
    backup = events.index("backup")

    assert bootstrap < maintenance < backup < apply_provision


def test_core_update_does_not_run_dislikes_prebackup_bootstrap(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    result = run_update(environment, "core")

    assert result.returncode == 0, result.stderr

    assert (
        "dislikes-runtime:provision"
        not in event_lines(environment)
    )



def _sports_docker_health_only_critical_json(
    health: str,
) -> str:
    return (
        '{"schema_version":1,"status":"critical","score":97,'
        '"category_scores":{"module:sports":86},'
        '"checks":['
        '{"category":"module:sports",'
        '"name":"atlas-sports-controller Health",'
        '"status":"critical",'
        '"message":"atlas-sports-controller health check is '
        + health
        + '",'
        '"details":{"module":"sports",'
        '"container":"atlas-sports-controller",'
        '"container_health":"'
        + health
        + '"}}'
        ']}'
    )


def test_post_apply_transient_sports_docker_starting_recovers_within_grace(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    # Call 1 is pre-update. Call 2 is the immediate private
    # post-apply Doctor while the newly created Sports container
    # is still inside Docker's normal healthcheck startup period.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_docker_health_only_critical_json("starting")
    )

    result = run_update(environment)

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    # The private verification must remain under maintenance and
    # receive a bounded retry before public traffic is reopened.
    assert events.count("doctor") >= 4
    assert "health-json" in events

    enable = events.index("maintenance:enable")
    health_json = events.index("health-json")
    disable = events.index("maintenance:disable")

    assert enable < health_json < disable
    assert not lock_path(environment).exists()




def test_post_apply_critical_health_json_is_classified_despite_nonzero_health_exit(
    tmp_path: Path,
) -> None:
    """Critical health JSON must remain classifiable when the health CLI exits 1."""
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    # Call 1 is the healthy pre-update Doctor.
    #
    # Call 2 observes the Sports controller during Docker's normal
    # startup period.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"

    # This is the production contract of atlas.health:
    #
    # * it emits valid structured JSON for a critical report;
    # * it exits with status 1 because the report is critical.
    #
    # The update classifier must inspect that JSON rather than treating
    # the process status itself as a classifier failure.
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_docker_health_only_critical_json("starting")
    )
    environment["ATLAS_TEST_HEALTH_STATUS"] = "1"

    result = run_update(environment)

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    assert events.count("doctor") >= 4
    assert events.count("health-json") >= 1
    assert "maintenance:enable" in events
    assert "maintenance:disable" in events
    assert events.index("health-json") < events.index(
        "maintenance:disable"
    )
    assert not lock_path(environment).exists()




def test_post_apply_unexpected_health_command_failure_remains_fail_closed(
    tmp_path: Path,
) -> None:
    """Unexpected structured-health command failures must not receive grace."""
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_docker_health_only_critical_json("starting")
    )

    # atlas.health uses 0 for non-critical and 1 for critical.
    # Any other command status represents an unexpected execution failure.
    environment["ATLAS_TEST_HEALTH_STATUS"] = "2"

    result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    assert events.count("doctor") == 2
    assert events.count("health-json") == 1
    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()



def test_post_apply_failed_doctor_with_recovered_health_snapshot_retries(
    tmp_path: Path,
) -> None:
    """A recovered second health snapshot must not turn startup recovery into failure."""
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    # Call 1 is the healthy pre-update Doctor.
    #
    # Call 2 observes a transient post-apply failure. Before the
    # classifier takes its independent structured-health snapshot,
    # the runtime has already recovered. The harness defaults the
    # structured health payload to:
    #
    #   {"status":"healthy","score":100,"checks":[]}
    #
    # This reproduces the production two-snapshot race.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"

    result = run_update(environment)

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    assert events.count("doctor") >= 4
    assert events.count("health-json") >= 1
    assert "maintenance:enable" in events
    assert "maintenance:disable" in events
    assert events.index("health-json") < events.index("maintenance:disable")
    assert not lock_path(environment).exists()



def test_post_apply_sports_docker_starting_grace_exhausts_fail_closed(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = (
        "2,3,4,5,6,7,8,9"
    )
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_docker_health_only_critical_json("starting")
    )

    result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    # Grace must exist, but remain bounded.
    assert 3 <= events.count("doctor") <= 9
    assert "health-json" in events

    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()


def test_post_apply_sports_docker_unhealthy_does_not_receive_startup_grace(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_docker_health_only_critical_json("unhealthy")
    )

    result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    # Only Docker's transient `starting` state is grace-eligible.
    # An actual unhealthy state must retain existing fail-fast behavior.
    assert events.count("doctor") == 2
    assert events.count("health-json") == 1
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()


def _sports_provider_only_critical_health_json() -> str:
    return (
        '{"schema_version":1,"status":"critical","score":97,'
        '"category_scores":{"module:sports":86},'
        '"checks":['
        '{"category":"module:sports",'
        '"name":"Provider Health",'
        '"status":"critical",'
        '"message":"Sports provider health is unavailable or degraded",'
        '"details":{"module":"sports",'
        '"path":"/mnt/storage/configs/sportyfin/state/provider-health.json",'
        '"provider_count":1}}'
        ']}'
    )


def test_post_apply_transient_sports_provider_health_recovers_within_grace(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(doctor_count)

    # Call 1 is the pre-update doctor.
    # Call 2 is the first post-apply doctor and represents the transient
    # Sports provider degradation observed in production.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_provider_only_critical_health_json()
    )

    result = run_update(environment)

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    # A post-apply failure that is limited to Sports Provider Health must
    # remain under maintenance and receive at least one bounded retry.
    assert events.count("doctor") >= 4
    assert "health-json" in events

    enable = events.index("maintenance:enable")
    disable = events.index("maintenance:disable")

    assert enable < events.index("health-json") < disable
    assert events[-3:] == ["maintenance:disable", "doctor", "verify"]
    assert not lock_path(environment).exists()


def test_post_apply_transient_sports_provider_health_grace_exhausts_fail_closed(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(doctor_count)

    # Pre-update doctor succeeds. Every later doctor remains degraded.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = (
        "2,3,4,5,6,7,8,9"
    )
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_provider_only_critical_health_json()
    )

    result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    # The grace path must actually retry, but remain bounded.
    assert 3 <= events.count("doctor") <= 9
    assert "health-json" in events

    # Persistent degradation must never reopen public traffic.
    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()

    assert "Recovery command: atlas deployment rollback" in result.stderr


def test_post_apply_unrelated_health_failure_does_not_receive_sports_grace(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(doctor_count)

    # Pre-update doctor succeeds; the first post-apply doctor fails.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        '{"schema_version":1,"status":"critical","score":90,'
        '"checks":['
        '{"category":"services",'
        '"name":"jellyfin",'
        '"status":"critical",'
        '"message":"jellyfin container is not running",'
        '"details":{"returncode":1}}'
        ']}'
    )

    result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    # Unrelated critical health is never grace-eligible.
    assert events.count("doctor") == 2
    assert events.count("health-json") == 1
    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()

    assert "Recovery command: atlas deployment rollback" in result.stderr


def test_post_apply_mixed_health_failure_does_not_receive_sports_grace(
    tmp_path: Path,
) -> None:
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(doctor_count)

    # Sports Provider Health is degraded, but another independent critical
    # check is also present. This must fail immediately rather than masking
    # the second failure behind the Sports grace period.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        '{"schema_version":1,"status":"critical","score":87,'
        '"checks":['
        '{"category":"module:sports",'
        '"name":"Provider Health",'
        '"status":"critical",'
        '"message":"Sports provider health is unavailable or degraded",'
        '"details":{"module":"sports","provider_count":1}},'
        '{"category":"services",'
        '"name":"jellyfin",'
        '"status":"critical",'
        '"message":"jellyfin container is not running",'
        '"details":{"returncode":1}}'
        ']}'
    )

    result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    # Grace is allowed only when Sports Provider Health is the sole
    # non-healthy check.
    assert events.count("doctor") == 2
    assert events.count("health-json") == 1
    assert "maintenance:enable" in events
    assert "maintenance:disable" not in events
    assert lock_path(environment).is_dir()

    assert "Recovery command: atlas deployment rollback" in result.stderr



def _sports_realistic_startup_bundle_critical_json() -> str:
    """Model correlated Sports failures during controller startup."""
    return (
        '{"schema_version":1,"status":"critical","score":90,'
        '"category_scores":{"module:sports":50},'
        '"checks":['
        '{"category":"module:sports",'
        '"name":"atlas-sports-controller Health",'
        '"status":"critical",'
        '"message":"atlas-sports-controller health check is starting",'
        '"details":{"module":"sports",'
        '"container":"atlas-sports-controller",'
        '"container_health":"starting"}},'
        '{"category":"module:sports",'
        '"name":"Controller Heartbeat",'
        '"status":"critical",'
        '"message":"Sports controller heartbeat is missing or stale",'
        '"details":{"module":"sports",'
        '"path":"/mnt/storage/configs/sportyfin/state/controller-heartbeat",'
        '"age_seconds":null}},'
        '{"category":"module:sports",'
        '"name":"Sports Health Endpoint",'
        '"status":"critical",'
        '"message":"Sports health endpoint is unavailable",'
        '"details":{"module":"sports",'
        '"url":"http://127.0.0.1:8097/health"}}'
        ']}'
    )


def test_post_apply_realistic_sports_startup_bundle_receives_grace(
    tmp_path: Path,
) -> None:
    """Correlated controller-startup checks must receive bounded startup grace."""
    environment = prepare_runtime(tmp_path)

    doctor_count = tmp_path / "doctor-count"
    environment["ATLAS_TEST_DOCTOR_COUNT_FILE"] = str(
        doctor_count
    )

    # Call 1 is pre-update.
    #
    # Call 2 models the first private post-apply Doctor while the new
    # Sports controller is still inside Docker's normal startup period.
    #
    # Real Sports health evaluates the controller heartbeat and private
    # health endpoint at the same time as Docker container health. Those
    # checks may therefore be critical while container_health=starting.
    environment["ATLAS_TEST_DOCTOR_FAIL_CALLS"] = "2"
    environment["ATLAS_TEST_HEALTH_JSON"] = (
        _sports_realistic_startup_bundle_critical_json()
    )

    result = run_update(environment)

    assert result.returncode == 0, result.stderr

    events = event_lines(environment)

    assert events.count("doctor") >= 4
    assert events.count("health-json") >= 1

    enable = events.index("maintenance:enable")
    health_json = events.index("health-json")
    disable = events.index("maintenance:disable")

    assert enable < health_json < disable
    assert not lock_path(environment).exists()



def test_update_refuses_when_scheduler_deployment_execution_lock_is_owned(
    tmp_path: Path,
) -> None:
    """Update must not begin while Scheduler owns the shared execution lock."""
    import fcntl

    environment = prepare_runtime(tmp_path)

    runtime_root = Path(
        environment["ATLAS_RUNTIME_CONFIG_DIR"]
    )
    exclusion_lock = (
        runtime_root / "deployment-scheduler.lock"
    )
    exclusion_lock.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with exclusion_lock.open("w", encoding="utf-8") as handle:
        fcntl.flock(
            handle.fileno(),
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )

        result = run_update(environment)

    assert result.returncode != 0

    events = event_lines(environment)

    # Exclusion must happen before production mutation/isolation begins.
    assert "maintenance:enable" not in events

    # The durable deployment transaction lock must not be acquired when
    # Scheduler already owns the execution exclusion boundary.
    assert not lock_path(environment).exists()
