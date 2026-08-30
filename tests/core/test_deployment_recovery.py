from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"
UPDATE = PROJECT_ROOT / "scripts" / "commands" / "update.sh"
ATLAS = PROJECT_ROOT / "scripts" / "atlas"
HELP = PROJECT_ROOT / "scripts" / "commands" / "help.sh"


def test_deployment_cli_exposes_baseline_and_rollback() -> None:
    atlas = ATLAS.read_text(encoding="utf-8")
    help_text = HELP.read_text(encoding="utf-8")

    assert 'source "$ATLAS_CLI_ROOT/commands/deployment.sh"' in atlas
    assert 'atlas_command_deployment "${@:2}"' in atlas
    assert "atlas deployment baseline" in help_text
    assert "atlas deployment rollback <deployment-id>" in help_text


def test_baseline_requires_doctor_verify_and_ingress() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    section = content.split("atlas_deployment_baseline() {", 1)[1].split(
        "atlas_deployment_prepare_update() {", 1
    )[0]

    assert "atlas_deployment_validate_source" in section
    assert "atlas_command_doctor" in section
    assert "atlas_command_verify" in section
    assert '"$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh"' in section
    assert "atlas_deployment_capture_images" in section
    assert "atlas_deployment_verify_runtime" in section


def test_baseline_archives_source_and_exact_image_identity() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")

    assert "git -C \"$ATLAS_PROJECT_DIR\" archive" in content
    assert "tar -tzf \"$temporary\"" in content
    assert "{{.Config.Image}}|{{.Image}}" in content
    assert "core-source.tar.gz" in content
    assert "ingress-source.tar.gz" in content


