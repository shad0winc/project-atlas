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
def _reset_budget(monkeypatch: pytest.MonkeyPatch) -> None:
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
