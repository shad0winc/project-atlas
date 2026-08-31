from __future__ import annotations

from types import SimpleNamespace

import pytest

from atlas_api.services.playback import (
    PlaybackService,
    PlaybackUnavailableError,
)


class FakeJellyfin:
    def __init__(self) -> None:
        self.playback_user_id: str | None = None

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
    ) -> dict:
        self.playback_user_id = user_id
        return {
            "media_source_id": "source-1",
            "duration_ticks": 100,
            "can_seek": True,
            "supports_direct_play": True,
            "supports_direct_stream": True,
            "supports_transcoding": True,
            "tracks": (),
            "stream_path": (
                "/videos/item-1/master.m3u8"
                "?MediaSourceId=source-1"
            ),
        }


def test_library_session_uses_linked_jellyfin_identity() -> None:
    jellyfin = FakeJellyfin()
    service = PlaybackService(
        jellyfin,
        jellyfin_public_url="https://jellyfin.example.test",
    )

    session = service.resolve_library_session(
        provider="jellyfin",
        item_id="item-1",
        jellyfin_user_id="a" * 32,
    )

    assert session.available is True
    assert jellyfin.playback_user_id == "a" * 32


def test_library_session_fails_closed_without_linked_identity() -> None:
    jellyfin = FakeJellyfin()
    service = PlaybackService(
        jellyfin,
        jellyfin_public_url="https://jellyfin.example.test",
    )

    with pytest.raises(
        PlaybackUnavailableError,
        match="not linked to Jellyfin",
    ):
        service.resolve_library_session(
            provider="jellyfin",
            item_id="item-1",
            jellyfin_user_id="",
        )

    assert jellyfin.playback_user_id is None