def test_prepare_update_preserves_exact_rollback_image_references(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline-test"
    transaction = tmp_path / "update-test"
    bin_dir = tmp_path / "bin"
    tags = tmp_path / "tags"
    baseline.mkdir()
    transaction.mkdir()
    bin_dir.mkdir()
    (baseline / "images.tsv").write_text(
        "core|docker-compose.yml|atlas|core|core-container|core:test|sha256:core\n"
        "ingress|stack/ingress.yml|atlas-ingress|portal|atlas-portal|atlas-portal:local|sha256:portal\n",
        encoding="utf-8",
    )
    docker = bin_dir / "docker"
    docker.write_text(
        textwrap.dedent(
            r"""
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "$1 $2" == "image inspect" && "${3:-}" != "--format" ]]; then
              exit 0
            fi
            if [[ "$1 $2" == "image tag" ]]; then
              printf '%s|%s\n' "$4" "$3" >> "$ATLAS_TEST_TAGS"
              exit 0
            fi
            if [[ "$1 $2 $3" == "image inspect --format" ]]; then
              awk -F'|' -v tag="$5" '$1 == tag {print $2; exit}' "$ATLAS_TEST_TAGS"
              exit 0
            fi
            exit 1
            """
        ).lstrip(),
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment['PATH']}",
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
            "ATLAS_TEST_TAGS": str(tags),
        }
    )
    harness = r'''
    set -euo pipefail
    source "$ATLAS_TEST_DEPLOYMENT"
    atlas_deployment_preserve_rollback_images "$1" "$2"
    '''
    result = subprocess.run(
        ["bash", "-c", textwrap.dedent(harness), "test", str(baseline), str(transaction)],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    retained = (transaction / "rollback-images.tsv").read_text(encoding="utf-8").splitlines()
    assert retained == [
        "sha256:core|atlas-rollback:update-test-1",
        "sha256:portal|atlas-rollback:update-test-2",
    ]


def test_runtime_drift_is_fail_closed() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")

    assert "runtime drift detected" in content
    assert "actual_image" in content
    assert "expected_image" in content


def test_update_requires_explicit_no_migration_declaration() -> None:
    content = UPDATE.read_text(encoding="utf-8")

    assert '"${1:-}" == \'--migration\'' in content
    assert '"${2:-}" == \'none\'' in content
    assert "State-changing migrations require release-specific recovery evidence" in content


def test_failed_update_points_operator_to_exact_rollback() -> None:
    content = UPDATE.read_text(encoding="utf-8")

    assert "Recovery command: atlas deployment rollback" in content
    assert "Maintenance mode remains enabled." in content
    assert "Deployment lock remains held for explicit recovery." in content


def test_rollback_requires_previous_verified_baseline_and_backup() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    section = content.split("atlas_deployment_rollback() {", 1)[1].split(
        "atlas_command_deployment() {", 1
    )[0]

    assert "previous_baseline" in section
    assert "recorded pre-update backup" in section
    assert "tar -tzf" in section
    assert "automatic rollback is blocked for state-changing migrations" in section


def test_rollback_uses_preserved_aliases_without_pull_or_build() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    section = content.split("atlas_deployment_restore_surface() {", 1)[1].split(
        "atlas_deployment_rollback() {", 1
    )[0]

    assert 'local rollback_images="$transaction/rollback-images.tsv"' in section
    assert '"$rollback_images"' in section
    assert 'recovery_tag="$(' in section
    assert 'docker image inspect "$recovery_tag"' in section
    assert "'{{.Id}}'" in section
    assert '== "$image_id"' in section
    assert "rollback-images.yml" in section
    assert "image: %s" in section
    assert '-f "$override"' in section
    assert "up -d --no-build --pull never" in section
    assert "docker pull" not in section
    assert 'docker image tag "$image_id" "$image_reference"' not in section


def test_restore_surface_uses_alias_for_digest_shaped_reference(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    records = runtime / "deployments" / "records"
    baseline = tmp_path / "baseline"
    transaction = records / "update-test"
    recovery_source = tmp_path / "source"
    bin_dir = tmp_path / "bin"
    tags = tmp_path / "tags"
    compose_events = tmp_path / "compose-events"

    baseline.mkdir()
    transaction.mkdir(parents=True)
    recovery_source.mkdir()
    bin_dir.mkdir()

    (recovery_source / "stack").mkdir()
    (recovery_source / "stack" / "ingress.yml").write_text(
        "services: {}\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            "tar",
            "-czf",
            str(baseline / "ingress-source.tar.gz"),
            "-C",
            str(recovery_source),
            ".",
        ],
        check=True,
    )

    digest_reference = (
        "registry.example/atlas/caddy@"
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )

    (baseline / "images.tsv").write_text(
        "ingress|stack/ingress.yml|atlas-ingress|caddy|"
        f"atlas-caddy|{digest_reference}|sha256:caddy\n",
        encoding="utf-8",
    )

    (transaction / "rollback-images.tsv").write_text(
        "sha256:caddy|atlas-rollback:update-test-1\n",
        encoding="utf-8",
    )

    tags.write_text(
        "atlas-rollback:update-test-1|sha256:caddy\n",
        encoding="utf-8",
    )

    docker = bin_dir / "docker"

    docker.write_text(
        textwrap.dedent(
            r'''
            #!/usr/bin/env bash
            set -euo pipefail

            if [[ "$1 $2" == "image inspect" && "${3:-}" != "--format" ]]; then
              awk -F'|' -v tag="$3" \
                '$1 == tag {found=1} END {exit !found}' \
                "$ATLAS_TEST_TAGS"
              exit $?
            fi

            if [[ "$1 $2 $3" == "image inspect --format" ]]; then
              awk -F'|' -v tag="$5" \
                '$1 == tag {print $2; exit}' \
                "$ATLAS_TEST_TAGS"
              exit 0
            fi

            if [[ "$1 $2" == "image tag" ]]; then
              echo "UNEXPECTED_IMAGE_TAG|$*" \
                >> "$ATLAS_TEST_COMPOSE_EVENTS"
              exit 90
            fi

            if [[ "$1" == "compose" ]]; then
              printf '%s\n' "$*" \
                >> "$ATLAS_TEST_COMPOSE_EVENTS"
              exit 0
            fi

            exit 1
            '''
        ).lstrip(),
        encoding="utf-8",
    )

    docker.chmod(0o755)

    live = tmp_path / "live"
    live.mkdir()
    (live / ".env").write_text(
        "ATLAS_TEST=1\n",
        encoding="utf-8",
    )

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment['PATH']}",
            "ATLAS_PROJECT_DIR": str(live),
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
            "ATLAS_TEST_TAGS": str(tags),
            "ATLAS_TEST_COMPOSE_EVENTS": str(compose_events),
        }
    )

    harness = r'''
    set -euo pipefail
    source "$ATLAS_TEST_DEPLOYMENT"
    atlas_deployment_restore_surface "$1" "$2" ingress
    '''

    result = subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
            "test",
            str(baseline),
            str(transaction),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    events = compose_events.read_text(
        encoding="utf-8"
    ).splitlines()

    assert not any(
        event.startswith("UNEXPECTED_IMAGE_TAG")
        for event in events
    )

    compose = next(
        event
        for event in events
        if not event.startswith("UNEXPECTED_IMAGE_TAG")
    )

    assert "--no-build" in compose
    assert "--pull never" in compose
    assert "rollback-images.yml" in compose

    recovery_dirs = list(
        transaction.glob("recovery-ingress.*")
    )

    assert len(recovery_dirs) == 1

    override = (
        recovery_dirs[0] / "rollback-images.yml"
    ).read_text(encoding="utf-8")

    assert override == (
        "services:\n"
        "  caddy:\n"
        "    image: atlas-rollback:update-test-1\n"
    )

    assert digest_reference not in override


