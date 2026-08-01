"""Provider-independent orchestration for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import (
    ManagedService,
    ServiceHealth,
    ServiceLifecycleError,
    ServiceRuntime,
)
from .provider import ServiceLifecycleProvider


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
