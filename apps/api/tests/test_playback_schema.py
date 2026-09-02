from types import SimpleNamespace

from atlas.media import PlaybackTrack
from atlas_api.schemas.playback import PlaybackSessionResponse


def test_playback_session_response_serializes_slotted_tracks() -> None:
    audio = PlaybackTrack(
        index=1,
        kind="Audio",
        label="English AAC",
        language="eng",
        codec="aac",
        default=True,
        forced=False,
    )
    subtitle = PlaybackTrack(
        index=2,
        kind="Subtitle",
        label="English",
        language="eng",
        codec="srt",
        default=False,
        forced=True,
    )

    session = SimpleNamespace(
        available=True,
        action=SimpleNamespace(value="watch"),
        label="Watch Now",
        backend="jellyfin",
        source_type=SimpleNamespace(value="on_demand"),
        provider="jellyfin",
        requested_target_id="series-id",
        playable_target_id="episode-id",
        title="Example Episode",
        media_type="Episode",
        duration_ticks=123456789,
        can_seek=True,
        audio_tracks=(audio,),
        subtitle_tracks=(subtitle,),
        previous_target_id=None,
        next_target_id="next-episode-id",
    )

    response = PlaybackSessionResponse.from_domain(
        session,
        playback_bootstrap_url=(
            "https://playback.shadowinc.co/"
            "_atlas/playback/bootstrap"
        ),
        playback_capability="test-capability",
    )

    assert len(response.audio_tracks) == 1
    assert response.audio_tracks[0].index == 1
    assert response.audio_tracks[0].kind == "Audio"
    assert response.audio_tracks[0].label == "English AAC"
    assert response.audio_tracks[0].language == "eng"
    assert response.audio_tracks[0].codec == "aac"
    assert response.audio_tracks[0].default is True
    assert response.audio_tracks[0].forced is False

    assert len(response.subtitle_tracks) == 1
    assert response.subtitle_tracks[0].index == 2
    assert response.subtitle_tracks[0].kind == "Subtitle"
    assert response.subtitle_tracks[0].label == "English"
    assert response.subtitle_tracks[0].language == "eng"
    assert response.subtitle_tracks[0].codec == "srt"
    assert response.subtitle_tracks[0].default is False
    assert response.subtitle_tracks[0].forced is True