def test_restore_surface_fails_when_rollback_alias_is_missing(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    records = runtime / "deployments" / "records"
    baseline = tmp_path / "baseline"
    transaction = records / "update-test"
    source = tmp_path / "source"

    baseline.mkdir()
    transaction.mkdir(parents=True)
    source.mkdir()

    (source / "docker-compose.yml").write_text(
        "services: {}\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            "tar",
            "-czf",
            str(baseline / "core-source.tar.gz"),
            "-C",
            str(source),
            ".",
        ],
        check=True,
    )

    (baseline / "images.tsv").write_text(
        "core|docker-compose.yml|atlas|core|"
        "core-container|core:test|sha256:core\n",
        encoding="utf-8",
    )

    (transaction / "rollback-images.tsv").write_text(
        "sha256:other|atlas-rollback:update-test-1\n",
        encoding="utf-8",
    )

    live = tmp_path / "live"
    live.mkdir()

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_PROJECT_DIR": str(live),
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        }
    )

    harness = r'''
    set -euo pipefail
    source "$ATLAS_TEST_DEPLOYMENT"
    atlas_deployment_restore_surface "$1" "$2" core
    '''

    result = subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
            "test",
            str(baseline),
            str(transaction),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert (
        "rollback alias missing for image sha256:core (core)"
        in result.stderr
    )


def test_rollback_source_uses_persistent_deployment_record_namespace() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")

    helper = content.split(
        "atlas_deployment_create_recovery_dir() {",
        1,
    )[1].split(
        "atlas_deployment_record_value() {",
        1,
    )[0]

    restore = content.split(
        "atlas_deployment_restore_surface() {",
        1,
    )[1].split(
        "atlas_deployment_rollback() {",
        1,
    )[0]

    assert 'records="$(atlas_deployment_records_dir)"' in helper
    assert 'records_real="$(realpath -e "$records")"' in helper
    assert 'transaction_real="$(realpath -e "$transaction")"' in helper
    assert 'dirname "$transaction_real"' in helper
    assert '== "$records_real"' in helper
    assert 'atlas_deployment_valid_id "$transaction_id"' in helper
    assert (
        '"$transaction_real/recovery-${surface}.XXXXXX"'
        in helper
    )

    assert "atlas_deployment_create_recovery_dir" in restore
    assert 'tar -xzf "$archive" -C "$recovery"' in restore
    assert 'mktemp -d "$transaction/recovery-${surface}.XXXXXX"' not in restore
    assert "git checkout" not in restore
    assert "git reset" not in restore


