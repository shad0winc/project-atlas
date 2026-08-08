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


def test_rollback_uses_immutable_images_without_pull_or_build() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    section = content.split("atlas_deployment_restore_surface() {", 1)[1].split(
        "atlas_deployment_rollback() {", 1
    )[0]

    assert 'docker image inspect "$image_id"' in section
    assert 'docker image tag "$image_id" "$image_reference"' in section
    assert "up -d --no-build --pull never" in section
    assert "docker pull" not in section


def test_rollback_source_is_extracted_outside_live_git_worktree() -> None:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    section = content.split("atlas_deployment_restore_surface() {", 1)[1].split(
        "atlas_deployment_rollback() {", 1
    )[0]

    assert 'mktemp -d "$transaction/recovery-${surface}.XXXXXX"' in section
    assert 'tar -xzf "$archive" -C "$recovery"' in section
    assert "git checkout" not in section
    assert "git reset" not in section


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
