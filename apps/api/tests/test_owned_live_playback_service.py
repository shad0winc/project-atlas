from __future__ import annotations
import json
from unittest.mock import patch
import pytest
from atlas.media.jellyfin import JellyfinProvider
from atlas.jellyfin_live_streams import OwnedJellyfinLiveStreams
from atlas_api.services.playback import PlaybackService, PlaybackNotFoundError


class Response:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self):
        return json.dumps(self.data).encode()


ITEM = {"Id": "item", "Name": "Live game", "Type": "TvChannel"}
INFO = {
    "PlaySessionId": "play-one",
    "MediaSources": [
        {
            "Id": "source-one",
            "RequiresOpening": True,
            "OpenToken": "secret-open-token",
            "MediaStreams": [],
        }
    ],
}
OPEN = {
    "MediaSource": {
        "Id": "source-one",
        "LiveStreamId": "live-one",
        "TranscodingUrl": "/videos/item/live.m3u8",
        "MediaStreams": [],
        "RunTimeTicks": 123,
    }
}


def test_service_records_owner_and_closes_on_authenticated_release(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    service = PlaybackService(
        JellyfinProvider("http://jellyfin", "secret"),
        jellyfin_public_url="https://playback.example",
        live_streams=store,
    )
    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response({"Items": [ITEM]}),
            Response([]),
            Response(INFO),
            Response(OPEN),
            Response({}),
        ],
    ) as http:
        result = service.resolve_live_session(
            provider="jellyfin",
            item_id="item",
            jellyfin_user_id="jf-user",
            atlas_session_id="atlas-session",
            atlas_user_id="atlas-user",
        )
        assert result.can_seek is False
        assert "LiveStreamId=live-one" in result.stream_path
        service.authorize_live_stream(
            user_id="atlas-user",
            item_id="item",
            live_stream_id="live-one",
            play_session_id="play-one",
            media_source_id="source-one",
        )
        service.heartbeat_live_stream(session_id="atlas-session", user_id="atlas-user")
        service.release_live_stream(session_id="atlas-session", user_id="atlas-user")
    assert (
        http.call_args.args[0].full_url
        == "http://jellyfin/LiveStreams/Close?liveStreamId=live-one"
    )
    assert json.loads(store.path.read_text())["streams"] == {}


def test_service_cleanup_survives_validation_failure_after_open(tmp_path):
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    service = PlaybackService(
        JellyfinProvider("http://jellyfin", "secret"),
        jellyfin_public_url="https://playback.example",
        live_streams=store,
    )
    opened = {
        "MediaSource": {
            **OPEN["MediaSource"],
            "TranscodingUrl": "/videos/other/live.m3u8",
        }
    }
    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response({"Items": [ITEM]}),
            Response([]),
            Response(INFO),
            Response(opened),
            Response({}),
        ],
    ) as http:
        with pytest.raises(PlaybackNotFoundError):
            service.resolve_live_session(
                provider="jellyfin",
                item_id="item",
                jellyfin_user_id="jf-user",
                atlas_session_id="s",
                atlas_user_id="u",
            )
    assert http.call_count == 5
    assert json.loads(store.path.read_text())["streams"] == {}
