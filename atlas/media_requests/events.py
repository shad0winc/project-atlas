"""Normalized lifecycle events for Atlas media requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .models import (
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)
from .provider import ProviderEventContext


class MediaRequestEventError(ValueError):
    """Raised when a media-request event contract is invalid."""


class MediaRequestEventType(str, Enum):
    """Provider-neutral media-request lifecycle event types."""

    CREATED = "request.created"
    SUBMITTED = "request.submitted"
    PENDING = "request.pending"
    APPROVED = "request.approved"
    SEARCHING = "request.searching"
    DOWNLOADING = "request.downloading"
    IMPORTING = "request.importing"
    AVAILABLE = "request.available"
    REJECTED = "request.rejected"
    FAILED = "request.failed"
    CANCELLED = "request.cancelled"


_STATUS_EVENTS: dict[MediaRequestStatus, MediaRequestEventType] = {
    MediaRequestStatus.PENDING: MediaRequestEventType.PENDING,
    MediaRequestStatus.APPROVED: MediaRequestEventType.APPROVED,
    MediaRequestStatus.SEARCHING: MediaRequestEventType.SEARCHING,
    MediaRequestStatus.DOWNLOADING: MediaRequestEventType.DOWNLOADING,
    MediaRequestStatus.IMPORTING: MediaRequestEventType.IMPORTING,
    MediaRequestStatus.AVAILABLE: MediaRequestEventType.AVAILABLE,
    MediaRequestStatus.REJECTED: MediaRequestEventType.REJECTED,
    MediaRequestStatus.FAILED: MediaRequestEventType.FAILED,
    MediaRequestStatus.CANCELLED: MediaRequestEventType.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class MediaRequestEvent:
    """Immutable, provider-neutral request event payload."""

    event_type: MediaRequestEventType
    request_id: str
    user_id: str
    provider: str
    provider_media_id: str
    media_type: MediaRequestType
    title: str
    status: MediaRequestStatus
    occurred_at: datetime
    provider_request_id: str | None = None
    year: int | None = None
    season_number: int | None = None
    available_at: str | None = None
    context: ProviderEventContext | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        event_type = _normalize_event_type(self.event_type)
        request_id = _required_text(self.request_id, "request_id")
        user_id = _required_text(self.user_id, "user_id")
        provider = _required_text(
            self.provider,
            "provider",
        ).lower().replace(" ", "-")
        provider_media_id = _required_text(
            self.provider_media_id,
            "provider_media_id",
        )
        media_type = _normalize_media_type(self.media_type)
        title = _required_text(self.title, "title")
        status = _normalize_status(self.status)
        occurred_at = _normalize_datetime(
            self.occurred_at,
            "occurred_at",
        )
        provider_request_id = _optional_text(
            self.provider_request_id,
            "provider_request_id",
        )
        available_at = _optional_timestamp(
            self.available_at,
            "available_at",
        )
        metadata = _normalize_metadata(self.metadata)

        if (
            self.context is not None
            and not isinstance(self.context, ProviderEventContext)
        ):
            raise MediaRequestEventError(
                "context must be a ProviderEventContext or null",
            )

        if event_type in {
            MediaRequestEventType.SUBMITTED,
            MediaRequestEventType.APPROVED,
            MediaRequestEventType.SEARCHING,
            MediaRequestEventType.DOWNLOADING,
            MediaRequestEventType.IMPORTING,
            MediaRequestEventType.AVAILABLE,
            MediaRequestEventType.REJECTED,
            MediaRequestEventType.FAILED,
            MediaRequestEventType.CANCELLED,
        } and provider_request_id is None:
            raise MediaRequestEventError(
                "provider_request_id is required for submitted lifecycle events",
            )

        expected_status = _event_status(event_type)
        if expected_status is not None and status is not expected_status:
            raise MediaRequestEventError(
                "event_type does not match request status",
            )

        if status is MediaRequestStatus.AVAILABLE and available_at is None:
            raise MediaRequestEventError(
                "available_at is required for available events",
            )

        if status is not MediaRequestStatus.AVAILABLE and available_at is not None:
            raise MediaRequestEventError(
                "available_at is only valid for available events",
            )

        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "provider_media_id", provider_media_id)
        object.__setattr__(self, "media_type", media_type)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(
            self,
            "provider_request_id",
            provider_request_id,
        )
        object.__setattr__(self, "available_at", available_at)
        object.__setattr__(self, "metadata", metadata)

    @property
    def name(self) -> str:
        """Return the event-bus name."""

        return self.event_type.value

    def to_payload(self) -> dict[str, Any]:
        """Serialize the event payload expected by Atlas publishers."""

        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "provider": self.provider,
            "provider_request_id": self.provider_request_id,
            "provider_media_id": self.provider_media_id,
            "media_type": self.media_type.value,
            "title": self.title,
            "year": self.year,
            "season_number": self.season_number,
            "status": self.status.value,
            "terminal": self.status in {
                MediaRequestStatus.AVAILABLE,
                MediaRequestStatus.REJECTED,
                MediaRequestStatus.FAILED,
                MediaRequestStatus.CANCELLED,
            },
            "available_at": self.available_at,
            "occurred_at": (
                self.occurred_at
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "context": (
                self.context.to_dict()
                if self.context is not None
                else None
            ),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete event contract."""

        return {
            "event": self.name,
            "payload": self.to_payload(),
        }

    @classmethod
    def from_request(
        cls,
        event_type: MediaRequestEventType | str,
        request: MediaRequest,
        *,
        occurred_at: datetime,
        context: ProviderEventContext | None = None,
        metadata: Mapping[str, str] | tuple[tuple[str, str], ...] = (),
    ) -> "MediaRequestEvent":
        """Build one event from a normalized request."""

        if not isinstance(request, MediaRequest):
            raise MediaRequestEventError(
                "request must be a MediaRequest",
            )

        return cls(
            event_type=event_type,
            request_id=request.request_id,
            user_id=request.user_id,
            provider=request.provider,
            provider_request_id=request.provider_request_id,
            provider_media_id=request.provider_media_id,
            media_type=request.media_type,
            title=request.title,
            year=request.year,
            season_number=request.season_number,
            status=request.status,
            available_at=request.available_at,
            occurred_at=occurred_at,
            context=context,
            metadata=_normalize_metadata(metadata),
        )


