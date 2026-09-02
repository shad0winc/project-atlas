from __future__ import annotations

import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from atlas.media.jellyfin import JellyfinProvider
from atlas.media.provider import MediaProviderError


USER_A = "a" * 32
USER_B = "b" * 32


class Response:
    def __init__(self, value: object) -> None:
        self.value = value

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.value).encode()


def global_movie(
    *,
    date_created: object = "2026-08-01T00:00:00Z",
    runtime_ticks: object = 1_000,
) -> dict[str, object]:
    return {
        "Items": [
            {
                "Id": "movie-1",
                "Name": "Example Movie",
                "Type": "Movie",
                "DateCreated": date_created,
                "RunTimeTicks": runtime_ticks,
            }
        ],
        "StartIndex": 0,
        "TotalRecordCount": 1,
    }


def user_movie(
    user_id: str,
    *,
    played: object,
    position: object,
    last_played: object,
    runtime_ticks: object = 1_000,
) -> dict[str, object]:
    return {
        "Id": "movie-1",
        "Name": "Example Movie",
        "Type": "Movie",
        "RunTimeTicks": runtime_ticks,
        "UserData": {
            "Played": played,
            "PlaybackPositionTicks": position,
            "LastPlayedDate": last_played,
        },
        "_test_user_id": user_id,
    }


def provider() -> JellyfinProvider:
    return JellyfinProvider(
        "http://jellyfin:8096",
        "secret",
    )


def test_retention_state_normalizes_global_and_user_data() -> None:
    responses = [
        Response(global_movie()),
        Response(
            user_movie(
                USER_A,
                played=True,
                position=950,
                last_played="2026-08-20T00:00:00Z",
            )
        ),
        Response(
            user_movie(
                USER_B,
                played=False,
                position=0,
                last_played=None,
            )
        ),
    ]

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=responses,
    ) as request:
        state = provider().get_retention_state(
            "movie-1",
            user_ids=(USER_A, USER_B),
        )

    assert state == {
        "media_type": "movie",
        "date_created": "2026-08-01T00:00:00Z",
        "users": (
            {
                "jellyfin_user_id": USER_A,
                "played": True,
                "playback_position_ticks": 950,
                "runtime_ticks": 1000,
                "last_played_at": "2026-08-20T00:00:00Z",
            },
            {
                "jellyfin_user_id": USER_B,
                "played": False,
                "playback_position_ticks": 0,
                "runtime_ticks": 1000,
                "last_played_at": None,
            },
        ),
    }

    assert request.call_count == 3

    urls = [
        call.args[0].full_url
        for call in request.call_args_list
    ]

    assert urls[0] == (
        "http://jellyfin:8096/"
        "Items?Ids=movie-1&Recursive=true&Limit=1"
    )

    assert urls[1] == (
        "http://jellyfin:8096/"
        f"Users/{USER_A}/Items/movie-1"
    )

    assert urls[2] == (
        "http://jellyfin:8096/"
        f"Users/{USER_B}/Items/movie-1"
    )

    for call in request.call_args_list:
        assert (
            call.args[0].headers["X-emby-token"]
            == "secret"
        )


def test_retention_state_preserves_requested_user_order() -> None:
    responses = [
        Response(global_movie()),
        Response(
            user_movie(
                USER_B,
                played=False,
                position=100,
                last_played="2026-08-20T00:00:00Z",
            )
        ),
        Response(
            user_movie(
                USER_A,
                played=True,
                position=1000,
                last_played="2026-08-10T00:00:00Z",
            )
        ),
    ]

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=responses,
    ):
        state = provider().get_retention_state(
            "movie-1",
            user_ids=(USER_B, USER_A),
        )

    assert tuple(
        entry["jellyfin_user_id"]
        for entry in state["users"]
    ) == (
        USER_B,
        USER_A,
    )


