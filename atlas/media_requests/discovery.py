"""Read-only media-discovery contracts for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .models import MediaRequestType


class MediaDiscoveryError(ValueError):
    """Raised when a normalized media-discovery contract is invalid."""


class MediaDiscoveryAvailability(str, Enum):
    """Normalized Jellyseerr discovery availability state."""

    NOT_TRACKED = "not_tracked"
    UNKNOWN = "unknown"
    PENDING = "pending"
    PROCESSING = "processing"
    PARTIALLY_AVAILABLE = "partially_available"
    AVAILABLE = "available"
    BLOCKLISTED = "blocklisted"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class MediaDiscoveryItem:
    """One normalized movie or TV discovery result."""

    provider_media_id: str
    media_type: MediaRequestType
    title: str
    availability: MediaDiscoveryAvailability
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None

    def __post_init__(self) -> None:
        provider_media_id = _numeric_identity(
            self.provider_media_id,
            "provider_media_id",
        )

        media_type = _media_type(
            self.media_type,
            "media_type",
        )

        title = _required_text(
            self.title,
            "title",
        )

        availability = _availability(
            self.availability,
            "availability",
        )

        year = _optional_year(
            self.year,
            "year",
        )

        overview = _optional_text(
            self.overview,
            "overview",
        )

        poster_path = _optional_path(
            self.poster_path,
            "poster_path",
        )

        object.__setattr__(
            self,
            "provider_media_id",
            provider_media_id,
        )
        object.__setattr__(
            self,
            "media_type",
            media_type,
        )
        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "availability",
            availability,
        )
        object.__setattr__(
            self,
            "year",
            year,
        )
        object.__setattr__(
            self,
            "overview",
            overview,
        )
        object.__setattr__(
            self,
            "poster_path",
            poster_path,
        )

    @property
    def request_eligible(
        self,
    ) -> bool:
        """Return whether B3.3 may present a Request action."""

        return (
            self.availability
            is MediaDiscoveryAvailability.NOT_TRACKED
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Return a deterministic serialized discovery item."""

        return {
            "provider_media_id":
                self.provider_media_id,
            "media_type":
                self.media_type.value,
            "title":
                self.title,
            "year":
                self.year,
            "overview":
                self.overview,
            "poster_path":
                self.poster_path,
            "availability":
                self.availability.value,
            "request_eligible":
                self.request_eligible,
        }


@dataclass(frozen=True, slots=True)
class MediaDiscoveryPage:
    """One normalized Jellyseerr discovery/search page."""

    items: tuple[
        MediaDiscoveryItem,
        ...,
    ]
    page: int
    total_pages: int

    def __post_init__(self) -> None:
        try:
            items = tuple(
                self.items
            )
        except TypeError as exc:
            raise MediaDiscoveryError(
                "items must be iterable"
            ) from exc

        for index, item in enumerate(
            items
        ):
            if not isinstance(
                item,
                MediaDiscoveryItem,
            ):
                raise MediaDiscoveryError(
                    f"items[{index}] must be a "
                    "MediaDiscoveryItem"
                )

        page = _positive_integer(
            self.page,
            "page",
        )

        total_pages = _non_negative_integer(
            self.total_pages,
            "total_pages",
        )

        if items and total_pages == 0:
            raise MediaDiscoveryError(
                "total_pages cannot be zero "
                "when items are present"
            )

        identities = {
            (
                item.media_type,
                item.provider_media_id,
            )
            for item in items
        }

        if len(identities) != len(items):
            raise MediaDiscoveryError(
                "discovery item identities "
                "must be unique within a page"
            )

        object.__setattr__(
            self,
            "items",
            items,
        )
        object.__setattr__(
            self,
            "page",
            page,
        )
        object.__setattr__(
            self,
            "total_pages",
            total_pages,
        )

    @property
    def next_page(
        self,
    ) -> int | None:
        """Return the next provider page when one exists."""

        if (
            self.total_pages == 0
            or self.page >= self.total_pages
        ):
            return None

        return self.page + 1

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Return a deterministic serialized discovery page."""

        return {
            "items": [
                item.to_dict()
                for item in self.items
            ],
            "page":
                self.page,
            "total_pages":
                self.total_pages,
            "next_page":
                self.next_page,
        }


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be text"
        )

    normalized = value.strip()

    if not normalized:
        raise MediaDiscoveryError(
            f"{field_name} is required"
        )

    return normalized


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be text or null"
        )

    normalized = value.strip()

    return (
        normalized
        if normalized
        else None
    )


def _optional_path(
    value: object,
    field_name: str,
) -> str | None:
    normalized = _optional_text(
        value,
        field_name,
    )

    if normalized is None:
        return None

    if not normalized.startswith(
        "/"
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be a relative provider path"
        )

    return normalized


def _numeric_identity(
    value: object,
    field_name: str,
) -> str:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (
                str,
                int,
            ),
        )
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be text or an integer"
        )

    normalized = str(
        value
    ).strip()

    if not normalized:
        raise MediaDiscoveryError(
            f"{field_name} is required"
        )

    if (
        not normalized.isdigit()
        or int(normalized) <= 0
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be a positive "
            "numeric TMDB identifier"
        )

    return normalized


def _media_type(
    value: object,
    field_name: str,
) -> MediaRequestType:
    if isinstance(
        value,
        MediaRequestType,
    ):
        normalized = value
    elif isinstance(
        value,
        str,
    ):
        candidate = (
            value
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        try:
            normalized = (
                MediaRequestType(
                    candidate
                )
            )
        except ValueError as exc:
            raise MediaDiscoveryError(
                f"{field_name} is unsupported"
            ) from exc
    else:
        raise MediaDiscoveryError(
            f"{field_name} must be a "
            "MediaRequestType or text"
        )

    if normalized not in {
        MediaRequestType.MOVIE,
        MediaRequestType.TV,
    }:
        raise MediaDiscoveryError(
            f"{field_name} must be movie or tv"
        )

    return normalized


def _availability(
    value: object,
    field_name: str,
) -> MediaDiscoveryAvailability:
    if isinstance(
        value,
        MediaDiscoveryAvailability,
    ):
        return value

    if not isinstance(
        value,
        str,
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be "
            "MediaDiscoveryAvailability or text"
        )

    normalized = (
        value
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return MediaDiscoveryAvailability(
            normalized
        )
    except ValueError as exc:
        raise MediaDiscoveryError(
            f"{field_name} is unsupported"
        ) from exc


def _optional_year(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            int,
        )
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be an integer or null"
        )

    current_year = (
        datetime.now(
            timezone.utc
        ).year
    )

    if not (
        1888
        <= value
        <= current_year + 10
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be between "
            f"1888 and {current_year + 10}"
        )

    return value


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            int,
        )
        or value <= 0
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be a positive integer"
        )

    return value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise MediaDiscoveryError(
            f"{field_name} must be a "
            "non-negative integer"
        )

    return value
