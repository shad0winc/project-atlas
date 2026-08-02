"""Provider-independent orchestration for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from ..models import (
    ManagedService,
    ServiceHealth,
    ServiceLifecycleError,
    ServiceRuntime,
)
from ..provider import ServiceLifecycleProvider


@dataclass(frozen=True)
class ServiceHealthEntry:
    """Pair one managed-service identity with its health evaluation."""

    service: ManagedService
    health: ServiceHealth

    def __post_init__(self) -> None:
        if not isinstance(self.service, ManagedService):
            raise ServiceLifecycleError(
                "aggregate health entries require ManagedService identities",
            )
        if not isinstance(self.health, ServiceHealth):
            raise ServiceLifecycleError(
                "aggregate health entries require ServiceHealth evaluations",
            )

    @property
    def requires_attention(self) -> bool:
        return (
            self.health.action_required
            or bool(self.health.warnings)
            or bool(self.health.errors)
            or self.health.status.value != "healthy"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "service": self.service.to_dict(),
            "health": self.health.to_dict(),
            "requires_attention": self.requires_attention,
        }


@dataclass(frozen=True)
class InfrastructureHealthReport:
    """Normalized aggregate health for all Atlas-managed services."""

    entries: tuple[ServiceHealthEntry, ...]
    score: int
    status: str
    evaluated_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple) or any(
            not isinstance(entry, ServiceHealthEntry)
            for entry in self.entries
        ):
            raise ServiceLifecycleError(
                "aggregate health entries must be a tuple of ServiceHealthEntry",
            )
        if not isinstance(self.score, int) or isinstance(self.score, bool):
            raise ServiceLifecycleError(
                "aggregate health score must be an integer",
            )
        if not 0 <= self.score <= 100:
            raise ServiceLifecycleError(
                "aggregate health score must be between 0 and 100",
            )
        if self.status not in {
            "healthy",
            "degraded",
            "unhealthy",
            "unknown",
        }:
            raise ServiceLifecycleError(
                "aggregate health status is invalid",
            )
        if not isinstance(self.evaluated_at, str) or not self.evaluated_at:
            raise ServiceLifecycleError(
                "aggregate health evaluated_at must be non-empty text",
            )

    @property
    def counts(self) -> dict[str, int]:
        counts = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0,
        }
        for entry in self.entries:
            counts[entry.health.status.value] += 1
        return counts

    @property
    def attention(self) -> tuple[ServiceHealthEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if entry.requires_attention
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(
            f"{entry.service.identifier}: {warning}"
            for entry in self.entries
            for warning in entry.health.warnings
        )

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(
            f"{entry.service.identifier}: {error}"
            for entry in self.entries
            for error in entry.health.errors
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "score": self.score,
            "total_services": len(self.entries),
            "counts": self.counts,
            "attention_required": [
                entry.to_dict()
                for entry in self.attention
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "services": [
                entry.to_dict()
                for entry in self.entries
            ],
            "evaluated_at": self.evaluated_at,
        }


@dataclass(frozen=True)
class ServiceRuntimeEntry:
    """Pair one managed-service identity with its runtime inspection."""

    service: ManagedService
    runtime: ServiceRuntime

    def __post_init__(self) -> None:
        if not isinstance(self.service, ManagedService):
            raise ServiceLifecycleError(
                "infrastructure summary entries require ManagedService identities",
            )
        if not isinstance(self.runtime, ServiceRuntime):
            raise ServiceLifecycleError(
                "infrastructure summary entries require ServiceRuntime inspections",
            )

    @property
    def category(self) -> str:
        state = self.runtime.state.casefold()

        if state == "running":
            return "running"
        if state == "restarting":
            return "restarting"
        if state in {"dead", "failed"}:
            return "failed"
        if (
            self.runtime.exit_code not in {None, 0}
            and state not in {"running", "restarting"}
        ):
            return "failed"
        if state in {"created", "exited", "paused", "removing", "stopped"}:
            return "stopped"
        return "unknown"

    def to_dict(self) -> dict[str, object]:
        return {
            "service": self.service.to_dict(),
            "runtime": self.runtime.to_dict(),
            "category": self.category,
        }


@dataclass(frozen=True)
class InfrastructureSummary:
    """Normalized operational summary for Atlas-managed infrastructure."""

    runtime_entries: tuple[ServiceRuntimeEntry, ...]
    health: InfrastructureHealthReport
    evaluated_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_entries, tuple) or any(
            not isinstance(entry, ServiceRuntimeEntry)
            for entry in self.runtime_entries
        ):
            raise ServiceLifecycleError(
                "infrastructure runtime entries must be a tuple of ServiceRuntimeEntry",
            )
        if not isinstance(self.health, InfrastructureHealthReport):
            raise ServiceLifecycleError(
                "infrastructure summary health must be InfrastructureHealthReport",
            )
        if not isinstance(self.evaluated_at, str) or not self.evaluated_at:
            raise ServiceLifecycleError(
                "infrastructure summary evaluated_at must be non-empty text",
            )

        runtime_ids = tuple(
            entry.service.identifier
            for entry in self.runtime_entries
        )
        health_ids = tuple(
            entry.service.identifier
            for entry in self.health.entries
        )
        if runtime_ids != health_ids:
            raise ServiceLifecycleError(
                "infrastructure summary runtime and health identities must match",
            )

    @property
    def services(self) -> tuple[ManagedService, ...]:
        return tuple(entry.service for entry in self.runtime_entries)

    @property
    def provider(self) -> str:
        values = sorted({service.provider for service in self.services})
        if not values:
            return "unknown"
        if len(values) == 1:
            return values[0]
        return "mixed"

    @property
    def compose_project(self) -> str | None:
        values = sorted(
            {
                service.compose_project
                for service in self.services
                if service.compose_project is not None
            }
        )
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return "mixed"

    @property
    def enabled_counts(self) -> dict[str, int]:
        enabled = sum(1 for service in self.services if service.enabled)
        return {
            "enabled": enabled,
            "disabled": len(self.services) - enabled,
        }

    @property
    def runtime_counts(self) -> dict[str, int]:
        counts = {
            "running": 0,
            "stopped": 0,
            "restarting": 0,
            "failed": 0,
            "unknown": 0,
        }
        for entry in self.runtime_entries:
            counts[entry.category] += 1
        return counts

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "compose_project": self.compose_project,
            "total_services": len(self.services),
            "service_counts": self.enabled_counts,
            "runtime_counts": self.runtime_counts,
            "health_counts": self.health.counts,
            "score": self.health.score,
            "status": self.health.status,
            "attention_required": [
                entry.to_dict()
                for entry in self.health.attention
            ],
            "services": [
                entry.to_dict()
                for entry in self.runtime_entries
            ],
            "evaluated_at": self.evaluated_at,
        }


@dataclass(frozen=True)
class ServiceDependencyNode:
    """Normalized dependency relationships for one managed service."""

    service: ManagedService
    dependencies: tuple[ManagedService, ...] = ()
    dependents: tuple[ManagedService, ...] = ()
    unresolved_dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.service, ManagedService):
            raise ServiceLifecycleError(
                "dependency graph nodes require ManagedService identities",
            )
        if not isinstance(self.dependencies, tuple) or any(
            not isinstance(item, ManagedService)
            for item in self.dependencies
        ):
            raise ServiceLifecycleError(
                "dependency graph dependencies must be a tuple of ManagedService",
            )
        if not isinstance(self.dependents, tuple) or any(
            not isinstance(item, ManagedService)
            for item in self.dependents
        ):
            raise ServiceLifecycleError(
                "dependency graph dependents must be a tuple of ManagedService",
            )
        if not isinstance(self.unresolved_dependencies, tuple) or any(
            not isinstance(item, str) or not item
            for item in self.unresolved_dependencies
        ):
            raise ServiceLifecycleError(
                "unresolved dependencies must be a tuple of identifiers",
            )

        dependency_ids = tuple(item.identifier for item in self.dependencies)
        dependent_ids = tuple(item.identifier for item in self.dependents)

        if len(dependency_ids) != len(set(dependency_ids)):
            raise ServiceLifecycleError(
                "dependency graph node contains duplicate dependencies",
            )
        if len(dependent_ids) != len(set(dependent_ids)):
            raise ServiceLifecycleError(
                "dependency graph node contains duplicate dependents",
            )
        if len(self.unresolved_dependencies) != len(
            set(self.unresolved_dependencies)
        ):
            raise ServiceLifecycleError(
                "dependency graph node contains duplicate unresolved dependencies",
            )
        if self.service.identifier in {
            *dependency_ids,
            *dependent_ids,
            *self.unresolved_dependencies,
        }:
            raise ServiceLifecycleError(
                "dependency graph nodes cannot reference themselves",
            )

    @property
    def connected(self) -> bool:
        return bool(
            self.dependencies
            or self.dependents
            or self.unresolved_dependencies
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "service": self.service.to_dict(),
            "dependencies": [
                item.to_dict()
                for item in self.dependencies
            ],
            "dependents": [
                item.to_dict()
                for item in self.dependents
            ],
            "unresolved_dependencies": list(self.unresolved_dependencies),
            "connected": self.connected,
        }


@dataclass(frozen=True)
class InfrastructureDependencyGraph:
    """Normalized dependency graph for all Atlas-managed services."""

    nodes: tuple[ServiceDependencyNode, ...]
    evaluated_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, tuple) or any(
            not isinstance(node, ServiceDependencyNode)
            for node in self.nodes
        ):
            raise ServiceLifecycleError(
                "infrastructure graph nodes must be ServiceDependencyNode objects",
            )
        if not isinstance(self.evaluated_at, str) or not self.evaluated_at:
            raise ServiceLifecycleError(
                "infrastructure graph evaluated_at must be non-empty text",
            )

        identifiers = tuple(node.service.identifier for node in self.nodes)
        if len(identifiers) != len(set(identifiers)):
            raise ServiceLifecycleError(
                "infrastructure graph contains duplicate service identifiers",
            )

        known = set(identifiers)
        for node in self.nodes:
            for dependency in node.dependencies:
                if dependency.identifier not in known:
                    raise ServiceLifecycleError(
                        "resolved graph dependency is not a graph service",
                    )
            for dependent in node.dependents:
                if dependent.identifier not in known:
                    raise ServiceLifecycleError(
                        "resolved graph dependent is not a graph service",
                    )
            if known.intersection(node.unresolved_dependencies):
                raise ServiceLifecycleError(
                    "unresolved graph dependencies must not reference known services",
                )

    @property
    def services(self) -> tuple[ManagedService, ...]:
        return tuple(node.service for node in self.nodes)

    @property
    def provider(self) -> str:
        values = sorted({service.provider for service in self.services})
        if not values:
            return "unknown"
        if len(values) == 1:
            return values[0]
        return "mixed"

    @property
    def compose_project(self) -> str | None:
        values = sorted(
            {
                service.compose_project
                for service in self.services
                if service.compose_project is not None
            }
        )
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return "mixed"

    @property
    def roots(self) -> tuple[ServiceDependencyNode, ...]:
        return tuple(node for node in self.nodes if node.dependents)

    @property
    def standalone(self) -> tuple[ServiceDependencyNode, ...]:
        return tuple(node for node in self.nodes if not node.connected)

    @property
    def unresolved(self) -> tuple[ServiceDependencyNode, ...]:
        return tuple(
            node
            for node in self.nodes
            if node.unresolved_dependencies
        )

    @property
    def edge_count(self) -> int:
        return sum(len(node.dependencies) for node in self.nodes)

    def node(self, identifier: str) -> ServiceDependencyNode:
        normalized = _normalize_identifier(identifier)
        for node in self.nodes:
            if node.service.identifier == normalized:
                return node
        raise ServiceLifecycleError(
            f"service is not present in dependency graph: {normalized}",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "compose_project": self.compose_project,
            "total_services": len(self.nodes),
            "total_edges": self.edge_count,
            "roots": [node.to_dict() for node in self.roots],
            "standalone": [
                node.service.to_dict()
                for node in self.standalone
            ],
            "unresolved": [node.to_dict() for node in self.unresolved],
            "nodes": [node.to_dict() for node in self.nodes],
            "evaluated_at": self.evaluated_at,
        }


@dataclass(frozen=True)
class ServiceLifecycleService:
    """Validate and orchestrate read-only service-lifecycle operations."""

    provider: ServiceLifecycleProvider

    def __post_init__(self) -> None:
        if not isinstance(
            self.provider,
            ServiceLifecycleProvider,
        ):
            raise ServiceLifecycleError(
                "provider must implement ServiceLifecycleProvider",
            )

    def list_services(self) -> tuple[ManagedService, ...]:
        """Return validated services in deterministic order."""

        try:
            services = self.provider.list_services()
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to list services",
            ) from exc

        if (
            isinstance(services, (str, bytes))
            or not isinstance(services, Sequence)
        ):
            raise ServiceLifecycleError(
                "provider services must be a collection",
            )

        normalized: list[ManagedService] = []
        identifiers: set[str] = set()

        for service in services:
            if not isinstance(service, ManagedService):
                raise ServiceLifecycleError(
                    "provider services must contain ManagedService objects",
                )

            if service.identifier in identifiers:
                raise ServiceLifecycleError(
                    "provider returned duplicate service identifier: "
                    f"{service.identifier}",
                )

            identifiers.add(service.identifier)
            normalized.append(service)

        return tuple(
            sorted(
                normalized,
                key=lambda service: (
                    service.name.casefold(),
                    service.identifier,
                ),
            )
        )

    def inspect_service(
        self,
        identifier: str,
    ) -> ManagedService:
        """Return one validated managed-service identity."""

        normalized_identifier = _normalize_identifier(
            identifier,
        )

        try:
            service = self.provider.inspect_service(
                normalized_identifier,
            )
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to inspect service: "
                f"{normalized_identifier}",
            ) from exc

        if not isinstance(service, ManagedService):
            raise ServiceLifecycleError(
                "provider service inspection must return ManagedService",
            )

        if service.identifier != normalized_identifier:
            raise ServiceLifecycleError(
                "provider returned mismatched service identifier: "
                f"expected {normalized_identifier}, "
                f"received {service.identifier}",
            )

        return service

    def inspect_runtime(
        self,
        identifier: str,
    ) -> ServiceRuntime:
        """Return one validated service runtime."""

        normalized_identifier = _normalize_identifier(
            identifier,
        )

        try:
            runtime = self.provider.inspect_runtime(
                normalized_identifier,
            )
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to inspect runtime: "
                f"{normalized_identifier}",
            ) from exc

        if not isinstance(runtime, ServiceRuntime):
            raise ServiceLifecycleError(
                "provider runtime inspection must return ServiceRuntime",
            )

        return runtime

    def inspect_health(
        self,
        identifier: str,
    ) -> ServiceHealth:
        """Return one validated service-health evaluation."""

        normalized_identifier = _normalize_identifier(
            identifier,
        )

        try:
            health = self.provider.inspect_health(
                normalized_identifier,
            )
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to inspect health: "
                f"{normalized_identifier}",
            ) from exc

        if not isinstance(health, ServiceHealth):
            raise ServiceLifecycleError(
                "provider health inspection must return ServiceHealth",
            )

        return health

    def inspect_health_report(self) -> InfrastructureHealthReport:
        """Return aggregate health for all configured managed services."""

        services = self.list_services()
        return self._build_health_report(
            services,
            evaluated_at=_utc_now(),
        )

    def inspect_summary(self) -> InfrastructureSummary:
        """Return one normalized infrastructure summary."""

        services = self.list_services()
        evaluated_at = _utc_now()
        runtime_entries = tuple(
            ServiceRuntimeEntry(
                service=managed_service,
                runtime=self.inspect_runtime(managed_service.identifier),
            )
            for managed_service in services
        )
        health = self._build_health_report(
            services,
            evaluated_at=evaluated_at,
        )

        return InfrastructureSummary(
            runtime_entries=runtime_entries,
            health=health,
            evaluated_at=evaluated_at,
        )

    def inspect_graph(self) -> InfrastructureDependencyGraph:
        """Return the normalized managed-service dependency graph."""

        services = self.list_services()
        by_identifier = {service.identifier: service for service in services}
        dependents: dict[str, list[ManagedService]] = {
            service.identifier: []
            for service in services
        }

        for managed_service in services:
            for dependency_identifier in managed_service.dependencies:
                dependency = by_identifier.get(dependency_identifier)
                if dependency is not None:
                    dependents[dependency.identifier].append(managed_service)

        nodes = tuple(
            ServiceDependencyNode(
                service=managed_service,
                dependencies=tuple(
                    by_identifier[dependency_identifier]
                    for dependency_identifier in managed_service.dependencies
                    if dependency_identifier in by_identifier
                ),
                dependents=tuple(
                    sorted(
                        dependents[managed_service.identifier],
                        key=lambda service: (
                            service.name.casefold(),
                            service.identifier,
                        ),
                    )
                ),
                unresolved_dependencies=tuple(
                    dependency_identifier
                    for dependency_identifier in managed_service.dependencies
                    if dependency_identifier not in by_identifier
                ),
            )
            for managed_service in services
        )

        return InfrastructureDependencyGraph(
            nodes=nodes,
            evaluated_at=_utc_now(),
        )


    def _build_health_report(
        self,
        services: tuple[ManagedService, ...],
        *,
        evaluated_at: str,
    ) -> InfrastructureHealthReport:
        entries = tuple(
            ServiceHealthEntry(
                service=managed_service,
                health=self.inspect_health(managed_service.identifier),
            )
            for managed_service in services
        )
        score = (
            sum(entry.health.score for entry in entries) // len(entries)
            if entries
            else 0
        )

        return InfrastructureHealthReport(
            entries=entries,
            score=score,
            status=_aggregate_status(entries, score),
            evaluated_at=evaluated_at,
        )


def _aggregate_status(
    entries: tuple[ServiceHealthEntry, ...],
    score: int,
) -> str:
    if not entries:
        return "unknown"
    if any(entry.health.errors for entry in entries):
        return "unhealthy"
    if score >= 90:
        return "healthy"
    if score >= 70:
        return "degraded"
    return "unhealthy"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_identifier(
    value: object,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            "service identifier must be non-empty text",
        )

    normalized = value.strip().casefold()

    try:
        probe = ManagedService(
            identifier=normalized,
            name="Service",
            provider="service-lifecycle",
        )
    except ServiceLifecycleError as exc:
        raise ServiceLifecycleError(
            f"invalid service identifier: {normalized}: {exc}",
        ) from exc

    return probe.identifier