def event_type_for_status(
    status: MediaRequestStatus | str,
) -> MediaRequestEventType:
    """Return the canonical lifecycle event for one request status."""

    normalized = _normalize_status(status)
    return _STATUS_EVENTS[normalized]


def _event_status(
    event_type: MediaRequestEventType,
) -> MediaRequestStatus | None:
    if event_type in {
        MediaRequestEventType.CREATED,
        MediaRequestEventType.SUBMITTED,
    }:
        return None

    for status, candidate in _STATUS_EVENTS.items():
        if candidate is event_type:
            return status

    raise MediaRequestEventError(
        f"unsupported media-request event type: {event_type.value}",
    )


def _normalize_event_type(
    value: MediaRequestEventType | str,
) -> MediaRequestEventType:
    if isinstance(value, MediaRequestEventType):
        return value

    if not isinstance(value, str):
        raise MediaRequestEventError(
            "event_type must be MediaRequestEventType or text",
        )

    try:
        return MediaRequestEventType(value.strip().lower())
    except ValueError as exc:
        raise MediaRequestEventError(
            f"unsupported media-request event type: {value!r}",
        ) from exc


def _normalize_media_type(
    value: MediaRequestType | str,
) -> MediaRequestType:
    if isinstance(value, MediaRequestType):
        return value

    if not isinstance(value, str):
        raise MediaRequestEventError(
            "media_type must be MediaRequestType or text",
        )

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    try:
        return MediaRequestType(normalized)
    except ValueError as exc:
        raise MediaRequestEventError(
            f"unsupported media_type: {value!r}",
        ) from exc


def _normalize_status(
    value: MediaRequestStatus | str,
) -> MediaRequestStatus:
    if isinstance(value, MediaRequestStatus):
        return value

    if not isinstance(value, str):
        raise MediaRequestEventError(
            "status must be MediaRequestStatus or text",
        )

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    try:
        return MediaRequestStatus(normalized)
    except ValueError as exc:
        raise MediaRequestEventError(
            f"unsupported status: {value!r}",
        ) from exc


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MediaRequestEventError(f"{field_name} is required")

    return value.strip()


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_text(value, field_name)


def _normalize_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise MediaRequestEventError(
            f"{field_name} must be a datetime",
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise MediaRequestEventError(
            f"{field_name} must be timezone-aware",
        )

    return value.astimezone(timezone.utc)


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    normalized = _required_text(value, field_name)
    candidate = (
        normalized[:-1] + "+00:00"
        if normalized.endswith("Z")
        else normalized
    )

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise MediaRequestEventError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise MediaRequestEventError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_metadata(
    value: object,
) -> tuple[tuple[str, str], ...]:
    if isinstance(value, Mapping):
        items = tuple(value.items())
    elif isinstance(value, tuple):
        items = value
    else:
        raise MediaRequestEventError(
            "metadata must be a mapping or tuple of pairs",
        )

    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()

    for index, item in enumerate(items):
        if not isinstance(item, tuple) or len(item) != 2:
            raise MediaRequestEventError(
                f"metadata[{index}] must be a key/value pair",
            )

        key = _required_text(item[0], f"metadata[{index}].key")
        metadata_value = _required_text(
            item[1],
            f"metadata[{index}].value",
        )

        if key in seen:
            raise MediaRequestEventError(
                f"duplicate metadata key: {key}",
            )

        seen.add(key)
        normalized.append((key, metadata_value))

    return tuple(sorted(normalized))
