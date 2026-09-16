from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPORTS = ROOT / "modules" / "sports"

COMPOSE = SPORTS / "docker-compose.yml"
INSTALL = SPORTS / "scripts" / "install.sh"
UPDATE = SPORTS / "scripts" / "update.sh"
VERIFY = SPORTS / "scripts" / "verify.sh"


def _text(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
    )


def test_sports_compose_host_source_uses_atlas_project_dir() -> None:
    content = _text(COMPOSE)

    assert (
        '      context: "${ATLAS_PROJECT_DIR:-/opt/project-atlas}"\n'
        in content
    )

    assert (
        '      - "${ATLAS_PROJECT_DIR:-/opt/project-atlas}:'
        '/opt/project-atlas:ro"\n'
        in content
    )

    assert (
        "      context: /opt/project-atlas\n"
        not in content
    )

    assert (
        "      - /opt/project-atlas:/opt/project-atlas:ro\n"
        not in content
    )


def test_sports_host_lifecycle_scripts_use_atlas_project_dir() -> None:
    expected = (
        'PROJECT_DIR="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"'
    )

    for path in (
        INSTALL,
        UPDATE,
        VERIFY,
    ):
        content = _text(path)

        assert expected in content
        assert (
            'PROJECT_DIR="/opt/project-atlas"'
            not in content
        )


def test_sports_container_internal_project_root_remains_stable() -> None:
    compose = _text(COMPOSE)
    dockerfile = _text(
        SPORTS / "Dockerfile"
    )

    assert (
        '      ATLAS_BINARY: "/opt/project-atlas/scripts/atlas"\n'
        in compose
    )

    assert (
        'WORKDIR /opt/project-atlas\n'
        in dockerfile
    )

    assert (
        'ENV PYTHONPATH="/opt/project-atlas:'
        '/opt/project-atlas/modules/sports/src"\n'
        in dockerfile
    )

    assert (
        'CMD ["python3", '
        '"/opt/project-atlas/modules/sports/src/worker.py"]\n'
        in dockerfile
    )


def test_sports_compose_project_root_default_is_production_path() -> None:
    content = _text(COMPOSE)

    assert content.count(
        "${ATLAS_PROJECT_DIR:-/opt/project-atlas}"
    ) == 2


def test_update_all_uses_transactional_sports_prepare_and_apply() -> None:
    update_source = (
        ROOT / "scripts" / "commands" / "update.sh"
    ).read_text(encoding="utf-8")

    assert "atlas_update_sports_prepare() {" in update_source
    assert "atlas_update_sports_apply() {" in update_source

    sports_prepare = update_source.split(
        "atlas_update_sports_prepare() {",
        1,
    )[1].split(
        "\natlas_update_",
        1,
    )[0]

    sports_apply = update_source.split(
        "atlas_update_sports_apply() {",
        1,
    )[1].split(
        "\natlas_update_",
        1,
    )[0]

    assert "\n    pull" in sports_prepare
    assert "\n    build" in sports_prepare

    assert "up -d" in sports_apply
    assert "--no-build" in sports_apply
    assert "--pull never" in sports_apply
    assert "\n    pull" not in sports_apply
    assert "\n    build" not in sports_apply

    prepare_scope = update_source.split(
        "atlas_update_prepare_scope() {",
        1,
    )[1].split(
        "\natlas_update_",
        1,
    )[0]

    apply_scope = update_source.split(
        "atlas_update_apply_scope() {",
        1,
    )[1].split(
        "\natlas_update_",
        1,
    )[0]

    prepare_all = prepare_scope.split(
        "all)",
        1,
    )[1].split(
        ";;",
        1,
    )[0]

    apply_all = apply_scope.split(
        "all)",
        1,
    )[1].split(
        ";;",
        1,
    )[0]

    assert "atlas_update_sports_prepare" in prepare_all
    assert "atlas_update_sports_apply" in apply_all

    assert (
        'atlas_command_module_run_script "sports" "update"'
        not in apply_scope
    )
