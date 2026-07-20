"""Provider-neutral media models and interfaces for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol


class MediaProviderError(RuntimeError):
    """Raised when a media provider operation fails."""


class ProviderMutationError(ValueError):
    """Raised when a provider mutation result is invalid."""


class ProviderOperation(str, Enum):
    """Mutation operations supported by Atlas media providers."""

    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class MediaItem:
    """Provider-neutral media item."""

    provider: str
    item_id: str
    media_type: str
    title: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderMutationResult:
    """Normalized result returned by a media mutation provider."""

    provider: str
    operation: ProviderOperation
    item_id: str
    success: bool
    message: str
    executed_at: str

    def __post_init__(self) -> None:
        """Normalize and validate the mutation result."""

        provider = _required_text(
            self.provider,
            "provider",
        ).lower()

        item_id = _required_text(
            self.item_id,
            "item_id",
        )

        message = _required_text(
            self.message,
            "message",
        )

        try:
            operation = (
                self.operation
                if isinstance(self.operation, ProviderOperation)
                else ProviderOperation(self.operation)
            )
        except (TypeError, ValueError) as exc:
            raise ProviderMutationError(
                f"invalid provider operation: {self.operation}"
            ) from exc

        if not isinstance(self.success, bool):
            raise ProviderMutationError(
                "success must be a boolean"
            )

        executed_at = _required_timestamp(
            self.executed_at,
            "executed_at",
        )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "executed_at", executed_at)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "provider": self.provider,
            "operation": self.operation.value,
            "item_id": self.item_id,
            "success": self.success,
            "message": self.message,
            "executed_at": self.executed_at,
        }


class MediaProvider(Protocol):
    """Provider-neutral interface for media operations."""

    @property
    def name(self) -> str:
        """Return the normalized provider name."""

        ...

    def get_item(
        self,
        item_id: str,
    ) -> MediaItem:
        """Return one normalized media item."""

        ...

    def preview_delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        """Preview deletion without modifying external media."""

        ...


def _required_text(
    value: object,
    field_name: str,
) -> str:
    """Return a stripped, non-empty string."""

    if not isinstance(value, str) or not value.strip():
        raise ProviderMutationError(
            f"{field_name} is required"
        )

    return value.strip()


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    """Return a normalized timezone-aware UTC timestamp."""

    if not isinstance(value, str) or not value.strip():
        raise ProviderMutationError(
            f"{field_name} is required"
        )

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ProviderMutationError(
            f"{field_name} must be an ISO-8601 timestamp"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProviderMutationError(
            f"{field_name} must include a timezone"
        )

    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
