from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


SPORTS_SRC = Path(__file__).resolve().parents[2] / "modules" / "sports" / "src"


def _sports_module(name: str):
    path = str(SPORTS_SRC)
    if path not in sys.path:
        sys.path.insert(0, path)
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def test_legacy_subscription_normalizes_recording_disabled() -> None:
    subscriptions = _sports_module("subscriptions")
    normalized = subscriptions.normalize_subscription(
        {
            "subscription_id": "sub-legacy",
            "type": "team",
            "provider": "thesportsdb",
            "id": "team-1",
            "name": "Legacy Team",
            "user": "usr-1",
            "enabled": True,
        }
    )
    assert normalized["record"] is False


@pytest.mark.parametrize("subscription_type", ["event", "team", "league"])
def test_new_follow_defaults_recording_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    subscription_type: str,
) -> None:
    subscriptions = _sports_module("subscriptions")
    monkeypatch.setattr(subscriptions, "SUBSCRIPTIONS_FILE", tmp_path / "subscriptions.json")

    created, was_created = subscriptions.create_subscription(
        subscription_type,
        "thesportsdb",
        f"{subscription_type}-1",
        f"Test {subscription_type}",
        "usr-1",
    )

    assert was_created is True
    assert created["record"] is False
    persisted = subscriptions.load_subscriptions()
    assert len(persisted) == 1
    assert persisted[0]["record"] is False


def test_follow_only_produces_no_recording_games() -> None:
    worker = _sports_module("worker")
    games = [
        {
            "id": "game-1",
            "provider": "thesportsdb",
            "provider_event_id": "event-1",
            "home_team_id": "team-1",
            "away_team_id": "team-2",
            "league_id": "league-1",
        }
    ]
    follows = [
        {
            "subscription_id": "sub-1",
            "type": "team",
            "provider": "thesportsdb",
            "id": "team-1",
            "name": "Team One",
            "user": "usr-1",
            "enabled": True,
            "record": False,
        }
    ]
    assert worker._recording_enabled_games(games, follows) == []


def test_only_record_enabled_follow_can_feed_recording_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _sports_module("worker")
    games = [{"id": "game-1"}]
    follows = [
        {"subscription_id": "sub-off", "record": False},
        {"subscription_id": "sub-on", "record": True},
    ]
    captured: dict[str, object] = {}

    def fake_resolve(input_games, subscriptions):
        captured["games"] = input_games
        captured["subscriptions"] = subscriptions
        return [{"id": "game-1", "subscription_ids": ["sub-on"]}]

    monkeypatch.setattr(worker, "resolve_subscribed_games", fake_resolve)
    result = worker._recording_enabled_games(games, follows)

    assert result == [{"id": "game-1", "subscription_ids": ["sub-on"]}]
    assert captured["games"] == games
    assert captured["subscriptions"] == [follows[1]]
