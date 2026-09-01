from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from atlas_api.routes.v1.playback import _subtitle_stream_index
from atlas_api.services.playback import PlaybackService


class FakeJellyfin:
    def __init__(self) -> None:
        self.subtitle_stream_index: int | None = None

    def get_item(self, item_id: str):
        return SimpleNamespace(
            item_id=item_id,
            title="Example Movie",
            media_type="movie",
            metadata={"jellyfin_type": "movie"},
        )

    def get_playback_info(
        self,
        item_id: str,
        *,
        user_id: str,
        subtitle_stream_index: int | None = None,
    ) -> dict:
        self.subtitle_stream_index = subtitle_stream_index
        return {
            "media_source_id": "source-1",
            "duration_ticks": 100,
            "can_seek": True,
            "supports_direct_play": True,
            "supports_direct_stream": True,
            "supports_transcoding": True,
            "tracks": (
                {
                    "index": 2,
                    "kind": "subtitle",
                    "label": "English",
                    "language": "eng",
                    "codec": "srt",
                    "default": False,
                    "forced": False,
                },
            ),
            "stream_path": (
                "/videos/item-1/master.m3u8"
                "?MediaSourceId=source-1"
            ),
        }


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (None, None),
        ("", None),
        ("auto", None),
        ("AUTO", None),
        ("off", -1),
        ("OFF", -1),
        ("0", 0),
        ("2", 2),
        ("17", 17),
    ),
)
def test_subtitle_query_normalization(
    value: str | None,
    expected: int | None,
) -> None:
    assert _subtitle_stream_index(value) == expected


@pytest.mark.parametrize(
    "value",
    ("-1", "-2", "english", "2.5"),
)
def test_subtitle_query_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(HTTPException) as error:
        _subtitle_stream_index(value)

    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "selection",
    (None, -1, 2),
)
def test_library_session_forwards_subtitle_selection(
    selection: int | None,
) -> None:
    jellyfin = FakeJellyfin()
    service = PlaybackService(
        jellyfin,
        jellyfin_public_url="https://jellyfin.example.test",
    )

    session = service.resolve_library_session(
        provider="jellyfin",
        item_id="item-1",
        jellyfin_user_id="a" * 32,
        subtitle_stream_index=selection,
    )

    assert session.available is True
    assert jellyfin.subtitle_stream_index == selection
    assert session.subtitle_tracks[0].index == 2
