"""Normalized media-request domain models for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any


_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?$",
)
_PROVIDER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class MediaRequestError(ValueError):
    """Raised when a media-request model contains invalid data."""


class MediaRequestType(str, Enum):
    """Normalized media categories supported by Atlas requests."""

    MOVIE = "movie"
    TV = "tv"
    ANIME_MOVIE = "anime_movie"
    ANIME_TV = "anime_tv"
    SPORTS = "sports"


class MediaRequestStatus(str, Enum):
    """Normalized lifecycle states for an Atlas media request."""

    PENDING = "pending"
    APPROVED = "approved"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    AVAILABLE = "available"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class MediaRequest:
    """Normalized, provider-independent Atlas media-request contract."""

    request_id: str
    user_id: str
    media_type: MediaRequestType
    provider: str
    provider_media_id: str
    title: str
    status: MediaRequestStatus = MediaRequestStatus.PENDING
    provider_request_id: str | None = None
    year: int | None = None
    season_number: int | None = None
    created_at: str = field(default_factory=lambda: _now_timestamp())
    updated_at: str | None = None
    available_at: str | None = None

    def __post_init__(self) -> None:
        request_id = _required_identity(self.request_id, "request_id")
        user_id = _required_identity(self.user_id, "user_id")
        media_type = _normalize_media_type(self.media_type, "media_type")
        provider = _required_provider(self.provider, "provider")
        provider_media_id = _required_identity(
            self.provider_media_id,
            "provider_media_id",
        )
        title = _required_text(self.title, "title")
        status = _normalize_status(self.status, "status")
        provider_request_id = _optional_identity(
            self.provider_request_id,
            "provider_request_id",
        )
        year = _optional_year(self.year, "year")
        season_number = _optional_non_negative_integer(
            self.season_number,
            "season_number",
        )
        created_at = _required_timestamp(self.created_at, "created_at")
        updated_at = _optional_timestamp(self.updated_at, "updated_at")
        available_at = _optional_timestamp(
            self.available_at,
            "available_at",
        )

        if media_type in {
            MediaRequestType.MOVIE,
            MediaRequestType.ANIME_MOVIE,
            MediaRequestType.SPORTS,
        } and season_number is not None:
            raise MediaRequestError(
                "season_number is only valid for tv and anime_tv requests",
            )

        if status is MediaRequestStatus.AVAILABLE and available_at is None:
            raise MediaRequestError(
                "available_at is required when status is available",
            )

        if available_at is not None and status is not MediaRequestStatus.AVAILABLE:
            raise MediaRequestError(
                "available_at is only valid when status is available",
            )

        if updated_at is not None and updated_at < created_at:
            raise MediaRequestError(
                "updated_at must not be earlier than created_at",
            )

        if available_at is not None and available_at < created_at:
            raise MediaRequestError(
                "available_at must not be earlier than created_at",
            )

        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "media_type", media_type)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(
            self,
            "provider_media_id",
            provider_media_id,
        )
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "provider_request_id",
            provider_request_id,
        )
        object.__setattr__(self, "year", year)
        object.__setattr__(self, "season_number", season_number)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(
            self,
            "updated_at",
            updated_at or created_at,
        )
        object.__setattr__(self, "available_at", available_at)

    @property
    def terminal(self) -> bool:
        """Return whether the request has reached a terminal lifecycle state."""

        return self.status in {
            MediaRequestStatus.AVAILABLE,
            MediaRequestStatus.REJECTED,
            MediaRequestStatus.FAILED,
            MediaRequestStatus.CANCELLED,
        }

    @property
    def active(self) -> bool:
        """Return whether request processing may still continue."""

        return not self.terminal

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized media-request contract."""

        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "media_type": self.media_type.value,
            "provider": self.provider,
            "provider_request_id": self.provider_request_id,
            "provider_media_id": self.provider_media_id,
            "title": self.title,
            "year": self.year,
            "season_number": self.season_number,
            "status": self.status.value,
            "terminal": self.terminal,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "available_at": self.available_at,
        }


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise MediaRequestError(f"{field_name} must be text")

    normalized = value.strip()
    if not normalized:
        raise MediaRequestError(f"{field_name} is required")

    return normalized


def _required_identity(value: object, field_name: str) -> str:
    if isinstance(value, bool):
        raise MediaRequestError(
            f"{field_name} must be text or an integer",
        )

    if isinstance(value, int):
        normalized = str(value)
    else:
        normalized = _required_text(value, field_name)

    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise MediaRequestError(
            f"{field_name} contains unsupported characters",
        )

    return normalized


def _optional_identity(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_identity(value, field_name)


def _required_provider(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name).lower().replace(" ", "-")

    if not _PROVIDER_PATTERN.fullmatch(normalized):
        raise MediaRequestError(
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
        raise MediaRequestError(
            f"{field_name} must be a MediaRequestType or text",
        )

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    try:
        return MediaRequestType(normalized)
    except ValueError as exc:
        raise MediaRequestError(
            f"{field_name} is not supported: {value!r}",
        ) from exc


def _normalize_status(
    value: object,
    field_name: str,
) -> MediaRequestStatus:
    if isinstance(value, MediaRequestStatus):
        return value

    if not isinstance(value, str):
        raise MediaRequestError(
            f"{field_name} must be a MediaRequestStatus or text",
        )

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")

    try:
        return MediaRequestStatus(normalized)
    except ValueError as exc:
        raise MediaRequestError(
            f"{field_name} is not supported: {value!r}",
        ) from exc


def _optional_year(value: object, field_name: str) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise MediaRequestError(
            f"{field_name} must be an integer or null",
        )

    current_year = datetime.now(timezone.utc).year
    if not 1888 <= value <= current_year + 10:
        raise MediaRequestError(
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
        raise MediaRequestError(
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
        raise MediaRequestError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise MediaRequestError(
            f"{field_name} must include a timezone",
        )

    normalized = parsed.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")
