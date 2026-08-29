from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_api_uses_runtime_snapshot_provider() -> None:
    text = (
        ROOT
        / "apps/api/atlas_api/dependencies.py"
    ).read_text(encoding="utf-8")

    assert "RuntimeSnapshotProvider" in text
    assert (
        "ATLAS_SERVICE_LIFECYCLE_SNAPSHOT_PATH"
        in text
    )

    factory = text.split(
        "def get_service_lifecycle_service()",
        1,
    )[1].split(
        "def get_service_update_service()",
        1,
    )[0]

    assert "DockerComposeProvider" not in factory
    assert "/opt/project-atlas" not in factory


def test_api_mount_is_bounded_read_only() -> None:
    text = (
        ROOT / "stack/ingress.yml"
    ).read_text(encoding="utf-8")

    mount = (
        "/mnt/storage/configs/atlas/runtime/services:"
        "/mnt/storage/configs/atlas/runtime/services:ro"
    )

    assert mount in text

    assert (
        'ATLAS_SERVICE_LIFECYCLE_SNAPSHOT_PATH: '
        '"/mnt/storage/configs/atlas/runtime/'
        'services/latest.json"'
    ) in text


def test_api_does_not_gain_docker_control_plane() -> None:
    text = (
        ROOT / "stack/ingress.yml"
    ).read_text(encoding="utf-8")

    api = text.split(
        "\n  api:\n",
        1,
    )[1].split(
        "\n  identity-writer:\n",
        1,
    )[0]

    assert "/var/run/docker.sock" not in api
    assert "atlas-docker-api" not in api
    assert "DOCKER_HOST" not in api


def test_service_runtime_command_is_dispatch_only() -> None:
    command = (
        ROOT
        / "scripts/commands/service-runtime.sh"
    ).read_text(encoding="utf-8")

    assert "atlas-service-runtime.sh" in command
    assert "docker.sock" not in command


def test_runtime_publisher_uses_host_provider() -> None:
    text = (
        ROOT / "scripts/atlas-service-runtime.sh"
    ).read_text(encoding="utf-8")

    assert "DockerComposeProvider" in text
    assert "build_runtime_snapshot" in text
    assert "publish_runtime_snapshot" in text


def test_runtime_publisher_has_no_recursive_permissions() -> None:
    text = (
        ROOT / "scripts/atlas-service-runtime.sh"
    ).read_text(encoding="utf-8")

    forbidden = (
        "chmod -R",
        "chown -R",
        "find /mnt/storage",
    )

    for value in forbidden:
        assert value not in text
