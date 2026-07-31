"""
Discovery provider contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DiscoveryProvider(ABC):
    """Abstract interface implemented by discovery providers."""

    @abstractmethod
    def list_indexers(self):
        """Return discovered indexers."""

    @abstractmethod
    def list_categories(self):
        """Return supported categories."""

    @abstractmethod
    def list_applications(self):
        """Return connected applications."""
