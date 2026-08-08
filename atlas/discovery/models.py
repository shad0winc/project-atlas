"""Normalized Discovery domain models for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping


class DiscoveryError(ValueError):
    """Raised when a Discovery domain model contains invalid data."""


class DiscoveryCapability(str, Enum):
    """Media capabilities exposed by a discovery indexer."""

    MOVIES = "movies"
    TV = "tv"
    ANIME = "anime"
    MUSIC = "music"
    BOOKS = "books"
    GENERAL = "general"
    CUSTOM = "custom"


@dataclass(frozen=True)
class DiscoveryIndexer:
    """Provider-independent representation of one discovery indexer."""

    identifier: str
    name: str
    enabled: bool
    protocol: str
    priority: int | None = None
    capabilities: tuple[DiscoveryCapability, ...] = ()
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "identifier",
            _required_identifier(
                self.identifier,
                "identifier",
            ),
        )
        object.__setattr__(
            self,
            "name",
            _required_text(
                self.name,
                "name",
            ),
        )

        if not isinstance(self.enabled, bool):
            raise DiscoveryError("enabled must be a boolean")

        object.__setattr__(
            self,
            "protocol",
            _required_text(
                self.protocol,
                "protocol",
            ).lower(),
        )
        object.__setattr__(
            self,
            "priority",
            _optional_integer(
                self.priority,
                "priority",
            ),
        )
        object.__setattr__(
            self,
            "capabilities",
            _normalize_capabilities(
                self.capabilities,
            ),
        )
        object.__setattr__(
            self,
            "categories",
            _normalize_text_collection(
                self.categories,
                "categories",
            ),
        )
        object.__setattr__(
            self,
            "tags",
            _normalize_text_collection(
                self.tags,
                "tags",
            ),
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
        """Serialize the normalized indexer."""

        return {
            "identifier": self.identifier,
            "name": self.name,
            "enabled": self.enabled,
            "protocol": self.protocol,
            "priority": self.priority,
            "capabilities": [
                capability.value
                for capability in self.capabilities
            ],
            "categories": list(self.categories),
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class DiscoveryHealth:
    """Normalized health evaluation for the Discovery domain."""

    score: int = 100
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        if (
            isinstance(self.score, bool)
            or not isinstance(self.score, int)
            or not 0 <= self.score <= 100
        ):
            raise DiscoveryError(
                "score must be an integer between 0 and 100",
            )

        object.__setattr__(
            self,
            "warnings",
            _normalize_text_collection(
                self.warnings,
                "warnings",
            ),
        )
        object.__setattr__(
            self,
            "errors",
            _normalize_text_collection(
                self.errors,
                "errors",
            ),
        )

        if not isinstance(self.details, Mapping):
            raise DiscoveryError("details must be an object")

        object.__setattr__(
            self,
            "details",
            dict(self.details),
        )
        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(
                self.evaluated_at,
                "evaluated_at",
            ),
        )

    @property
    def healthy(self) -> bool:
        """Return whether the health evaluation contains no errors."""

        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized health evaluation."""

        return {
            "score": self.score,
            "healthy": self.healthy,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "details": dict(self.details),
            "evaluated_at": self.evaluated_at,
        }


def _required_identifier(
    value: object,
    field_name: str,
) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DiscoveryError(
            f"{field_name} must be a string or integer",
        )

    normalized = str(value).strip()

    if not normalized:
        raise DiscoveryError(f"{field_name} is required")

    return normalized


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"{field_name} is required")

    return value.strip()


def _optional_integer(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise DiscoveryError(
            f"{field_name} must be an integer or null",
        )

    return value


def _normalize_capabilities(
    values: object,
) -> tuple[DiscoveryCapability, ...]:
    if values is None:
        return ()

    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise DiscoveryError(
            "capabilities must be a collection",
        )

    normalized: set[DiscoveryCapability] = set()

    for value in values:
        try:
            capability = (
                value
                if isinstance(value, DiscoveryCapability)
                else DiscoveryCapability(value)
            )
        except (TypeError, ValueError) as exc:
            raise DiscoveryError(
                f"invalid discovery capability: {value}",
            ) from exc

        normalized.add(capability)

    return tuple(
        sorted(
            normalized,
            key=lambda capability: capability.value,
        )
    )


def _normalize_text_collection(
    values: object,
    field_name: str,
) -> tuple[str, ...]:
    if values is None:
        return ()

    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise DiscoveryError(
            f"{field_name} must be a collection",
        )

    normalized: set[str] = set()

    for value in values:
        normalized.add(
            _required_text(
                value,
                f"{field_name} value",
            ),
        )

    return tuple(sorted(normalized))


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"{field_name} is required")

    return _normalize_timestamp(
        value,
        field_name,
    )


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(
            f"{field_name} must be a timestamp or null",
        )

    return _normalize_timestamp(
        value,
        field_name,
    )


def _normalize_timestamp(
    value: str,
    field_name: str,
) -> str:
    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise DiscoveryError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise DiscoveryError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _now_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
