"""Normalized Atlas Retention Intelligence report models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class ARIError(ValueError):
    """Raised when an ARI model contains invalid data."""


@dataclass(frozen=True)
class AtlasMetadata:
    """Atlas metadata embedded in an ARI snapshot."""

    version: str
    hostname: str
    schema_version: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "version",
            _required_text(
                self.version,
                "version",
            ),
        )
        object.__setattr__(
            self,
            "hostname",
            _required_text(
                self.hostname,
                "hostname",
            ),
        )
        object.__setattr__(
            self,
            "schema_version",
            _positive_integer(
                self.schema_version,
                "schema_version",
            ),
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> AtlasMetadata:
        """Create normalized Atlas metadata from a mapping."""

        payload = _required_mapping(
            value,
            "atlas",
        )

        return cls(
            version=payload.get("version"),
            hostname=payload.get("hostname"),
            schema_version=payload.get("schema_version"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize Atlas metadata using the snapshot contract."""

        return {
            "version": self.version,
            "hostname": self.hostname,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class StorageSnapshot:
    """Storage metrics embedded in an ARI snapshot."""

    media_root: str
    capacity: str
    capacity_bytes: int
    used: str
    used_bytes: int
    available: str
    available_bytes: int
    utilization_percent: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "media_root",
            _required_text(
                self.media_root,
                "media_root",
            ),
        )
        object.__setattr__(
            self,
            "capacity",
            _required_text(
                self.capacity,
                "capacity",
            ),
        )
        object.__setattr__(
            self,
            "used",
            _required_text(
                self.used,
                "used",
            ),
        )
        object.__setattr__(
            self,
            "available",
            _required_text(
                self.available,
                "available",
            ),
        )

        object.__setattr__(
            self,
            "capacity_bytes",
            _nonnegative_integer(
                self.capacity_bytes,
                "capacity_bytes",
            ),
        )
        object.__setattr__(
            self,
            "used_bytes",
            _nonnegative_integer(
                self.used_bytes,
                "used_bytes",
            ),
        )
        object.__setattr__(
            self,
            "available_bytes",
            _nonnegative_integer(
                self.available_bytes,
                "available_bytes",
            ),
        )
        object.__setattr__(
            self,
            "utilization_percent",
            _percentage(
                self.utilization_percent,
                "utilization_percent",
            ),
        )

        if self.used_bytes > self.capacity_bytes:
            raise ARIError(
                "used_bytes cannot exceed capacity_bytes",
            )

        if self.available_bytes > self.capacity_bytes:
            raise ARIError(
                "available_bytes cannot exceed capacity_bytes",
            )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> StorageSnapshot:
        """Create normalized storage metrics from a mapping."""

        payload = _required_mapping(
            value,
            "storage",
        )

        return cls(
            media_root=payload.get("media_root"),
            capacity=payload.get("capacity"),
            capacity_bytes=payload.get("capacity_bytes"),
            used=payload.get("used"),
            used_bytes=payload.get("used_bytes"),
            available=payload.get("available"),
            available_bytes=payload.get("available_bytes"),
            utilization_percent=payload.get(
                "utilization_percent",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize storage metrics using the snapshot contract."""

        return {
            "media_root": self.media_root,
            "capacity": self.capacity,
            "capacity_bytes": self.capacity_bytes,
            "used": self.used,
            "used_bytes": self.used_bytes,
            "available": self.available,
            "available_bytes": self.available_bytes,
            "utilization_percent": self.utilization_percent,
        }



@dataclass(frozen=True)
class JellyfinLibrary:
    """One Jellyfin library represented in an ARI snapshot."""

    name: str
    type: str
    path: str
    status: str

    def __post_init__(self) -> None:
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
            "type",
            _required_text(
                self.type,
                "type",
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
            ),
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> JellyfinLibrary:
        """Create a Jellyfin library from a snapshot mapping."""

        payload = _required_mapping(
            value,
            "jellyfin library",
        )

        return cls(
            name=payload.get("name"),
            type=payload.get("type"),
            path=payload.get("path"),
            status=payload.get("status"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the Jellyfin library."""

        return {
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "status": self.status,
        }


@dataclass(frozen=True)
class JellyfinUser:
    """One Jellyfin user represented in an ARI snapshot."""

    name: str
    id: str
    administrator: bool
    disabled: bool
    hidden: bool
    last_activity: str | None = None

    def __post_init__(self) -> None:
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
            "id",
            _required_text(
                self.id,
                "id",
            ),
        )

        for field_name in (
            "administrator",
            "disabled",
            "hidden",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, bool):
                raise ARIError(
                    f"{field_name} must be a boolean",
                )

        object.__setattr__(
            self,
            "last_activity",
            _optional_timestamp(
                self.last_activity,
                "last_activity",
            ),
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> JellyfinUser:
        """Create a Jellyfin user from a snapshot mapping."""

        payload = _required_mapping(
            value,
            "jellyfin user",
        )

        return cls(
            name=payload.get("name"),
            id=payload.get("id"),
            administrator=payload.get("administrator"),
            disabled=payload.get("disabled"),
            hidden=payload.get("hidden"),
            last_activity=payload.get("last_activity"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the Jellyfin user."""

        return {
            "name": self.name,
            "id": self.id,
            "administrator": self.administrator,
            "disabled": self.disabled,
            "hidden": self.hidden,
            "last_activity": self.last_activity,
        }


@dataclass(frozen=True)
class JellyfinCounts:
    """Jellyfin media counts represented in an ARI snapshot."""

    movies: int
    series: int
    episodes: int
    songs: int
    albums: int
    books: int
    total_items: int

    def __post_init__(self) -> None:
        for field_name in (
            "movies",
            "series",
            "episodes",
            "songs",
            "albums",
            "books",
            "total_items",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonnegative_integer(
                    getattr(self, field_name),
                    field_name,
                ),
            )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> JellyfinCounts:
        """Create Jellyfin media counts from a snapshot mapping."""

        payload = _required_mapping(
            value,
            "jellyfin counts",
        )

        return cls(
            movies=payload.get("movies"),
            series=payload.get("series"),
            episodes=payload.get("episodes"),
            songs=payload.get("songs"),
            albums=payload.get("albums"),
            books=payload.get("books"),
            total_items=payload.get("total_items"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize Jellyfin media counts."""

        return {
            "movies": self.movies,
            "series": self.series,
            "episodes": self.episodes,
            "songs": self.songs,
            "albums": self.albums,
            "books": self.books,
            "total_items": self.total_items,
        }




@dataclass(frozen=True)
class JellyfinSnapshot:
    """Jellyfin server state embedded in an ARI snapshot."""

    server_name: str
    version: str
    id: str
    libraries: tuple[JellyfinLibrary, ...]
    users: tuple[JellyfinUser, ...]
    counts: JellyfinCounts

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "server_name",
            _required_text(
                self.server_name,
                "server_name",
            ),
        )
        object.__setattr__(
            self,
            "version",
            _required_text(
                self.version,
                "version",
            ),
        )
        object.__setattr__(
            self,
            "id",
            _required_text(
                self.id,
                "id",
            ),
        )

        libraries = _typed_tuple(
            self.libraries,
            JellyfinLibrary,
            "libraries",
        )
        users = _typed_tuple(
            self.users,
            JellyfinUser,
            "users",
        )

        object.__setattr__(
            self,
            "libraries",
            libraries,
        )
        object.__setattr__(
            self,
            "users",
            users,
        )

        if not isinstance(
            self.counts,
            JellyfinCounts,
        ):
            raise ARIError(
                "counts must be a JellyfinCounts",
            )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "JellyfinSnapshot":
        """Create a Jellyfin snapshot from a mapping."""

        payload = _required_mapping(
            value,
            "jellyfin",
        )

        libraries = _required_list(
            payload.get("libraries"),
            "jellyfin libraries",
        )
        users = _required_list(
            payload.get("users"),
            "jellyfin users",
        )

        return cls(
            server_name=payload.get("server_name"),
            version=payload.get("version"),
            id=payload.get("id"),
            libraries=tuple(
                JellyfinLibrary.from_dict(item)
                for item in libraries
            ),
            users=tuple(
                JellyfinUser.from_dict(item)
                for item in users
            ),
            counts=JellyfinCounts.from_dict(
                payload.get("counts"),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the Jellyfin snapshot."""

        return {
            "server_name": self.server_name,
            "version": self.version,
            "id": self.id,
            "libraries": [
                library.to_dict()
                for library in self.libraries
            ],
            "users": [
                user.to_dict()
                for user in self.users
            ],
            "counts": self.counts.to_dict(),
        }


@dataclass(frozen=True)
class ARIReport:
    """Complete normalized Atlas Retention Intelligence report."""

    timestamp: str
    atlas: AtlasMetadata
    storage: StorageSnapshot
    jellyfin: JellyfinSnapshot
    libraries: "FilesystemLibraries"

    SUPPORTED_SCHEMA_VERSION = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "timestamp",
            _required_timestamp(
                self.timestamp,
                "timestamp",
            ),
        )

        if not isinstance(
            self.atlas,
            AtlasMetadata,
        ):
            raise ARIError(
                "atlas must be an AtlasMetadata",
            )

        if not isinstance(
            self.storage,
            StorageSnapshot,
        ):
            raise ARIError(
                "storage must be a StorageSnapshot",
            )

        if not isinstance(
            self.jellyfin,
            JellyfinSnapshot,
        ):
            raise ARIError(
                "jellyfin must be a JellyfinSnapshot",
            )

        if not isinstance(
            self.libraries,
            FilesystemLibraries,
        ):
            raise ARIError(
                "libraries must be a FilesystemLibraries",
            )

        if (
            self.atlas.schema_version
            != self.SUPPORTED_SCHEMA_VERSION
        ):
            raise ARIError(
                "unsupported ARI schema_version: "
                f"{self.atlas.schema_version}"
            )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "ARIReport":
        """Create a complete ARI report from snapshot JSON."""

        payload = _required_mapping(
            value,
            "ARI report",
        )

        return cls(
            timestamp=payload.get("timestamp"),
            atlas=AtlasMetadata.from_dict(
                payload.get("atlas"),
            ),
            storage=StorageSnapshot.from_dict(
                payload.get("storage"),
            ),
            jellyfin=JellyfinSnapshot.from_dict(
                payload.get("jellyfin"),
            ),
            libraries=FilesystemLibraries.from_dict(
                payload.get("libraries"),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete ARI report contract."""

        return {
            "timestamp": self.timestamp,
            "atlas": self.atlas.to_dict(),
            "storage": self.storage.to_dict(),
            "jellyfin": self.jellyfin.to_dict(),
            "libraries": self.libraries.to_dict(),
        }


@dataclass(frozen=True)
class FilesystemLibrary:
    """Filesystem library statistics."""

    count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "count",
            _nonnegative_integer(
                self.count,
                "count",
            ),
        )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "FilesystemLibrary":
        payload = _required_mapping(
            value,
            "filesystem library",
        )

        return cls(
            count=payload.get("count"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
        }


@dataclass(frozen=True)
class FilesystemLibraries:
    """Filesystem library collection."""

    movies: FilesystemLibrary
    tv: FilesystemLibrary
    anime_movies: FilesystemLibrary
    anime_tv: FilesystemLibrary

    def __post_init__(self) -> None:
        for field_name in (
            "movies",
            "tv",
            "anime_movies",
            "anime_tv",
        ):
            value = getattr(self, field_name)

            if not isinstance(
                value,
                FilesystemLibrary,
            ):
                raise ARIError(
                    f"{field_name} must be a FilesystemLibrary",
                )

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "FilesystemLibraries":
        payload = _required_mapping(
            value,
            "libraries",
        )

        return cls(
            movies=FilesystemLibrary.from_dict(
                payload.get("movies"),
            ),
            tv=FilesystemLibrary.from_dict(
                payload.get("tv"),
            ),
            anime_movies=FilesystemLibrary.from_dict(
                payload.get("anime_movies"),
            ),
            anime_tv=FilesystemLibrary.from_dict(
                payload.get("anime_tv"),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "movies": self.movies.to_dict(),
            "tv": self.tv.to_dict(),
            "anime_movies": self.anime_movies.to_dict(),
            "anime_tv": self.anime_tv.to_dict(),
        }



def _required_list(
    value: object,
    field_name: str,
) -> list[Any]:
    if not isinstance(value, list):
        raise ARIError(
            f"{field_name} must be an array",
        )

    return value


def _typed_tuple(
    value: object,
    expected_type: type,
    field_name: str,
) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise ARIError(
            f"{field_name} must be an array",
        )

    normalized = tuple(value)

    if not all(
        isinstance(item, expected_type)
        for item in normalized
    ):
        raise ARIError(
            f"{field_name} must contain "
            f"{expected_type.__name__}",
        )

    return normalized


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    normalized = _optional_timestamp(
        value,
        field_name,
    )

    if normalized is None:
        raise ARIError(
            f"{field_name} is required",
        )

    return normalized


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise ARIError(
            f"{field_name} must be an ISO-8601 timestamp or null",
        )

    from datetime import datetime, timezone

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise ARIError(
            f"{field_name} must be an ISO-8601 timestamp or null",
        ) from exc

    if parsed.tzinfo is None:
        raise ARIError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

def _required_mapping(
    value: object,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ARIError(
            f"{field_name} must be an object",
        )

    return value


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ARIError(
            f"{field_name} is required",
        )

    return value.strip()


def _nonnegative_integer(
    value: object,
    field_name: str,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ARIError(
            f"{field_name} must be a nonnegative integer",
        )

    return value


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
    ):
        raise ARIError(
            f"{field_name} must be a positive integer",
        )

    return value


def _percentage(
    value: object,
    field_name: str,
) -> int:
    normalized = _nonnegative_integer(
        value,
        field_name,
    )

    if normalized > 100:
        raise ARIError(
            f"{field_name} must be between 0 and 100",
        )

    return normalized
