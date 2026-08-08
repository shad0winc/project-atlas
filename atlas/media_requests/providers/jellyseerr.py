"""Jellyseerr media-request provider adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Any, Callable
from urllib.parse import quote

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
