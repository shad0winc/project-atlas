from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from http import HTTPStatus

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "modules/sports/src"
CHANNEL = "sports-live-nfl-redzone"

@pytest.fixture
def domain(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SRC))
    subscriptions = importlib.import_module("subscriptions")
    monkeypatch.setattr(subscriptions, "SUBSCRIPTIONS_FILE", tmp_path / "subscriptions.json")
    spec = importlib.util.spec_from_file_location("atlas_channel_follow_private_test", SRC / "private_api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "create_subscription", subscriptions.create_subscription)
    monkeypatch.setattr(module, "load_subscriptions", subscriptions.load_subscriptions)
    monkeypatch.setattr(module, "normalize_subscription", subscriptions.normalize_subscription)
    monkeypatch.setattr(module, "remove_subscription", subscriptions.remove_subscription)
    monkeypatch.setattr(module, "_provider", lambda name: pytest.fail("Channel follow called a schedule provider"))
    sources = [SimpleNamespace(standalone=True, atlas_channel_id=CHANNEL, name="NFL RedZone")]
    monkeypatch.setattr(module, "default_live_source_registry", lambda: SimpleNamespace(list_sources=lambda: sources))
    return subscriptions, module, sources

def post(module, body, authorized=True):
    handler = object.__new__(module.Handler)
    handler.path = "/internal/v1/subscriptions"
    handler._require_auth = lambda: authorized
    handler._read_payload = lambda: body
    results = []
    handler._json = lambda code, payload: results.append((code, payload))
    handler.do_POST()
    return results

def body(user="user-one", **changes):
    return dict(user_id=user, provider="atlas", type="channel", provider_id=CHANNEL, **changes)

def test_channel_persists_reload_and_duplicate_is_idempotent(domain):
    subscriptions, module, _ = domain
    first = post(module, body())[0]
    second = post(module, body())[0]
    assert first[0] == HTTPStatus.OK
    assert first[1]["created"] is True
    assert second[1]["created"] is False
    assert first[1]["subscription"] == second[1]["subscription"]
    persisted = subscriptions.load_subscriptions()
    assert persisted == [first[1]["subscription"]]
    assert persisted[0]["id"] == CHANNEL
    assert persisted[0]["record"] is False
    assert module.Handler._user_subscriptions("user-two") == []

def test_two_users_have_separate_follows_and_owned_delete(domain):
    subscriptions, module, _ = domain
    first = post(module, body())[0][1]["subscription"]
    second = post(module, body("user-two"))[0][1]["subscription"]
    assert first["subscription_id"] != second["subscription_id"]
    handler = object.__new__(module.Handler)
    handler.path = "/internal/v1/subscriptions/" + first["subscription_id"] + "?user_id=user-two"
    handler._require_auth = lambda: True
    result = []
    handler._json = lambda code, payload: result.append((code, payload))
    handler.do_DELETE()
    assert result[-1][0] == HTTPStatus.NOT_FOUND
    assert len(subscriptions.load_subscriptions()) == 2
    handler.path = "/internal/v1/subscriptions/" + first["subscription_id"] + "?user_id=user-one"
    handler.do_DELETE()
    assert result[-1] == (HTTPStatus.OK, {"removed": True})
    assert subscriptions.load_subscriptions() == [second]

@pytest.mark.parametrize("case", ["missing", "event", "wrong_provider", "duplicate"])
def test_channel_target_validation_no_mutation(domain, case):
    subscriptions, module, sources = domain
    payload = body()
    if case == "missing": sources.clear()
    elif case == "event": sources[0].standalone = False
    elif case == "wrong_provider": payload["provider"] = "thesportsdb"
    else: sources.append(sources[0])
    assert post(module, payload)[0][0] in (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND)
    assert subscriptions.load_subscriptions() == []

def test_channel_auth_guard_and_recording_never_enabled(domain):
    subscriptions, module, _ = domain
    assert post(module, body(), authorized=False) == []
    assert subscriptions.load_subscriptions() == []
    follow = post(module, body())[0][1]["subscription"]
    with pytest.raises(ValueError, match="only supported for event"):
        subscriptions.update_subscription_recording(follow["subscription_id"], "user-one", True)
    assert subscriptions.normalize_subscription(dict(follow, record=True))["record"] is False
    assert subscriptions.filter_subscribed_games([{"provider":"atlas", "provider_event_id":CHANNEL}], [follow]) == []
    assert subscriptions.provider_discovery_targets([follow], "atlas") == {"events":[], "teams":[], "leagues":[]}

def test_disappeared_channel_follow_remains_owned_and_removable(domain):
    subscriptions, module, sources = domain
    follow = post(module, body())[0][1]["subscription"]
    sources.clear()
    assert module.Handler._user_subscriptions("user-one") == [follow]
    assert subscriptions.remove_subscription(follow["subscription_id"])
    assert subscriptions.load_subscriptions() == []
