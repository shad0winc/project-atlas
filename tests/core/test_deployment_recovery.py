from __future__ import annotations

from pathlib import Path


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
    release = section.rindex("atlas_deployment_release_lock")
    assert doctor < verify < disable < release