def test_recovery_directory_is_created_under_transaction_record_and_persists(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    records = runtime / "deployments" / "records"
    transaction = records / "update-test"

    transaction.mkdir(parents=True)

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        }
    )

    harness = r"""
    set -euo pipefail

    source "$ATLAS_TEST_DEPLOYMENT"

    atlas_deployment_create_recovery_dir \
      "$1" \
      ingress
    """

    result = subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
            "test",
            str(transaction),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    recovery = Path(result.stdout.strip())

    assert recovery.parent == transaction.resolve()
    assert recovery.name.startswith("recovery-ingress.")
    assert recovery.is_dir()

    # The helper returns without deleting the directory because
    # containers may retain bind mounts into this source tree.
    assert recovery.exists()


def test_recovery_directory_rejects_transaction_outside_records_namespace(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    records = runtime / "deployments" / "records"
    outsider = tmp_path / "outside" / "update-test"

    records.mkdir(parents=True)
    outsider.mkdir(parents=True)

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        }
    )

    harness = r"""
    set -euo pipefail

    source "$ATLAS_TEST_DEPLOYMENT"

    atlas_deployment_create_recovery_dir \
      "$1" \
      ingress
    """

    result = subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
            "test",
            str(outsider),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0

    assert (
        "rollback transaction is outside the deployment records namespace"
        in result.stderr
    )

    assert not list(
        outsider.glob("recovery-ingress.*")
    )


def test_rollback_reopens_traffic_only_after_verification() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    section = content.split("atlas_deployment_rollback() {", 1)[1].split(
        "atlas_command_deployment() {", 1
    )[0]

    doctor = section.index("atlas_command_doctor")
    verify = section.index("atlas_command_verify")
    disable = section.index("atlas_command_maintenance disable")
    public_verify = section.index("atlas_command_verify", disable)
    release = section.rindex("atlas_deployment_release_lock")
    set_current = section.index("atlas_deployment_set_current", disable)
    assert doctor < verify < disable < public_verify < set_current < release


def test_update_prepares_and_verifies_target_artifacts_before_maintenance() -> None:
    content = UPDATE.read_text(encoding="utf-8")
    section = content.split("atlas_command_update() {", 1)[1]

    doctor = section.index("atlas_command_doctor")
    prepare = section.index('atlas_update_prepare_scope "$scope"')
    verify = section.index('atlas_update_verify_target_images "$scope"')
    maintenance = section.index("atlas_command_maintenance enable")
    backup = section.index("atlas_command_backup")
    apply = section.index('atlas_update_apply_scope "$scope"')

    assert doctor < prepare < verify < maintenance < backup < apply


def test_update_publishes_dashboard_runtime_before_reopening_traffic() -> None:
    content = UPDATE.read_text(encoding="utf-8")
    section = content.split("atlas_command_update() {", 1)[1]

    first_verify = section.index(
        'atlas_update_post_verify "$scope"'
    )
    publish = section.index(
        'atlas_update_publish_dashboard_runtime "$scope"'
    )
    disable = section.index(
        "atlas_command_maintenance disable"
    )
    public_verify = section.index(
        'atlas_update_post_verify "$scope"',
        disable,
    )
    complete = section.index(
        'atlas_deployment_complete_update "$identifier"'
    )

    assert first_verify < publish < disable < public_verify < complete


def test_dashboard_runtime_update_hook_is_bounded_to_ingress_surface() -> None:
    content = UPDATE.read_text(encoding="utf-8")
    section = content.split(
        "atlas_update_publish_dashboard_runtime() {",
        1,
    )[1].split(
        "atlas_update_latest_backup() {",
        1,
    )[0]

    assert 'core)' in section
    assert 'return 0' in section
    assert 'ingress|all)' in section
    assert 'scripts/atlas-dashboard-runtime.sh' in section
    assert 'publish-all' in section


