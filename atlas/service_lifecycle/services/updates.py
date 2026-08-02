"""Provider-independent orchestration for Service Lifecycle update discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ..models import (
    ManagedService,
    ServiceLifecycleError,
)
from .lifecycle import ServiceLifecycleService
from ..update_models import (
    ServiceUpdate,
    UpdateReport,
)


@dataclass(frozen=True)
class ServiceUpdateService:
    """Validate and aggregate read-only service update metadata."""

    lifecycle: ServiceLifecycleService

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, ServiceLifecycleService):
            raise ServiceLifecycleError(
                "lifecycle must be ServiceLifecycleService",
            )

    def inspect_update(
        self,
        identifier: str,
    ) -> ServiceUpdate:
        """Return one validated update evaluation."""

        service = self.lifecycle.inspect_service(identifier)
        return self._inspect_managed_service(service)

    def inspect_updates(self) -> UpdateReport:
        """Return deterministic update metadata for all managed services."""

        services = self.lifecycle.list_services()
        updates = tuple(
            self._inspect_managed_service(service)
            for service in services
        )

        return UpdateReport(
            updates=updates,
            provider=_provider_name(services),
            evaluated_at=_utc_now(),
        )

    def _inspect_managed_service(
        self,
        service: ManagedService,
    ) -> ServiceUpdate:
        if not isinstance(service, ManagedService):
            raise ServiceLifecycleError(
                "update inspection requires ManagedService identity",
            )

        try:
            update = self.lifecycle.provider.inspect_update(
                service.identifier,
            )
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to inspect update: "
                f"{service.identifier}",
            ) from exc

        if not isinstance(update, ServiceUpdate):
            raise ServiceLifecycleError(
                "provider update inspection must return ServiceUpdate",
            )

        if update.service_identifier != service.identifier:
            raise ServiceLifecycleError(
                "provider returned mismatched update identifier: "
                f"expected {service.identifier}, "
                f"received {update.service_identifier}",
            )

        if update.service_name != service.name:
            raise ServiceLifecycleError(
                "provider returned mismatched update service name: "
                f"expected {service.name}, "
                f"received {update.service_name}",
            )

        return update


def _provider_name(
    services: tuple[ManagedService, ...],
) -> str:
    providers = sorted({
        service.provider
        for service in services
    })

    if not providers:
        return "unknown"
    if len(providers) == 1:
        return providers[0]
    return "mixed"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
