"""Jellyfin correlation and readiness contracts for Atlas requests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError


def provider() -> JellyfinProvider:
    return JellyfinProvider(
        "http://jellyfin:8096",
        "secret",
    )


def test_find_item_by_tmdb_returns_exact_movie_match() -> None:
    subject = provider()

    with patch.object(
        JellyfinProvider,
        "_get_json",
        return_value={
            "Items": [
                {
                    "Id": "movie-abc",
                    "Name": "Example Movie",
                    "Type": "Movie",
                    "ProviderIds": {
                        "Tmdb": "157336",
                    },
                },
                {
                    "Id": "movie-other",
                    "Name": "Other Movie",
                    "Type": "Movie",
                    "ProviderIds": {
                        "Tmdb": "999",
                    },
                },
            ],
            "StartIndex": 0,
            "TotalRecordCount": 2,
        },
    ) as get:
        restored = subject.find_item_by_tmdb(
            "157336",
            media_type="movie",
        )

    assert restored == "movie-abc"

    get.assert_called_once()
    path = get.call_args.args[0]

    assert path.startswith("/Items?")
    assert "Recursive=true" in path
    assert "IncludeItemTypes=Movie" in path
    assert "Fields=ProviderIds" in path
    assert "StartIndex=0" in path
    assert "Limit=200" in path


def test_find_item_by_tmdb_maps_tv_to_series() -> None:
    subject = provider()

    with patch.object(
        JellyfinProvider,
        "_get_json",
        return_value={
            "Items": [
                {
                    "Id": "series-abc",
                    "Name": "Example Series",
                    "Type": "Series",
                    "ProviderIds": {
                        "Tmdb": "1399",
                    },
                }
            ],
            "StartIndex": 0,
            "TotalRecordCount": 1,
        },
    ) as get:
        restored = subject.find_item_by_tmdb(
            "1399",
            media_type="tv",
        )

    assert restored == "series-abc"
    assert "IncludeItemTypes=Series" in get.call_args.args[0]


def test_find_item_by_tmdb_returns_none_when_not_present() -> None:
    subject = provider()

    with patch.object(
        JellyfinProvider,
        "_get_json",
        return_value={
            "Items": [
                {
                    "Id": "movie-other",
                    "Type": "Movie",
                    "ProviderIds": {
                        "Tmdb": "999",
                    },
                }
            ],
            "StartIndex": 0,
            "TotalRecordCount": 1,
        },
    ):
        restored = subject.find_item_by_tmdb(
            "157336",
            media_type="movie",
        )

    assert restored is None


def test_find_item_by_tmdb_rejects_duplicate_exact_matches() -> None:
    subject = provider()

    with patch.object(
        JellyfinProvider,
        "_get_json",
        return_value={
            "Items": [
                {
                    "Id": "movie-a",
                    "Type": "Movie",
                    "ProviderIds": {
                        "Tmdb": "157336",
                    },
                },
                {
                    "Id": "movie-b",
                    "Type": "Movie",
                    "ProviderIds": {
                        "Tmdb": "157336",
                    },
                },
            ],
            "StartIndex": 0,
            "TotalRecordCount": 2,
        },
    ):
        with pytest.raises(
            MediaProviderError,
            match="multiple Jellyfin items",
        ):
            subject.find_item_by_tmdb(
                "157336",
                media_type="movie",
            )


@pytest.mark.parametrize(
    ("tmdb_id", "media_type"),
    [
        ("", "movie"),
        ("   ", "movie"),
        ("0", "movie"),
        ("-1", "movie"),
        ("abc", "movie"),
        ("157336", "other"),
    ],
)
def test_find_item_by_tmdb_validates_identity_and_type(
    tmdb_id: str,
    media_type: str,
) -> None:
    with pytest.raises(MediaProviderError):
        provider().find_item_by_tmdb(
            tmdb_id,
            media_type=media_type,
        )


def test_item_is_playable_uses_user_neutral_playback_info() -> None:
    subject = provider()

    response = {
        "MediaSources": [
            {
                "Id": "source-1",
                "SupportsDirectPlay": True,
                "SupportsDirectStream": True,
                "SupportsTranscoding": True,
                "DirectStreamUrl": (
                    "/Videos/movie-abc/stream"
                    "?Static=true"
                ),
            }
        ]
    }

    with patch.object(
        JellyfinProvider,
        "_request_json",
        return_value=response,
    ) as request:
        restored = subject.is_item_playable(
            "movie-abc"
        )

    assert restored is True

    request.assert_called_once()
    args = request.call_args

    assert args.args[0] == (
        "/Items/movie-abc/PlaybackInfo"
    )
    assert args.kwargs["method"] == "POST"

    payload = args.kwargs["payload"]

    assert "UserId" not in payload
    assert payload["EnableDirectPlay"] is True
    assert payload["EnableDirectStream"] is True
    assert payload["EnableTranscoding"] is True


def test_item_is_playable_returns_false_without_media_source() -> None:
    subject = provider()

    with patch.object(
        JellyfinProvider,
        "_request_json",
        return_value={
            "MediaSources": [],
        },
    ):
        assert (
            subject.is_item_playable(
                "movie-abc"
            )
            is False
        )


def test_item_is_playable_returns_false_without_stream_capability() -> None:
    subject = provider()

    with patch.object(
        JellyfinProvider,
        "_request_json",
        return_value={
            "MediaSources": [
                {
                    "Id": "source-1",
                    "SupportsDirectPlay": False,
                    "SupportsDirectStream": False,
                    "SupportsTranscoding": False,
                }
            ],
        },
    ):
        assert (
            subject.is_item_playable(
                "movie-abc"
            )
            is False
        )


def test_item_is_playable_rejects_invalid_response() -> None:
    subject = provider()

    with patch.object(
        JellyfinProvider,
        "_request_json",
        return_value=[],
    ):
        with pytest.raises(
            MediaProviderError,
            match="playback readiness",
        ):
            subject.is_item_playable(
                "movie-abc"
            )
