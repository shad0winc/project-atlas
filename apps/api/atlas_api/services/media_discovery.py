"""Read-only Jellyseerr media discovery application service."""

from __future__ import annotations

from typing import Protocol

from atlas.media_requests import (
    MediaDiscoveryPage,
    MediaRequestProviderError,
    MediaRequestProviderOperationError,
    default_jellyseerr_media_request_provider,
)


class MediaDiscoveryServiceError(
    RuntimeError
):
    """Base API media-discovery failure."""


class MediaDiscoveryValidationError(
    MediaDiscoveryServiceError
):
    """Raised when caller discovery input is invalid."""


class MediaDiscoveryUnavailableError(
    MediaDiscoveryServiceError
):
    """Raised when Jellyseerr discovery cannot be read safely."""


class MediaDiscoveryProvider(
    Protocol
):
    """Read-only provider methods used by Atlas media discovery."""

    def search_media(
        self,
        query: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        """Search provider media."""

        ...

    def discover_media(
        self,
        media_type: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        """Browse provider media."""

        ...


class MediaDiscoveryAPIService:
    """Expose normalized read-only provider discovery."""

    def __init__(
        self,
        provider: MediaDiscoveryProvider,
    ) -> None:
        if not callable(
            getattr(
                provider,
                "search_media",
                None,
            )
        ):
            raise TypeError(
                "provider must expose search_media"
            )

        if not callable(
            getattr(
                provider,
                "discover_media",
                None,
            )
        ):
            raise TypeError(
                "provider must expose discover_media"
            )

        self._provider = provider

    def search(
        self,
        query: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        normalized_query = (
            _query(
                query
            )
        )
        normalized_page = (
            _page(
                page
            )
        )

        try:
            return (
                self._provider
                .search_media(
                    normalized_query,
                    page=normalized_page,
                )
            )
        except (
            MediaRequestProviderError,
            MediaRequestProviderOperationError,
        ) as exc:
            raise MediaDiscoveryUnavailableError(
                "media discovery provider "
                "is unavailable"
            ) from exc

    def discover(
        self,
        media_type: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        normalized_type = (
            _media_type(
                media_type
            )
        )
        normalized_page = (
            _page(
                page
            )
        )

        try:
            return (
                self._provider
                .discover_media(
                    normalized_type,
                    page=normalized_page,
                )
            )
        except (
            MediaRequestProviderError,
            MediaRequestProviderOperationError,
        ) as exc:
            raise MediaDiscoveryUnavailableError(
                "media discovery provider "
                "is unavailable"
            ) from exc


def build_default_media_discovery_api_service(
) -> MediaDiscoveryAPIService:
    """Build the configured Jellyseerr discovery application service."""

    try:
        provider = (
            default_jellyseerr_media_request_provider()
        )
    except (
        MediaRequestProviderError,
        MediaRequestProviderOperationError,
        OSError,
        ValueError,
    ) as exc:
        raise MediaDiscoveryUnavailableError(
            "media discovery provider "
            "is unavailable"
        ) from exc

    return MediaDiscoveryAPIService(
        provider
    )


def _query(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise MediaDiscoveryValidationError(
            "query must be text"
        )

    normalized = value.strip()

    if not normalized:
        raise MediaDiscoveryValidationError(
            "query is required"
        )

    if len(normalized) > 200:
        raise MediaDiscoveryValidationError(
            "query must contain at most "
            "200 characters"
        )

    return normalized


def _media_type(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise MediaDiscoveryValidationError(
            "media_type must be text"
        )

    normalized = (
        value
        .strip()
        .lower()
    )

    if normalized not in {
        "movie",
        "tv",
    }:
        raise MediaDiscoveryValidationError(
            "media_type must be movie or tv"
        )

    return normalized


def _page(
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            int,
        )
        or value <= 0
    ):
        raise MediaDiscoveryValidationError(
            "page must be a positive integer"
        )

    return value
