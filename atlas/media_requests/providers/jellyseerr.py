"""Jellyseerr media-request provider adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Any, Callable
from urllib.parse import quote, urlencode

from ..discovery import (
    MediaDiscoveryAvailability,
    MediaDiscoveryError,
    MediaDiscoveryItem,
    MediaDiscoveryPage,
)
from ..models import (
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)
from ..provider import (
    MediaRequestProviderError,
    ProviderCapabilities,
    ProviderEventContext,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderStatusResult,
    ProviderSubmissionResult,
)
from .base import (
    BaseMediaRequestHTTPProvider,
    MediaRequestHTTPError,
)


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class JellyseerrMediaRequestProvider(BaseMediaRequestHTTPProvider):
    """Translate Jellyseerr request resources into Atlas contracts."""

    clock: Clock = field(
        default=_utc_now,
        repr=False,
        compare=False,
    )

    @property
    def name(self) -> str:
        return "jellyseerr"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types=(
                MediaRequestType.MOVIE,
                MediaRequestType.TV,
                MediaRequestType.ANIME_MOVIE,
                MediaRequestType.ANIME_TV,
            ),
            supports_submission=True,
            supports_status=True,
            supports_cancellation=True,
            supports_webhooks=True,
        )

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        if not isinstance(request, MediaRequest):
            raise MediaRequestProviderError(
                "request must be a MediaRequest",
            )
        if request.provider != self.name:
            raise MediaRequestProviderError(
                "request provider must be jellyseerr",
            )
        if not self.capabilities().supports(request.media_type):
            raise MediaRequestProviderError(
                f"unsupported Jellyseerr media type: {request.media_type.value}",
            )

        payload: dict[str, Any] = {
            "mediaType": _jellyseerr_media_type(request.media_type),
            "mediaId": _numeric_identifier(
                request.provider_media_id,
                "provider_media_id",
            ),
        }

        if request.media_type in {
            MediaRequestType.TV,
            MediaRequestType.ANIME_TV,
        }:
            payload["seasons"] = (
                [request.season_number]
                if request.season_number is not None
                else "all"
            )

        response = self._post_json("/api/v1/request", payload)
        resource = _required_mapping(
            response,
            "Jellyseerr request response",
        )
        provider_request_id = _required_identifier(
            resource.get("id"),
            "Jellyseerr request id",
        )
        status = _normalize_status(resource)
        created_at = _required_timestamp(
            resource.get("createdAt"),
            "Jellyseerr request createdAt",
        )
        updated_at = _optional_timestamp(
            resource.get("updatedAt"),
            "Jellyseerr request updatedAt",
        ) or created_at

        return ProviderSubmissionResult(
            provider=self.name,
            provider_request_id=provider_request_id,
            status=status,
            submitted_at=created_at,
            updated_at=updated_at,
            context=self._context(request, resource),
        )

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        normalized_id = _required_identifier(
            provider_request_id,
            "provider_request_id",
        )
        response = self._get_json(
            f"/api/v1/request/{quote(normalized_id, safe='')}",
        )
        resource = _required_mapping(
            response,
            "Jellyseerr request response",
        )
        returned_id = _required_identifier(
            resource.get("id"),
            "Jellyseerr request id",
        )
        if returned_id != normalized_id:
            raise MediaRequestProviderError(
                "Jellyseerr returned a mismatched request id",
            )

        status = _normalize_status(resource)
        updated_at = _required_timestamp(
            resource.get("updatedAt")
            or resource.get("createdAt"),
            "Jellyseerr request updatedAt",
        )
        available_at = (
            updated_at
            if status is MediaRequestStatus.AVAILABLE
            else None
        )

        return ProviderStatusResult(
            provider=self.name,
            provider_request_id=returned_id,
            status=status,
            updated_at=updated_at,
            available_at=available_at,
            context=_context_from_resource(resource),
        )

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        normalized_id = _required_identifier(
            provider_request_id,
            "provider_request_id",
        )
        self._delete_json(
            f"/api/v1/request/{quote(normalized_id, safe='')}",
        )

        return ProviderStatusResult(
            provider=self.name,
            provider_request_id=normalized_id,
            status=MediaRequestStatus.CANCELLED,
            updated_at=self._timestamp(),
        )

    def search_media(
        self,
        query: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        """Search Jellyseerr for normalized movie/TV discovery items."""

        normalized_query = _search_query(
            query
        )
        normalized_page = _discovery_page_number(
            page
        )

        query_string = urlencode(
            {
                "query":
                    normalized_query,
                "page":
                    normalized_page,
            }
        )

        response = self._get_json(
            f"/api/v1/search?{query_string}"
        )

        return _normalize_discovery_page(
            response,
            expected_media_type=None,
        )

    def discover_media(
        self,
        media_type: MediaRequestType | str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        """Return one Jellyseerr movie or TV discovery page."""

        normalized_type = (
            _discovery_media_type(
                media_type
            )
        )
        normalized_page = (
            _discovery_page_number(
                page
            )
        )

        path_segment = (
            "movies"
            if normalized_type
            is MediaRequestType.MOVIE
            else "tv"
        )

        query_string = urlencode(
            {
                "page":
                    normalized_page,
            }
        )

        response = self._get_json(
            "/api/v1/discover/"
            f"{path_segment}?"
            f"{query_string}"
        )

        return _normalize_discovery_page(
            response,
            expected_media_type=(
                normalized_type
            ),
        )

    def health(self) -> ProviderHealth:
        try:
            response = self._get_json("/api/v1/status")
            resource = _required_mapping(
                response,
                "Jellyseerr status response",
            )
        except (MediaRequestHTTPError, MediaRequestProviderError) as exc:
            return ProviderHealth(
                provider=self.name,
                status=ProviderHealthStatus.UNAVAILABLE,
                checked_at=self._timestamp(),
                message=str(exc),
            )

        version = resource.get("version")
        message = (
            f"Jellyseerr {version}"
            if isinstance(version, str) and version.strip()
            else "Jellyseerr API is reachable"
        )

        return ProviderHealth(
            provider=self.name,
            status=ProviderHealthStatus.HEALTHY,
            checked_at=self._timestamp(),
            message=message,
        )

    def _timestamp(self) -> str:
        value = self.clock()

        if not isinstance(value, datetime):
            raise MediaRequestProviderError(
                "clock must return a datetime",
            )
        if value.tzinfo is None or value.utcoffset() is None:
            raise MediaRequestProviderError(
                "clock must return a timezone-aware datetime",
            )

        return (
            value.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _context(
        self,
        request: MediaRequest,
        resource: Mapping[str, Any],
    ) -> ProviderEventContext:
        media = resource.get("media")
        media_id = request.provider_media_id

        if isinstance(media, Mapping) and media.get("tmdbId") is not None:
            media_id = _required_identifier(
                media.get("tmdbId"),
                "Jellyseerr media tmdbId",
            )

        return ProviderEventContext(
            provider=self.name,
            provider_media_id=media_id,
            media_type=request.media_type,
            title=request.title,
            year=request.year,
            season_number=request.season_number,
            metadata={
                "atlas_request_id": request.request_id,
                "atlas_user_id": request.user_id,
            },
        )


def default_jellyseerr_media_request_provider(
) -> JellyseerrMediaRequestProvider:
    """Build the configured Jellyseerr request provider."""

    base_url = os.getenv("ATLAS_JELLYSEERR_URL", "").strip()

    if not base_url:
        host = os.getenv("LXC_IP", "127.0.0.1").strip() or "127.0.0.1"
        port = os.getenv("JELLYSEERR_PORT", "5055").strip() or "5055"
        base_url = f"http://{host}:{port}"

    return JellyseerrMediaRequestProvider(
        base_url=base_url,
        api_key=os.getenv("ATLAS_JELLYSEERR_API_KEY", ""),
    )


# Keep aligned with the pinned Seerr runtime MediaStatus enum.
# The upstream OpenAPI description omits the blocklisted state.
_DISCOVERY_MEDIA_STATUS = {
    1:
        MediaDiscoveryAvailability.UNKNOWN,
    2:
        MediaDiscoveryAvailability.PENDING,
    3:
        MediaDiscoveryAvailability.PROCESSING,
    4:
        MediaDiscoveryAvailability.PARTIALLY_AVAILABLE,
    5:
        MediaDiscoveryAvailability.AVAILABLE,
    6:
        MediaDiscoveryAvailability.BLOCKLISTED,
    7:
        MediaDiscoveryAvailability.DELETED,
}


def _normalize_discovery_page(
    value: object,
    *,
    expected_media_type: MediaRequestType | None,
) -> MediaDiscoveryPage:
    resource = _required_mapping(
        value,
        "Jellyseerr discovery response",
    )

    page = _positive_integer(
        resource.get("page"),
        "Jellyseerr discovery page",
    )

    total_pages = _non_negative_integer(
        resource.get("totalPages"),
        "Jellyseerr discovery totalPages",
    )

    results = resource.get(
        "results"
    )

    if not isinstance(
        results,
        list,
    ):
        raise MediaRequestProviderError(
            "Jellyseerr discovery results "
            "must be an array"
        )

    items: list[
        MediaDiscoveryItem
    ] = []

    for index, result in enumerate(
        results
    ):
        raw_item = _required_mapping(
            result,
            "Jellyseerr discovery "
            f"results[{index}]",
        )

        media_type = (
            expected_media_type
            if expected_media_type
            is not None
            else _search_result_media_type(
                raw_item.get(
                    "mediaType"
                )
            )
        )

        # General Jellyseerr search also returns people.
        # They are not an Atlas Request target.
        if media_type is None:
            continue

        try:
            item = _discovery_item(
                raw_item,
                media_type=media_type,
            )
        except MediaDiscoveryError as exc:
            raise MediaRequestProviderError(
                "Jellyseerr returned invalid "
                "media discovery metadata"
            ) from exc

        items.append(
            item
        )

    try:
        return MediaDiscoveryPage(
            items=tuple(
                items
            ),
            page=page,
            total_pages=total_pages,
        )
    except MediaDiscoveryError as exc:
        raise MediaRequestProviderError(
            "Jellyseerr returned an invalid "
            "media discovery page"
        ) from exc


def _discovery_item(
    resource: Mapping[str, Any],
    *,
    media_type: MediaRequestType,
) -> MediaDiscoveryItem:
    provider_media_id = str(
        _numeric_identifier(
            resource.get("id"),
            "Jellyseerr discovery id",
        )
    )

    if media_type is MediaRequestType.MOVIE:
        title = _required_discovery_text(
            resource.get("title"),
            "Jellyseerr movie title",
        )
        year = _year_from_date(
            resource.get(
                "releaseDate"
            ),
            "Jellyseerr movie releaseDate",
        )
    else:
        title = _required_discovery_text(
            resource.get("name"),
            "Jellyseerr TV name",
        )
        year = _year_from_date(
            resource.get(
                "firstAirDate"
            ),
            "Jellyseerr TV firstAirDate",
        )

    availability = (
        _discovery_availability(
            resource.get(
                "mediaInfo"
            )
        )
    )

    return MediaDiscoveryItem(
        provider_media_id=(
            provider_media_id
        ),
        media_type=media_type,
        title=title,
        year=year,
        overview=_optional_discovery_text(
            resource.get(
                "overview"
            ),
            "Jellyseerr discovery overview",
        ),
        poster_path=_optional_discovery_text(
            resource.get(
                "posterPath"
            ),
            "Jellyseerr discovery posterPath",
        ),
        availability=availability,
    )


def _discovery_availability(
    media_info: object,
) -> MediaDiscoveryAvailability:
    # Jellyseerr does not attach MediaInfo to an untracked result.
    # That is the one state B3.1 treats as immediately requestable.
    if media_info is None:
        return (
            MediaDiscoveryAvailability
            .NOT_TRACKED
        )

    resource = _required_mapping(
        media_info,
        "Jellyseerr discovery mediaInfo",
    )

    status = _required_integer(
        resource.get("status"),
        "Jellyseerr discovery mediaInfo status",
    )

    availability = (
        _DISCOVERY_MEDIA_STATUS
        .get(status)
    )

    if availability is None:
        raise MediaRequestProviderError(
            "Jellyseerr returned an unsupported "
            "media availability status"
        )

    return availability


def _search_result_media_type(
    value: object,
) -> MediaRequestType | None:
    if not isinstance(
        value,
        str,
    ):
        raise MediaRequestProviderError(
            "Jellyseerr search mediaType "
            "must be text"
        )

    normalized = (
        value
        .strip()
        .lower()
    )

    if normalized == "person":
        return None

    if normalized == "movie":
        return MediaRequestType.MOVIE

    if normalized == "tv":
        return MediaRequestType.TV

    raise MediaRequestProviderError(
        "Jellyseerr returned an unsupported "
        "search mediaType"
    )


def _discovery_media_type(
    value: MediaRequestType | str,
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
            raise MediaRequestProviderError(
                "media_type must be movie or tv"
            ) from exc
    else:
        raise MediaRequestProviderError(
            "media_type must be a "
            "MediaRequestType or text"
        )

    if normalized not in {
        MediaRequestType.MOVIE,
        MediaRequestType.TV,
    }:
        raise MediaRequestProviderError(
            "media_type must be movie or tv"
        )

    return normalized


def _search_query(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise MediaRequestProviderError(
            "query must be text"
        )

    normalized = value.strip()

    if not normalized:
        raise MediaRequestProviderError(
            "query is required"
        )

    if len(normalized) > 200:
        raise MediaRequestProviderError(
            "query must contain at most "
            "200 characters"
        )

    return normalized


def _discovery_page_number(
    value: object,
) -> int:
    return _positive_integer(
        value,
        "page",
    )


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
        raise MediaRequestProviderError(
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
        raise MediaRequestProviderError(
            f"{field_name} must be a "
            "non-negative integer"
        )

    return value


def _required_discovery_text(
    value: object,
    field_name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
    ):
        raise MediaRequestProviderError(
            f"{field_name} is required"
        )

    return value.strip()


def _optional_discovery_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise MediaRequestProviderError(
            f"{field_name} must be text or null"
        )

    normalized = value.strip()

    return (
        normalized
        if normalized
        else None
    )


def _year_from_date(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise MediaRequestProviderError(
            f"{field_name} must be text or null"
        )

    normalized = value.strip()

    if not normalized:
        return None

    if (
        len(normalized) < 4
        or not normalized[:4].isdigit()
    ):
        raise MediaRequestProviderError(
            f"{field_name} must begin with a year"
        )

    return int(
        normalized[:4]
    )


def _normalize_status(
    resource: Mapping[str, Any],
) -> MediaRequestStatus:
    request_status = _required_integer(
        resource.get("status"),
        "Jellyseerr request status",
    )
    media = resource.get("media")
    media_status: int | None = None

    if isinstance(media, Mapping) and media.get("status") is not None:
        media_status = _required_integer(
            media.get("status"),
            "Jellyseerr media status",
        )

    if media_status == 5:
        return MediaRequestStatus.AVAILABLE
    if request_status == 3:
        return MediaRequestStatus.REJECTED
    if media_status == 6:
        return MediaRequestStatus.FAILED
    if media_status == 4:
        return MediaRequestStatus.IMPORTING
    if media_status == 3:
        return MediaRequestStatus.SEARCHING
    if request_status == 2:
        return MediaRequestStatus.APPROVED
    if request_status == 1:
        return MediaRequestStatus.PENDING

    raise MediaRequestProviderError(
        "Jellyseerr returned unsupported request status",
    )


def _context_from_resource(
    resource: Mapping[str, Any],
) -> ProviderEventContext | None:
    media = resource.get("media")
    if not isinstance(media, Mapping):
        return None

    tmdb_id = media.get("tmdbId")
    if tmdb_id is None:
        return None

    media_type = resource.get("type") or resource.get("mediaType")
    if not isinstance(media_type, str):
        return None

    normalized_type = (
        MediaRequestType.MOVIE
        if media_type.strip().lower() == "movie"
        else MediaRequestType.TV
        if media_type.strip().lower() == "tv"
        else None
    )
    if normalized_type is None:
        return None

    title = media.get("title") or media.get("name")
    if not isinstance(title, str) or not title.strip():
        return None

    return ProviderEventContext(
        provider="jellyseerr",
        provider_media_id=_required_identifier(
            tmdb_id,
            "Jellyseerr media tmdbId",
        ),
        media_type=normalized_type,
        title=title,
    )


def _jellyseerr_media_type(
    media_type: MediaRequestType,
) -> str:
    if media_type in {
        MediaRequestType.MOVIE,
        MediaRequestType.ANIME_MOVIE,
    }:
        return "movie"
    if media_type in {
        MediaRequestType.TV,
        MediaRequestType.ANIME_TV,
    }:
        return "tv"
    raise MediaRequestProviderError(
        f"unsupported Jellyseerr media type: {media_type.value}",
    )


def _numeric_identifier(
    value: object,
    field_name: str,
) -> int:
    normalized = _required_identifier(value, field_name)
    if not normalized.isdigit():
        raise MediaRequestProviderError(
            f"{field_name} must be a numeric TMDB identifier",
        )
    return int(normalized)


def _required_identifier(
    value: object,
    field_name: str,
) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise MediaRequestProviderError(
            f"{field_name} must be text or an integer",
        )
    normalized = str(value).strip()
    if not normalized:
        raise MediaRequestProviderError(
            f"{field_name} is required",
        )
    return normalized


def _required_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MediaRequestProviderError(
            f"{field_name} must be an integer",
        )
    return value


def _required_mapping(
    value: object,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MediaRequestProviderError(
            f"{field_name} must be an object",
        )
    return value


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MediaRequestProviderError(
            f"{field_name} is required",
        )

    candidate = value.strip()
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

    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _required_timestamp(value, field_name)