def test_dashboard_runtime_publication_failure_uses_maintenance_failure_path() -> None:
    content = UPDATE.read_text(encoding="utf-8")
    section = content.split("atlas_command_update() {", 1)[1]

    publish = section.index(
        'if ! atlas_update_publish_dashboard_runtime "$scope"; then'
    )
    disable = section.index(
        "atlas_command_maintenance disable"
    )

    failure_window = section[publish:disable]

    assert "atlas_update_fail_after_maintenance" in failure_window
    assert "Dashboard runtime publication failed." in failure_window
    assert "return 1" in failure_window


def test_update_verifies_every_rendered_target_image_is_local() -> None:
    content = UPDATE.read_text(encoding="utf-8")
    section = content.split(
        "atlas_update_verify_compose_images() {",
        1,
    )[1].split(
        "atlas_update_verify_target_images() {",
        1,
    )[0]

    assert "config --images" in section
    assert "LC_ALL=C sort -u" in section
    assert 'docker image inspect "$image"' in section
    assert "target image is not locally available" in section
    assert "target Compose image set is empty" in section


def test_update_apply_is_network_and_build_independent() -> None:
    content = UPDATE.read_text(encoding="utf-8")

    core = content.split("atlas_update_core_apply() {", 1)[1].split(
        "atlas_update_ingress_apply() {",
        1,
    )[0]

    ingress = content.split("atlas_update_ingress_apply() {", 1)[1].split(
        "atlas_update_apply_scope() {",
        1,
    )[0]

    for section in (core, ingress):
        assert "--no-build" in section
        assert "--pull never" in section
        assert "\n    pull" not in section
        assert "\n    build" not in section


def test_update_acquires_network_artifacts_only_before_maintenance() -> None:
    content = UPDATE.read_text(encoding="utf-8")

    core_prepare = content.split(
        "atlas_update_core_prepare() {",
        1,
    )[1].split(
        "atlas_update_ingress_prepare() {",
        1,
    )[0]

    ingress_prepare = content.split(
        "atlas_update_ingress_prepare() {",
        1,
    )[1].split(
        "atlas_update_prepare_scope() {",
        1,
    )[0]

    assert "\n    pull" in core_prepare
    assert "\n    pull caddy" in ingress_prepare
    assert "\n    build portal api sports-writer" in ingress_prepare


def test_rollback_readiness_helpers_are_bounded_and_fail_closed() -> None:
    content = Path("scripts/commands/deployment.sh").read_text(
        encoding="utf-8"
    )

    assert "atlas_deployment_ingress_container_state() {" in content
    assert "atlas_deployment_readiness_sleep() {" in content
    assert "atlas_deployment_wait_for_ingress_readiness() {" in content

    assert 'ATLAS_ROLLBACK_READINESS_ATTEMPTS:-18' in content
    assert 'ATLAS_ROLLBACK_READINESS_INTERVAL_SECONDS:-5' in content

    assert "atlas-api" in content
    assert "atlas-portal" in content
    assert "atlas-caddy" in content

    assert "healthy)" in content
    assert "starting)" in content
    assert "unhealthy|missing|'')" in content
    assert "unexpected health state" in content
    assert "readiness timed out" in content


def test_rollback_readiness_waiter_is_inspection_only() -> None:
    content = Path("scripts/commands/deployment.sh").read_text(
        encoding="utf-8"
    )

    start = content.index(
        "atlas_deployment_wait_for_ingress_readiness() {"
    )
    end = content.index(
        "\natlas_deployment_rollback() {",
        start,
    )
    section = content[start:end]

    assert "atlas_deployment_ingress_container_state" in section
    assert "atlas_deployment_readiness_sleep" in section

    forbidden = (
        "docker start",
        "docker stop",
        "docker restart",
        "docker compose",
        "docker pull",
        "docker build",
        "docker image tag",
        "atlas_command_maintenance",
        "atlas_deployment_set_status",
        "atlas_deployment_set_current",
        "atlas_deployment_release_lock",
    )

    for phrase in forbidden:
        assert phrase not in section


