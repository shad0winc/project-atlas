"""Provider-independent media-request contracts for Project Atlas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Mapping

from .models import (
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)


_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?$",
)
_PROVIDER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class MediaRequestProviderError(ValueError):
    """Raised when a media-request provider contract is invalid."""


class MediaRequestProviderOperationError(RuntimeError):
    """Raised when a provider operation cannot be completed."""


class ProviderHealthStatus(str, Enum):
    """Normalized health states for media-request providers."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderCapabilities:
    """Normalized capabilities advertised by one provider."""

    media_types: tuple[MediaRequestType, ...]
    supports_submission: bool = True
    supports_status: bool = True
    supports_cancellation: bool = False
    supports_webhooks: bool = False

    def __post_init__(self) -> None:
        media_types = _normalize_media_types(self.media_types)

        for field_name in (
            "supports_submission",
            "supports_status",
            "supports_cancellation",
            "supports_webhooks",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise MediaRequestProviderError(
                    f"{field_name} must be a boolean",
                )

        object.__setattr__(self, "media_types", media_types)

    def supports(self, media_type: object) -> bool:
        """Return whether this provider supports one normalized media type."""

        normalized = _normalize_media_type(media_type, "media_type")
        return normalized in self.media_types

    def to_dict(self) -> dict[str, Any]:
        """Serialize provider capabilities."""

        return {
            "media_types": [
                media_type.value
                for media_type in self.media_types
            ],
            "supports_submission": self.supports_submission,
            "supports_status": self.supports_status,
            "supports_cancellation": self.supports_cancellation,
            "supports_webhooks": self.supports_webhooks,
        }


@dataclass(frozen=True)
class ProviderEventContext:
    """Provider-neutral lifecycle context for future Atlas event publication."""

    provider: str
    provider_media_id: str
    media_type: MediaRequestType
    title: str
    year: int | None = None
    season_number: int | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        provider = _required_provider(self.provider, "provider")
        provider_media_id = _required_identity(
            self.provider_media_id,
            "provider_media_id",
        )
        media_type = _normalize_media_type(
            self.media_type,
            "media_type",
        )
        title = _required_text(self.title, "title")
        year = _optional_year(self.year, "year")
        season_number = _optional_non_negative_integer(
            self.season_number,
            "season_number",
        )
        metadata = _normalize_metadata(self.metadata)

        if media_type in {
            MediaRequestType.MOVIE,
            MediaRequestType.ANIME_MOVIE,
            MediaRequestType.SPORTS,
        } and season_number is not None:
            raise MediaRequestProviderError(
                "season_number is only valid for tv and anime_tv context",
            )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "provider_media_id",
            provider_media_id,
        )
        object.__setattr__(self, "media_type", media_type)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "year", year)
        object.__setattr__(self, "season_number", season_number)
        object.__setattr__(self, "metadata", metadata)

    def to_dict(self) -> dict[str, Any]:
        """Serialize provider event context."""

        return {
            "provider": self.provider,
            "provider_media_id": self.provider_media_id,
            "media_type": self.media_type.value,
            "title": self.title,
            "year": self.year,
            "season_number": self.season_number,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProviderSubmissionResult:
    """Normalized result returned after provider submission."""

    provider: str
    provider_request_id: str
    status: MediaRequestStatus
    submitted_at: str
    updated_at: str | None = None
    context: ProviderEventContext | None = None

    def __post_init__(self) -> None:
        provider = _required_provider(self.provider, "provider")
        provider_request_id = _required_identity(
            self.provider_request_id,
            "provider_request_id",
        )
        status = _normalize_status(self.status, "status")
        submitted_at = _required_timestamp(
            self.submitted_at,
            "submitted_at",
        )
        updated_at = _optional_timestamp(
            self.updated_at,
            "updated_at",
        )

        if updated_at is not None:
            updated_at = _ordered_provider_timestamp(
                submitted_at,
                updated_at,
                field_name="updated_at",
            )

        if (
            self.context is not None
            and not isinstance(self.context, ProviderEventContext)
        ):
            raise MediaRequestProviderError(
                "context must be a ProviderEventContext or null",
            )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "provider_request_id",
            provider_request_id,
        )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "submitted_at", submitted_at)
        object.__setattr__(
            self,
            "updated_at",
            updated_at or submitted_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized provider submission result."""

        return {
            "provider": self.provider,
            "provider_request_id": self.provider_request_id,
            "status": self.status.value,
            "submitted_at": self.submitted_at,
            "updated_at": self.updated_at,
            "context": (
                self.context.to_dict()
                if self.context is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ProviderStatusResult:
    """Normalized provider-side lifecycle status."""

    provider: str
    provider_request_id: str
    status: MediaRequestStatus
    updated_at: str
    available_at: str | None = None
    error: str | None = None
    context: ProviderEventContext | None = None

    def __post_init__(self) -> None:
        provider = _required_provider(self.provider, "provider")
        provider_request_id = _required_identity(
            self.provider_request_id,
            "provider_request_id",
        )
        status = _normalize_status(self.status, "status")
        updated_at = _required_timestamp(
            self.updated_at,
            "updated_at",
        )
        available_at = _optional_timestamp(
            self.available_at,
            "available_at",
        )
        error = _optional_text(self.error, "error")

        if status is MediaRequestStatus.AVAILABLE and available_at is None:
            raise MediaRequestProviderError(
                "available_at is required when status is available",
            )

        if available_at is not None and status is not MediaRequestStatus.AVAILABLE:
            raise MediaRequestProviderError(
                "available_at is only valid when status is available",
            )

        if status is MediaRequestStatus.FAILED and error is None:
            raise MediaRequestProviderError(
                "error is required when status is failed",
            )

        if error is not None and status is not MediaRequestStatus.FAILED:
            raise MediaRequestProviderError(
                "error is only valid when status is failed",
            )

        if (
            self.context is not None
            and not isinstance(self.context, ProviderEventContext)
        ):
            raise MediaRequestProviderError(
                "context must be a ProviderEventContext or null",
            )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "provider_request_id",
            provider_request_id,
        )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "available_at", available_at)
        object.__setattr__(self, "error", error)

    @property
    def terminal(self) -> bool:
        """Return whether the provider status is terminal."""

        return self.status in {
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.REJECTED,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized provider status."""

        return {
            "provider": self.provider,
            "provider_request_id": self.provider_request_id,
            "status": self.status.value,
            "terminal": self.terminal,
            "updated_at": self.updated_at,
            "available_at": self.available_at,
            "error": self.error,
            "context": (
                self.context.to_dict()
                if self.context is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ProviderHealth:
    """Normalized provider health result."""

    provider: str
    status: ProviderHealthStatus
    checked_at: str = field(default_factory=lambda: _now_timestamp())
    message: str | None = None

    def __post_init__(self) -> None:
        provider = _required_provider(self.provider, "provider")
        status = _normalize_health_status(self.status, "status")
        checked_at = _required_timestamp(
            self.checked_at,
            "checked_at",
        )
        message = _optional_text(self.message, "message")

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "checked_at", checked_at)
        object.__setattr__(self, "message", message)

    @property
    def available(self) -> bool:
        """Return whether provider operations may be attempted."""

        return self.status in {
            ProviderHealthStatus.HEALTHY,
            ProviderHealthStatus.DEGRADED,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize provider health."""

        return {
            "provider": self.provider,
            "status": self.status.value,
            "available": self.available,
            "checked_at": self.checked_at,
            "message": self.message,
        }


class MediaRequestProvider(ABC):
    """Provider-independent media-request integration boundary."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the normalized provider name."""

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""

    def validate_submission(
        self,
        request: MediaRequest,
    ) -> None:
        """Validate deterministic submission prerequisites before persistence."""

        return None

    @abstractmethod
    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        """Submit one Atlas media request."""

    @abstractmethod
    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        """Return normalized provider-side status."""

    @abstractmethod
    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        """Cancel one provider-side request."""

    @abstractmethod
    def health(self) -> ProviderHealth:
        """Return normalized provider health."""


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_instant(value: str) -> datetime:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(candidate).astimezone(timezone.utc)


def _ordered_provider_timestamp(
    submitted_at: str,
    candidate: str,
    *,
    field_name: str,
) -> str:
    submitted_instant = _timestamp_instant(submitted_at)
    candidate_instant = _timestamp_instant(candidate)

    if candidate_instant >= submitted_instant:
        return candidate

    if (
        submitted_instant.replace(microsecond=0)
        == candidate_instant.replace(microsecond=0)
    ):
        return submitted_at

    raise MediaRequestProviderError(
        f"{field_name} must not be earlier than submitted_at",
    )


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise MediaRequestProviderError(f"{field_name} must be text")

    normalized = value.strip()
    if not normalized:
        raise MediaRequestProviderError(f"{field_name} is required")

    return normalized


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_text(value, field_name)


def _required_identity(value: object, field_name: str) -> str:
    if isinstance(value, bool):
        raise MediaRequestProviderError(
            f"{field_name} must be text or an integer",
        )

    if isinstance(value, int):
        normalized = str(value)
    else:
        normalized = _required_text(value, field_name)

    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise MediaRequestProviderError(
            f"{field_name} contains unsupported characters",
        )

    return normalized


def _required_provider(value: object, field_name: str) -> str:
    normalized = _required_text(
        value,
        field_name,
    ).lower().replace(" ", "-")

    if not _PROVIDER_PATTERN.fullmatch(normalized):
        raise MediaRequestProviderError(
            f"{field_name} contains unsupported characters",
        )

    return normalized


def _normalize_media_type(
    value: object,
    field_name: str,
) -> MediaRequestType:
    if isinstance(value, MediaRequestType):
        return value

    if not isinstance(value, str):
        raise MediaRequestProviderError(
            f"{field_name} must be a MediaRequestType or text",
        )

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    try:
        return MediaRequestType(normalized)
    except ValueError as exc:
        raise MediaRequestProviderError(
            f"{field_name} is not supported: {value!r}",
        ) from exc


def _normalize_media_types(
    value: object,
) -> tuple[MediaRequestType, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise MediaRequestProviderError(
            "media_types must be a tuple",
        )

    normalized: list[MediaRequestType] = []
    seen: set[MediaRequestType] = set()

    for index, item in enumerate(value):
        media_type = _normalize_media_type(
            item,
            f"media_types[{index}]",
        )

        if media_type in seen:
            raise MediaRequestProviderError(
                f"duplicate media type: {media_type.value}",
            )

        seen.add(media_type)
        normalized.append(media_type)

    if not normalized:
        raise MediaRequestProviderError(
            "media_types must not be empty",
        )

    return tuple(sorted(normalized, key=lambda item: item.value))


def _normalize_status(
    value: object,
    field_name: str,
) -> MediaRequestStatus:
    if isinstance(value, MediaRequestStatus):
        return value

    if not isinstance(value, str):
        raise MediaRequestProviderError(
            f"{field_name} must be a MediaRequestStatus or text",
        )

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    try:
        return MediaRequestStatus(normalized)
    except ValueError as exc:
        raise MediaRequestProviderError(
            f"{field_name} is not supported: {value!r}",
        ) from exc


def _normalize_health_status(
    value: object,
    field_name: str,
) -> ProviderHealthStatus:
    if isinstance(value, ProviderHealthStatus):
        return value

    if not isinstance(value, str):
        raise MediaRequestProviderError(
            f"{field_name} must be a ProviderHealthStatus or text",
        )

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    try:
        return ProviderHealthStatus(normalized)
    except ValueError as exc:
        raise MediaRequestProviderError(
            f"{field_name} is not supported: {value!r}",
        ) from exc


def _optional_year(value: object, field_name: str) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise MediaRequestProviderError(
            f"{field_name} must be an integer or null",
        )

    current_year = datetime.now(timezone.utc).year
    if not 1888 <= value <= current_year + 10:
        raise MediaRequestProviderError(
            f"{field_name} must be between 1888 and {current_year + 10}",
        )

    return value


def _optional_non_negative_integer(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MediaRequestProviderError(
            f"{field_name} must be a non-negative integer or null",
        )

    return value


def _required_timestamp(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name)
    return _normalize_timestamp(normalized, field_name)


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    normalized = _required_text(value, field_name)
    return _normalize_timestamp(normalized, field_name)


def _normalize_timestamp(value: str, field_name: str) -> str:
    candidate = value

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise MediaRequestProviderError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise MediaRequestProviderError(
            f"{field_name} must include a timezone",
        )

    normalized = parsed.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _normalize_metadata(
    value: object,
) -> tuple[tuple[str, str], ...]:
    if isinstance(value, Mapping):
        items = tuple(value.items())
    elif isinstance(value, tuple):
        items = value
    else:
        raise MediaRequestProviderError(
            "metadata must be a mapping or tuple of pairs",
        )

    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()

    for index, item in enumerate(items):
        if not isinstance(item, tuple) or len(item) != 2:
            raise MediaRequestProviderError(
                f"metadata[{index}] must be a key/value pair",
            )

        raw_key, raw_value = item
        key = _required_text(raw_key, f"metadata[{index}].key")
        metadata_value = _required_text(
            raw_value,
            f"metadata[{index}].value",
        )

        if key in seen:
            raise MediaRequestProviderError(
                f"duplicate metadata key: {key}",
            )

        seen.add(key)
        normalized.append((key, metadata_value))

    return tuple(sorted(normalized))
