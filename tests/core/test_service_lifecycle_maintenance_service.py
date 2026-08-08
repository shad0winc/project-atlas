"""Tests for read-only Maintenance History orchestration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    ImageReference,
    MaintenanceAction,
    MaintenanceRecord,
    MaintenanceReport,
    MaintenanceResult,
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceLifecycleProvider,
    ServiceLifecycleService,
    ServiceMaintenanceHistoryService,
    ServiceRuntime,
    ServiceUpdate,
    UpdateStatus,
)


class HistoryProvider(ServiceLifecycleProvider):
    """Configurable provider for maintenance-history tests."""

    def __init__(self) -> None:
        self.services = (
            ManagedService(
                identifier="sonarr",
                name="Sonarr",
                provider="stub",
            ),
        )
        self.history: object = MaintenanceReport(
            records=(),
            provider="stub",
            generated_at="2026-08-02T03:00:00Z",
        )
        self.service_history: object = MaintenanceReport(
            records=(),
            provider="stub",
            generated_at="2026-08-02T03:00:00Z",
        )
        self.failure_method: str | None = None
        self.failure: Exception = RuntimeError("provider failed")
        self.calls: list[tuple[str, str | None]] = []

    def list_services(self):
        self.calls.append(("list_services", None))
        return self.services

    def inspect_service(self, identifier: str):
        self.calls.append(("inspect_service", identifier))
        return next(
            service
            for service in self.services
            if service.identifier == identifier
        )

    def inspect_runtime(self, identifier: str):
        return ServiceRuntime(
            state="running",
            health="healthy",
            image=ServiceImage(
                reference="example/service:stable",
            ),
        )

    def inspect_health(self, identifier: str):
        return ServiceHealth(
            status=ServiceHealthStatus.HEALTHY,
        )

    def inspect_update(self, identifier: str):
        service = self.inspect_service(identifier)
        return ServiceUpdate(
            service_identifier=service.identifier,
            service_name=service.name,
            current_image=ImageReference.parse(
                "example/service:stable"
            ),
            status=UpdateStatus.UNKNOWN,
        )

    def inspect_history(self):
        self.calls.append(("inspect_history", None))
        if self.failure_method == "inspect_history":
            raise self.failure
        return self.history

    def inspect_service_history(self, identifier: str):
        self.calls.append(("inspect_service_history", identifier))
        if self.failure_method == "inspect_service_history":
            raise self.failure
        return self.service_history


def make_record(
    *,
    identifier: str = "sonarr",
    name: str = "Sonarr",
) -> MaintenanceRecord:
    return MaintenanceRecord(
        service_identifier=identifier,
        service_name=name,
        action=MaintenanceAction.UPDATE_CHECK,
        result=MaintenanceResult.SUCCESS,
        started_at="2026-08-02T02:50:00Z",
        completed_at="2026-08-02T02:50:02Z",
        provider="stub",
    )


def make_service() -> tuple[
    ServiceMaintenanceHistoryService,
    HistoryProvider,
]:
    provider = HistoryProvider()
    lifecycle = ServiceLifecycleService(provider)
    return ServiceMaintenanceHistoryService(lifecycle), provider


def test_maintenance_service_is_immutable() -> None:
    service, _ = make_service()

    with pytest.raises(FrozenInstanceError):
        service.lifecycle = object()  # type: ignore[misc]


@pytest.mark.parametrize("value", [None, object(), "service"])
def test_maintenance_service_requires_lifecycle(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="lifecycle must be ServiceLifecycleService",
    ):
        ServiceMaintenanceHistoryService(  # type: ignore[arg-type]
            value
        )


def test_provider_default_history_is_empty() -> None:
    provider = HistoryProvider()

    report = ServiceLifecycleProvider.inspect_history(provider)

    assert report.records == ()
    assert report.provider == "unknown"


def test_provider_default_service_history_validates_identity() -> None:
    provider = HistoryProvider()

    report = ServiceLifecycleProvider.inspect_service_history(
        provider,
        "sonarr",
    )

    assert report.records == ()
    assert report.provider == "stub"
    assert provider.calls == [("inspect_service", "sonarr")]


def test_inspect_history_returns_validated_report() -> None:
    service, provider = make_service()
    report = MaintenanceReport(
        records=(make_record(),),
        provider="stub",
        generated_at="2026-08-02T03:00:00Z",
    )
    provider.history = report

    assert service.inspect_history() is report


def test_inspect_history_requires_report_contract() -> None:
    service, provider = make_service()
    provider.history = object()

    with pytest.raises(
        ServiceLifecycleError,
        match="provider maintenance history must return MaintenanceReport",
    ):
        service.inspect_history()


def test_inspect_history_preserves_domain_error() -> None:
    service, provider = make_service()
    provider.failure_method = "inspect_history"
    provider.failure = ServiceLifecycleError("known history failure")

    with pytest.raises(
        ServiceLifecycleError,
        match="known history failure",
    ):
        service.inspect_history()


def test_inspect_history_translates_unexpected_error() -> None:
    service, provider = make_service()
    provider.failure_method = "inspect_history"

    with pytest.raises(
        ServiceLifecycleError,
        match="service provider failed to inspect maintenance history",
    ):
        service.inspect_history()


def test_service_history_normalizes_identifier() -> None:
    service, provider = make_service()
    report = MaintenanceReport(
        records=(make_record(),),
        provider="stub",
        generated_at="2026-08-02T03:00:00Z",
    )
    provider.service_history = report

    assert service.inspect_service_history(" SONARR ") is report
    assert provider.calls == [
        ("inspect_service", "sonarr"),
        ("inspect_service_history", "sonarr"),
    ]


def test_service_history_requires_report_contract() -> None:
    service, provider = make_service()
    provider.service_history = object()

    with pytest.raises(
        ServiceLifecycleError,
        match="provider maintenance history must return MaintenanceReport",
    ):
        service.inspect_service_history("sonarr")


def test_service_history_requires_matching_identifier() -> None:
    service, provider = make_service()
    provider.service_history = MaintenanceReport(
        records=(
            make_record(
                identifier="radarr",
                name="Radarr",
            ),
        ),
        provider="stub",
        generated_at="2026-08-02T03:00:00Z",
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="mismatched maintenance service identifier",
    ):
        service.inspect_service_history("sonarr")


def test_service_history_requires_matching_name() -> None:
    service, provider = make_service()
    provider.service_history = MaintenanceReport(
        records=(
            make_record(name="Different"),
        ),
        provider="stub",
        generated_at="2026-08-02T03:00:00Z",
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="mismatched maintenance service name",
    ):
        service.inspect_service_history("sonarr")