def test_retention_state_supports_no_linked_users() -> None:
    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(global_movie()),
    ) as request:
        state = provider().get_retention_state(
            "movie-1",
            user_ids=(),
        )

    assert state == {
        "media_type": "movie",
        "date_created": "2026-08-01T00:00:00Z",
        "users": (),
    }

    assert request.call_count == 1


def test_retention_state_maps_series_without_interpreting_watch_state() -> None:
    response = {
        "Items": [
            {
                "Id": "series-1",
                "Name": "Example Series",
                "Type": "Series",
                "DateCreated": "2026-01-01T00:00:00Z",
                "RunTimeTicks": 1000,
            }
        ],
        "StartIndex": 0,
        "TotalRecordCount": 1,
    }

    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(response),
    ):
        state = provider().get_retention_state(
            "series-1",
            user_ids=(),
        )

    assert state["media_type"] == "tv"
    assert state["date_created"] == "2026-01-01T00:00:00Z"
    assert state["users"] == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("DateCreated", None),
        ("DateCreated", ""),
        ("RunTimeTicks", None),
        ("RunTimeTicks", 0),
        ("RunTimeTicks", -1),
        ("RunTimeTicks", True),
    ],
)
def test_retention_state_rejects_invalid_global_metadata(
    field: str,
    value: object,
) -> None:
    item = global_movie()["Items"][0]
    assert isinstance(item, dict)
    item[field] = value

    with patch(
        "atlas.media.jellyfin.urlopen",
        return_value=Response(
            {
                "Items": [item],
                "StartIndex": 0,
                "TotalRecordCount": 1,
            }
        ),
    ):
        with pytest.raises(MediaProviderError):
            provider().get_retention_state(
                "movie-1",
                user_ids=(USER_A,),
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Played", None),
        ("Played", 1),
        ("PlaybackPositionTicks", None),
        ("PlaybackPositionTicks", -1),
        ("PlaybackPositionTicks", True),
    ],
)
def test_retention_state_rejects_invalid_user_data(
    field: str,
    value: object,
) -> None:
    user = user_movie(
        USER_A,
        played=False,
        position=0,
        last_played=None,
    )

    user_data = user["UserData"]
    assert isinstance(user_data, dict)
    user_data[field] = value

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(global_movie()),
            Response(user),
        ],
    ):
        with pytest.raises(MediaProviderError):
            provider().get_retention_state(
                "movie-1",
                user_ids=(USER_A,),
            )


def test_retention_state_rejects_position_beyond_runtime() -> None:
    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(global_movie()),
            Response(
                user_movie(
                    USER_A,
                    played=True,
                    position=1001,
                    runtime_ticks=1000,
                    last_played="2026-08-20T00:00:00Z",
                )
            ),
        ],
    ):
        with pytest.raises(MediaProviderError):
            provider().get_retention_state(
                "movie-1",
                user_ids=(USER_A,),
            )


def test_retention_state_rejects_mismatched_user_item() -> None:
    user = user_movie(
        USER_A,
        played=False,
        position=0,
        last_played=None,
    )
    user["Id"] = "different-item"

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(global_movie()),
            Response(user),
        ],
    ):
        with pytest.raises(
            MediaProviderError,
            match="mismatched",
        ):
            provider().get_retention_state(
                "movie-1",
                user_ids=(USER_A,),
            )


def test_retention_state_propagates_user_lookup_failure() -> None:
    error = HTTPError(
        "url",
        500,
        "bad",
        {},
        io.BytesIO(),
    )

    with patch(
        "atlas.media.jellyfin.urlopen",
        side_effect=[
            Response(global_movie()),
            error,
        ],
    ):
        with pytest.raises(MediaProviderError):
            provider().get_retention_state(
                "movie-1",
                user_ids=(USER_A,),
            )


def test_retention_state_rejects_duplicate_user_ids() -> None:
    with pytest.raises(MediaProviderError):
        provider().get_retention_state(
            "movie-1",
            user_ids=(USER_A, USER_A),
        )
