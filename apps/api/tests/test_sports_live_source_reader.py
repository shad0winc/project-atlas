from __future__ import annotations

import pytest

from atlas_api.services.sports import (
    SportsWriterBackedAPIService,
    SportsWriterTransportError,
)


class FakeSportsWriter(
    SportsWriterBackedAPIService
):
    def __init__(
        self,
        payload: dict[str, object],
    ) -> None:
        self.payload = payload
        self.calls: list[
            tuple[str, str]
        ] = []

    def _request(
        self,
        method: str,
        path: str,
        payload=None,
    ) -> dict[str, object]:
        assert payload is None
        self.calls.append(
            (method, path)
        )
        return self.payload


def test_list_live_sources_returns_safe_resource_association() -> None:
    service = FakeSportsWriter(
        {
            "live_sources": [
                {
                    "id": "game-one",
                    "name": "Game One",
                    "provider": "thesportsdb",
                    "provider_event_id": "123",
                    "standalone": False,
                    "atlas_channel_id": (
                        "sports-live-game-one"
                    ),
                    "resource_source_ids": [
                        "xc-4-account",
                        "fallback-account",
                    ],
                }
            ]
        }
    )

    result = service.list_live_sources()

    assert service.calls == [
        (
            "GET",
            "/internal/v1/live-sources",
        )
    ]

    assert result == [
        {
            "id": "game-one",
            "name": "Game One",
            "provider": "thesportsdb",
            "provider_event_id": "123",
            "standalone": False,
            "atlas_channel_id": (
                "sports-live-game-one"
            ),
            "resource_source_ids": [
                "xc-4-account",
                "fallback-account",
            ],
        }
    ]


def test_list_live_sources_accepts_legacy_missing_resource_association() -> None:
    service = FakeSportsWriter(
        {
            "live_sources": [
                {
                    "id": "legacy-game",
                    "name": "Legacy Game",
                    "provider": "thesportsdb",
                    "provider_event_id": "456",
                    "standalone": False,
                }
            ]
        }
    )

    result = service.list_live_sources()

    assert result[0][
        "atlas_channel_id"
    ] is None

    assert result[0][
        "resource_source_ids"
    ] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "live_sources": {},
        },
        {
            "live_sources": [
                "not-an-object",
            ],
        },
        {
            "live_sources": [
                {
                    "id": "game-one",
                    "name": "Game One",
                    "provider": "thesportsdb",
                    "provider_event_id": "123",
                    "standalone": False,
                    "stream_url": (
                        "https://private.invalid/live"
                    ),
                }
            ],
        },
        {
            "live_sources": [
                {
                    "id": "game-one",
                    "name": "Game One",
                    "provider": "thesportsdb",
                    "provider_event_id": "123",
                    "standalone": False,
                    "resource_source_ids": (
                        "xc-4-account"
                    ),
                }
            ],
        },
        {
            "live_sources": [
                {
                    "id": "game-one",
                    "name": "Game One",
                    "provider": "thesportsdb",
                    "provider_event_id": "123",
                    "standalone": False,
                    "resource_source_ids": [
                        "",
                    ],
                }
            ],
        },
        {
            "live_sources": [
                {
                    "id": "game-one",
                    "name": "Game One",
                    "provider": "thesportsdb",
                    "provider_event_id": "123",
                    "standalone": False,
                    "resource_source_ids": [
                        "xc-4-account",
                        "xc-4-account",
                    ],
                }
            ],
        },
    ],
)
def test_list_live_sources_rejects_unsafe_or_invalid_payload(
    payload,
) -> None:
    service = FakeSportsWriter(
        payload
    )

    with pytest.raises(
        SportsWriterTransportError
    ):
        service.list_live_sources()


def test_list_live_sources_requires_channel_id_for_resource_managed_source() -> None:
    service = FakeSportsWriter(
        {
            "live_sources": [
                {
                    "id": "game-one",
                    "name": "Game One",
                    "provider": "thesportsdb",
                    "provider_event_id": "123",
                    "standalone": False,
                    "resource_source_ids": [
                        "xc-4-account",
                    ],
                }
            ]
        }
    )

    with pytest.raises(
        SportsWriterTransportError
    ):
        service.list_live_sources()


@pytest.mark.parametrize(
    "atlas_channel_id",
    [
        "",
        "   ",
        4,
        True,
    ],
)
def test_list_live_sources_rejects_invalid_channel_id(
    atlas_channel_id,
) -> None:
    service = FakeSportsWriter(
        {
            "live_sources": [
                {
                    "id": "game-one",
                    "name": "Game One",
                    "provider": "thesportsdb",
                    "provider_event_id": "123",
                    "standalone": False,
                    "atlas_channel_id": (
                        atlas_channel_id
                    ),
                    "resource_source_ids": [
                        "xc-4-account",
                    ],
                }
            ]
        }
    )

    with pytest.raises(
        SportsWriterTransportError
    ):
        service.list_live_sources()
