"""Tests for provider-independent Service Lifecycle update orchestration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    ImageReference,
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceLifecycleProvider,
    ServiceLifecycleService,
    ServiceRuntime,
    ServiceUpdate,
    ServiceUpdateService,
    UpdateReport,
    UpdateStatus,
)


class UpdateProvider(ServiceLifecycleProvider):
    """Configurable provider for update-service contracts."""

    def __init__(self) -> None:
        self.services: tuple[ManagedService, ...] = ()
        self.updates: dict[str, object] = {}
        self.calls: list[tuple[str, str | None]] = []
        self.failure_method: str | None = None
        self.failure: Exception = RuntimeError("provider failed")

    def list_services(self):
        self.calls.append(("list_services", None))
        if self.failure_method == "list_services":
            raise self.failure
        return self.services

    def inspect_service(self, identifier: str):
        self.calls.append(("inspect_service", identifier))
        if self.failure_method == "inspect_service":
            raise self.failure
        return next(
            service
            for service in self.services
            if service.identifier == identifier
        )

    def inspect_runtime(self, identifier: str):
        self.calls.append(("inspect_runtime", identifier))
        return ServiceRuntime(
            state="running",
            health="healthy",
            image=ServiceImage(
                reference="example/service:stable",
                repository="example/service",
                tag="stable",
            ),
        )

    def inspect_health(self, identifier: str):
        self.calls.append(("inspect_health", identifier))
        return ServiceHealth(
            status=ServiceHealthStatus.HEALTHY,
        )

    def inspect_update(self, identifier: str):
        self.calls.append(("inspect_update", identifier))
        if self.failure_method == "inspect_update":
            raise self.failure
        return self.updates[identifier]


def managed(
    identifier: str,
    *,
    name: str | None = None,
    provider: str = "stub",
) -> ManagedService:
    return ManagedService(
        identifier=identifier,
        name=name or identifier.replace("-", " ").title(),
        provider=provider,
    )


def update_for(
    service: ManagedService,
    *,
    status: UpdateStatus = UpdateStatus.UNKNOWN,
) -> ServiceUpdate:
    return ServiceUpdate(
        service_identifier=service.identifier,
        service_name=service.name,
        current_image=ImageReference.parse(
            "example/service:stable"
        ),
        status=status,
        available_image=(
            ImageReference.parse("example/service:next")
            if status is UpdateStatus.UPDATE_AVAILABLE
            else None
        ),
        evaluated_at="2026-08-02T01:50:00Z",
    )


def make_update_service(
    services: tuple[ManagedService, ...] = (),
) -> tuple[ServiceUpdateService, UpdateProvider]:
    provider = UpdateProvider()
    provider.services = services
    provider.updates = {
        service.identifier: update_for(service)
        for service in services
    }
    lifecycle = ServiceLifecycleService(provider)
    return ServiceUpdateService(lifecycle), provider


def test_update_service_is_immutable() -> None:
    service, _ = make_update_service()

    with pytest.raises(FrozenInstanceError):
        service.lifecycle = object()  # type: ignore[misc]


@pytest.mark.parametrize(
    "value",
    [None, object(), "service"],
)
def test_update_service_requires_lifecycle(value: object) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="lifecycle must be ServiceLifecycleService",
    ):
        ServiceUpdateService(value)  # type: ignore[arg-type]


def test_inspect_update_normalizes_identity() -> None:
    sonarr = managed("sonarr", name="Sonarr")
    service, provider = make_update_service((sonarr,))

    result = service.inspect_update(" SONARR ")

    assert result is provider.updates["sonarr"]
    assert provider.calls == [
        ("inspect_service", "sonarr"),
        ("inspect_update", "sonarr"),
    ]


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, True, 42, object()],
)
def test_inspect_update_requires_identifier(value: object) -> None:
    service, _ = make_update_service()

    with pytest.raises(ServiceLifecycleError):
        service.inspect_update(value)  # type: ignore[arg-type]


def test_inspect_update_requires_service_update_result() -> None:
    sonarr = managed("sonarr")
    service, provider = make_update_service((sonarr,))
    provider.updates["sonarr"] = object()

    with pytest.raises(
        ServiceLifecycleError,
        match="provider update inspection must return ServiceUpdate",
    ):
        service.inspect_update("sonarr")


def test_inspect_update_requires_matching_identifier() -> None:
    sonarr = managed("sonarr")
    radarr = managed("radarr")
    service, provider = make_update_service((sonarr,))
    provider.updates["sonarr"] = update_for(radarr)

    with pytest.raises(
        ServiceLifecycleError,
        match="provider returned mismatched update identifier",
    ):
        service.inspect_update("sonarr")


def test_inspect_update_requires_matching_service_name() -> None:
    sonarr = managed("sonarr", name="Sonarr")
    service, provider = make_update_service((sonarr,))
    provider.updates["sonarr"] = ServiceUpdate(
        service_identifier="sonarr",
        service_name="Different",
        current_image=ImageReference.parse(
            "example/service:stable"
        ),
        status=UpdateStatus.UNKNOWN,
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="provider returned mismatched update service name",
    ):
        service.inspect_update("sonarr")


def test_inspect_update_preserves_domain_error() -> None:
    sonarr = managed("sonarr")
    service, provider = make_update_service((sonarr,))
    provider.failure_method = "inspect_update"
    provider.failure = ServiceLifecycleError("known failure")

    with pytest.raises(
        ServiceLifecycleError,
        match="known failure",
    ):
        service.inspect_update("sonarr")


def test_inspect_update_translates_unexpected_failure() -> None:
    sonarr = managed("sonarr")
    service, provider = make_update_service((sonarr,))
    provider.failure_method = "inspect_update"

    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "service provider failed to inspect update: sonarr"
        ),
    ):
        service.inspect_update("sonarr")


def test_inspect_updates_empty_inventory_is_explicit() -> None:
    service, provider = make_update_service()

    report = service.inspect_updates()

    assert isinstance(report, UpdateReport)
    assert report.updates == ()
    assert report.provider == "unknown"
    assert report.status == "current"
    assert report.to_dict()["total_services"] == 0
    assert provider.calls == [("list_services", None)]


def test_inspect_updates_aggregates_all_services() -> None:
    sonarr = managed("sonarr", name="Sonarr")
    radarr = managed("radarr", name="Radarr")
    service, provider = make_update_service((sonarr, radarr))
    provider.updates["sonarr"] = update_for(
        sonarr,
        status=UpdateStatus.MUTABLE_TAG,
    )
    provider.updates["radarr"] = update_for(
        radarr,
        status=UpdateStatus.CURRENT,
    )

    report = service.inspect_updates()

    assert report.provider == "stub"
    assert report.status == "attention"
    assert report.counts["mutable-tag"] == 1
    assert report.counts["current"] == 1
    assert tuple(
        item.service_identifier
        for item in report.updates
    ) == ("sonarr", "radarr")
    assert provider.calls == [
        ("list_services", None),
        ("inspect_update", "radarr"),
        ("inspect_update", "sonarr"),
    ]


def test_inspect_updates_uses_deterministic_report_order() -> None:
    current = managed("current")
    unknown = managed("unknown")
    mutable = managed("mutable")
    available = managed("available")
    service, provider = make_update_service(
        (current, unknown, mutable, available),
    )
    provider.updates = {
        current.identifier: update_for(
            current,
            status=UpdateStatus.CURRENT,
        ),
        unknown.identifier: update_for(
            unknown,
            status=UpdateStatus.UNKNOWN,
        ),
        mutable.identifier: update_for(
            mutable,
            status=UpdateStatus.MUTABLE_TAG,
        ),
        available.identifier: update_for(
            available,
            status=UpdateStatus.UPDATE_AVAILABLE,
        ),
    }

    report = service.inspect_updates()

    assert tuple(
        item.service_identifier
        for item in report.updates
    ) == (
        "available",
        "mutable",
        "unknown",
        "current",
    )


def test_inspect_updates_reports_mixed_provider() -> None:
    sonarr = managed(
        "sonarr",
        provider="docker-compose",
    )
    external = managed(
        "external",
        provider="external",
    )
    service, _ = make_update_service((sonarr, external))

    report = service.inspect_updates()

    assert report.provider == "mixed"


def test_inspect_updates_validates_each_provider_result() -> None:
    sonarr = managed("sonarr")
    radarr = managed("radarr")
    service, provider = make_update_service((sonarr, radarr))
    provider.updates["radarr"] = object()

    with pytest.raises(
        ServiceLifecycleError,
        match="provider update inspection must return ServiceUpdate",
    ):
        service.inspect_updates()


def test_inspect_updates_preserves_list_domain_error() -> None:
    service, provider = make_update_service()
    provider.failure_method = "list_services"
    provider.failure = ServiceLifecycleError("known list failure")

    with pytest.raises(
        ServiceLifecycleError,
        match="known list failure",
    ):
        service.inspect_updates()


def test_inspect_updates_translates_list_failure() -> None:
    service, provider = make_update_service()
    provider.failure_method = "list_services"

    with pytest.raises(
        ServiceLifecycleError,
        match="service provider failed to list services",
    ):
        service.inspect_updates()


def test_update_report_serialization_is_preserved() -> None:
    sonarr = managed("sonarr", name="Sonarr")
    service, provider = make_update_service((sonarr,))
    provider.updates["sonarr"] = update_for(
        sonarr,
        status=UpdateStatus.MUTABLE_TAG,
    )

    payload = service.inspect_updates().to_dict()

    assert payload["provider"] == "stub"
    assert payload["status"] == "attention"
    assert payload["requires_attention"] is True
    assert payload["counts"]["mutable-tag"] == 1
    assert payload["updates"][0]["service_identifier"] == "sonarr"
