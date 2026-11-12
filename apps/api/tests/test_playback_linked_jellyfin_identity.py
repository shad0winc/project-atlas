from __future__ import annotations

from types import SimpleNamespace

import pytest

from atlas_api.schemas.playback import PlaybackSessionResponse
from atlas_api.services.playback import (
    PlaybackService,
    PlaybackUnavailableError,
)


class FakeJellyfin:
    def __init__(self) -> None:
        self.playback_user_id: str | None = None
        self.prefer_english_audio = False
        self.selected_version_id: str | None = None

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
        prefer_english_audio: bool = False,
        selected_version_id: str | None = None,
    ) -> dict:
        self.playback_user_id = user_id
        self.prefer_english_audio = prefer_english_audio
        self.selected_version_id = selected_version_id
        return {
            "media_source_id": selected_version_id or "source-1",
            "selected_version_id": selected_version_id,
            "versions": (
                {"id": "source-1", "width": 3840, "height": 2160},
                {"id": "source-2", "width": 1920, "height": 1080},
            ) if selected_version_id is not None else (),
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
    assert jellyfin.prefer_english_audio is True


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


def test_library_version_uses_linked_identity_and_serializes_dimensions() -> None:
    jellyfin = FakeJellyfin()
    service = PlaybackService(jellyfin, jellyfin_public_url="https://jellyfin.example.test")
    session = service.resolve_library_session(
        provider="jellyfin",
        item_id="item-1",
        jellyfin_user_id="a" * 32,
        selected_version_id="source-2",
    )
    response = PlaybackSessionResponse.from_domain(
        session, playback_bootstrap_url="https://playback.example.test", playback_capability="fixture"
    ).model_dump(mode="json")

    assert jellyfin.playback_user_id == "a" * 32
    assert jellyfin.selected_version_id == "source-2"
    assert response["selected_version_id"] == "source-2"
    assert response["versions"] == [
        {"id": "source-1", "width": 3840, "height": 2160},
        {"id": "source-2", "width": 1920, "height": 1080},
    ]
