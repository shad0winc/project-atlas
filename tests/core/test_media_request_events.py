"""Contract tests for normalized media-request events."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from atlas.media_requests import (
    MediaRequest,
    MediaRequestEvent,
    MediaRequestEventError,
    MediaRequestEventType,
    MediaRequestStatus,
    ProviderEventContext,
    event_type_for_status,
)


OCCURRED = datetime(2026, 8, 3, 4, 0, tzinfo=timezone.utc)


def make_request(**overrides: object) -> MediaRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": "movie",
        "provider": "jellyseerr",
        "provider_media_id": "157336",
        "title": "Interstellar",
        "year": 2014,
        "created_at": "2026-08-03T03:00:00Z",
    }
    values.update(overrides)
    return MediaRequest(**values)


@pytest.mark.parametrize(
    ("status", "event_type"),
    [
        ("pending", MediaRequestEventType.PENDING),
        ("approved", MediaRequestEventType.APPROVED),
        ("searching", MediaRequestEventType.SEARCHING),
        ("downloading", MediaRequestEventType.DOWNLOADING),
        ("importing", MediaRequestEventType.IMPORTING),
        ("available", MediaRequestEventType.AVAILABLE),
        ("rejected", MediaRequestEventType.REJECTED),
        ("failed", MediaRequestEventType.FAILED),
        ("cancelled", MediaRequestEventType.CANCELLED),
    ],
)
def test_event_type_for_status(
    status: str,
    event_type: MediaRequestEventType,
) -> None:
    assert event_type_for_status(status) is event_type


def test_created_event_from_request() -> None:
    event = MediaRequestEvent.from_request(
        "request.created",
        make_request(),
        occurred_at=OCCURRED,
        metadata={"source": "portal"},
    )

    assert event.name == "request.created"
    assert event.status is MediaRequestStatus.PENDING
    assert event.metadata == (("source", "portal"),)
    assert event.to_dict() == {
        "event": "request.created",
        "payload": {
            "request_id": "request-001",
            "user_id": "user-001",
            "provider": "jellyseerr",
            "provider_request_id": None,
            "provider_media_id": "157336",
            "media_type": "movie",
            "title": "Interstellar",
            "year": 2014,
            "season_number": None,
            "status": "pending",
            "terminal": False,
            "available_at": None,
            "occurred_at": "2026-08-03T04:00:00Z",
            "context": None,
            "metadata": {"source": "portal"},
        },
    }


def test_submitted_event_requires_provider_request_id() -> None:
    with pytest.raises(
        MediaRequestEventError,
        match="provider_request_id",
    ):
        MediaRequestEvent.from_request(
            "request.submitted",
            make_request(),
            occurred_at=OCCURRED,
        )


def test_available_event_requires_available_at() -> None:
    with pytest.raises(
        MediaRequestEventError,
        match="available_at",
    ):
        MediaRequestEvent(
            event_type="request.available",
            request_id="request-001",
            user_id="user-001",
            provider="jellyseerr",
            provider_request_id="42",
            provider_media_id="157336",
            media_type="movie",
            title="Interstellar",
            year=2014,
            status="available",
            occurred_at=OCCURRED,
        )


def test_available_event_serializes_context() -> None:
    context = ProviderEventContext(
        provider="jellyseerr",
        provider_media_id="157336",
        media_type="movie",
        title="Interstellar",
        metadata={"library": "Movies"},
    )
    request = make_request(
        provider_request_id="42",
        status="available",
        updated_at="2026-08-03T04:00:00Z",
        available_at="2026-08-03T04:00:00Z",
    )

    event = MediaRequestEvent.from_request(
        "request.available",
        request,
        occurred_at=OCCURRED,
        context=context,
    )

    assert event.to_payload()["terminal"] is True
    assert event.to_payload()["context"] == context.to_dict()


def test_lifecycle_event_must_match_status() -> None:
    with pytest.raises(
        MediaRequestEventError,
        match="does not match",
    ):
        MediaRequestEvent.from_request(
            "request.approved",
            make_request(provider_request_id="42"),
            occurred_at=OCCURRED,
        )


def test_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(
        MediaRequestEventError,
        match="timezone-aware",
    ):
        MediaRequestEvent.from_request(
            "request.created",
            make_request(),
            occurred_at=datetime(2026, 8, 3, 4, 0),
        )


def test_event_models_are_immutable() -> None:
    event = MediaRequestEvent.from_request(
        "request.created",
        make_request(),
        occurred_at=OCCURRED,
    )

    with pytest.raises(FrozenInstanceError):
        event.title = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "event_type",
    ["", "request.unknown", None, True],
)
def test_rejects_invalid_event_type(event_type: object) -> None:
    with pytest.raises(MediaRequestEventError):
        MediaRequestEvent.from_request(
            event_type,  # type: ignore[arg-type]
            make_request(),
            occurred_at=OCCURRED,
        )


def test_rejects_invalid_context() -> None:
    with pytest.raises(
        MediaRequestEventError,
        match="context",
    ):
        MediaRequestEvent.from_request(
            "request.created",
            make_request(),
            occurred_at=OCCURRED,
            context=object(),  # type: ignore[arg-type]
        )
