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
