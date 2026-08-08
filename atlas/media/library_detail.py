"""Normalized media-library detail contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal


MediaLibraryDetailStatus = Literal[
    "available",
    "unavailable",
]

MediaLibrarySynchronization = Literal[
    "synchronized",
    "out_of_sync",
    "unknown",
]

MEDIA_LIBRARY_IDS = frozenset(
    {
        "movies",
        "television",
        "anime-movies",
        "anime-television",
        "music",
        "books",
        "photos",
    }
)


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
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a string or null"
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


def _required_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be a boolean"
        )

    return value


def _optional_boolean(
    value: object,
    field_name: str,
) -> bool | None:
    if value is None:
        return None

    return _required_boolean(
        value,
        field_name,
    )


@dataclass(frozen=True)
class MediaLibraryFilesystem:
    """Filesystem information for one Atlas media library."""

    path: str
    item_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "path",
            _required_text(
                self.path,
                "path",
            ),
        )
        object.__setattr__(
            self,
            "item_count",
            _nonnegative_integer(
                self.item_count,
                "item_count",
            ),
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "MediaLibraryFilesystem":
        """Create filesystem detail from a mapping."""

        if not isinstance(value, dict):
            raise ValueError(
                "filesystem must be an object"
            )

        return cls(
            path=value.get("path"),
            item_count=value.get("item_count"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize filesystem detail."""

        return {
            "path": self.path,
            "item_count": self.item_count,
        }


@dataclass(frozen=True)
class MediaLibraryProvider:
    """Provider information for one Atlas media library."""

    name: str
    library_name: str
    library_type: str
    path: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _required_text(
                self.name,
                "name",
            ).lower(),
        )
        object.__setattr__(
            self,
            "library_name",
            _required_text(
                self.library_name,
                "library_name",
            ),
        )
        object.__setattr__(
            self,
            "library_type",
            _required_text(
                self.library_type,
                "library_type",
            ).lower(),
        )
        object.__setattr__(
            self,
            "path",
            _required_text(
                self.path,
                "path",
            ),
        )
        object.__setattr__(
            self,
            "status",
            _required_text(
                self.status,
                "status",
            ).lower(),
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "MediaLibraryProvider":
        """Create provider detail from a mapping."""

        if not isinstance(value, dict):
            raise ValueError(
                "provider must be an object"
            )

        return cls(
            name=value.get("name"),
            library_name=value.get("library_name"),
            library_type=value.get("library_type"),
            path=value.get("path"),
            status=value.get("status"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize provider detail."""

        return {
            "name": self.name,
            "library_name": self.library_name,
            "library_type": self.library_type,
            "path": self.path,
            "status": self.status,
        }


@dataclass(frozen=True)
class MediaLibraryValidation:
    """Validation state for one Atlas media library."""

    configured: bool
    path_matches: bool | None
    synchronization: MediaLibrarySynchronization

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "configured",
            _required_boolean(
                self.configured,
                "configured",
            ),
        )
        object.__setattr__(
            self,
            "path_matches",
            _optional_boolean(
                self.path_matches,
                "path_matches",
            ),
        )

        if self.synchronization not in (
            "synchronized",
            "out_of_sync",
            "unknown",
        ):
            raise ValueError(
                "synchronization must be synchronized, "
                "out_of_sync, or unknown"
            )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "MediaLibraryValidation":
        """Create validation detail from a mapping."""

        if not isinstance(value, dict):
            raise ValueError(
                "validation must be an object"
            )

        return cls(
            configured=value.get("configured"),
            path_matches=value.get("path_matches"),
            synchronization=value.get("synchronization"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize validation detail."""

        return {
            "configured": self.configured,
            "path_matches": self.path_matches,
            "synchronization": self.synchronization,
        }


@dataclass(frozen=True)
class MediaLibraryDetail:
    """Normalized read-only detail for one Atlas media library."""

    id: str
    label: str
    status: MediaLibraryDetailStatus
    generated_at: str
    count: int | None
    validation: MediaLibraryValidation
    detail: str | None = None
    filesystem: MediaLibraryFilesystem | None = None
    provider: MediaLibraryProvider | None = None

    def __post_init__(self) -> None:
        normalized_id = _required_text(
            self.id,
            "id",
        ).lower()

        if normalized_id not in MEDIA_LIBRARY_IDS:
            raise ValueError(
                f"unsupported media library ID: {normalized_id}"
            )

        object.__setattr__(
            self,
            "id",
            normalized_id,
        )
        object.__setattr__(
            self,
            "label",
            _required_text(
                self.label,
                "label",
            ),
        )
        object.__setattr__(
            self,
            "generated_at",
            _normalized_timestamp(
                self.generated_at,
                "generated_at",
            ),
        )

        if self.status not in (
            "available",
            "unavailable",
        ):
            raise ValueError(
                "status must be available or unavailable"
            )

        if self.count is not None:
            object.__setattr__(
                self,
                "count",
                _nonnegative_integer(
                    self.count,
                    "count",
                ),
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
            _optional_text(
                self.detail,
                "detail",
            ),
        )

        if (
            self.filesystem is not None
            and not isinstance(
                self.filesystem,
                MediaLibraryFilesystem,
            )
        ):
            raise ValueError(
                "filesystem must be "
                "MediaLibraryFilesystem or null"
            )

        if (
            self.provider is not None
            and not isinstance(
                self.provider,
                MediaLibraryProvider,
            )
        ):
            raise ValueError(
                "provider must be "
                "MediaLibraryProvider or null"
            )

        if not isinstance(
            self.validation,
            MediaLibraryValidation,
        ):
            raise ValueError(
                "validation must be "
                "MediaLibraryValidation"
            )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "MediaLibraryDetail":
        """Create media-library detail from a mapping."""

        if not isinstance(value, dict):
            raise ValueError(
                "media library detail must be an object"
            )

        filesystem_value = value.get("filesystem")
        provider_value = value.get("provider")

        return cls(
            id=value.get("id"),
            label=value.get("label"),
            status=value.get("status"),
            generated_at=value.get("generated_at"),
            count=value.get("count"),
            detail=value.get("detail"),
            filesystem=(
                None
                if filesystem_value is None
                else MediaLibraryFilesystem.from_dict(
                    filesystem_value
                )
            ),
            provider=(
                None
                if provider_value is None
                else MediaLibraryProvider.from_dict(
                    provider_value
                )
            ),
            validation=MediaLibraryValidation.from_dict(
                value.get("validation")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete media-library detail."""

        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "generated_at": self.generated_at,
            "count": self.count,
            "detail": self.detail,
            "filesystem": (
                None
                if self.filesystem is None
                else self.filesystem.to_dict()
            ),
            "provider": (
                None
                if self.provider is None
                else self.provider.to_dict()
            ),
            "validation": self.validation.to_dict(),
        }
