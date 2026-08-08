"""Read-only media-library detail assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
from typing import Callable

from atlas.ari import (
    ARIError,
    ARIReport,
    JellyfinLibrary,
)
from atlas.media import (
    MEDIA_LIBRARY_IDS,
    MediaLibraryDetail,
    MediaLibraryFilesystem,
    MediaLibraryProvider,
    MediaLibraryValidation,
)


Clock = Callable[[], datetime]


@dataclass(frozen=True)
class MediaLibraryDefinition:
    """Stable mapping between Atlas and provider library identities."""

    id: str
    label: str
    directory_name: str
    jellyfin_names: tuple[str, ...]
    jellyfin_types: tuple[str, ...]


MEDIA_LIBRARY_DEFINITIONS = (
    MediaLibraryDefinition(
        id="movies",
        label="Movies",
        directory_name="Movies",
        jellyfin_names=("movies",),
        jellyfin_types=("movies",),
    ),
    MediaLibraryDefinition(
        id="television",
        label="Television",
        directory_name="TV",
        jellyfin_names=("television", "tv", "tv shows"),
        jellyfin_types=("tvshows", "shows"),
    ),
    MediaLibraryDefinition(
        id="anime-movies",
        label="Anime Movies",
        directory_name="Anime Movies",
        jellyfin_names=("anime movies",),
        jellyfin_types=("movies",),
    ),
    MediaLibraryDefinition(
        id="anime-television",
        label="Anime Television",
        directory_name="Anime TV",
        jellyfin_names=(
            "anime television",
            "anime tv",
            "anime shows",
        ),
        jellyfin_types=("tvshows", "shows"),
    ),
    MediaLibraryDefinition(
        id="music",
        label="Music",
        directory_name="Music",
        jellyfin_names=("music",),
        jellyfin_types=("music",),
    ),
    MediaLibraryDefinition(
        id="books",
        label="Books",
        directory_name="Books",
        jellyfin_names=("books",),
        jellyfin_types=("books",),
    ),
    MediaLibraryDefinition(
        id="photos",
        label="Photos",
        directory_name="Photos",
        jellyfin_names=("photos",),
        jellyfin_types=("photos", "homevideos"),
    ),
)

_DEFINITIONS_BY_ID = {
    definition.id: definition
    for definition in MEDIA_LIBRARY_DEFINITIONS
}


class MediaLibraryDetailService:
    """Read one normalized media-library detail from ARI."""

    def __init__(
        self,
        snapshot_path: Path,
        *,
        clock: Clock | None = None,
    ) -> None:
        if not isinstance(snapshot_path, Path):
            raise TypeError(
                "snapshot_path must be a Path"
            )

        if clock is not None and not callable(clock):
            raise TypeError(
                "clock must be callable or null"
            )

        self._snapshot_path = snapshot_path.expanduser()
        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

    def read_detail(
        self,
        library_id: str,
    ) -> MediaLibraryDetail:
        """Return detail for one stable Atlas media-library ID."""

        definition = self._definition(library_id)

        try:
            report = self._read_report()
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ARIError,
            ValueError,
        ) as error:
            return self._unavailable(
                definition,
                detail=(
                    "Unable to read the latest ARI snapshot: "
                    f"{type(error).__name__}"
                ),
            )

        return self._from_report(
            definition,
            report,
        )

    def _read_report(self) -> ARIReport:
        payload = json.loads(
            self._snapshot_path.read_text(
                encoding="utf-8"
            )
        )

        return ARIReport.from_dict(payload)

    def _from_report(
        self,
        definition: MediaLibraryDefinition,
        report: ARIReport,
    ) -> MediaLibraryDetail:
        count, detail = self._count(
            definition.id,
            report,
        )

        filesystem_path = str(
            PurePosixPath(
                report.storage.media_root
            )
            / definition.directory_name
        )

        filesystem = (
            None
            if count is None
            else MediaLibraryFilesystem(
                path=filesystem_path,
                item_count=count,
            )
        )

        jellyfin_library = self._provider_library(
            definition,
            report.jellyfin.libraries,
        )

        provider = (
            None
            if jellyfin_library is None
            else MediaLibraryProvider(
                name="jellyfin",
                library_name=jellyfin_library.name,
                library_type=jellyfin_library.type,
                path=jellyfin_library.path,
                status=jellyfin_library.status,
            )
        )

        path_matches = (
            None
            if jellyfin_library is None
            else self._paths_match(
                filesystem_path,
                jellyfin_library.path,
            )
        )

        synchronization = (
            "unknown"
            if path_matches is None
            else (
                "synchronized"
                if path_matches
                else "out_of_sync"
            )
        )

        return MediaLibraryDetail(
            id=definition.id,
            label=definition.label,
            status=(
                "available"
                if count is not None
                else "unavailable"
            ),
            generated_at=report.timestamp,
            count=count,
            detail=detail,
            filesystem=filesystem,
            provider=provider,
            validation=MediaLibraryValidation(
                configured=provider is not None,
                path_matches=path_matches,
                synchronization=synchronization,
            ),
        )

    def _unavailable(
        self,
        definition: MediaLibraryDefinition,
        *,
        detail: str,
    ) -> MediaLibraryDetail:
        return MediaLibraryDetail(
            id=definition.id,
            label=definition.label,
            status="unavailable",
            generated_at=self._timestamp(),
            count=None,
            detail=detail,
            filesystem=None,
            provider=None,
            validation=MediaLibraryValidation(
                configured=False,
                path_matches=None,
                synchronization="unknown",
            ),
        )

    @staticmethod
    def _definition(
        library_id: str,
    ) -> MediaLibraryDefinition:
        if not isinstance(library_id, str):
            raise TypeError(
                "library_id must be a string"
            )

        normalized_id = library_id.strip().lower()

        if normalized_id not in MEDIA_LIBRARY_IDS:
            raise KeyError(
                f"unsupported media library ID: {normalized_id}"
            )

        return _DEFINITIONS_BY_ID[normalized_id]

    @staticmethod
    def _count(
        library_id: str,
        report: ARIReport,
    ) -> tuple[int | None, str]:
        if library_id == "movies":
            return (
                report.libraries.movies.count,
                "Filesystem library count",
            )

        if library_id == "television":
            return (
                report.libraries.tv.count,
                "Filesystem library count",
            )

        if library_id == "anime-movies":
            return (
                report.libraries.anime_movies.count,
                "Filesystem library count",
            )

        if library_id == "anime-television":
            return (
                report.libraries.anime_tv.count,
                "Filesystem library count",
            )

        if library_id == "music":
            return (
                report.jellyfin.counts.songs,
                "Jellyfin song count",
            )

        if library_id == "books":
            return (
                report.jellyfin.counts.books,
                "Jellyfin book count",
            )

        return (
            None,
            "Photo counts are not yet collected by ARI",
        )

    @staticmethod
    def _provider_library(
        definition: MediaLibraryDefinition,
        libraries: tuple[JellyfinLibrary, ...],
    ) -> JellyfinLibrary | None:
        normalized_names = {
            name.casefold()
            for name in definition.jellyfin_names
        }

        for library in libraries:
            if library.name.strip().casefold() in normalized_names:
                return library

        type_matches = tuple(
            library
            for library in libraries
            if library.type.strip().casefold()
            in definition.jellyfin_types
        )

        if len(type_matches) == 1:
            return type_matches[0]

        return None

    @staticmethod
    def _paths_match(
        filesystem_path: str,
        provider_path: str,
    ) -> bool:
        filesystem_name = (
            PurePosixPath(filesystem_path)
            .name
            .strip()
            .casefold()
        )
        provider_name = (
            PurePosixPath(provider_path)
            .name
            .strip()
            .casefold()
        )

        return filesystem_name == provider_name

    def _timestamp(self) -> str:
        timestamp = self._clock()

        if (
            not isinstance(timestamp, datetime)
            or timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(
                "clock must return a timezone-aware datetime"
            )

        return (
            timestamp.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
