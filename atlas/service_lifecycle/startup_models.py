"""Immutable startup-order contracts for Atlas-managed services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import ManagedService, ServiceLifecycleError


class StartupDependencyCondition(str, Enum):
    """Supported Compose dependency readiness conditions."""

    SERVICE_STARTED = "service_started"
    SERVICE_HEALTHY = "service_healthy"
    SERVICE_COMPLETED_SUCCESSFULLY = "service_completed_successfully"


@dataclass(frozen=True)
class ServiceStartupDependency:
    """One normalized startup dependency for a managed service."""

    identifier: str
    condition: StartupDependencyCondition = (
        StartupDependencyCondition.SERVICE_STARTED
    )
    required: bool = True

    def __post_init__(self) -> None:
        identifier = _required_identifier(
            self.identifier,
            "identifier",
        )

        condition = _normalize_condition(
            self.condition,
            "condition",
        )

        if not isinstance(self.required, bool):
            raise ServiceLifecycleError(
                "required must be a boolean",
            )

        object.__setattr__(
            self,
            "identifier",
            identifier,
        )
        object.__setattr__(
            self,
            "condition",
            condition,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the normalized startup dependency."""

        return {
            "identifier": self.identifier,
            "condition": self.condition.value,
            "required": self.required,
        }


@dataclass(frozen=True)
class ServiceStartupContract:
    """Normalized startup policy for one managed service."""

    service: ManagedService
    dependencies: tuple[ServiceStartupDependency, ...] = ()
    namespace_target: str | None = None
    restart_policy: str | None = None
    healthcheck_configured: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.service, ManagedService):
            raise ServiceLifecycleError(
                "service must be a ManagedService",
            )

        dependencies = _normalize_dependencies(
            self.dependencies,
        )

        dependency_ids = tuple(
            dependency.identifier
            for dependency in dependencies
        )

        if self.service.identifier in dependency_ids:
            raise ServiceLifecycleError(
                "startup dependencies must not contain "
                "the service identifier",
            )

        namespace_target = _optional_identifier(
            self.namespace_target,
            "namespace_target",
        )

        if namespace_target == self.service.identifier:
            raise ServiceLifecycleError(
                "namespace_target must not reference "
                "the service identifier",
            )

        restart_policy = _optional_text(
            self.restart_policy,
            "restart_policy",
        )

        if not isinstance(self.healthcheck_configured, bool):
            raise ServiceLifecycleError(
                "healthcheck_configured must be a boolean",
            )

        object.__setattr__(
            self,
            "dependencies",
            dependencies,
        )
        object.__setattr__(
            self,
            "namespace_target",
            namespace_target,
        )
        object.__setattr__(
            self,
            "restart_policy",
            (
                restart_policy.casefold()
                if restart_policy is not None
                else None
            ),
        )

    @property
    def dependency_identifiers(self) -> tuple[str, ...]:
        """Return dependency identities in deterministic order."""

        return tuple(
            dependency.identifier
            for dependency in self.dependencies
        )

    def dependency(
        self,
        identifier: str,
    ) -> ServiceStartupDependency:
        """Return one startup dependency by normalized identity."""

        normalized = _required_identifier(
            identifier,
            "identifier",
        )

        for dependency in self.dependencies:
            if dependency.identifier == normalized:
                return dependency

        raise ServiceLifecycleError(
            "startup dependency is not present: "
            f"{normalized}",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized startup contract."""

        return {
            "service": self.service.to_dict(),
            "dependencies": [
                dependency.to_dict()
                for dependency in self.dependencies
            ],
            "dependency_identifiers": list(
                self.dependency_identifiers
            ),
            "namespace_target": self.namespace_target,
            "restart_policy": self.restart_policy,
            "healthcheck_configured": (
                self.healthcheck_configured
            ),
        }


def _normalize_dependencies(
    value: object,
) -> tuple[ServiceStartupDependency, ...]:
    if not isinstance(value, tuple):
        raise ServiceLifecycleError(
            "dependencies must be a tuple of "
            "ServiceStartupDependency",
        )

    if any(
        not isinstance(item, ServiceStartupDependency)
        for item in value
    ):
        raise ServiceLifecycleError(
            "dependencies must be a tuple of "
            "ServiceStartupDependency",
        )

    by_identifier: dict[str, ServiceStartupDependency] = {}

    for dependency in value:
        if dependency.identifier in by_identifier:
            raise ServiceLifecycleError(
                "startup dependencies must have "
                "unique identifiers",
            )

        by_identifier[dependency.identifier] = dependency

    return tuple(
        sorted(
            by_identifier.values(),
            key=lambda dependency: dependency.identifier,
        )
    )


def _normalize_condition(
    value: object,
    field_name: str,
) -> StartupDependencyCondition:
    if isinstance(value, StartupDependencyCondition):
        return value

    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be a supported "
            "startup dependency condition",
        )

    try:
        return StartupDependencyCondition(
            value.strip().casefold()
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be a supported "
            "startup dependency condition",
        ) from exc


def _required_identifier(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(
        value,
        field_name,
    ).casefold()

    if any(
        character.isspace()
        for character in normalized
    ):
        raise ServiceLifecycleError(
            f"{field_name} must not contain whitespace",
        )

    return normalized


def _optional_identifier(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_identifier(
        value,
        field_name,
    )


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_text(
        value,
        field_name,
    )


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} is required",
        )

    return value.strip()
