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
class ServiceImage:
    """Normalized image identity for one managed service."""

    reference: str
    repository: str | None = None
    tag: str | None = None
    digest: str | None = None
    image_id: str | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        reference = _required_text(
            self.reference,
            "reference",
        )

        repository = _optional_text(
            self.repository,
            "repository",
        )
        tag = _optional_text(
            self.tag,
            "tag",
        )
        digest = _optional_digest(
            self.digest,
            "digest",
        )
        image_id = _optional_digest(
            self.image_id,
            "image_id",
        )

        object.__setattr__(
            self,
            "reference",
            reference,
        )
        object.__setattr__(
            self,
            "repository",
            repository,
        )
        object.__setattr__(
            self,
            "tag",
            tag,
        )
        object.__setattr__(
            self,
            "digest",
            digest,
        )
        object.__setattr__(
            self,
            "image_id",
            image_id,
        )
        object.__setattr__(
            self,
            "created_at",
            _optional_timestamp(
                self.created_at,
                "created_at",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized service-image contract."""

        return {
            "reference": self.reference,
            "repository": self.repository,
            "tag": self.tag,
            "digest": self.digest,
            "image_id": self.image_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ServiceRuntime:
    """Normalized runtime state for one managed service."""

    state: str
    health: str
    image: ServiceImage
    restart_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    status_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "state",
            _required_service_identifier(
                self.state,
                "state",
            ),
        )
        object.__setattr__(
            self,
            "health",
            _required_service_identifier(
                self.health,
                "health",
            ),
        )

        if not isinstance(self.image, ServiceImage):
            raise ServiceLifecycleError(
                "image must be a ServiceImage",
            )

        if (
            isinstance(self.restart_count, bool)
            or not isinstance(self.restart_count, int)
            or self.restart_count < 0
        ):
            raise ServiceLifecycleError(
                "restart_count must be a non-negative integer",
            )

        object.__setattr__(
            self,
            "started_at",
            _optional_timestamp(
                self.started_at,
                "started_at",
            ),
        )
        object.__setattr__(
            self,
            "finished_at",
            _optional_timestamp(
                self.finished_at,
                "finished_at",
            ),
        )

        if (
            self.exit_code is not None
            and (
                isinstance(self.exit_code, bool)
                or not isinstance(self.exit_code, int)
            )
        ):
            raise ServiceLifecycleError(
                "exit_code must be an integer or null",
            )

        object.__setattr__(
            self,
            "status_message",
            _optional_text(
                self.status_message,
                "status_message",
            ),
        )

    @property
    def running(self) -> bool:
        """Return whether the service runtime is currently running."""

        return self.state == "running"

    @property
    def healthy(self) -> bool:
        """Return whether the runtime health state is healthy."""

        return self.health == "healthy"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized service-runtime contract."""

        return {
            "state": self.state,
            "health": self.health,
            "running": self.running,
            "healthy": self.healthy,
            "image": self.image.to_dict(),
            "restart_count": self.restart_count,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "status_message": self.status_message,
        }


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


def _optional_digest(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    normalized = _required_text(
        value,
        field_name,
    ).casefold()

    if not normalized.startswith("sha256:"):
        raise ServiceLifecycleError(
            f"{field_name} must use the sha256 algorithm",
        )

    digest_value = normalized.removeprefix("sha256:")

    if (
        len(digest_value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in digest_value
        )
    ):
        raise ServiceLifecycleError(
            f"{field_name} must contain a valid sha256 digest",
        )

    return normalized


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
