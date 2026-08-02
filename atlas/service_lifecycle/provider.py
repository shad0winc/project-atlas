"""Provider-independent contracts for Atlas Service Lifecycle."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .models import ManagedService, ServiceHealth, ServiceRuntime
from .update_models import ServiceUpdate
from .maintenance_models import MaintenanceReport


class ServiceLifecycleProvider(ABC):
    """Abstract read-only interface for infrastructure providers."""

    @abstractmethod
    def list_services(self) -> Sequence[ManagedService]:
        """Return all Atlas-managed services known to the provider."""

    @abstractmethod
    def inspect_service(self, identifier: str) -> ManagedService:
        """Return normalized identity information for one service."""

    @abstractmethod
    def inspect_runtime(self, identifier: str) -> ServiceRuntime:
        """Return normalized runtime state for one service."""

    @abstractmethod
    def inspect_health(self, identifier: str) -> ServiceHealth:
        """Return normalized health information for one service."""

    @abstractmethod
    def inspect_update(self, identifier: str) -> ServiceUpdate:
        """Return locally verifiable read-only update metadata."""

    def inspect_history(self) -> MaintenanceReport:
        """Return read-only maintenance history for all services.

        Providers without persistence return a valid empty report.
        """

        return MaintenanceReport(
            records=(),
            provider="unknown",
        )

    def inspect_service_history(
        self,
        identifier: str,
    ) -> MaintenanceReport:
        """Return read-only maintenance history for one service.

        Providers without persistence validate service identity and
        return a valid empty report.
        """

        service = self.inspect_service(identifier)
        return MaintenanceReport(
            records=(),
            provider=service.provider,
        )
