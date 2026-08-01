"""Provider-independent contracts for Atlas Service Lifecycle."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .models import (
    ManagedService,
    ServiceHealth,
    ServiceRuntime,
)


class ServiceLifecycleProvider(ABC):
    """Abstract read-only interface for infrastructure providers."""

    @abstractmethod
    def list_services(self) -> Sequence[ManagedService]:
        """Return all Atlas-managed services known to the provider."""

    @abstractmethod
    def inspect_service(
        self,
        identifier: str,
    ) -> ManagedService:
        """Return normalized identity information for one service."""

    @abstractmethod
    def inspect_runtime(
        self,
        identifier: str,
    ) -> ServiceRuntime:
        """Return normalized runtime state for one service."""

    @abstractmethod
    def inspect_health(
        self,
        identifier: str,
    ) -> ServiceHealth:
        """Return normalized health information for one service."""
