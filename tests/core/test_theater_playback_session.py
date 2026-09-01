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



def _playback_source(
    *,
    subtitle_query: str = "",
    subtitle_streams: list[dict] | None = None,
):
    return {
        "MediaSources": [
            {
                "Id": "source-1",
                "SupportsDirectPlay": True,
                "SupportsDirectStream": True,
                "SupportsTranscoding": True,
                "TranscodingUrl": (
                    "/videos/abc/master.m3u8"
                    "?MediaSourceId=source-1"
                    + subtitle_query
                ),
                "MediaStreams": (
                    []
                    if subtitle_streams is None
                    else subtitle_streams
                ),
            }
        ]
    }


def test_playback_info_forwards_selected_subtitle_stream():
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(
                _playback_source(
                    subtitle_streams=[
                        {
                            "Index": 2,
                            "Type": "Subtitle",
                            "Codec": "subrip",
                            "DisplayTitle": "English",
                        }
                    ],
                )
            ),
            Response(
                _playback_source(
                    subtitle_query=(
                        "&SubtitleStreamIndex=2"
                        "&SubtitleMethod=Encode"
                    ),
                    subtitle_streams=[
                        {
                            "Index": 2,
                            "Type": "Subtitle",
                            "Codec": "subrip",
                            "DisplayTitle": "English",
                        }
                    ],
                )
            ),
        ],
    ) as request:
        result = provider.get_playback_info(
            "abc",
            user_id="a" * 32,
            subtitle_stream_index=2,
        )

    assert request.call_count == 2

    first = request.call_args_list[0].args[0]
    second = request.call_args_list[1].args[0]

    first_payload = json.loads(
        first.data.decode("utf-8")
    )

    second_payload = json.loads(
        second.data.decode("utf-8")
    )

    assert "SubtitleStreamIndex" not in first_payload
    assert "MediaSourceId" not in first_payload

    assert second_payload["MediaSourceId"] == "source-1"
    assert second_payload["SubtitleStreamIndex"] == 2
    assert (
        second_payload[
            "AlwaysBurnInSubtitleWhenTranscoding"
        ]
        is True
    )

    assert all(
        profile["Method"] == "Encode"
        for profile in second_payload[
            "DeviceProfile"
        ]["SubtitleProfiles"]
    )

    assert (
        "SubtitleStreamIndex=2"
        in result["stream_path"]
    )
    assert (
        "SubtitleMethod=Encode"
        in result["stream_path"]
    )

    assert "server-secret" not in (
        first.data.decode("utf-8")
        + second.data.decode("utf-8")
    )


def test_playback_info_forwards_subtitle_off():
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(
                _playback_source()
            ),
            Response(
                _playback_source()
            ),
        ],
    ) as request:
        provider.get_playback_info(
            "abc",
            user_id="a" * 32,
            subtitle_stream_index=-1,
        )

    assert request.call_count == 2

    first = request.call_args_list[0].args[0]
    second = request.call_args_list[1].args[0]

    first_payload = json.loads(
        first.data.decode("utf-8")
    )

    second_payload = json.loads(
        second.data.decode("utf-8")
    )

    assert "SubtitleStreamIndex" not in first_payload
    assert "MediaSourceId" not in first_payload

    assert second_payload["MediaSourceId"] == "source-1"
    assert second_payload["SubtitleStreamIndex"] == -1

    assert (
        "AlwaysBurnInSubtitleWhenTranscoding"
        not in second_payload
    )


def test_selected_subtitle_requests_jellyfin_burn_in() -> None:
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    subtitle = {
        "Index": 2,
        "Type": "Subtitle",
        "Codec": "subrip",
        "DisplayTitle": "English",
        "IsDefault": False,
        "IsForced": False,
    }

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(
                _playback_source(
                    subtitle_streams=[subtitle],
                )
            ),
            Response(
                _playback_source(
                    subtitle_query=(
                        "&SubtitleStreamIndex=2"
                        "&SubtitleMethod=Encode"
                    ),
                    subtitle_streams=[subtitle],
                )
            ),
        ],
    ) as request:
        provider.get_playback_info(
            "abc",
            user_id="a" * 32,
            subtitle_stream_index=2,
        )

    second = request.call_args_list[1].args[0]

    payload = json.loads(
        second.data.decode("utf-8")
    )

    assert payload["MediaSourceId"] == "source-1"
    assert payload["SubtitleStreamIndex"] == 2
    assert (
        payload[
            "AlwaysBurnInSubtitleWhenTranscoding"
        ]
        is True
    )

    subtitle_profiles = payload[
        "DeviceProfile"
    ]["SubtitleProfiles"]

    assert {
        "Format": "subrip",
        "Method": "Encode",
    } in subtitle_profiles

    assert all(
        entry["Method"] == "Encode"
        for entry in subtitle_profiles
    )


def test_subtitle_off_does_not_request_burn_in() -> None:
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(
                _playback_source()
            ),
            Response(
                _playback_source()
            ),
        ],
    ) as request:
        provider.get_playback_info(
            "abc",
            user_id="a" * 32,
            subtitle_stream_index=-1,
        )

    second = request.call_args_list[1].args[0]

    payload = json.loads(
        second.data.decode("utf-8")
    )

    assert payload["MediaSourceId"] == "source-1"
    assert payload["SubtitleStreamIndex"] == -1

    assert (
        "AlwaysBurnInSubtitleWhenTranscoding"
        not in payload
    )


def test_auto_subtitle_playback_remains_single_request() -> None:
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(
            _playback_source()
        ),
    ) as request:
        provider.get_playback_info(
            "abc",
            user_id="a" * 32,
        )

    assert request.call_count == 1

    sent = request.call_args.args[0]

    payload = json.loads(
        sent.data.decode("utf-8")
    )

    assert "MediaSourceId" not in payload
    assert "SubtitleStreamIndex" not in payload
    assert (
        "AlwaysBurnInSubtitleWhenTranscoding"
        not in payload
    )


def test_subtitle_selection_fails_closed_if_source_changes() -> None:
    provider = JellyfinProvider(
        "http://jellyfin:8096",
        "server-secret",
    )

    changed = _playback_source()
    changed["MediaSources"][0]["Id"] = "source-2"

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(
                _playback_source()
            ),
            Response(changed),
        ],
    ):
        try:
            provider.get_playback_info(
                "abc",
                user_id="a" * 32,
                subtitle_stream_index=2,
            )
        except Exception as exc:
            assert (
                "changed media source"
                in str(exc)
            )
        else:
            raise AssertionError(
                "source identity change must fail closed"
            )
