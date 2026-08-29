from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.service_lifecycle import (
    ServiceLifecycleError,
)
from atlas.service_lifecycle.providers.runtime_snapshot import (
    RuntimeSnapshotProvider,
)


def snapshot_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-29T02:30:00Z",
        "provider": "docker-compose",
        "services": [
            {
                "service": {
                    "identifier": "jellyfin",
                    "name": "Jellyfin",
                    "provider": "docker-compose",
                    "enabled": True,
                    "compose_project": "atlas",
                    "container_name": "jellyfin",
                    "dependencies": [],
                    "created_at": None,
                    "updated_at": None,
                },
                "runtime": {
                    "state": "running",
                    "health": "healthy",
                    "running": True,
                    "healthy": True,
                    "image": {
                        "reference": "jellyfin/jellyfin:latest",
                        "repository": "jellyfin/jellyfin",
                        "tag": "latest",
                        "digest": None,
                        "image_id": "sha256:" + ("a" * 64),
                        "created_at": None,
                    },
                    "restart_count": 0,
                    "started_at": None,
                    "finished_at": None,
                    "exit_code": None,
                    "status_message": None,
                },
                "health": {
                    "status": "healthy",
                    "score": 100,
                    "healthy": True,
                    "action_required": False,
                    "warnings": [],
                    "errors": [],
                    "details": {},
                    "evaluated_at": "2026-08-29T02:30:00Z",
                },
                "update": {
                    "service_identifier": "jellyfin",
                    "service_name": "Jellyfin",
                    "status": "current",
                    "requires_attention": False,
                    "current_image": {
                        "repository": "jellyfin/jellyfin",
                        "tag": "latest",
                        "digest": None,
                        "raw_reference": (
                            "jellyfin/jellyfin:latest"
                        ),
                    },
                    "available_image": None,
                    "reason": None,
                    "details": {},
                    "evaluated_at": "2026-08-29T02:30:00Z",
                },
            },
        ],
        "history": {
            "provider": "docker-compose",
            "generated_at": "2026-08-29T02:30:00Z",
            "total_records": 0,
            "counts": {},
            "requires_attention": False,
            "records": [],
        },
    }


def write_snapshot(
    tmp_path: Path,
    payload: dict[str, object] | None = None,
) -> Path:
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps(
            payload if payload is not None
            else snapshot_payload()
        ),
        encoding="utf-8",
    )
    return path


def test_runtime_snapshot_provider_reads_service_contract(
    tmp_path: Path,
) -> None:
    provider = RuntimeSnapshotProvider(
        write_snapshot(tmp_path)
    )

    services = provider.list_services()

    assert len(services) == 1
    assert services[0].identifier == "jellyfin"
    assert services[0].name == "Jellyfin"

    detail = provider.inspect_service("jellyfin")
    assert detail.identifier == "jellyfin"

    runtime = provider.inspect_runtime("jellyfin")
    assert runtime.state == "running"
    assert runtime.health == "healthy"
    assert runtime.image.reference == (
        "jellyfin/jellyfin:latest"
    )

    health = provider.inspect_health("jellyfin")
    assert health.status.value == "healthy"
    assert health.score == 100

    update = provider.inspect_update("jellyfin")
    assert update.service_identifier == "jellyfin"
    assert update.status.value == "current"


def test_runtime_snapshot_provider_reads_history(
    tmp_path: Path,
) -> None:
    provider = RuntimeSnapshotProvider(
        write_snapshot(tmp_path)
    )

    history = provider.inspect_history()

    assert history.provider == "docker-compose"
    assert history.records == ()

    service_history = provider.inspect_service_history(
        "jellyfin"
    )

    assert service_history.records == ()


def test_runtime_snapshot_provider_rejects_unknown_service(
    tmp_path: Path,
) -> None:
    provider = RuntimeSnapshotProvider(
        write_snapshot(tmp_path)
    )

    with pytest.raises(ServiceLifecycleError):
        provider.inspect_service("missing")

    with pytest.raises(ServiceLifecycleError):
        provider.inspect_runtime("missing")

    with pytest.raises(ServiceLifecycleError):
        provider.inspect_health("missing")

    with pytest.raises(ServiceLifecycleError):
        provider.inspect_update("missing")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "schema_version": 2,
            "generated_at": "2026-08-29T02:30:00Z",
            "provider": "docker-compose",
            "services": [],
            "history": {
                "provider": "docker-compose",
                "generated_at": "2026-08-29T02:30:00Z",
                "records": [],
            },
        },
        {
            "schema_version": 1,
            "generated_at": "2026-08-29T02:30:00Z",
            "provider": "docker-compose",
            "services": "invalid",
            "history": {
                "provider": "docker-compose",
                "generated_at": "2026-08-29T02:30:00Z",
                "records": [],
            },
        },
    ],
)
def test_runtime_snapshot_provider_rejects_invalid_contract(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    provider = RuntimeSnapshotProvider(
        write_snapshot(tmp_path, payload)
    )

    with pytest.raises(ServiceLifecycleError):
        provider.list_services()


def test_runtime_snapshot_provider_rejects_missing_file(
    tmp_path: Path,
) -> None:
    provider = RuntimeSnapshotProvider(
        tmp_path / "missing.json"
    )

    with pytest.raises(ServiceLifecycleError):
        provider.list_services()


def test_runtime_snapshot_provider_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "latest.json"
    path.write_text("{not-json", encoding="utf-8")

    provider = RuntimeSnapshotProvider(path)

    with pytest.raises(ServiceLifecycleError):
        provider.list_services()


def test_runtime_snapshot_provider_has_no_docker_dependency() -> None:
    source = Path(
        "atlas/service_lifecycle/providers/"
        "runtime_snapshot.py"
    )

    if not source.exists():
        pytest.skip("provider not implemented yet")

    text = source.read_text(encoding="utf-8")

    forbidden = (
        "subprocess",
        "docker.sock",
        "DOCKER_HOST",
        "DockerComposeProvider",
        "docker compose",
    )

    for value in forbidden:
        assert value not in text