def test_rollback_readiness_is_after_restore_before_verification() -> None:
    content = Path("scripts/commands/deployment.sh").read_text(
        encoding="utf-8"
    )

    start = content.index("atlas_deployment_rollback() {")
    section = content[start:]

    restore = section.index(
        'atlas_deployment_restore_surface "$baseline" "$transaction" ingress'
    )
    readiness = section.index(
        "atlas_deployment_wait_for_ingress_readiness"
    )
    doctor = section.index(
        "atlas_command_doctor || return 1"
    )

    assert restore < readiness < doctor


def test_core_rollback_bypasses_ingress_readiness_by_scope() -> None:
    content = Path("scripts/commands/deployment.sh").read_text(
        encoding="utf-8"
    )

    start = content.index("atlas_deployment_rollback() {")
    section = content[start:]

    readiness_guard = """if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    echo 'Post-restore ingress readiness:'
    atlas_deployment_wait_for_ingress_readiness"""

    assert readiness_guard in section


def test_rollback_readiness_failure_precedes_state_finalization() -> None:
    content = Path("scripts/commands/deployment.sh").read_text(
        encoding="utf-8"
    )

    start = content.index("atlas_deployment_rollback() {")
    section = content[start:]

    readiness = section.index(
        "atlas_deployment_wait_for_ingress_readiness"
    )
    maintenance_disable = section.index(
        "atlas_command_maintenance disable"
    )
    set_current = section.index(
        'atlas_deployment_set_current "$previous_id"'
    )
    rolled_back = section.index(
        'atlas_deployment_set_status "$transaction" rolled_back'
    )
    release = section.index(
        'atlas_deployment_release_lock "$identifier"',
        rolled_back,
    )

    assert readiness < maintenance_disable
    assert readiness < set_current
    assert readiness < rolled_back
    assert rolled_back < release


def _run_rollback_readiness_behavior(
    tmp_path: Path,
    states: dict[str, list[tuple[str, str]]],
    *,
    attempts: int = 3,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    bin_dir = tmp_path / "bin"
    state_dir = tmp_path / "states"
    inspect_events = tmp_path / "inspect-events"

    bin_dir.mkdir()
    state_dir.mkdir()

    for container, sequence in states.items():
        lines = [
            f"{status}|{health}"
            for status, health in sequence
        ]

        (state_dir / container).write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    docker = bin_dir / "docker"

    docker.write_text(
        textwrap.dedent(
            r'''
            #!/usr/bin/env bash
            set -euo pipefail

            if [[ "${1:-}" != "inspect" || "${2:-}" != "--format" ]]; then
              exit 91
            fi

            format="${3:-}"
            container="${4:-}"
            states="$ATLAS_TEST_READINESS_STATE_DIR/$container"

            [[ -f "$states" ]] || exit 1

            count="$(
              awk -F'|' -v container="$container" \
                '$1 == container {count++} END {print count + 0}' \
                "$ATLAS_TEST_READINESS_INSPECT_EVENTS" 2>/dev/null ||
              true
            )"

            index=$((count / 2 + 1))

            line="$(
              sed -n "${index}p" "$states"
            )"

            if [[ -z "$line" ]]; then
              line="$(tail -n 1 "$states")"
            fi

            status="${line%%|*}"
            health="${line#*|}"

            printf '%s|%s\n' \
              "$container" \
              "$format" \
              >> "$ATLAS_TEST_READINESS_INSPECT_EVENTS"

            case "$format" in
              '{{.State.Status}}')
                printf '%s\n' "$status"
                ;;
              '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}')
                printf '%s\n' "$health"
                ;;
              *)
                exit 92
                ;;
            esac
            '''
        ).lstrip(),
        encoding="utf-8",
    )

    docker.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment['PATH']}",
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
            "ATLAS_TEST_READINESS_STATE_DIR": str(state_dir),
            "ATLAS_TEST_READINESS_INSPECT_EVENTS": str(
                inspect_events
            ),
            "ATLAS_ROLLBACK_READINESS_ATTEMPTS": str(attempts),
            "ATLAS_ROLLBACK_READINESS_INTERVAL_SECONDS": "0",
        }
    )

    harness = r'''
    set -euo pipefail

    source "$ATLAS_TEST_DEPLOYMENT"

    atlas_deployment_wait_for_ingress_readiness
    '''

    result = subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    events = []

    if inspect_events.exists():
        events = inspect_events.read_text(
            encoding="utf-8"
        ).splitlines()

    return result, events


