from __future__ import annotations
import json
from pathlib import Path
import pytest
from atlas.jellyfin_live_streams import (
    OwnedJellyfinLiveStreams,
    LiveStreamOwnershipError,
)


def response(stream_id="shared-stream"):
    return {"MediaSource": {"LiveStreamId": stream_id}}


def test_open_intent_is_durable_before_remote_call_and_has_private_permissions(
    tmp_path,
):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")

    def operation():
        state = json.loads(store.path.read_text())
        assert state["streams"]["s"]["status"] == "opening"
        assert store.path.stat().st_mode & 0o777 == 0o600
        return response()

    with store.scope(
        session_id="s", user_id="u", item_id="i", close=lambda _: None
    ) as owner:
        owner.open(operation)
    assert json.loads(store.path.read_text())["streams"]["s"]["status"] == "active"


def test_other_user_cannot_release_or_heartbeat_owner(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    calls = []
    with store.scope(
        session_id="s", user_id="a", item_id="i", close=calls.append
    ) as owner:
        owner.open(response)
    for operation in (
        lambda: store.release(session_id="s", user_id="b", close=calls.append),
        lambda: store.heartbeat(session_id="s", user_id="b"),
    ):
        with pytest.raises(LiveStreamOwnershipError):
            operation()
    assert calls == []
    assert store.release(session_id="s", user_id="a", close=calls.append)
    assert calls == ["shared-stream"]
    assert not store.release(session_id="s", user_id="a", close=calls.append)
    assert calls == ["shared-stream"]


def test_shared_id_releases_one_consumer_per_owned_acquisition(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    calls = []
    for key, user in [("one", "a"), ("two", "b")]:
        with store.scope(
            session_id=key, user_id=user, item_id="i", close=calls.append
        ) as owner:
            owner.open(response)
    store.release(session_id="one", user_id="a", close=calls.append)
    assert list(json.loads(store.path.read_text())["streams"]) == ["two"]
    assert calls == ["shared-stream"]


def test_validation_failure_closes_already_recorded_stream(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    calls = []
    with pytest.raises(ValueError):
        with store.scope(
            session_id="s", user_id="u", item_id="i", close=calls.append
        ) as owner:
            owner.open(response)
            raise ValueError("bad URL")
    assert calls == ["shared-stream"]
    assert json.loads(store.path.read_text())["streams"] == {}


@pytest.mark.parametrize(
    "operation", [lambda: (_ for _ in ()).throw(TimeoutError()), lambda: {}]
)
def test_ambiguous_open_is_latched_and_blocks_new_opens(tmp_path, operation):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    with pytest.raises(Exception):
        with store.scope(
            session_id="s",
            user_id="u",
            item_id="i",
            close=lambda _: pytest.fail("no known ID"),
        ) as owner:
            owner.open(operation)
    assert json.loads(store.path.read_text())["streams"]["s"]["status"] == "blocked"
    restarted = OwnedJellyfinLiveStreams(store.path)
    with pytest.raises(LiveStreamOwnershipError):
        with restarted.scope(
            session_id="next", user_id="v", item_id="other", close=lambda _: None
        ) as owner:
            owner.open(lambda: pytest.fail("latched state must reject remote open"))


def test_close_intent_is_durable_and_uncertain_close_is_not_retried(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    with store.scope(
        session_id="s", user_id="u", item_id="i", close=lambda _: None
    ) as owner:
        owner.open(response)

    def close(_):
        assert json.loads(store.path.read_text())["streams"]["s"]["status"] == "closing"
        raise TimeoutError()

    with pytest.raises(LiveStreamOwnershipError):
        store.release(session_id="s", user_id="u", close=close)
    with pytest.raises(LiveStreamOwnershipError):
        store.release(
            session_id="s",
            user_id="u",
            close=lambda _: pytest.fail("must not repeat uncertain decrement"),
        )
    assert json.loads(store.path.read_text())["streams"]["s"]["status"] == "blocked"


def test_restart_reaps_only_expired_owners_and_heartbeat_keeps_other_viewer(tmp_path):
    now = [0.0]
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json", clock=lambda: now[0])
    for key in ("a", "b"):
        with store.scope(
            session_id=key, user_id=key, item_id="i", close=lambda _: None
        ) as owner:
            owner.open(lambda: response(key))
    now[0] = 60
    store.heartbeat(session_id="b", user_id="b")
    now[0] = 91
    calls = []
    restarted = OwnedJellyfinLiveStreams(store.path, clock=lambda: now[0])
    assert restarted.reap(calls.append) == 1
    assert calls == ["a"]
    assert list(json.loads(store.path.read_text())["streams"]) == ["b"]


def test_expired_heartbeat_cannot_resurrect_a_stream(tmp_path):
    now = [0.0]
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json", clock=lambda: now[0])
    with store.scope(
        session_id="s", user_id="u", item_id="i", close=lambda _: None
    ) as owner:
        owner.open(response)
    now[0] = 90
    with pytest.raises(LiveStreamOwnershipError):
        store.heartbeat(session_id="s", user_id="u")


def test_invalid_state_never_calls_upstream(tmp_path):
    path = tmp_path / "streams.json"
    path.write_text('{"version":99,"streams":{}}')
    store = OwnedJellyfinLiveStreams(path)
    with pytest.raises(LiveStreamOwnershipError):
        store.reap(lambda _: pytest.fail("no upstream call"))
