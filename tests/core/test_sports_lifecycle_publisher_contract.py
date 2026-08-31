from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPORTS_SRC = ROOT / "modules" / "sports" / "src"


def _controller(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.syspath_prepend(str(SPORTS_SRC))

    for name in ("controller", "feed", "lifecycle"):
        sys.modules.pop(name, None)

    controller = importlib.import_module("controller")

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "games.json"

    monkeypatch.setattr(controller, "STATE_DIR", state_dir)
    monkeypatch.setattr(controller, "STATE_FILE", state_file)
    monkeypatch.setattr(controller, "generate_feed", lambda: 0)

    return controller, state_file


def _game(status: str) -> dict[str, object]:
    return {
        "id": "event-001",
        "provider": "thesportsdb",
        "provider_event_id": "event-001",
        "name": "Atlas Home vs Atlas Away",
        "status": status,
        "start_at": "2026-08-07T00:00:00+00:00",
        "subscription_count": 1,
        "subscription_types": ["event"],
        "subscribed_users": ["user-001"],
        "subscription_ids": ["subscription-001"],
    }


def test_started_event_uses_atlas_module_publish_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    controller, state_file = _controller(monkeypatch, tmp_path)

    previous = _game("scheduled")
    previous["lifecycle_state"] = "scheduled"
    state_file.write_text(
        json.dumps({"event-001": previous}) + "\n",
        encoding="utf-8",
    )

    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        controller,
        "publish_event",
        lambda *args: calls.append(args),
    )

    controller.process_games(
        [_game("live")],
        now=datetime(2026, 8, 7, 0, 30, tzinfo=timezone.utc),
    )

    assert len(calls) == 1
    module, event_name, payload = calls[0]
    assert module == "sports"
    assert event_name == "sports.game-started"
    assert payload["game_id"] == "event-001"
    assert payload["status"] == "started"


def test_finished_event_uses_atlas_module_publish_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    controller, state_file = _controller(monkeypatch, tmp_path)

    previous = _game("final")
    previous["lifecycle_state"] = "grace"
    previous["final_at"] = "2026-08-07T00:00:00+00:00"
    state_file.write_text(
        json.dumps({"event-001": previous}) + "\n",
        encoding="utf-8",
    )

    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        controller,
        "publish_event",
        lambda *args: calls.append(args),
    )

    controller.process_games(
        [_game("finished")],
        now=datetime(2026, 8, 7, 1, 0, tzinfo=timezone.utc),
    )

    assert len(calls) == 1
    module, event_name, payload = calls[0]
    assert module == "sports"
    assert event_name == "sports.game-finished"
    assert payload["game_id"] == "event-001"
    assert payload["status"] == "finished"
