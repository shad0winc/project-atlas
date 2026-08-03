"""Request notification integration tests."""

from __future__ import annotations

import sys
from pathlib import Path

NOTIFICATIONS_SRC = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "notifications"
    / "src"
)

sys.path.insert(
    0,
    str(NOTIFICATIONS_SRC),
)

from formatter import (  # noqa: E402
    notification_description,
    notification_fields,
    notification_route,
    notification_title,
)
from processor import (  # noqa: E402
    build_notification,
    classify_severity,
)


def request_event(
    event_name: str = "request.available",
    media_type: str = "movie",
) -> dict:
    return {
        "id": "evt-request-1",
        "event": event_name,
        "source": "media-requests",
        "payload": {
            "request_id": "req-1",
            "user_id": "user-1",
            "provider": "jellyseerr",
            "provider_request_id": "42",
            "provider_media_id": "550",
            "media_type": media_type,
            "title": "Fight Club",
            "year": 1999,
            "season_number": None,
            "status": event_name.removeprefix(
                "request."
            ),
            "terminal": event_name in {
                "request.available",
                "request.rejected",
                "request.failed",
                "request.cancelled",
            },
            "available_at": (
                "2026-08-03T04:00:00Z"
                if event_name == "request.available"
                else None
            ),
            "occurred_at": "2026-08-03T04:00:00Z",
            "context": None,
            "metadata": {},
        },
    }


def test_request_routes_use_media_type() -> None:
    expected = {
        "movie": "movies",
        "tv": "tv",
        "anime_movie": "anime_movies",
        "anime_tv": "anime_tv",
    }

    for media_type, route in expected.items():
        notification = build_notification(
            request_event(
                media_type=media_type,
            )
        )

        assert notification_route(notification) == route


def test_unknown_request_media_type_routes_to_system() -> None:
    notification = build_notification(
        request_event(
            media_type="unknown",
        )
    )

    assert notification_route(notification) == "system"


def test_available_request_is_ready_to_watch_success() -> None:
    notification = build_notification(
        request_event()
    )

    assert notification["severity"] == "success"
    assert notification_title(notification) == "Ready to Watch"

    assert (
        notification_description(notification)
        == "Fight Club (1999) is ready to watch."
    )


def test_request_fields_include_normalized_context() -> None:
    notification = build_notification(
        request_event()
    )

    fields = {
        field["name"]: field["value"]
        for field in notification_fields(
            notification
        )
    }

    assert fields["Media"] == "Fight Club"
    assert fields["Year"] == "1999"
    assert fields["Type"] == "Movie"
    assert fields["Status"] == "Available"
    assert fields["Provider"] == "Jellyseerr"
    assert fields["Request ID"] == "req-1"

    assert (
        fields["Available At"]
        == "2026-08-03T04:00:00Z"
    )


def test_request_season_is_included_when_present() -> None:
    event = request_event(
        media_type="tv",
    )
    event["payload"]["season_number"] = 3

    notification = build_notification(event)

    fields = {
        field["name"]: field["value"]
        for field in notification_fields(
            notification
        )
    }

    assert fields["Season"] == "3"


def test_request_lifecycle_titles_are_explicit() -> None:
    expected = {
        "request.created": "Media Request Created",
        "request.submitted": "Media Request Submitted",
        "request.pending": "Media Request Pending",
        "request.approved": "Media Request Approved",
        "request.searching": "Media Search Started",
        "request.downloading": "Media Download Started",
        "request.importing": "Media Import Started",
        "request.available": "Ready to Watch",
        "request.rejected": "Media Request Rejected",
        "request.failed": "Media Request Failed",
        "request.cancelled": "Media Request Cancelled",
    }

    for event_name, title in expected.items():
        notification = build_notification(
            request_event(event_name)
        )

        assert notification_title(notification) == title


def test_request_terminal_failure_severity_is_warning() -> None:
    for event_name in (
        "request.failed",
        "request.rejected",
        "request.cancelled",
    ):
        assert (
            classify_severity(
                event_name,
                {},
            )
            == "warning"
        )


def test_non_terminal_request_severity_is_info() -> None:
    for event_name in (
        "request.created",
        "request.submitted",
        "request.pending",
        "request.approved",
        "request.searching",
        "request.downloading",
        "request.importing",
    ):
        assert (
            classify_severity(
                event_name,
                {},
            )
            == "info"
        )


def test_request_processing_preserves_event_contract() -> None:
    event = request_event()
    notification = build_notification(event)

    assert notification["event_id"] == event["id"]
    assert notification["event"] == event["event"]
    assert notification["source"] == event["source"]
    assert notification["payload"] == event["payload"]
