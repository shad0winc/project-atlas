"""Provider-independent orchestration for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from .models import (
    ManagedService,
    ServiceHealth,
    ServiceLifecycleError,
    ServiceRuntime,
)
from .provider import ServiceLifecycleProvider


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

        entries = tuple(
            ServiceHealthEntry(
                service=managed_service,
                health=self.inspect_health(managed_service.identifier),
            )
            for managed_service in self.list_services()
        )

        score = (
            sum(entry.health.score for entry in entries) // len(entries)
            if entries
            else 0
        )
        status = _aggregate_status(entries, score)

        return InfrastructureHealthReport(
            entries=entries,
            score=score,
            status=status,
            evaluated_at=_utc_now(),
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
