"""Cross-boundary unavailable-provider safety tests for M-023.23."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from urllib.error import URLError

import pytest

from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError


def _sports_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType, ModuleType, ModuleType]:
    project_root = Path(__file__).resolve().parents[2]
    sports_src = project_root / "modules" / "sports" / "src"
    monkeypatch.syspath_prepend(str(sports_src))

    controller = importlib.import_module("controller")
    recordings = importlib.import_module("recordings")
    worker = importlib.import_module("worker")

    return controller, recordings, worker


def test_jellyfin_unreachable_listing_is_not_empty_success() -> None:
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=URLError("connection refused"),
    ):
        with pytest.raises(
            MediaProviderError,
            match="Jellyfin is unreachable",
        ):
            provider.list_media_item_ids()


def test_jellyfin_timeout_listing_is_not_empty_success() -> None:
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=TimeoutError("timed out"),
    ):
        with pytest.raises(
            MediaProviderError,
            match="Jellyfin is unreachable",
        ):
            provider.list_media_item_ids()


def test_sports_empty_provider_input_preserves_recording_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, recordings, _ = _sports_modules(monkeypatch)
    registry = tmp_path / "recordings.json"
    existing = {
        "recording-event-001": {
            "id": "recording-event-001",
            "game_id": "event-001",
            "status": "recording",
            "pid": 12345,
            "process_start_time": 67890,
        }
    }
    registry.write_text(
        json.dumps(existing) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        recordings,
        "RECORDINGS_FILE",
        registry,
    )

    result = recordings.plan_recordings([])

    assert result == existing
    assert json.loads(registry.read_text(encoding="utf-8")) == existing


def test_sports_empty_provider_input_preserves_nonfinished_game_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    controller, _, _ = _sports_modules(monkeypatch)
    state_dir = tmp_path / "state"
    state_file = state_dir / "games.json"
    state_dir.mkdir(parents=True)
    existing = {
        "event-001": {
            "id": "event-001",
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
            "name": "Atlas Home vs Atlas Away",
            "lifecycle_state": "live",
            "updated_at": "2026-08-07T00:00:00+00:00",
        }
    }
    state_file.write_text(
        json.dumps(existing) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(controller, "STATE_DIR", state_dir)
    monkeypatch.setattr(controller, "STATE_FILE", state_file)
    monkeypatch.setattr(controller, "generate_feed", lambda: 0)

    result = controller.process_games(
        [],
        now=datetime(
            2026,
            8,
            7,
            1,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert set(result) == {"event-001"}
    assert result["event-001"]["lifecycle_state"] == "live"
    assert json.loads(
        state_file.read_text(encoding="utf-8")
    )["event-001"]["lifecycle_state"] == "live"


def test_sports_provider_failure_is_degraded_not_empty_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, worker = _sports_modules(monkeypatch)

    class UnavailableProvider:
        name = "thesportsdb"

        def fetch_games(self, **_: object) -> list[dict[str, object]]:
            raise RuntimeError("provider unavailable")

    existing = {
        "event-001": {
            "id": "event-001",
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
            "lifecycle_state": "live",
        }
    }

    monkeypatch.setattr(
        worker,
        "enabled_providers",
        lambda: [UnavailableProvider()],
    )
    monkeypatch.setattr(worker, "load_state", lambda: existing)
    monkeypatch.setattr(worker, "load_provider_health", lambda: {})
    monkeypatch.setattr(
        worker,
        "active_subscriptions",
        lambda: [{"provider": "thesportsdb"}],
    )
    monkeypatch.setattr(
        worker,
        "filter_subscribed_games",
        lambda games, _subscriptions: list(games),
    )
    monkeypatch.setattr(
        worker,
        "provider_discovery_targets",
        lambda _subscriptions, _provider: {
            "events": [],
            "teams": [],
            "leagues": [],
        },
    )
    monkeypatch.setattr(
        worker,
        "resolve_subscribed_games",
        lambda _games, _subscriptions: [],
    )
    monkeypatch.setattr(worker, "publish_event", lambda *args: None)

    result = worker.run_provider_pipeline()

    assert result is not None
    assert result["provider_games"] == []
    assert result["degraded_count"] == 1
    assert set(result["subscribed_previous_games"]) == {"event-001"}
    health = result["provider_health"]["thesportsdb"]
    assert health["status"] == "degraded"
    assert health["consecutive_failures"] == 1
    assert health["last_error"] == "provider unavailable"
