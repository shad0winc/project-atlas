"""Contract tests for ServiceLifecycleService."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceLifecycleProvider,
    ServiceLifecycleService,
    ServiceRuntime,
)


class StubProvider(ServiceLifecycleProvider):
    """Configurable provider for service-layer contracts."""

    def __init__(self) -> None:
        self.services: object = ()
        self.service: object = ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="stub",
        )
        self.runtime: object = ServiceRuntime(
            state="running",
            health="healthy",
            image=ServiceImage(
                reference="sonarr:latest",
            ),
        )
        self.health: object = ServiceHealth(
            status=ServiceHealthStatus.HEALTHY,
        )
        self.failure: Exception | None = None
        self.calls: list[tuple[str, str | None]] = []

    def _raise_failure(self) -> None:
        if self.failure is not None:
            raise self.failure

    def list_services(self):
        self.calls.append(("list_services", None))
        self._raise_failure()
        return self.services

    def inspect_service(self, identifier: str):
        self.calls.append(("inspect_service", identifier))
        self._raise_failure()
        return self.service

    def inspect_runtime(self, identifier: str):
        self.calls.append(("inspect_runtime", identifier))
        self._raise_failure()
        return self.runtime

    def inspect_health(self, identifier: str):
        self.calls.append(("inspect_health", identifier))
        self._raise_failure()
        return self.health


def make_service() -> tuple[ServiceLifecycleService, StubProvider]:
    provider = StubProvider()

    return (
        ServiceLifecycleService(provider),
        provider,
    )


def test_service_requires_provider_contract() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="provider must implement ServiceLifecycleProvider",
    ):
        ServiceLifecycleService(
            provider=object(),  # type: ignore[arg-type]
        )


def test_service_is_immutable() -> None:
    service, provider = make_service()

    with pytest.raises(FrozenInstanceError):
        service.provider = provider  # type: ignore[misc]


def test_list_services_validates_sorts_and_returns_tuple() -> None:
    service, provider = make_service()

    provider.services = [
        ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="stub",
        ),
        ManagedService(
            identifier="bazarr",
            name="Bazarr",
            provider="stub",
        ),
        ManagedService(
            identifier="radarr",
            name="Radarr",
            provider="stub",
        ),
    ]

    result = service.list_services()

    assert isinstance(result, tuple)
    assert tuple(item.identifier for item in result) == (
        "bazarr",
        "radarr",
        "sonarr",
    )


@pytest.mark.parametrize(
    "value",
    [
        "sonarr",
        b"sonarr",
        None,
        42,
        True,
        object(),
    ],
)
def test_list_services_requires_collection(
    value: object,
) -> None:
    service, provider = make_service()
    provider.services = value

    with pytest.raises(
        ServiceLifecycleError,
        match="provider services must be a collection",
    ):
        service.list_services()


def test_list_services_requires_managed_service_children() -> None:
    service, provider = make_service()
    provider.services = [
        "sonarr",
    ]

    with pytest.raises(
        ServiceLifecycleError,
        match="must contain ManagedService objects",
    ):
        service.list_services()


def test_list_services_rejects_duplicate_identifiers() -> None:
    service, provider = make_service()
    provider.services = [
        ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="stub",
        ),
        ManagedService(
            identifier="sonarr",
            name="Sonarr Duplicate",
            provider="stub",
        ),
    ]

    with pytest.raises(
        ServiceLifecycleError,
        match="duplicate service identifier: sonarr",
    ):
        service.list_services()


@pytest.mark.parametrize(
    ("method_name", "expected_call"),
    [
        (
            "inspect_service",
            "inspect_service",
        ),
        (
            "inspect_runtime",
            "inspect_runtime",
        ),
        (
            "inspect_health",
            "inspect_health",
        ),
    ],
)
def test_inspection_methods_normalize_identifier(
    method_name: str,
    expected_call: str,
) -> None:
    service, provider = make_service()
    method = getattr(service, method_name)

    method("  SONARR  ")

    assert provider.calls == [
        (
            expected_call,
            "sonarr",
        ),
    ]


@pytest.mark.parametrize(
    "method_name",
    [
        "inspect_service",
        "inspect_runtime",
        "inspect_health",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        42,
        object(),
    ],
)
def test_inspection_methods_require_identifier(
    method_name: str,
    value: object,
) -> None:
    service, _ = make_service()
    method = getattr(service, method_name)

    with pytest.raises(
        ServiceLifecycleError,
        match="service identifier must be non-empty text",
    ):
        method(value)


@pytest.mark.parametrize(
    "method_name",
    [
        "inspect_service",
        "inspect_runtime",
        "inspect_health",
    ],
)
def test_inspection_methods_reject_malformed_identifier(
    method_name: str,
) -> None:
    service, _ = make_service()
    method = getattr(service, method_name)

    with pytest.raises(
        ServiceLifecycleError,
        match="invalid service identifier",
    ):
        method("sonarr/api")


def test_inspect_service_requires_managed_service_result() -> None:
    service, provider = make_service()
    provider.service = "sonarr"

    with pytest.raises(
        ServiceLifecycleError,
        match="must return ManagedService",
    ):
        service.inspect_service("sonarr")


def test_inspect_service_requires_matching_identity() -> None:
    service, provider = make_service()
    provider.service = ManagedService(
        identifier="radarr",
        name="Radarr",
        provider="stub",
    )

    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "expected sonarr, received radarr"
        ),
    ):
        service.inspect_service("sonarr")


def test_inspect_runtime_requires_runtime_result() -> None:
    service, provider = make_service()
    provider.runtime = "running"

    with pytest.raises(
        ServiceLifecycleError,
        match="must return ServiceRuntime",
    ):
        service.inspect_runtime("sonarr")


def test_inspect_health_requires_health_result() -> None:
    service, provider = make_service()
    provider.health = "healthy"

    with pytest.raises(
        ServiceLifecycleError,
        match="must return ServiceHealth",
    ):
        service.inspect_health("sonarr")


@pytest.mark.parametrize(
    "method_name",
    [
        "list_services",
        "inspect_service",
        "inspect_runtime",
        "inspect_health",
    ],
)
def test_service_preserves_known_domain_errors(
    method_name: str,
) -> None:
    service, provider = make_service()
    provider.failure = ServiceLifecycleError(
        "known provider failure",
    )
    method = getattr(service, method_name)

    arguments = (
        ()
        if method_name == "list_services"
        else ("sonarr",)
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="known provider failure",
    ):
        method(*arguments)


@pytest.mark.parametrize(
    ("method_name", "expected_message"),
    [
        (
            "list_services",
            "service provider failed to list services",
        ),
        (
            "inspect_service",
            "service provider failed to inspect service: sonarr",
        ),
        (
            "inspect_runtime",
            "service provider failed to inspect runtime: sonarr",
        ),
        (
            "inspect_health",
            "service provider failed to inspect health: sonarr",
        ),
    ],
)
def test_service_translates_unexpected_provider_failure(
    method_name: str,
    expected_message: str,
) -> None:
    service, provider = make_service()
    provider.failure = RuntimeError(
        "unexpected",
    )
    method = getattr(service, method_name)

    arguments = (
        ()
        if method_name == "list_services"
        else ("sonarr",)
    )

    with pytest.raises(
        ServiceLifecycleError,
        match=expected_message,
    ) as exc_info:
        method(*arguments)

    assert isinstance(
        exc_info.value.__cause__,
        RuntimeError,
    )


def test_inspect_health_report_aggregates_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = [
        ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="stub",
        ),
        ManagedService(
            identifier="bazarr",
            name="Bazarr",
            provider="stub",
        ),
    ]
    health_by_identifier = {
        "bazarr": ServiceHealth(
            status=ServiceHealthStatus.DEGRADED,
            score=80,
            warnings=("No Docker health check configured",),
        ),
        "sonarr": ServiceHealth(
            status=ServiceHealthStatus.HEALTHY,
            score=100,
        ),
    }

    def inspect_health(identifier: str):
        provider.calls.append(("inspect_health", identifier))
        return health_by_identifier[identifier]

    provider.inspect_health = inspect_health  # type: ignore[method-assign]
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T20:30:00Z",
    )

    report = service.inspect_health_report()

    assert report.score == 90
    assert report.status == "healthy"
    assert report.counts == {
        "healthy": 1,
        "degraded": 1,
        "unhealthy": 0,
        "unknown": 0,
    }
    assert tuple(
        entry.service.identifier
        for entry in report.entries
    ) == ("bazarr", "sonarr")
    assert tuple(
        entry.service.identifier
        for entry in report.attention
    ) == ("bazarr",)
    assert report.warnings == (
        "bazarr: No Docker health check configured",
    )
    assert report.errors == ()
    assert report.evaluated_at == "2026-08-01T20:30:00Z"
    assert provider.calls == [
        ("list_services", None),
        ("inspect_health", "bazarr"),
        ("inspect_health", "sonarr"),
    ]


def test_inspect_health_report_errors_force_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = [provider.service]
    provider.health = ServiceHealth(
        status=ServiceHealthStatus.DEGRADED,
        score=95,
        errors=("Container restart loop detected",),
    )
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T20:30:00Z",
    )

    report = service.inspect_health_report()

    assert report.score == 95
    assert report.status == "unhealthy"
    assert report.errors == (
        "sonarr: Container restart loop detected",
    )


def test_inspect_health_report_empty_inventory_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = ()
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T20:30:00Z",
    )

    report = service.inspect_health_report()

    assert report.score == 0
    assert report.status == "unknown"
    assert report.counts == {
        "healthy": 0,
        "degraded": 0,
        "unhealthy": 0,
        "unknown": 0,
    }
    assert report.entries == ()
    assert report.attention == ()



def test_inspect_summary_aggregates_runtime_and_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = [
        ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="docker-compose",
            compose_project="project-atlas",
        ),
        ManagedService(
            identifier="bazarr",
            name="Bazarr",
            provider="docker-compose",
            compose_project="project-atlas",
            enabled=False,
        ),
    ]
    runtime_by_identifier = {
        "bazarr": ServiceRuntime(
            state="exited",
            health="unknown",
            image=ServiceImage(reference="bazarr:latest"),
            exit_code=0,
        ),
        "sonarr": ServiceRuntime(
            state="running",
            health="healthy",
            image=ServiceImage(reference="sonarr:latest"),
            exit_code=0,
        ),
    }
    health_by_identifier = {
        "bazarr": ServiceHealth(
            status=ServiceHealthStatus.DEGRADED,
            score=80,
            warnings=("Stopped",),
        ),
        "sonarr": ServiceHealth(
            status=ServiceHealthStatus.HEALTHY,
            score=100,
        ),
    }

    def inspect_runtime(identifier: str):
        provider.calls.append(("inspect_runtime", identifier))
        return runtime_by_identifier[identifier]

    def inspect_health(identifier: str):
        provider.calls.append(("inspect_health", identifier))
        return health_by_identifier[identifier]

    provider.inspect_runtime = inspect_runtime  # type: ignore[method-assign]
    provider.inspect_health = inspect_health  # type: ignore[method-assign]
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T22:00:00Z",
    )

    summary = service.inspect_summary()

    assert summary.provider == "docker-compose"
    assert summary.compose_project == "project-atlas"
    assert summary.enabled_counts == {"enabled": 1, "disabled": 1}
    assert summary.runtime_counts == {
        "running": 1,
        "stopped": 1,
        "restarting": 0,
        "failed": 0,
        "unknown": 0,
    }
    assert summary.health.score == 90
    assert summary.health.status == "healthy"
    assert summary.evaluated_at == "2026-08-01T22:00:00Z"
    assert summary.to_dict()["total_services"] == 2
    assert provider.calls == [
        ("list_services", None),
        ("inspect_runtime", "bazarr"),
        ("inspect_runtime", "sonarr"),
        ("inspect_health", "bazarr"),
        ("inspect_health", "sonarr"),
    ]


def test_inspect_summary_empty_inventory_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = ()
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T22:00:00Z",
    )

    summary = service.inspect_summary()

    assert summary.provider == "unknown"
    assert summary.compose_project is None
    assert summary.runtime_counts == {
        "running": 0,
        "stopped": 0,
        "restarting": 0,
        "failed": 0,
        "unknown": 0,
    }
    assert summary.health.status == "unknown"
    assert summary.health.score == 0


def test_runtime_entry_classifies_nonzero_exit_as_failed() -> None:
    from atlas.service_lifecycle.service import ServiceRuntimeEntry

    entry = ServiceRuntimeEntry(
        service=ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="stub",
        ),
        runtime=ServiceRuntime(
            state="exited",
            health="unknown",
            image=ServiceImage(reference="sonarr:latest"),
            exit_code=1,
        ),
    )

    assert entry.category == "failed"

def test_service_package_export() -> None:
    from atlas import service_lifecycle

    assert (
        service_lifecycle.ServiceLifecycleService
        is ServiceLifecycleService
    )

def test_inspect_graph_builds_resolved_reverse_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = [
        ManagedService(
            identifier="jellyfin",
            name="Jellyfin",
            provider="docker-compose",
            compose_project="project-atlas",
        ),
        ManagedService(
            identifier="jellyseerr",
            name="Jellyseerr",
            provider="docker-compose",
            compose_project="project-atlas",
            dependencies=("jellyfin", "radarr"),
        ),
        ManagedService(
            identifier="radarr",
            name="Radarr",
            provider="docker-compose",
            compose_project="project-atlas",
        ),
        ManagedService(
            identifier="bazarr",
            name="Bazarr",
            provider="docker-compose",
            compose_project="project-atlas",
        ),
    ]
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T23:15:00Z",
    )

    graph = service.inspect_graph()

    assert graph.provider == "docker-compose"
    assert graph.compose_project == "project-atlas"
    assert graph.edge_count == 2
    assert tuple(node.service.identifier for node in graph.roots) == (
        "jellyfin",
        "radarr",
    )
    assert tuple(
        item.identifier
        for item in graph.node("jellyfin").dependents
    ) == ("jellyseerr",)
    assert tuple(
        item.identifier
        for item in graph.node("jellyseerr").dependencies
    ) == ("jellyfin", "radarr")
    assert tuple(
        node.service.identifier
        for node in graph.standalone
    ) == ("bazarr",)
    assert graph.unresolved == ()
    assert graph.evaluated_at == "2026-08-01T23:15:00Z"
    assert provider.calls == [("list_services", None)]


def test_inspect_graph_preserves_unresolved_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = [
        ManagedService(
            identifier="qbittorrent",
            name="Qbittorrent",
            provider="docker-compose",
            dependencies=("gluetun",),
        ),
    ]
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T23:15:00Z",
    )

    graph = service.inspect_graph()

    assert graph.edge_count == 0
    assert graph.roots == ()
    assert graph.standalone == ()
    assert tuple(
        node.service.identifier
        for node in graph.unresolved
    ) == ("qbittorrent",)
    assert graph.node("qbittorrent").unresolved_dependencies == (
        "gluetun",
    )
    assert graph.to_dict()["unresolved"][0][
        "unresolved_dependencies"
    ] == ["gluetun"]


def test_inspect_graph_empty_inventory_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, provider = make_service()
    provider.services = ()
    monkeypatch.setattr(
        "atlas.service_lifecycle.service._utc_now",
        lambda: "2026-08-01T23:15:00Z",
    )

    graph = service.inspect_graph()

    assert graph.provider == "unknown"
    assert graph.compose_project is None
    assert graph.nodes == ()
    assert graph.roots == ()
    assert graph.standalone == ()
    assert graph.edge_count == 0


def test_dependency_graph_node_rejects_self_reference() -> None:
    from atlas.service_lifecycle.service import ServiceDependencyNode

    managed_service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="stub",
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="cannot reference themselves",
    ):
        ServiceDependencyNode(
            service=managed_service,
            dependencies=(managed_service,),
        )