def test_rollback_readiness_behavior_already_healthy_succeeds(
    tmp_path: Path,
) -> None:
    result, events = _run_rollback_readiness_behavior(
        tmp_path,
        {
            "atlas-api": [("running", "healthy")],
            "atlas-portal": [("running", "healthy")],
            "atlas-caddy": [("running", "healthy")],
        },
    )

    assert result.returncode == 0, result.stderr
    assert len(events) == 6


def test_rollback_readiness_behavior_starting_then_healthy_retries(
    tmp_path: Path,
) -> None:
    result, events = _run_rollback_readiness_behavior(
        tmp_path,
        {
            "atlas-api": [
                ("running", "starting"),
                ("running", "healthy"),
            ],
            "atlas-portal": [
                ("running", "healthy"),
                ("running", "healthy"),
            ],
            "atlas-caddy": [
                ("running", "healthy"),
                ("running", "healthy"),
            ],
        },
        attempts=2,
    )

    assert result.returncode == 0, result.stderr
    assert len(events) == 12


def test_rollback_readiness_behavior_unhealthy_fails_immediately(
    tmp_path: Path,
) -> None:
    result, events = _run_rollback_readiness_behavior(
        tmp_path,
        {
            "atlas-api": [("running", "unhealthy")],
            "atlas-portal": [("running", "healthy")],
            "atlas-caddy": [("running", "healthy")],
        },
    )

    assert result.returncode != 0
    assert "atlas-api health=unhealthy" in result.stderr
    assert len(events) == 2


def test_rollback_readiness_behavior_non_running_fails_immediately(
    tmp_path: Path,
) -> None:
    result, events = _run_rollback_readiness_behavior(
        tmp_path,
        {
            "atlas-api": [("exited", "healthy")],
            "atlas-portal": [("running", "healthy")],
            "atlas-caddy": [("running", "healthy")],
        },
    )

    assert result.returncode != 0
    assert "atlas-api is not running" in result.stderr
    assert "status=exited" in result.stderr
    assert len(events) == 2


def test_rollback_readiness_behavior_missing_health_fails_immediately(
    tmp_path: Path,
) -> None:
    result, events = _run_rollback_readiness_behavior(
        tmp_path,
        {
            "atlas-api": [("running", "missing")],
            "atlas-portal": [("running", "healthy")],
            "atlas-caddy": [("running", "healthy")],
        },
    )

    assert result.returncode != 0
    assert "atlas-api health=missing" in result.stderr
    assert len(events) == 2


def test_rollback_readiness_behavior_starting_timeout_is_bounded(
    tmp_path: Path,
) -> None:
    result, events = _run_rollback_readiness_behavior(
        tmp_path,
        {
            "atlas-api": [("running", "starting")],
            "atlas-portal": [("running", "healthy")],
            "atlas-caddy": [("running", "healthy")],
        },
        attempts=3,
    )

    assert result.returncode != 0
    assert (
        "rollback ingress readiness timed out after 3 attempts"
        in result.stderr
    )

    # Three containers, two inspect operations each,
    # across exactly three bounded attempts.
    assert len(events) == 18
