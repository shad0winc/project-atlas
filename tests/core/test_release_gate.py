from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release-gate.yml"
PROCEDURE = PROJECT_ROOT / "docs" / "operations" / "RELEASE_PROMOTION.md"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_release_gate_targets_main_and_release_branches() -> None:
    content = workflow_text()

    assert "pull_request:" in content
    assert "push:" in content
    assert "- main" in content
    assert "- 'release/**'" in content


def test_release_gate_has_read_only_repository_permissions() -> None:
    content = workflow_text()

    assert "permissions:\n  contents: read" in content


def test_release_gate_runs_complete_core_regression() -> None:
    content = workflow_text()

    assert "python -m pytest tests/core -q" in content
    assert "python -m compileall -q atlas modules/sports/src tests" in content


def test_release_gate_runs_api_regression() -> None:
    content = workflow_text()

    assert "python -m pip install -e './apps/api[test]'" in content
    assert "python -m pytest apps/api/tests -q" in content


def test_release_gate_runs_sports_integration() -> None:
    content = workflow_text()

    assert "python modules/sports/tests/run_tests.py" in content


def test_release_gate_runs_portal_quality_and_build() -> None:
    content = workflow_text()

    for command in (
        "npm ci",
        "npm run lint",
        "npm run typecheck",
        "npm test",
        "npm run build",
    ):
        assert command in content


def test_release_contract_rejects_image_pruning() -> None:
    content = workflow_text()

    assert "docker image prune" in content
    assert "deployment path prunes rollback images" in content


def test_final_gate_depends_on_every_validation_surface() -> None:
    content = workflow_text()
    gate = content.split("  release-gate:\n", 1)[1]

    assert "if: ${{ always() }}" in gate
    for job in ("core", "api", "sports", "portal", "contracts"):
        assert f"      - {job}\n" in gate
    assert "Atlas release gate: PASS" in gate


def test_branch_protection_procedure_does_not_claim_external_state() -> None:
    content = PROCEDURE.read_text(encoding="utf-8")

    assert "repository hosting must be inspected" in content
    assert "`release-gate` status check is required" in content
    assert "force pushes are blocked" in content
    assert "branch deletion is blocked" in content


def test_procedure_preserves_legacy_v1_tag_blocker() -> None:
    content = PROCEDURE.read_text(encoding="utf-8")

    assert "historical `v1.0.0` tag remains a separate release blocker" in content
    assert "does not reinterpret, move, delete" in content


# M-023.24.5 clean-runner portability contracts


def test_atlas_cli_supports_explicit_project_root() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    content = (root / "scripts" / "atlas").read_text(
        encoding="utf-8",
    )

    assert (
        'PROJECT_DIR="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"'
        in content
    )


def test_release_gate_core_uses_checkout_project_root() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    content = (
        root / ".github" / "workflows" / "release-gate.yml"
    ).read_text(encoding="utf-8")

    core = content.split("  core:\n", 1)[1].split(
        "  api:\n",
        1,
    )[0]

    assert "ATLAS_PROJECT_DIR: ${{ github.workspace }}" in core


def test_release_gate_sports_matches_python_runtime() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    content = (
        root / ".github" / "workflows" / "release-gate.yml"
    ).read_text(encoding="utf-8")

    sports = content.split("  sports:\n", 1)[1].split(
        "  portal:\n",
        1,
    )[0]

    assert "python-version: '3.13'" in sports


def test_release_gate_installs_sports_ffmpeg_dependency() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]

    workflow = (
        root / ".github" / "workflows" / "release-gate.yml"
    ).read_text(encoding="utf-8")

    dockerfile = (
        root / "modules" / "sports" / "Dockerfile"
    ).read_text(encoding="utf-8")

    sports = workflow.split("  sports:\n", 1)[1].split(
        "  portal:\n",
        1,
    )[0]

    assert "ffmpeg" in dockerfile
    assert (
        "sudo apt-get install -y --no-install-recommends ffmpeg"
        in sports
    )


# M-023.24.5 isolated runner state contracts


def test_shared_config_preserves_explicit_project_root() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    content = (
        root / "config" / "atlas.conf"
    ).read_text(encoding="utf-8")

    assert (
        'ATLAS_PROJECT_DIR="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"'
        in content
    )


def test_release_gate_sports_uses_isolated_runner_storage() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    content = (
        root / ".github" / "workflows" / "release-gate.yml"
    ).read_text(encoding="utf-8")

    sports = content.split("  sports:\n", 1)[1].split(
        "  portal:\n",
        1,
    )[0]

    assert (
        "SPORTS_MEDIA_DIR: "
        "${{ runner.temp }}/atlas-sports/media"
        in sports
    )
    assert (
        "SPORTS_RECORDING_LOG_DIR: "
        "${{ runner.temp }}/atlas-sports/logs"
        in sports
    )
    assert (
        "SPORTS_RECORDINGS_FILE: "
        "${{ runner.temp }}/atlas-sports/recordings/recordings.json"
        in sports
    )
