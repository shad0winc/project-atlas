"""Normalized media-library summary contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from atlas.ari import ARIReport


MediaLibraryStatus = Literal[
    "available",
    "unavailable",
]


@dataclass(frozen=True)
class MediaLibraryCount:
    """One normalized media-library count."""

    id: str
    label: str
    count: int | None
    status: MediaLibraryStatus
    detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "id",
            _required_text(self.id, "id").lower(),
        )
        object.__setattr__(
            self,
            "label",
            _required_text(self.label, "label"),
        )

        if self.count is not None:
            object.__setattr__(
                self,
                "count",
                _nonnegative_integer(self.count, "count"),
            )

        if self.status not in (
            "available",
            "unavailable",
        ):
            raise ValueError(
                "status must be available or unavailable"
            )

        if self.status == "available" and self.count is None:
            raise ValueError(
                "available media libraries require a count"
            )

        if self.status == "unavailable" and self.count is not None:
            raise ValueError(
                "unavailable media libraries cannot have a count"
            )

        object.__setattr__(
            self,
            "detail",
            _optional_text(self.detail),
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "MediaLibraryCount":
        """Create a media-library count from a mapping."""

        if not isinstance(value, dict):
            raise ValueError(
                "media library count must be an object"
            )

        return cls(
            id=value.get("id"),
            label=value.get("label"),
            count=value.get("count"),
            status=value.get("status"),
            detail=value.get("detail"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the media-library count."""

        return {
            "id": self.id,
            "label": self.label,
            "count": self.count,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class MediaLibrarySummary:
    """Normalized media-library statistics for the Atlas Portal."""

    generated_at: str
    libraries: tuple[MediaLibraryCount, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generated_at",
            _normalized_timestamp(
                self.generated_at,
                "generated_at",
            ),
        )

        if not isinstance(
            self.libraries,
            (tuple, list),
        ):
            raise ValueError(
                "libraries must be an array"
            )

        normalized_libraries = tuple(self.libraries)

        if not all(
            isinstance(library, MediaLibraryCount)
            for library in normalized_libraries
        ):
            raise ValueError(
                "libraries must contain MediaLibraryCount values"
            )

        library_ids = {
            library.id
            for library in normalized_libraries
        }

        if len(library_ids) != len(normalized_libraries):
            raise ValueError(
                "media library IDs must be unique"
            )

        object.__setattr__(
            self,
            "libraries",
            normalized_libraries,
        )

    @classmethod
    def from_ari_report(
        cls,
        report: ARIReport,
    ) -> "MediaLibrarySummary":
        """Build a media summary from a validated ARI report."""

        if not isinstance(report, ARIReport):
            raise TypeError(
                "report must be an ARIReport"
            )

        return cls(
            generated_at=report.timestamp,
            libraries=(
                MediaLibraryCount(
                    id="movies",
                    label="Movies",
                    count=report.libraries.movies.count,
                    status="available",
                    detail="Filesystem library count",
                ),
                MediaLibraryCount(
                    id="television",
                    label="Television",
                    count=report.libraries.tv.count,
                    status="available",
                    detail="Filesystem library count",
                ),
                MediaLibraryCount(
                    id="anime-movies",
                    label="Anime Movies",
                    count=report.libraries.anime_movies.count,
                    status="available",
                    detail="Filesystem library count",
                ),
                MediaLibraryCount(
                    id="anime-television",
                    label="Anime Television",
                    count=report.libraries.anime_tv.count,
                    status="available",
                    detail="Filesystem library count",
                ),
                MediaLibraryCount(
                    id="music",
                    label="Music",
                    count=report.jellyfin.counts.songs,
                    status="available",
                    detail="Jellyfin song count",
                ),
                MediaLibraryCount(
                    id="books",
                    label="Books",
                    count=report.jellyfin.counts.books,
                    status="available",
                    detail="Jellyfin book count",
                ),
                MediaLibraryCount(
                    id="photos",
                    label="Photos",
                    count=None,
                    status="unavailable",
                    detail="Photo counts are not yet collected by ARI",
                ),
            ),
        )

    @classmethod
    def unavailable(
        cls,
        *,
        generated_at: str | None = None,
        detail: str = "ARI media statistics are unavailable",
    ) -> "MediaLibrarySummary":
        """Return the stable unavailable summary contract."""

        timestamp = generated_at or (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

        labels = (
            ("movies", "Movies"),
            ("television", "Television"),
            ("anime-movies", "Anime Movies"),
            ("anime-television", "Anime Television"),
            ("music", "Music"),
            ("books", "Books"),
            ("photos", "Photos"),
        )

        return cls(
            generated_at=timestamp,
            libraries=tuple(
                MediaLibraryCount(
                    id=library_id,
                    label=label,
                    count=None,
                    status="unavailable",
                    detail=detail,
                )
                for library_id, label in labels
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete media-library summary."""

        return {
            "generated_at": self.generated_at,
            "libraries": [
                library.to_dict()
                for library in self.libraries
            ],
        }


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field_name} is required"
        )

    return value.strip()


def _optional_text(
    value: object,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            "detail must be a string or null"
        )

    normalized = value.strip()

    return normalized or None


def _nonnegative_integer(
    value: object,
    field_name: str,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(
            f"{field_name} must be a nonnegative integer"
        )

    return value


def _normalized_timestamp(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(
        value,
        field_name,
    )

    try:
        timestamp = datetime.fromisoformat(
            normalized.replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ValueError(
            f"{field_name} must be an ISO-8601 timestamp"
        ) from error

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(
            f"{field_name} must include a timezone"
        )

    return (
        timestamp.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
