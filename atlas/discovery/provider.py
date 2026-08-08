"""Discovery provider contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .models import DiscoveryIndexer


class DiscoveryProvider(ABC):
    """Abstract interface implemented by discovery providers."""

    @abstractmethod
    def list_indexers(self) -> Sequence[DiscoveryIndexer]:
        """Return provider indexers normalized as DiscoveryIndexer models."""

    @abstractmethod
    def list_categories(self) -> Sequence[str]:
        """Return normalized category names supported by the provider."""

    @abstractmethod
    def list_applications(self) -> Sequence[str]:
        """Return normalized names of connected provider applications."""
