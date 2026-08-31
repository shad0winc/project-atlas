import pytest

from atlas.media.playback import (
    PlaybackAction,
    PlaybackActionKind,
    PlaybackSourceType,
)


def test_jellyfin_library_playback_action_is_safe_and_stable():
    action = PlaybackAction.jellyfin_library(
        "jf-item-123",
        public_base_url="https://jellyfin.shadowinc.co",
    )

    assert action.available is True
    assert action.action is PlaybackActionKind.WATCH_NOW
    assert action.label == "Watch Now"
    assert action.backend == "jellyfin"
    assert action.source_type is PlaybackSourceType.LIBRARY
    assert action.provider == "jellyfin"
    assert action.target_id == "jf-item-123"
    assert action.href == (
        "https://jellyfin.shadowinc.co/"
        "web/index.html#!/details?id=jf-item-123"
    )


def test_jellyfin_library_playback_action_escapes_item_identity():
    action = PlaybackAction.jellyfin_library(
        "item / unsafe",
        public_base_url="https://jellyfin.shadowinc.co/",
    )
    assert action.href is not None
    assert "item%20%2F%20unsafe" in action.href


@pytest.mark.parametrize(
    "public_url",
    [
        "",
        "http://192.168.30.213:8096",
        "http://jellyfin:8096",
    ],
)
def test_jellyfin_library_requires_public_https_destination(public_url):
    with pytest.raises(ValueError):
        PlaybackAction.jellyfin_library(
            "item-1",
            public_base_url=public_url,
        )


def test_jellyfin_library_playback_action_rejects_empty_identity():
    with pytest.raises(ValueError):
        PlaybackAction.jellyfin_library(
            " ",
            public_base_url="https://jellyfin.shadowinc.co",
        )
