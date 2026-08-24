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


def test_branch_protection_procedure_records_verified_external_state() -> None:
    content = PROCEDURE.read_text(encoding="utf-8")

    assert "Repository hosting was inspected during M-023.24" in content
    assert "promotion ruleset was configured for `main` and `release/**`" in content
    assert "the aggregate `release-gate` status check to pass" in content
    assert "protected branches to be up to date before merge" in content
    assert "force pushes to be blocked" in content
    assert "branch deletion to be blocked" in content
    assert "an empty default bypass list" in content
    assert "Atlas Release Gate / release-gate" in content


def test_procedure_records_reconciled_v1_tag_state() -> None:
    content = PROCEDURE.read_text(encoding="utf-8")

    assert "## Reconciled v1.0.0 Tag State" in content
    assert "historical premature `v1.0.0` tag was explicitly reconciled" in content
    assert "deleted locally and from `origin`" in content
    assert "historical commit remains preserved in normal Git history" in content
    assert "does not itself certify or publish Project Atlas" in content
    assert "must point to the exact certified final-release commit" in content


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


# M-023.24.5 runner-context placement contract


def test_runner_context_is_scoped_to_sports_execution_step() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    content = (
        root / ".github" / "workflows" / "release-gate.yml"
    ).read_text(encoding="utf-8")

    sports = content.split("  sports:\n", 1)[1].split(
        "  portal:\n",
        1,
    )[0]

    job_header = sports.split(
        "      - uses:",
        1,
    )[0]

    assert "${{ runner.temp }}" not in job_header

    execution = sports.split(
        "      - name: Run Sports integration suite\n",
        1,
    )[1]

    assert (
        "SPORTS_MEDIA_DIR: "
        "${{ runner.temp }}/atlas-sports/media"
        in execution
    )
    assert (
        "SPORTS_RECORDING_LOG_DIR: "
        "${{ runner.temp }}/atlas-sports/logs"
        in execution
    )
    assert (
        "SPORTS_RECORDINGS_FILE: "
        "${{ runner.temp }}/atlas-sports/recordings/recordings.json"
        in execution
    )

# M-023.24.5 modern GitHub Actions contract


def test_release_gate_uses_modern_github_actions() -> None:
    from pathlib import Path

    workflow = Path(
        ".github/workflows/release-gate.yml"
    ).read_text(encoding="utf-8")

    assert workflow.count(
        "actions/checkout@v7"
    ) == 5

    assert workflow.count(
        "actions/setup-python@v7"
    ) == 3

    assert workflow.count(
        "actions/setup-node@v7"
    ) == 1

    legacy_versions = (
        "actions/checkout@v4",
        "actions/checkout@v5",
        "actions/checkout@v6",
        "actions/setup-python@v4",
        "actions/setup-python@v5",
        "actions/setup-python@v6",
        "actions/setup-node@v4",
        "actions/setup-node@v5",
        "actions/setup-node@v6",
    )

    for legacy_version in legacy_versions:
        assert legacy_version not in workflow
