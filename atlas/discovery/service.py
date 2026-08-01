"""Discovery domain service."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import (
    DiscoveryCapability,
    DiscoveryError,
    DiscoveryHealth,
    DiscoveryIndexer,
)
from .providers import DiscoveryProvider
from .report import DiscoveryReport


class DiscoveryService:
    """Coordinate provider-independent Discovery domain operations."""

    def __init__(self, provider: DiscoveryProvider) -> None:
        if not isinstance(provider, DiscoveryProvider):
            raise DiscoveryError(
                "provider must implement DiscoveryProvider",
            )

        self._provider = provider

    @property
    def provider(self) -> DiscoveryProvider:
        """Return the configured discovery provider."""

        return self._provider

    def list_indexers(
        self,
        *,
        enabled: bool | None = None,
    ) -> tuple[DiscoveryIndexer, ...]:
        """Return normalized provider indexers in deterministic order."""

        if enabled is not None and not isinstance(enabled, bool):
            raise DiscoveryError(
                "enabled filter must be a boolean or null",
            )

        provider_indexers = self._provider.list_indexers()
        indexers = _normalize_indexers(provider_indexers)

        if enabled is not None:
            indexers = tuple(
                indexer
                for indexer in indexers
                if indexer.enabled is enabled
            )

        return indexers

    def health(self) -> DiscoveryHealth:
        """Evaluate basic health for the configured discovery provider."""

        indexers = self.list_indexers()
        warnings: list[str] = []
        errors: list[str] = []

        disabled_count = sum(
            1
            for indexer in indexers
            if not indexer.enabled
        )

        if not indexers:
            errors.append(
                "No discovery indexers were returned by the provider",
            )

        if disabled_count:
            noun = "indexer" if disabled_count == 1 else "indexers"
            warnings.append(
                f"{disabled_count} discovery {noun} disabled",
            )

        score = max(
            0,
            100
            - (len(warnings) * 5)
            - (len(errors) * 25),
        )

        return DiscoveryHealth(
            score=score,
            warnings=warnings,
            errors=errors,
            details={
                "indexer_count": len(indexers),
                "enabled_indexer_count": (
                    len(indexers) - disabled_count
                ),
                "disabled_indexer_count": disabled_count,
            },
        )

    def report(self) -> DiscoveryReport:
        """Build a normalized summary of discovery state."""

        indexers = self.list_indexers()
        health = self.health()

        enabled_count = sum(
            1
            for indexer in indexers
            if indexer.enabled
        )

        capabilities = sorted(
            {
                capability.value
                for indexer in indexers
                for capability in indexer.capabilities
            }
        )

        categories = sorted(
            {
                category
                for indexer in indexers
                for category in indexer.categories
            }
        )

        tags = sorted(
            {
                tag
                for indexer in indexers
                for tag in indexer.tags
            }
        )

        metadata: dict[str, Any] = {
            "enabled_indexer_count": enabled_count,
            "disabled_indexer_count": (
                len(indexers) - enabled_count
            ),
            "capabilities": capabilities,
            "categories": categories,
            "tags": tags,
            "health": health.to_dict(),
        }

        return DiscoveryReport(
            indexer_count=len(indexers),
            warning_count=len(health.warnings),
            error_count=len(health.errors),
            metadata=metadata,
        )


def _normalize_indexers(
    values: object,
) -> tuple[DiscoveryIndexer, ...]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Iterable)
    ):
        raise DiscoveryError(
            "provider indexers must be a collection",
        )

    normalized = tuple(values)

    for indexer in normalized:
        if not isinstance(indexer, DiscoveryIndexer):
            raise DiscoveryError(
                "provider indexers must contain "
                "DiscoveryIndexer values",
            )

    identifiers: set[str] = set()

    for indexer in normalized:
        if indexer.identifier in identifiers:
            raise DiscoveryError(
                "provider indexers contain duplicate identifier: "
                f"{indexer.identifier}",
            )

        identifiers.add(indexer.identifier)

    return tuple(
        sorted(
            normalized,
            key=lambda indexer: (
                indexer.name.casefold(),
                indexer.identifier,
            ),
        )
    )
