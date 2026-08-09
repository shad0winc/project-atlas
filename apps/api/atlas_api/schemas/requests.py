"""Authenticated media-request API contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict

from atlas.media_requests import (
    MediaRequest,
    MediaRequestStatus,
)


_RECOVERY_REQUIRED_STATUSES = frozenset(
    {
        MediaRequestStatus.SUBMITTING,
        MediaRequestStatus.CANCELLING,
    }
)


class MediaRequestCreateRequest(BaseModel):
    """Caller-controlled fields for one new media request."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    media_type: str
    provider_media_id: str
    title: str
    year: int | None = None
    season_number: int | None = None


class MediaRequestResponse(BaseModel):
    """Self-scoped media-request representation returned to a user."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    request_id: str
    user_id: str
    media_type: str
    provider: str
    provider_media_id: str
    title: str
    year: int | None
    season_number: int | None
    status: str
    terminal: bool
    active: bool
    can_cancel: bool
    recovery_required: bool
    created_at: str
    updated_at: str
    available_at: str | None

    @classmethod
    def from_domain(
        cls,
        request: MediaRequest,
    ) -> Self:
        """Adapt one validated Core request into its public API form."""

        if not isinstance(request, MediaRequest):
            raise TypeError(
                "request must be a MediaRequest"
            )

        recovery_required = (
            request.status
            in _RECOVERY_REQUIRED_STATUSES
        )

        can_cancel = (
            request.provider_request_id is not None
            and request.active
            and not recovery_required
        )

        return cls(
            request_id=request.request_id,
            user_id=request.user_id,
            media_type=request.media_type.value,
            provider=request.provider,
            provider_media_id=request.provider_media_id,
            title=request.title,
            year=request.year,
            season_number=request.season_number,
            status=request.status.value,
            terminal=request.terminal,
            active=request.active,
            can_cancel=can_cancel,
            recovery_required=recovery_required,
            created_at=request.created_at,
            updated_at=request.updated_at,
            available_at=request.available_at,
        )


class MediaRequestListResponse(BaseModel):
    """Collection of requests owned by one authenticated user."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    requests: tuple[MediaRequestResponse, ...]
