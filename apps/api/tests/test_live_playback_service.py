from __future__ import annotations

import pytest

from atlas.media import (
    MediaItem,
    PlaybackActionKind,
    PlaybackSourceType,
)
from atlas_api.services.playback import (
    PlaybackNotFoundError,
    PlaybackService,
)


class FakeJellyfin:
    def __init__(
        self,
        jellyfin_type: str = "TvChannel",
    ) -> None:
        self.item = MediaItem(
            "jellyfin",
            "channel-1",
            "other",
            "NFL RedZone",
            {"jellyfin_type": jellyfin_type},
        )

    def get_item(self, item_id: str):
        assert item_id == "channel-1"
        return self.item

    def get_playback_info(
        self,
        item_id: str,
        **kwargs,
    ):
        assert item_id == "channel-1"
        assert kwargs["user_id"] == "jf-user-1"

        return {
            "duration_ticks": None,
            "can_seek": False,
            "stream_path": (
                "/videos/channel-1/master.m3u8"
                "?MediaSourceId=source-1"
            ),
            "tracks": (),
        }


def test_resolve_live_session_uses_live_contract() -> None:
    service = PlaybackService(
        FakeJellyfin(),
        jellyfin_public_url=(
            "https://example.invalid"
        ),
    )

    session = service.resolve_live_session(
        provider="jellyfin",
        item_id="channel-1",
        jellyfin_user_id="jf-user-1",
    )

    assert (
        session.action
        is PlaybackActionKind.WATCH_LIVE
    )
    assert (
        session.source_type
        is PlaybackSourceType.LIVE
    )
    assert session.label == "Watch Live"
    assert session.title == "NFL RedZone"


def test_resolve_live_session_accepts_legacy_live_tv_channel_type() -> None:
    service = PlaybackService(
        FakeJellyfin("LiveTvChannel"),
        jellyfin_public_url=(
            "https://example.invalid"
        ),
    )

    session = service.resolve_live_session(
        provider="jellyfin",
        item_id="channel-1",
        jellyfin_user_id="jf-user-1",
    )

    assert session.action is PlaybackActionKind.WATCH_LIVE


@pytest.mark.parametrize(
    "subtitle_stream_index",
    [True, -2],
)
def test_resolve_live_session_rejects_invalid_subtitle_selection(
    subtitle_stream_index,
) -> None:
    service = PlaybackService(
        FakeJellyfin(),
        jellyfin_public_url=(
            "https://example.invalid"
        ),
    )

    from atlas_api.services.playback import PlaybackUnavailableError

    with pytest.raises(PlaybackUnavailableError):
        service.resolve_live_session(
            provider="jellyfin",
            item_id="channel-1",
            jellyfin_user_id="jf-user-1",
            subtitle_stream_index=subtitle_stream_index,
        )


def test_resolve_live_session_rejects_non_live_item() -> None:
    service = PlaybackService(
        FakeJellyfin("Movie"),
        jellyfin_public_url=(
            "https://example.invalid"
        ),
    )

    with pytest.raises(PlaybackNotFoundError):
        service.resolve_live_session(
            provider="jellyfin",
            item_id="channel-1",
            jellyfin_user_id="jf-user-1",
        )
