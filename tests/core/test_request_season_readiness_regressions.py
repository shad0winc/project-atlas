"""Regression coverage for season-scoped request readiness."""

from types import SimpleNamespace

from atlas.media_requests.discovery import MediaDiscoveryAvailability
from atlas.media_requests.models import MediaRequestStatus
from atlas.media_requests.providers.jellyseerr import (
    JellyseerrMediaRequestProvider,
)
from atlas.media_requests.readiness import JellyfinRequestReadiness


class _MappingEpisodeLibrary:
    def find_item_by_tmdb(self, tmdb_id: str, *, media_type: str) -> str | None:
        assert tmdb_id == "94664"
        assert media_type == "tv"
        return "series-1"

    def list_series_episodes(self, series_id: str) -> tuple[dict[str, object], ...]:
        assert series_id == "series-1"
        return (
            {"id": "s1e1", "season_number": 1},
            {"id": "s2e1", "season_number": 2},
            {"id": "s2e2", "season_number": 2},
        )

    def is_item_playable(self, item_id: str) -> bool:
        return item_id in {"s1e1", "s2e1", "s2e2"}


def test_series_readiness_accepts_jellyfin_mapping_episode_contract() -> None:
    readiness = JellyfinRequestReadiness(_MappingEpisodeLibrary())
    assert readiness._series_ready("94664", season_number=2) is True


class _SeasonDetailProvider:
    def __init__(self, availability: MediaDiscoveryAvailability) -> None:
        self.availability = availability

    def get_tv_detail(self, provider_media_id: object) -> SimpleNamespace:
        assert provider_media_id == 236235
        return SimpleNamespace(
            seasons=(
                SimpleNamespace(
                    season_number=1,
                    availability=self.availability,
                ),
            ),
        )


def _tv_request_resource() -> dict[str, object]:
    return {
        "status": 5,
        "media": {
            "mediaType": "tv",
            "status": 4,
            "tmdbId": 236235,
        },
        "seasons": [
            {
                "seasonNumber": 1,
                "status": 5,
            },
        ],
    }


def test_available_requested_season_promotes_series_importing_to_processing() -> None:
    provider = _SeasonDetailProvider(MediaDiscoveryAvailability.AVAILABLE)
    result = JellyseerrMediaRequestProvider._season_scoped_status(
        provider,
        _tv_request_resource(),
        MediaRequestStatus.IMPORTING,
    )
    assert result is MediaRequestStatus.PROCESSING


def test_partial_requested_season_preserves_existing_provider_status() -> None:
    provider = _SeasonDetailProvider(
        MediaDiscoveryAvailability.PARTIALLY_AVAILABLE
    )
    result = JellyseerrMediaRequestProvider._season_scoped_status(
        provider,
        _tv_request_resource(),
        MediaRequestStatus.IMPORTING,
    )
    assert result is MediaRequestStatus.IMPORTING
