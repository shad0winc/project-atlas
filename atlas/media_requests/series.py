"""Read-only TV-series detail contracts for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from .discovery import MediaDiscoveryAvailability


class MediaSeriesError(ValueError):
    """Raised when a normalized TV-series detail contract is invalid."""


class MediaSeriesStatus(str, Enum):
    """Normalized provider lifecycle state for a television series."""

    RETURNING = "returning"
    PLANNED = "planned"
    IN_PRODUCTION = "in_production"
    ENDED = "ended"
    CANCELLED = "cancelled"
    PILOT = "pilot"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MediaSeriesSeason:
    """One requestable non-special television season."""

    season_number: int
    name: str
    episode_count: int
    air_date: str | None = None

    def __post_init__(self) -> None:
        season_number = _positive_integer(
            self.season_number,
            "season_number",
        )
        name = _required_text(
            self.name,
            "name",
        )
        episode_count = _non_negative_integer(
            self.episode_count,
            "episode_count",
        )
        air_date = _optional_date(
            self.air_date,
            "air_date",
        )

        object.__setattr__(
            self,
            "season_number",
            season_number,
        )
        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "episode_count",
            episode_count,
        )
        object.__setattr__(
            self,
            "air_date",
            air_date,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Return deterministic serialized season metadata."""

        return {
            "season_number":
                self.season_number,
            "name":
                self.name,
            "episode_count":
                self.episode_count,
            "air_date":
                self.air_date,
        }


@dataclass(frozen=True, slots=True)
class MediaSeriesDetail:
    """Normalized TV-series detail used for explicit season selection."""

    provider_media_id: str
    title: str
    status: MediaSeriesStatus
    in_production: bool
    is_anime: bool
    availability: MediaDiscoveryAvailability
    seasons: tuple[
        MediaSeriesSeason,
        ...,
    ]
    year: int | None = None
    overview: str | None = None
    poster_path: str | None = None

    def __post_init__(self) -> None:
        provider_media_id = _numeric_identity(
            self.provider_media_id,
            "provider_media_id",
        )
        title = _required_text(
            self.title,
            "title",
        )
        status = _status(
            self.status,
            "status",
        )
        in_production = _boolean(
            self.in_production,
            "in_production",
        )
        is_anime = _boolean(
            self.is_anime,
            "is_anime",
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

        try:
            seasons = tuple(
                self.seasons
            )
        except TypeError as exc:
            raise MediaSeriesError(
                "seasons must be iterable"
            ) from exc

        for index, season in enumerate(
            seasons
        ):
            if not isinstance(
                season,
                MediaSeriesSeason,
            ):
                raise MediaSeriesError(
                    f"seasons[{index}] must be a "
                    "MediaSeriesSeason"
                )

        season_numbers = [
            season.season_number
            for season in seasons
        ]

        if (
            len(set(season_numbers))
            != len(season_numbers)
        ):
            raise MediaSeriesError(
                "season numbers must be unique"
            )

        seasons = tuple(
            sorted(
                seasons,
                key=lambda season:
                    season.season_number,
            )
        )

        object.__setattr__(
            self,
            "provider_media_id",
            provider_media_id,
        )
        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "status",
            status,
        )
        object.__setattr__(
            self,
            "in_production",
            in_production,
        )
        object.__setattr__(
            self,
            "is_anime",
            is_anime,
        )
        object.__setattr__(
            self,
            "availability",
            availability,
        )
        object.__setattr__(
            self,
            "seasons",
            seasons,
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
        """Return advisory whole-series eligibility from provider state."""

        return (
            self.availability
            is MediaDiscoveryAvailability.NOT_TRACKED
        )

    @property
    def is_ongoing(
        self,
    ) -> bool:
        """Return whether provider metadata describes an active series."""

        return (
            self.in_production
            or self.status
            in {
                MediaSeriesStatus.RETURNING,
                MediaSeriesStatus.PLANNED,
                MediaSeriesStatus.IN_PRODUCTION,
                MediaSeriesStatus.PILOT,
            }
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Return deterministic serialized TV-series detail."""

        return {
            "provider_media_id":
                self.provider_media_id,
            "title":
                self.title,
            "year":
                self.year,
            "overview":
                self.overview,
            "poster_path":
                self.poster_path,
            "status":
                self.status.value,
            "in_production":
                self.in_production,
            "is_ongoing":
                self.is_ongoing,
            "is_anime":
                self.is_anime,
            "availability":
                self.availability.value,
            "request_eligible":
                self.request_eligible,
            "seasons": [
                season.to_dict()
                for season in self.seasons
            ],
        }


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise MediaSeriesError(
            f"{field_name} must be text"
        )

    normalized = value.strip()

    if not normalized:
        raise MediaSeriesError(
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
        raise MediaSeriesError(
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
        raise MediaSeriesError(
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
        raise MediaSeriesError(
            f"{field_name} must be text or an integer"
        )

    normalized = str(
        value
    ).strip()

    if (
        not normalized
        or not normalized.isdigit()
        or int(normalized) <= 0
    ):
        raise MediaSeriesError(
            f"{field_name} must be a positive "
            "numeric TMDB identifier"
        )

    return normalized


def _status(
    value: object,
    field_name: str,
) -> MediaSeriesStatus:
    if isinstance(
        value,
        MediaSeriesStatus,
    ):
        return value

    if not isinstance(
        value,
        str,
    ):
        raise MediaSeriesError(
            f"{field_name} must be MediaSeriesStatus or text"
        )

    normalized = (
        value
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return MediaSeriesStatus(
            normalized
        )
    except ValueError as exc:
        raise MediaSeriesError(
            f"{field_name} is unsupported"
        ) from exc


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
        raise MediaSeriesError(
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
        raise MediaSeriesError(
            f"{field_name} is unsupported"
        ) from exc


def _boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(
        value,
        bool,
    ):
        raise MediaSeriesError(
            f"{field_name} must be a boolean"
        )

    return value


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
        raise MediaSeriesError(
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
        raise MediaSeriesError(
            f"{field_name} must be between "
            f"1888 and {current_year + 10}"
        )

    return value


def _optional_date(
    value: object,
    field_name: str,
) -> str | None:
    normalized = _optional_text(
        value,
        field_name,
    )

    if normalized is None:
        return None

    try:
        date.fromisoformat(
            normalized
        )
    except ValueError as exc:
        raise MediaSeriesError(
            f"{field_name} must be an ISO date"
        ) from exc

    return normalized


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
        raise MediaSeriesError(
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
        raise MediaSeriesError(
            f"{field_name} must be a non-negative integer"
        )

    return value
