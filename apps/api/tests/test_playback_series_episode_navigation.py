"""RED contracts for explicit Theater series episode navigation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from atlas_api.services.playback import (
    PlaybackNotFoundError,
    PlaybackService,
)


@dataclass(frozen=True)
class FakeItem:
    title: str = "Example Series"
    media_type: str = "tv"
    metadata: dict[str, object] | None = None


class FakeJellyfin:
    def __init__(self) -> None:
        self.episode_lists: list[str] = []

    def get_item(self, item_id: str) -> FakeItem:
        assert item_id == "series-1"
        return FakeItem(
            metadata={
                "jellyfin_type": "Series",
            }
        )

    def list_series_episodes(
        self,
        series_id: str,
    ) -> tuple[dict[str, object], ...]:
        self.episode_lists.append(series_id)

        return (
            {
                "id": "episode-s01e01",
                "title": "Pilot",
                "series_name": "Example Series",
                "season_number": 1,
                "episode_number": 1,
            },
            {
                "id": "episode-s01e02",
                "title": "Second",
                "series_name": "Example Series",
                "season_number": 1,
                "episode_number": 2,
            },
            {
                "id": "episode-s02e01",
                "title": "Return",
                "series_name": "Example Series",
                "season_number": 2,
                "episode_number": 1,
            },
        )


def test_library_series_exposes_browser_safe_episode_navigation() -> None:
    jellyfin = FakeJellyfin()

    service = PlaybackService(
        jellyfin,  # type: ignore[arg-type]
        jellyfin_public_url="https://jellyfin.example.test",
    )

    episodes = service.list_library_series_episodes(
        provider="jellyfin",
        item_id="series-1",
    )

    assert jellyfin.episode_lists == ["series-1"]

    assert episodes == (
        {
            "id": "episode-s01e01",
            "title": "Pilot",
            "series_name": "Example Series",
            "season_number": 1,
            "episode_number": 1,
        },
        {
            "id": "episode-s01e02",
            "title": "Second",
            "series_name": "Example Series",
            "season_number": 1,
            "episode_number": 2,
        },
        {
            "id": "episode-s02e01",
            "title": "Return",
            "series_name": "Example Series",
            "season_number": 2,
            "episode_number": 1,
        },
    )


def test_library_series_episode_navigation_rejects_non_jellyfin_provider() -> None:
    service = PlaybackService(
        FakeJellyfin(),  # type: ignore[arg-type]
        jellyfin_public_url="https://jellyfin.example.test",
    )

    with pytest.raises(PlaybackNotFoundError):
        service.list_library_series_episodes(
            provider="unsupported",
            item_id="series-1",
        )
