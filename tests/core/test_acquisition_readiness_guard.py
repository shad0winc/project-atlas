"""Explicit acquisition intent cannot pass legacy playability readiness."""

import pytest

from atlas.media_requests.models import (
    MediaAudioPreference,
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)
from atlas.media_requests.readiness import (
    JellyfinRequestReadiness,
    MediaRequestReadinessError,
)


class PlayableLibrary:
    def __init__(self):
        self.calls = []

    def find_item_by_tmdb(self, tmdb_id, *, media_type):
        self.calls.append("lookup")
        return "item-001"

    def list_series_episodes(self, series_id):
        self.calls.append("episodes")
        raise AssertionError("Explicit intent must not use legacy season readiness")

    def is_item_playable(self, item_id):
        self.calls.append("playable")
        return True


def make_request(media_type, policy, *, status=MediaRequestStatus.PROCESSING,
                 provider_media_id="157336"):
    return MediaRequest(
        request_id="request-001", user_id="user-001", media_type=media_type,
        provider="jellyseerr", provider_media_id=provider_media_id,
        title="Readiness fixture", status=status, audio_preference=policy,
        season_number=1 if media_type in {
            MediaRequestType.TV, MediaRequestType.ANIME_TV
        } else None,
    )


@pytest.mark.parametrize("media_type", [
    MediaRequestType.MOVIE, MediaRequestType.ANIME_MOVIE,
    MediaRequestType.TV, MediaRequestType.ANIME_TV,
])
@pytest.mark.parametrize("policy", list(MediaAudioPreference))
def test_explicit_policy_cannot_become_ready_from_playability(media_type, policy):
    library = PlayableLibrary()
    request = make_request(media_type, policy)
    before = request.to_dict()
    assert JellyfinRequestReadiness(library).is_ready(request) is False
    assert library.calls == []
    assert request.to_dict() == before
    assert request.status is MediaRequestStatus.PROCESSING


@pytest.mark.parametrize("media_type", [MediaRequestType.MOVIE, MediaRequestType.ANIME_MOVIE])
def test_unspecified_policy_preserves_legacy_movie_readiness(media_type):
    library = PlayableLibrary()
    assert JellyfinRequestReadiness(library).is_ready(make_request(media_type, None)) is True
    assert library.calls == ["lookup", "playable"]


def test_explicit_policy_still_requires_processing_status():
    library = PlayableLibrary()
    with pytest.raises(MediaRequestReadinessError, match="processing"):
        JellyfinRequestReadiness(library).is_ready(make_request(
            MediaRequestType.MOVIE, MediaAudioPreference.ENGLISH_REQUIRED,
            status=MediaRequestStatus.PENDING,
        ))
    assert library.calls == []


def test_explicit_policy_still_requires_valid_tmdb_identity():
    library = PlayableLibrary()
    with pytest.raises(MediaRequestReadinessError, match="TMDB"):
        JellyfinRequestReadiness(library).is_ready(make_request(
            MediaRequestType.MOVIE, MediaAudioPreference.ORIGINAL_SUBBED,
            provider_media_id="invalid",
        ))
    assert library.calls == []
