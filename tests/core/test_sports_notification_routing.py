# Sports notification routing stabilization contracts.

from __future__ import annotations

import sys
from pathlib import Path

NOTIFICATIONS_SRC = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "notifications"
    / "src"
)
sys.path.insert(0, str(NOTIFICATIONS_SRC))

from formatter import notification_route  # noqa: E402
from router import NotificationRouter  # noqa: E402


class RecordingAdapter:
    name = "recording"

    def __init__(self) -> None:
        self.events: list[str] = []

    def enabled(self) -> bool:
        return True

    def deliver(self, notification: dict[str, object]) -> bool:
        self.events.append(str(notification.get("event", "")))
        return True


def notification(event_name: str) -> dict[str, object]:
    return {
        "event": event_name,
        "source": "sports",
        "severity": "info",
        "payload": {},
    }


def test_provider_health_routes_to_system() -> None:
    assert notification_route(
        notification("sports.provider-degraded")
    ) == "system"
    assert notification_route(
        notification("sports.provider-recovered")
    ) == "system"


def test_normal_sports_events_keep_sports_route() -> None:
    assert notification_route(
        notification("sports.ready")
    ) == "sports"


def test_game_lifecycle_is_log_only_until_user_preferences_exist() -> None:
    router = NotificationRouter()
    adapter = RecordingAdapter()
    router.adapters = [adapter]

    assert router.deliver(
        notification("sports.game-started")
    )
    assert router.deliver(
        notification("sports.game-finished")
    )

    assert adapter.events == []


def test_other_sports_notifications_still_deliver() -> None:
    router = NotificationRouter()
    adapter = RecordingAdapter()
    router.adapters = [adapter]

    assert router.deliver(
        notification("sports.ready")
    )

    assert adapter.events == ["sports.ready"]
