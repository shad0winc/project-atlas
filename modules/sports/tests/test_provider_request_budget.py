from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message

import pytest

from providers import thesportsdb


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return io.StringIO(json.dumps(self._payload))

    def __exit__(self, *_: object) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        thesportsdb,
        "_PROVIDER_BUDGET_FILE",
        tmp_path / "provider-request-budget.json",
    )
    thesportsdb._reset_request_budget_for_tests()
    monkeypatch.setenv("SPORTS_THESPORTSDB_API_KEY", "test-key")
    monkeypatch.setenv("SPORTS_PROVIDER_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("SPORTS_DISCOVERY_DAYS_AHEAD", "14")
    monkeypatch.setenv("SPORTS_THESPORTSDB_LEAGUE_IDS", "4391")


def test_same_request_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(*_: object, **__: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response(
            {"teams": [{"idTeam": "1", "strTeam": "Detroit Lions"}]}
        )

    monkeypatch.setattr(
        thesportsdb.urllib.request,
        "urlopen",
        fake_urlopen,
    )
    provider = thesportsdb.TheSportsDBProvider()

    assert provider.search_teams("Detroit Lions")
    assert provider.search_teams("Detroit Lions")
    assert calls == 1


def test_cache_keys_do_not_collide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_urlopen(*_: object, **__: object) -> _Response:
        nonlocal calls
        calls += 1
        return _Response({"teams": []})

    monkeypatch.setattr(
        thesportsdb.urllib.request,
        "urlopen",
        fake_urlopen,
    )
    provider = thesportsdb.TheSportsDBProvider()

    provider.search_teams("Detroit Lions")
    provider.search_teams("Detroit Tigers")

    assert calls == 2


def test_http_429_enters_local_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    headers = Message()
    headers["Retry-After"] = "45"

    def fake_urlopen(*_: object, **__: object):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            url="https://redacted.invalid/",
            code=429,
            msg="Too Many Requests",
            hdrs=headers,
            fp=None,
        )

    monkeypatch.setattr(
        thesportsdb.urllib.request,
        "urlopen",
        fake_urlopen,
    )
    provider = thesportsdb.TheSportsDBProvider()

    with pytest.raises(
        thesportsdb.SportsProviderRateLimitError
    ) as first:
        provider.search_teams("Detroit Lions")

    assert first.value.retry_after_seconds == 45

    with pytest.raises(
        thesportsdb.SportsProviderRateLimitError
    ):
        provider.search_teams("Detroit Lions")

    assert calls == 1


def test_retry_after_is_bounded() -> None:
    headers = Message()
    headers["Retry-After"] = "99999"
    error = urllib.error.HTTPError(
        url="https://redacted.invalid/",
        code=429,
        msg="Too Many Requests",
        hdrs=headers,
        fp=None,
    )

    assert thesportsdb._retry_after_seconds(error) == 300


def test_cache_entry_count_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(thesportsdb, "_CACHE_MAX_ENTRIES", 3)

    def fake_urlopen(*_: object, **__: object) -> _Response:
        return _Response({"teams": []})

    monkeypatch.setattr(
        thesportsdb.urllib.request,
        "urlopen",
        fake_urlopen,
    )
    provider = thesportsdb.TheSportsDBProvider()

    for value in ("one", "two", "three", "four"):
        provider.search_teams(value)

    assert len(thesportsdb._RESPONSE_CACHE) == 3


def test_shared_cooldown_blocks_second_process_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    budget_file = tmp_path / "provider-request-budget.json"
    monkeypatch.setattr(thesportsdb, "_PROVIDER_BUDGET_FILE", budget_file)
    monkeypatch.setattr(thesportsdb.time, "time", lambda: 1_000.0)
    thesportsdb._write_shared_rate_limit_until(1_045.0)
    provider = thesportsdb.TheSportsDBProvider()
    with pytest.raises(thesportsdb.SportsProviderRateLimitError) as exc_info:
        provider.request_json("searchteams.php", {"t": "Detroit Lions"})
    assert 44 <= exc_info.value.retry_after_seconds <= 45


def test_shared_cooldown_ignores_expired_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    budget_file = tmp_path / "provider-request-budget.json"
    monkeypatch.setattr(thesportsdb, "_PROVIDER_BUDGET_FILE", budget_file)
    monkeypatch.setattr(thesportsdb.time, "time", lambda: 1_000.0)
    thesportsdb._write_shared_rate_limit_until(990.0)
    assert thesportsdb._shared_retry_after_seconds() == 0


def test_search_endpoints_use_short_cache_ttl() -> None:
    assert (
        thesportsdb._cache_ttl_seconds("searchteams.php")
        == thesportsdb._SEARCH_CACHE_TTL_SECONDS
    )
    assert (
        thesportsdb._cache_ttl_seconds("search_all_teams.php")
        == thesportsdb._SEARCH_CACHE_TTL_SECONDS
    )
    assert (
        thesportsdb._cache_ttl_seconds("searchevents.php")
        == thesportsdb._SEARCH_CACHE_TTL_SECONDS
    )


def test_search_leagues_deduplicates_provider_league_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(
        self: thesportsdb.TheSportsDBProvider,
        endpoint: str,
        parameters: dict[str, str],
    ) -> dict[str, object]:
        assert endpoint == "search_all_teams.php"
        assert parameters == {"l": "MLB"}
        return {
            "teams": [
                {
                    "idLeague": "4424",
                    "strLeague": "MLB",
                    "strSport": "Baseball",
                    "strCountry": "United States",
                },
                {
                    "idLeague": "4424",
                    "strLeague": "MLB",
                    "strSport": "Baseball",
                    "strCountry": "United States",
                },
            ]
        }

    monkeypatch.setattr(
        thesportsdb.TheSportsDBProvider,
        "request_json",
        fake_request,
    )

    provider = thesportsdb.TheSportsDBProvider()

    assert provider.search_leagues("MLB") == [
        {
            "provider": "thesportsdb",
            "id": "4424",
            "name": "MLB",
            "sport": "Baseball",
            "country": "United States",
        }
    ]


def test_search_events_merges_team_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = thesportsdb.TheSportsDBProvider()

    monkeypatch.setattr(
        provider,
        "request_json",
        lambda endpoint, parameters: (
            {"event": []}
            if endpoint == "searchevents.php"
            else {}
        ),
    )
    monkeypatch.setattr(
        provider,
        "search_teams",
        lambda query: [
            {
                "id": "135260",
                "name": "New York Yankees",
            }
        ],
    )
    monkeypatch.setattr(
        provider,
        "search_leagues",
        lambda query: [],
    )
    monkeypatch.setattr(
        provider,
        "fetch_team_events",
        lambda team_id: [
            {
                "idEvent": "2599999",
                "strEvent": "New York Yankees vs Boston Red Sox",
                "strSport": "Baseball",
                "strLeague": "MLB",
                "idLeague": "4424",
                "strHomeTeam": "New York Yankees",
                "strAwayTeam": "Boston Red Sox",
                "idHomeTeam": "135260",
                "idAwayTeam": "135252",
                "strTimestamp": "2099-09-10T00:07:00",
                "strStatus": "Not Started",
            }
        ],
    )

    results = provider.search_events("New York Yankees")

    assert len(results) == 1
    assert results[0]["provider_event_id"] == "2599999"
    assert results[0]["league"] == "MLB"


def test_search_events_excludes_stale_direct_provider_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = thesportsdb.TheSportsDBProvider()

    monkeypatch.setattr(
        provider,
        "request_json",
        lambda endpoint, parameters: {
            "event": [
                {
                    "idEvent": "old-event",
                    "strEvent": "New York Yankees vs Boston Red Sox",
                    "strSport": "Baseball",
                    "strLeague": "MLB",
                    "idLeague": "4424",
                    "strTimestamp": "2018-10-10T00:07:00",
                    "strStatus": "Match Finished",
                }
            ]
        },
    )
    monkeypatch.setattr(provider, "search_teams", lambda query: [])
    monkeypatch.setattr(provider, "search_leagues", lambda query: [])

    assert provider.search_events("New York Yankees") == []
