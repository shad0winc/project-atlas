from __future__ import annotations

import json
from unittest.mock import patch

from atlas.media.jellyfin import JellyfinProvider


class Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.value).encode("utf-8")


def test_playback_info_keeps_privileged_data_server_side():
    provider = JellyfinProvider("http://jellyfin:8096", "server-secret")
    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(
            {
                "MediaSources": [
                    {
                        "Id": "source-1",
                        "RunTimeTicks": 123456,
                        "SupportsDirectPlay": True,
                        "SupportsDirectStream": True,
                        "SupportsTranscoding": True,
                        "TranscodingUrl": (
                            "/videos/abc/master.m3u8"
                            "?ApiKey=server-secret"
                            "&MediaSourceId=source-1"
                        ),
                        "Path": "/media/private/movie.mkv",
                        "MediaStreams": [
                            {
                                "Index": 1,
                                "Type": "Audio",
                                "DisplayTitle": "English AAC",
                                "Language": "eng",
                                "Codec": "aac",
                                "IsDefault": True,
                            },
                            {
                                "Index": 2,
                                "Type": "Subtitle",
                                "DisplayTitle": "English",
                                "Language": "eng",
                                "Codec": "srt",
                            },
                        ],
                    }
                ]
            }
        ),
    ) as request:
        result = provider.get_playback_info(
            "abc",
            user_id="a" * 32,
        )

    sent = request.call_args.args[0]
    assert sent.method == "POST"
    assert sent.headers["X-emby-token"] == "server-secret"
    assert sent.full_url.endswith("/Items/abc/PlaybackInfo")

    assert result["stream_path"] == (
        "/videos/abc/master.m3u8"
        "?MediaSourceId=source-1"
    )

    serialized = json.dumps(result)
    assert "server-secret" not in serialized
    assert "jellyfin:8096" not in serialized
    assert "/media/private/movie.mkv" not in serialized
    assert "X-Emby-Token" not in serialized


def test_series_episode_listing_is_browser_safe_and_ordered():
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(
            {
                "Items": [
                    {
                        "Id": "episode-1",
                        "Name": "First",
                        "SeriesName": "Example Series",
                        "ParentIndexNumber": 1,
                        "IndexNumber": 1,
                        "Path": "/media/private/episode-1.mkv",
                    },
                    {
                        "Id": "episode-2",
                        "Name": "Second",
                        "SeriesName": "Example Series",
                        "ParentIndexNumber": 1,
                        "IndexNumber": 2,
                        "Path": "/media/private/episode-2.mkv",
                    },
                ]
            }
        ),
    ):
        episodes = provider.list_series_episodes("series-1")

    assert episodes == (
        {
            "id": "episode-1",
            "title": "First",
            "series_name": "Example Series",
            "season_number": 1,
            "episode_number": 1,
        },
        {
            "id": "episode-2",
            "title": "Second",
            "series_name": "Example Series",
            "season_number": 1,
            "episode_number": 2,
        },
    )

    serialized = json.dumps(episodes)
    assert "/media/private/" not in serialized
    assert "server-secret" not in serialized


def test_playback_info_forwards_selected_subtitle_stream():
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(
            {
                "MediaSources": [
                    {
                        "Id": "source-1",
                        "SupportsDirectPlay": True,
                        "SupportsDirectStream": True,
                        "SupportsTranscoding": True,
                        "TranscodingUrl": (
                            "/videos/abc/master.m3u8"
                            "?MediaSourceId=source-1"
                            "&SubtitleStreamIndex=2"
                        ),
                        "MediaStreams": [],
                    }
                ]
            }
        ),
    ) as request:
        provider.get_playback_info(
            "abc",
            user_id="a" * 32,
            subtitle_stream_index=2,
        )

    sent = request.call_args.args[0]
    payload = json.loads(sent.data.decode("utf-8"))

    assert payload["SubtitleStreamIndex"] == 2
    assert "server-secret" not in sent.data.decode("utf-8")


def test_playback_info_forwards_subtitle_off():
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(
            {
                "MediaSources": [
                    {
                        "Id": "source-1",
                        "SupportsDirectPlay": True,
                        "SupportsDirectStream": True,
                        "SupportsTranscoding": True,
                        "TranscodingUrl": (
                            "/videos/abc/master.m3u8"
                            "?MediaSourceId=source-1"
                        ),
                        "MediaStreams": [],
                    }
                ]
            }
        ),
    ) as request:
        provider.get_playback_info(
            "abc",
            user_id="a" * 32,
            subtitle_stream_index=-1,
        )

    sent = request.call_args.args[0]
    payload = json.loads(sent.data.decode("utf-8"))

    assert payload["SubtitleStreamIndex"] == -1
