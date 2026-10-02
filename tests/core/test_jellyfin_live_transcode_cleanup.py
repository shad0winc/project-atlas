from __future__ import annotations

import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

from atlas.jellyfin_live_streams import (
    OwnedJellyfinLiveStreams,
    LiveStreamOwnershipError,
)
from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError


def opened(store, session="old", user="alice", play="play-old"):
    with store.scope(
        session_id=session, user_id=user, item_id="game", close=lambda _: None
    ) as owner:
        owner.open(
            lambda: {"MediaSource": {"LiveStreamId": "shared"}},
            play_session_id=play,
            media_source_id="source",
        )


def test_release_stops_exact_job_before_close_with_durable_intent(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    opened(store)
    calls = []

    def stop(play):
        assert (
            json.loads(store.path.read_text())["streams"]["old"]["status"] == "closing"
        )
        calls.append(("stop", play))

    def close(live):
        assert calls == [("stop", "play-old")]
        calls.append(("close", live))

    assert store.release(
        session_id="old", user_id="alice", stop_transcode=stop, close=close
    )
    assert calls == [("stop", "play-old"), ("close", "shared")]
    assert not store.release(
        session_id="old", user_id="alice", stop_transcode=stop, close=close
    )
    assert json.loads(store.path.read_text())["streams"] == {}


def test_expiry_after_restart_stops_only_expired_owner(tmp_path):
    now = [0]
    path = tmp_path / "streams.json"
    store = OwnedJellyfinLiveStreams(path, clock=lambda: now[0])
    opened(store)
    now[0] = 40
    opened(store, session="other", user="bob", play="play-other")
    now[0] = 91
    restarted = OwnedJellyfinLiveStreams(path, clock=lambda: now[0])
    calls = []
    assert (
        restarted.reap(
            lambda live: calls.append(("close", live)),
            stop_transcode=lambda play: calls.append(("stop", play)),
        )
        == 1
    )
    assert calls == [("stop", "play-old"), ("close", "shared")]
    restarted.authorize(
        user_id="bob",
        item_id="game",
        live_stream_id="shared",
        play_session_id="play-other",
        media_source_id="source",
    )


def test_uncertain_stop_blocks_close_retry_and_reopen(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    opened(store)
    calls = []

    def stop(play):
        calls.append(("stop", play))
        raise TimeoutError("uncertain remote outcome")

    with pytest.raises(LiveStreamOwnershipError, match="reconciliation"):
        store.release(
            session_id="old",
            user_id="alice",
            stop_transcode=stop,
            close=lambda live: calls.append(("close", live)),
        )
    assert calls == [("stop", "play-old")]
    assert json.loads(store.path.read_text())["streams"]["old"]["status"] == "blocked"
    with pytest.raises(LiveStreamOwnershipError, match="reconciliation"):
        store.release(
            session_id="old", user_id="alice", stop_transcode=stop, close=lambda _: None
        )
    with pytest.raises(LiveStreamOwnershipError, match="reconciliation"):
        store.reap(lambda _: None, stop_transcode=stop)
    with pytest.raises(LiveStreamOwnershipError, match="reconciliation"):
        opened(store, session="new", play="play-new")
    assert calls == [("stop", "play-old")]


@pytest.mark.parametrize("play", [None, "", " ", 123])
def test_missing_play_identity_never_stops_device_or_closes_consumer(tmp_path, play):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    opened(store, play=play)
    calls = []
    with pytest.raises(LiveStreamOwnershipError, match="reconciliation"):
        store.release(
            session_id="old",
            user_id="alice",
            stop_transcode=lambda value: calls.append(value),
            close=lambda value: calls.append(value),
        )
    assert calls == []
    assert json.loads(store.path.read_text())["streams"]["old"]["status"] == "blocked"


def test_other_user_cannot_stop_an_owner(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    opened(store)
    calls = []
    with pytest.raises(LiveStreamOwnershipError, match="unavailable"):
        store.release(
            session_id="old",
            user_id="bob",
            stop_transcode=lambda value: calls.append(value),
            close=lambda value: calls.append(value),
        )
    assert calls == []
    assert json.loads(store.path.read_text())["streams"]["old"]["status"] == "active"


def test_setup_failure_stops_transcode_before_closing_acquired_consumer(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    calls = []
    with pytest.raises(ValueError, match="invalid playback"):
        with store.scope(
            session_id="old",
            user_id="alice",
            item_id="game",
            stop_transcode=lambda play: calls.append(("stop", play)),
            close=lambda live: calls.append(("close", live)),
        ) as owner:
            owner.open(
                lambda: {"MediaSource": {"LiveStreamId": "shared"}},
                play_session_id="play-old",
            )
            raise ValueError("invalid playback")
    assert calls == [("stop", "play-old"), ("close", "shared")]
    assert json.loads(store.path.read_text())["streams"] == {}


def test_provider_stops_session_using_authenticated_delete_and_empty_response():
    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self):
            return b""

    provider = JellyfinProvider("http://jellyfin", "secret")
    with patch("atlas.media.jellyfin.urlopen", return_value=EmptyResponse()) as http:
        provider.stop_live_transcode("play-old")
    request = http.call_args.args[0]
    assert request.get_method() == "DELETE"
    assert urlsplit(request.full_url).path == "/Videos/ActiveEncodings"
    assert parse_qs(urlsplit(request.full_url).query) == {
        "DeviceId": ["atlas-api"],
        "PlaySessionId": ["play-old"],
    }
    assert "secret" in request.get_header("Authorization")
    assert http.call_args.kwargs["timeout"] == 30


@pytest.mark.parametrize("play", [None, "", " "])
def test_provider_never_sends_device_only_stop(play):
    with patch("atlas.media.jellyfin.urlopen") as http:
        with pytest.raises(MediaProviderError, match="play_session_id is required"):
            JellyfinProvider("http://jellyfin", "secret").stop_live_transcode(play)
    http.assert_not_called()
