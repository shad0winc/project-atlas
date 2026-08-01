"""Normalized Service Lifecycle domain models for Project Atlas."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any


_SERVICE_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class ServiceLifecycleError(ValueError):
    """Raised when a Service Lifecycle model contains invalid data."""


@dataclass(frozen=True)
class ManagedService:
    """Provider-independent identity for one Atlas-managed service."""

    identifier: str
    name: str
    provider: str
    enabled: bool = True
    compose_project: str | None = None
    container_name: str | None = None
    dependencies: tuple[str, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        identifier = _required_service_identifier(
            self.identifier,
            "identifier",
        )

        object.__setattr__(
            self,
            "identifier",
            identifier,
        )
        object.__setattr__(
            self,
            "name",
            _required_text(
                self.name,
                "name",
            ),
        )
        object.__setattr__(
            self,
            "provider",
            _required_service_identifier(
                self.provider,
                "provider",
            ),
        )

        if not isinstance(self.enabled, bool):
            raise ServiceLifecycleError(
                "enabled must be a boolean",
            )

        object.__setattr__(
            self,
            "compose_project",
            _optional_text(
                self.compose_project,
                "compose_project",
            ),
        )
        object.__setattr__(
            self,
            "container_name",
            _optional_text(
                self.container_name,
                "container_name",
            ),
        )

        dependencies = _normalize_service_identifiers(
            self.dependencies,
            "dependencies",
        )

        if identifier in dependencies:
            raise ServiceLifecycleError(
                "dependencies must not contain the service identifier",
            )

        object.__setattr__(
            self,
            "dependencies",
            dependencies,
        )
        object.__setattr__(
            self,
            "created_at",
            _optional_timestamp(
                self.created_at,
                "created_at",
            ),
        )
        object.__setattr__(
            self,
            "updated_at",
            _optional_timestamp(
                self.updated_at,
                "updated_at",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized managed-service identity."""

        return {
            "identifier": self.identifier,
            "name": self.name,
            "provider": self.provider,
            "enabled": self.enabled,
            "compose_project": self.compose_project,
            "container_name": self.container_name,
            "dependencies": list(self.dependencies),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _required_service_identifier(
    value: object,
    field_name: str,
) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ServiceLifecycleError(
            f"{field_name} must be a string or integer",
        )

    normalized = str(value).strip().casefold()

    if not normalized:
        raise ServiceLifecycleError(
            f"{field_name} is required",
        )

    if not _SERVICE_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ServiceLifecycleError(
            f"{field_name} must contain only lowercase letters, "
            "numbers, periods, underscores, or hyphens",
        )

    return normalized


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} is required",
        )

    return value.strip()


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be non-empty text or null",
        )

    return value.strip()


def _normalize_service_identifiers(
    values: object,
    field_name: str,
) -> tuple[str, ...]:
    if values is None:
        return ()

    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Iterable)
    ):
        raise ServiceLifecycleError(
            f"{field_name} must be a collection",
        )

    normalized = {
        _required_service_identifier(
            value,
            f"{field_name} value",
        )
        for value in values
    }

    return tuple(sorted(normalized))


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be a timestamp or null",
        )

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise ServiceLifecycleError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
