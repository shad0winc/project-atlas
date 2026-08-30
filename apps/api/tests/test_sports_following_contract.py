from __future__ import annotations

from atlas_api.services.sports import SportsWriterBackedAPIService


def _service_with_request(fake_request):
    service = object.__new__(SportsWriterBackedAPIService)
    service._request = fake_request
    return service


def test_team_search_uses_private_writer_boundary() -> None:
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        return {"teams": [{"type": "team", "provider": "thesportsdb", "provider_id": "1", "name": "Team"}]}

    service = _service_with_request(request)
    result = service.search_teams(provider_name="thesportsdb", query="Team")
    assert result[0]["provider_id"] == "1"
    assert calls == [("GET", "/internal/v1/search/teams?provider=thesportsdb&query=Team", None)]


def test_league_search_uses_private_writer_boundary() -> None:
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        return {"leagues": [{"type": "league", "provider": "thesportsdb", "provider_id": "2", "name": "League"}]}

    service = _service_with_request(request)
    result = service.search_leagues(provider_name="thesportsdb", query="League")
    assert result[0]["provider_id"] == "2"
    assert calls == [("GET", "/internal/v1/search/leagues?provider=thesportsdb&query=League", None)]


def test_follow_list_is_scoped_with_authenticated_user_id() -> None:
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        return {"subscriptions": []}

    service = _service_with_request(request)
    assert service.list_subscriptions_for_user(user_id="usr-one") == []
    assert calls == [("GET", "/internal/v1/subscriptions?user_id=usr-one", None)]


def test_follow_creation_sends_user_identity_and_not_recording_intent() -> None:
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        return {
            "subscription": {
                "subscription_id": "sub-1",
                "type": "team",
                "provider": "thesportsdb",
                "id": "team-1",
                "name": "Team One",
                "user": "usr-one",
                "enabled": True,
                "record": False,
                "created_at": None,
            },
            "created": True,
        }

    service = _service_with_request(request)
    subscription, created = service.create_follow_subscription(
        user_id="usr-one",
        provider_name="thesportsdb",
        subscription_type="team",
        provider_id="team-1",
    )
    assert created is True
    assert subscription["record"] is False
    assert calls == [(
        "POST",
        "/internal/v1/subscriptions",
        {
            "user_id": "usr-one",
            "provider": "thesportsdb",
            "type": "team",
            "provider_id": "team-1",
        },
    )]


def test_unfollow_sends_owner_identity_to_private_writer() -> None:
    calls = []

    def request(method, path, body=None):
        calls.append((method, path, body))
        return {"removed": False}

    service = _service_with_request(request)
    assert service.remove_follow_subscription(
        user_id="usr-two",
        subscription_id="sub-other",
    ) is False
    assert calls == [(
        "DELETE",
        "/internal/v1/subscriptions/sub-other?user_id=usr-two",
        None,
    )]
