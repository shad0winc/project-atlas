from __future__ import annotations
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import pytest
from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError
from atlas.jellyfin_live_streams import OwnedJellyfinLiveStreams


class Response:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self):
        return json.dumps(self.data).encode()


def setup_payload():
    return {
        "PlaySessionId": "play-one",
        "MediaSources": [
            {
                "Id": "source-one",
                "RequiresOpening": True,
                "RequiresClosing": True,
                "OpenToken": "private-open-token",
                "MediaStreams": [],
                "TranscodingUrl": "/videos/item/live.m3u8?MediaSourceId=source-one",
            }
        ],
    }


def opened_payload(url="/videos/item/live.m3u8?MediaSourceId=source-one"):
    return {
        "MediaSource": {
            "Id": "source-one",
            "LiveStreamId": "live-one",
            "RequiresClosing": True,
            "TranscodingUrl": url,
            "MediaStreams": [],
        }
    }


def test_unopened_source_is_rejected_without_owner():
    provider = JellyfinProvider("http://jellyfin", "secret")
    with patch(
        "atlas.media.jellyfin.urlopen", return_value=Response(setup_payload())
    ) as http:
        with pytest.raises(MediaProviderError, match="requires an Atlas owner"):
            provider.get_playback_info("item", user_id="u")
    assert http.call_count == 1


def test_live_open_carries_profile_and_playback_id_and_returns_safe_url(tmp_path):
    provider = JellyfinProvider("http://jellyfin", "secret")
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[Response(setup_payload()), Response(opened_payload())],
    ) as http:
        with store.scope(
            session_id="s",
            user_id="u",
            item_id="item",
            close=provider.close_live_stream,
        ) as owner:
            result = provider.get_playback_info(
                "item", user_id="jf-user", live_stream_owner=owner
            )
    assert http.call_count == 2
    request = http.call_args.args[0]
    assert request.full_url == "http://jellyfin/LiveStreams/Open"
    body = json.loads(request.data)
    assert body["OpenToken"] == "private-open-token"
    assert body["PlaySessionId"] == "play-one"
    assert body["ItemId"] == "item" and body["UserId"] == "jf-user"
    assert body["DeviceProfile"]["Name"] == "Atlas Theater Browser"
    query = parse_qs(urlsplit(result["stream_path"]).query)
    assert query["LiveStreamId"] == ["live-one"]
    assert query["MediaSourceId"] == ["source-one"]
    assert query["PlaySessionId"] == ["play-one"]
    assert "private-open-token" not in result["stream_path"]
    assert "secret" not in result["stream_path"]


@pytest.mark.parametrize(
    "url",
    [
        "https://wrong/live.m3u8",
        "/videos/other/live.m3u8",
        "/videos/item/live.m3u8?LiveStreamId=someone-else",
    ],
)
def test_bad_opened_url_closes_only_owned_stream(tmp_path, url):
    provider = JellyfinProvider("http://jellyfin", "secret")
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(setup_payload()),
            Response(opened_payload(url)),
            Response({}),
        ],
    ) as http:
        with pytest.raises(MediaProviderError):
            with store.scope(
                session_id="s",
                user_id="u",
                item_id="item",
                close=provider.close_live_stream,
            ) as owner:
                provider.get_playback_info("item", user_id="u", live_stream_owner=owner)
    assert http.call_count == 3
    assert parse_qs(urlsplit(http.call_args.args[0].full_url).query) == {
        "liveStreamId": ["live-one"]
    }


def test_subtitle_selection_is_forwarded_to_open(tmp_path):
    provider = JellyfinProvider("http://jellyfin", "secret")
    store = OwnedJellyfinLiveStreams(tmp_path / "streams.json")
    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(setup_payload()),
            Response(setup_payload()),
            Response(opened_payload()),
        ],
    ) as http:
        with store.scope(
            session_id="s",
            user_id="u",
            item_id="item",
            close=provider.close_live_stream,
        ) as owner:
            provider.get_playback_info(
                "item", user_id="u", subtitle_stream_index=2, live_stream_owner=owner
            )
    body = json.loads(http.call_args.args[0].data)
    assert body["SubtitleStreamIndex"] == 2
    assert body["AlwaysBurnInSubtitleWhenTranscoding"] is True
