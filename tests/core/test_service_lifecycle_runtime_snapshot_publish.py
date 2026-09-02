from __future__ import annotations

from atlas.service_lifecycle import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceLifecycleProvider,
    ServiceRuntime,
)
from atlas.service_lifecycle.maintenance_models import (
    MaintenanceReport,
)
from atlas.service_lifecycle.runtime_snapshot import (
    RUNTIME_SNAPSHOT_SCHEMA_VERSION,
    build_runtime_snapshot,
)
from atlas.service_lifecycle.update_models import (
    ImageReference,
    ServiceUpdate,
    UpdateStatus,
)


class SnapshotProvider(ServiceLifecycleProvider):
    def __init__(self) -> None:
        self.service = ManagedService(
            identifier="jellyfin",
            name="Jellyfin",
            provider="docker-compose",
            compose_project="atlas",
            container_name="jellyfin",
        )

        self.runtime = ServiceRuntime(
            state="running",
            health="healthy",
            image=ServiceImage(
                reference="jellyfin/jellyfin:latest",
                repository="jellyfin/jellyfin",
                tag="latest",
                image_id="sha256:" + ("a" * 64),
            ),
        )

        self.health = ServiceHealth(
            status=ServiceHealthStatus.HEALTHY,
            score=100,
            evaluated_at=(
                "2026-08-29T02:40:00Z"
            ),
        )

        self.update = ServiceUpdate(
            service_identifier="jellyfin",
            service_name="Jellyfin",
            current_image=ImageReference(
                repository="jellyfin/jellyfin",
                tag="latest",
                raw_reference=(
                    "jellyfin/jellyfin:latest"
                ),
            ),
            status=UpdateStatus.CURRENT,
            evaluated_at=(
                "2026-08-29T02:40:00Z"
            ),
        )

    def list_services(self):
        return (self.service,)

    def inspect_service(self, identifier):
        self._validate(identifier)
        return self.service

    def inspect_runtime(self, identifier):
        self._validate(identifier)
        return self.runtime

    def inspect_health(self, identifier):
        self._validate(identifier)
        return self.health

    def inspect_update(self, identifier):
        self._validate(identifier)
        return self.update

    def inspect_history(self):
        return MaintenanceReport(
            records=(),
            provider="docker-compose",
            generated_at=(
                "2026-08-29T02:40:00Z"
            ),
        )

    def inspect_service_history(self, identifier):
        self._validate(identifier)
        return self.inspect_history()

    def _validate(self, identifier):
        if identifier != "jellyfin":
            raise ServiceLifecycleError(
                f"unknown service: {identifier}"
            )


def test_build_runtime_snapshot_serializes_contract():
    payload = build_runtime_snapshot(
        SnapshotProvider(),
        generated_at="2026-08-29T02:41:00Z",
    )

    assert payload["schema_version"] == (
        RUNTIME_SNAPSHOT_SCHEMA_VERSION
    )
    assert payload["generated_at"] == (
        "2026-08-29T02:41:00Z"
    )
    assert payload["provider"] == "docker-compose"

    services = payload["services"]

    assert isinstance(services, list)
    assert len(services) == 1

    entry = services[0]

    assert entry["service"]["identifier"] == (
        "jellyfin"
    )
    assert entry["runtime"]["state"] == "running"
    assert entry["health"]["status"] == "healthy"
    assert entry["update"]["status"] == "current"

    assert payload["history"]["provider"] == (
        "docker-compose"
    )


def test_build_runtime_snapshot_is_consumable_by_provider(
    tmp_path,
):
    from atlas.service_lifecycle.providers.runtime_snapshot import (
        RuntimeSnapshotProvider,
    )

    import json

    payload = build_runtime_snapshot(
        SnapshotProvider(),
        generated_at="2026-08-29T02:41:00Z",
    )

    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    provider = RuntimeSnapshotProvider(path)

    services = provider.list_services()

    assert tuple(
        service.identifier
        for service in services
    ) == ("jellyfin",)

    assert (
        provider.inspect_runtime(
            "jellyfin"
        ).state
        == "running"
    )

    assert (
        provider.inspect_health(
            "jellyfin"
        ).status.value
        == "healthy"
    )

    assert (
        provider.inspect_update(
            "jellyfin"
        ).status.value
        == "current"
    )


def test_build_runtime_snapshot_rejects_update_identity_mismatch():
    provider = SnapshotProvider()

    provider.update = ServiceUpdate(
        service_identifier="wrong",
        service_name="Jellyfin",
        current_image=provider.update.current_image,
        status=UpdateStatus.CURRENT,
        evaluated_at="2026-08-29T02:40:00Z",
    )

    import pytest

    with pytest.raises(
        ServiceLifecycleError,
        match="mismatched update identifier",
    ):
        build_runtime_snapshot(provider)


def test_build_runtime_snapshot_rejects_update_name_mismatch():
    provider = SnapshotProvider()

    provider.update = ServiceUpdate(
        service_identifier="jellyfin",
        service_name="Wrong Name",
        current_image=provider.update.current_image,
        status=UpdateStatus.CURRENT,
        evaluated_at="2026-08-29T02:40:00Z",
    )

    import pytest

    with pytest.raises(
        ServiceLifecycleError,
        match="mismatched update service name",
    ):
        build_runtime_snapshot(provider)
