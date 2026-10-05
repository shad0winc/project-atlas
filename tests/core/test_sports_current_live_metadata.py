import pytest


def provider():
    from providers.thesportsdb import TheSportsDBProvider
    return TheSportsDBProvider()


@pytest.mark.parametrize("status", ["Q1", "Q2", "Q3", "Q4", "HT", "OT", "live", "in progress"])
def test_in_progress_statuses_are_live(status):
    assert provider().normalize_status({"strStatus": status}) == "live"


@pytest.mark.parametrize("status", ["FT", "final", "finished", "match finished"])
def test_finished_statuses_do_not_remain_live(status):
    assert provider().normalize_status({"strStatus": status}) == "final"


@pytest.mark.parametrize("status", ["", "NS", "Postponed", "Cancelled", "unknown"])
def test_unknown_or_non_live_statuses_are_not_live(status):
    assert provider().normalize_status({"strStatus": status}) != "live"


def test_private_event_metadata_exposes_only_identity_fields():
    from private_api import Handler
    event = {
        "provider": "thesportsdb", "provider_event_id": "2475436",
        "name": "Panthers vs Lions", "sport": "American Football", "league": "NFL",
        "start_at": "2026-10-05T00:20:00Z", "status": "live",
        "provider_league_id": "4391", "home_team_id": "134926", "away_team_id": "134930",
        "stream_url": "private", "credentials": "private",
    }
    result = Handler._safe_event(event)
    assert result["home_team_id"] == "134926"
    assert result["away_team_id"] == "134930"
    assert result["provider_league_id"] == "4391"
    assert "stream_url" not in result and "credentials" not in result


def test_followed_team_includes_live_recent_game_without_finished_results(monkeypatch):
    instance = provider()
    instance.discovery_days_ahead = 0
    calls = []
    live = {"idEvent": "live-game", "strStatus": "Q2"}
    finished = {"idEvent": "finished-game", "strStatus": "FT"}
    next_game = {"idEvent": "next-game", "strStatus": "NS"}
    def request(endpoint, parameters):
        calls.append((endpoint, parameters))
        if endpoint == "eventslast.php":
            return {"results": [live, finished]}
        assert endpoint == "eventsnext.php"
        return {"events": [next_game]}
    monkeypatch.setattr(instance, "request_json", request)
    monkeypatch.setattr(instance, "normalize_event", lambda event: {"provider_event_id": event["idEvent"], "status": instance.normalize_status(event)})
    assert instance.fetch_games(team_ids=["team"]) == [
        {"provider_event_id": "next-game", "status": "scheduled"},
        {"provider_event_id": "live-game", "status": "live"},
    ]
    assert calls == [("eventslast.php", {"id": "team"}), ("eventsnext.php", {"id": "team"})]


def test_private_event_missing_matching_ids_remain_unknown():
    from private_api import Handler
    event = {"provider": "thesportsdb", "provider_event_id": "game", "name": "Game", "sport": "Football", "league": "NFL", "start_at": "2026-10-05T00:20:00Z", "status": "live"}
    result = Handler._safe_event(event)
    assert result["home_team_id"] is None
    assert result["away_team_id"] is None
    assert result["provider_league_id"] is None
