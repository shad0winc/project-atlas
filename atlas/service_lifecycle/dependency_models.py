"""Normalized service-dependency graph contracts for Project Atlas."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any

from .models import ManagedService, ServiceLifecycleError


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


@dataclass(frozen=True, slots=True)
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

        dependencies = _normalize_services(
            self.dependencies,
            "dependency graph dependencies",
        )
        dependents = _normalize_services(
            self.dependents,
            "dependency graph dependents",
        )
        unresolved = _normalize_identifiers(
            self.unresolved_dependencies,
            "unresolved dependencies",
        )

        referenced = {
            *(item.identifier for item in dependencies),
            *(item.identifier for item in dependents),
            *unresolved,
        }
        if self.service.identifier in referenced:
            raise ServiceLifecycleError(
                "dependency graph nodes cannot reference themselves",
            )

        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "dependents", dependents)
        object.__setattr__(self, "unresolved_dependencies", unresolved)

    @property
    def connected(self) -> bool:
        """Return whether the service participates in any relationship."""

        return bool(
            self.dependencies
            or self.dependents
            or self.unresolved_dependencies
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized dependency node."""

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
            "unresolved_dependencies": list(
                self.unresolved_dependencies,
            ),
            "connected": self.connected,
        }


@dataclass(frozen=True, slots=True)
class InfrastructureDependencyGraph:
    """Normalized dependency graph for all Atlas-managed services."""

    nodes: tuple[ServiceDependencyNode, ...]
    evaluated_at: str

    def __post_init__(self) -> None:
        nodes = _normalize_nodes(self.nodes)
        evaluated_at = _required_timestamp(
            self.evaluated_at,
            "evaluated_at",
        )

        known = {
            node.service.identifier
            for node in nodes
        }
        for node in nodes:
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
                    "unresolved graph dependencies must not reference "
                    "known services",
                )

        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "evaluated_at", evaluated_at)

    @property
    def services(self) -> tuple[ManagedService, ...]:
        """Return graph service identities in deterministic order."""

        return tuple(node.service for node in self.nodes)

    @property
    def provider(self) -> str:
        """Return the common provider or an aggregate marker."""

        values = sorted({service.provider for service in self.services})
        if not values:
            return "unknown"
        if len(values) == 1:
            return values[0]
        return "mixed"

    @property
    def compose_project(self) -> str | None:
        """Return the common Compose project or an aggregate marker."""

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
        """Return services with one or more reverse dependents."""

        return tuple(node for node in self.nodes if node.dependents)

    @property
    def standalone(self) -> tuple[ServiceDependencyNode, ...]:
        """Return services without dependency relationships."""

        return tuple(node for node in self.nodes if not node.connected)

    @property
    def unresolved(self) -> tuple[ServiceDependencyNode, ...]:
        """Return services with unresolved dependency identifiers."""

        return tuple(
            node
            for node in self.nodes
            if node.unresolved_dependencies
        )

    @property
    def edge_count(self) -> int:
        """Return the number of resolved forward relationships."""

        return sum(len(node.dependencies) for node in self.nodes)

    def node(self, identifier: str) -> ServiceDependencyNode:
        """Return one graph node by normalized service identity."""

        normalized = _required_identifier(identifier, "service identifier")
        for node in self.nodes:
            if node.service.identifier == normalized:
                return node
        raise ServiceLifecycleError(
            f"service is not present in dependency graph: {normalized}",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized infrastructure dependency graph."""

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


def _normalize_services(
    values: object,
    field_name: str,
) -> tuple[ManagedService, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ServiceLifecycleError(
            f"{field_name} must be a collection of ManagedService",
        )

    normalized = tuple(values)
    if any(not isinstance(item, ManagedService) for item in normalized):
        raise ServiceLifecycleError(
            f"{field_name} must contain only ManagedService",
        )

    identifiers = tuple(item.identifier for item in normalized)
    if len(identifiers) != len(set(identifiers)):
        raise ServiceLifecycleError(
            f"{field_name} contains duplicate service identifiers",
        )

    return tuple(
        sorted(
            normalized,
            key=lambda item: (
                item.name.casefold(),
                item.identifier,
            ),
        )
    )


def _normalize_identifiers(
    values: object,
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ServiceLifecycleError(
            f"{field_name} must be a collection of identifiers",
        )

    normalized = tuple(
        _required_identifier(value, f"{field_name} value")
        for value in values
    )
    if len(normalized) != len(set(normalized)):
        raise ServiceLifecycleError(
            f"{field_name} contains duplicate identifiers",
        )
    return tuple(sorted(normalized))


def _normalize_nodes(values: object) -> tuple[ServiceDependencyNode, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ServiceLifecycleError(
            "infrastructure graph nodes must be a collection of "
            "ServiceDependencyNode",
        )

    normalized = tuple(values)
    if any(not isinstance(node, ServiceDependencyNode) for node in normalized):
        raise ServiceLifecycleError(
            "infrastructure graph nodes must contain only "
            "ServiceDependencyNode",
        )

    identifiers = tuple(node.service.identifier for node in normalized)
    if len(identifiers) != len(set(identifiers)):
        raise ServiceLifecycleError(
            "infrastructure graph contains duplicate service identifiers",
        )

    return tuple(
        sorted(
            normalized,
            key=lambda node: (
                node.service.name.casefold(),
                node.service.identifier,
            ),
        )
    )


def _required_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(f"{field_name} is required")
    normalized = value.strip().casefold()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ServiceLifecycleError(
            f"{field_name} must contain only lowercase letters, numbers, "
            "periods, underscores, or hyphens",
        )
    return normalized


def _required_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be an ISO-8601 timestamp",
        )
    try:
        parsed = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc
    if parsed.tzinfo is None:
        raise ServiceLifecycleError(
            f"{field_name} must include a timezone",
        )
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
