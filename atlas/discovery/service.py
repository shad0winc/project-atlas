"""
Discovery service.
"""

from __future__ import annotations

from .report import DiscoveryReport


class DiscoveryService:
    """Coordinates Discovery domain operations."""

    def list_indexers(self):
        return []

    def health(self):
        return None

    def report(self) -> DiscoveryReport:
        return DiscoveryReport()
