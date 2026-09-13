"""Scheduler registration contracts for media-request reconciliation."""

from __future__ import annotations

from typing import Any

from atlas.media_requests.scheduler import (
    MEDIA_REQUEST_RECONCILE_CALLBACK,
    MEDIA_REQUEST_RECONCILE_DESCRIPTION,
    MEDIA_REQUEST_RECONCILE_INTERVAL_SECONDS,
    MEDIA_REQUEST_RECONCILE_TASK_NAME,
    register_media_request_reconciliation,
)


class RecordingScheduler:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def register(
        self,
        name: str,
        interval_seconds: int,
        callback: str,
        *,
        description: str = "",
        enabled: bool = True,
        module: str | None = None,
    ) -> dict[str, Any]:
        value = {
            "name": name,
            "interval_seconds": interval_seconds,
            "callback": callback,
            "description": description,
            "enabled": enabled,
            "module": module,
        }
        self.calls.append(value)
        return value


def test_canonical_request_reconcile_scheduler_values_are_frozen() -> None:
    assert MEDIA_REQUEST_RECONCILE_TASK_NAME == "requests.reconcile"
    assert MEDIA_REQUEST_RECONCILE_INTERVAL_SECONDS == 60
    assert MEDIA_REQUEST_RECONCILE_CALLBACK == (
        "python3 -m atlas.media_requests.scheduled_reconcile"
    )
    assert MEDIA_REQUEST_RECONCILE_DESCRIPTION == (
        "Reconcile active media requests with provider status"
    )


def test_register_media_request_reconciliation_uses_core_scheduler() -> None:
    scheduler = RecordingScheduler()

    registered = register_media_request_reconciliation(scheduler)

    assert registered == {
        "name": "requests.reconcile",
        "interval_seconds": 60,
        "callback": (
            "python3 -m atlas.media_requests.scheduled_reconcile"
        ),
        "description": (
            "Reconcile active media requests with provider status"
        ),
        "enabled": True,
        "module": None,
    }
    assert scheduler.calls == [registered]


def test_register_media_request_reconciliation_accepts_overrides() -> None:
    scheduler = RecordingScheduler()

    registered = register_media_request_reconciliation(
        scheduler,
        interval_seconds=30,
        enabled=False,
    )

    assert registered["interval_seconds"] == 30
    assert registered["enabled"] is False
    assert registered["module"] is None
