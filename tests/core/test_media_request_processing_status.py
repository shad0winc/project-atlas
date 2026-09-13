"""Request processing-in-Jellyfin lifecycle contracts."""

from __future__ import annotations

from atlas.media_requests.events import (
    event_type_for_status,
)
from atlas.media_requests.models import (
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)


def make_processing_request() -> MediaRequest:
    return MediaRequest(
        request_id="req-processing",
        user_id="user-1",
        media_type=MediaRequestType.MOVIE,
        provider="jellyseerr",
        provider_media_id="157336",
        title="Example Movie",
        status=MediaRequestStatus.PROCESSING,
        provider_request_id="42",
        created_at="2026-09-13T03:00:00Z",
        updated_at="2026-09-13T03:30:00Z",
    )


def test_processing_status_has_stable_value() -> None:
    assert (
        MediaRequestStatus.PROCESSING.value
        == "processing"
    )


def test_processing_request_is_active_and_not_available() -> None:
    request = make_processing_request()

    assert request.status is MediaRequestStatus.PROCESSING
    assert request.active is True
    assert request.terminal is False
    assert request.available_at is None


def test_processing_status_maps_to_request_processing_event() -> None:
    event_type = event_type_for_status(
        MediaRequestStatus.PROCESSING
    )

    assert event_type.value == "request.processing"


def test_processing_request_serializes_without_available_at() -> None:
    payload = make_processing_request().to_dict()

    assert payload["status"] == "processing"
    assert payload["terminal"] is False
    assert payload["active"] is True
    assert payload["available_at"] is None
