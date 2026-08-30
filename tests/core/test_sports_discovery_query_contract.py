# Regression contracts for Sports team/league event discovery.

from __future__ import annotations

import inspect
from pathlib import Path

from apps.api.atlas_api.services.sports import SportsWriterBackedAPIService


def test_writer_event_adapter_projects_team_and_league_ids(monkeypatch) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://sports-writer:8003",
        token="test-token",
    )
    calls: list[tuple[str, str, object]] = []

    def fake_request(method: str, path: str, payload=None):
        calls.append((method, path, payload))
        return {"events": []}

    monkeypatch.setattr(service, "_request", fake_request)

    assert service.list_events_for_user(
        user_id="usr-test",
        provider_name="thesportsdb",
        team_ids=("team-1", "team-2"),
        league_ids=("league-1",),
    ) == []

    assert calls == [
        (
            "GET",
            "/internal/v1/events?"
            "user_id=usr-test&provider=thesportsdb"
            "&team_id=team-1&team_id=team-2&league_id=league-1",
            None,
        )
    ]


def test_private_writer_routes_discovery_through_fetch_games() -> None:
    source = Path("modules/sports/src/private_api.py").read_text(encoding="utf-8")
    assert 'params.get("team_id", [])' in source
    assert 'params.get("league_id", [])' in source
    assert "team_ids=team_ids or None" in source
    assert "league_ids=league_ids or None" in source


def test_public_events_route_exposes_team_and_league_filters() -> None:
    from apps.api.atlas_api.routes.v1.sports import list_sports_events

    signature = inspect.signature(list_sports_events)
    assert "team_id" in signature.parameters
    assert "league_id" in signature.parameters
