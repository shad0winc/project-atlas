from __future__ import annotations

import json

import pytest

from live_sources import (
    LiveSourceCatalogError,
    load_live_source_catalog,
    safe_source_summary,
)


def write_catalog(tmp_path, payload: object):
    path = tmp_path / "live-sources.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_unconfigured_catalog_is_empty(monkeypatch) -> None:
    monkeypatch.delenv(
        "SPORTS_LIVE_SOURCE_CATALOG_PATH",
        raising=False,
    )
    assert load_live_source_catalog().sources == ()


def test_event_and_standalone_sources(tmp_path) -> None:
    path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "game",
                    "name": "Lions vs Saints",
                    "stream_url": (
                        "https://example.invalid/game.m3u8"
                    ),
                    "provider": "TheSportsDB",
                    "provider_event_id": "2475377",
                },
                {
                    "id": "redzone",
                    "name": "NFL RedZone",
                    "stream_url": (
                        "https://example.invalid/redzone.m3u8"
                    ),
                    "standalone": True,
                },
            ]
        },
    )

    catalog = load_live_source_catalog(path)

    assert (
        catalog.for_event(
            "thesportsdb",
            "2475377",
        ).name
        == "Lions vs Saints"
    )
    assert [
        source.source_id
        for source in catalog.standalone_sources()
    ] == ["redzone"]


def test_safe_summary_hides_stream_url(tmp_path) -> None:
    path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "redzone",
                    "name": "NFL RedZone",
                    "stream_url": (
                        "https://example.invalid/redzone.m3u8"
                        "?token=secret"
                    ),
                    "standalone": True,
                }
            ]
        },
    )

    summary = safe_source_summary(
        load_live_source_catalog(path).sources[0]
    )

    assert "stream_url" not in summary
    assert "secret" not in repr(summary)


@pytest.mark.parametrize(
    "entry",
    [
        {
            "id": "bad",
            "name": "Bad",
            "stream_url": "file:///tmp/a.m3u8",
            "standalone": True,
        },
        {
            "id": "bad",
            "name": "Bad",
            "stream_url": (
                "https://user:pass@example.invalid/a.m3u8"
            ),
            "standalone": True,
        },
        {
            "id": "bad",
            "name": "Bad",
            "stream_url": "https://example.invalid/a.m3u8",
        },
        {
            "id": "bad",
            "name": "Bad",
            "stream_url": "https://example.invalid/a.m3u8",
            "provider": "thesportsdb",
        },
        {
            "id": "bad",
            "name": "Bad",
            "stream_url": "https://example.invalid/a.m3u8",
            "provider": "thesportsdb",
            "provider_event_id": "event-1",
            "standalone": True,
        },
    ],
)
def test_invalid_entries_fail_closed(
    tmp_path,
    entry,
) -> None:
    path = write_catalog(
        tmp_path,
        {"sources": [entry]},
    )

    with pytest.raises(LiveSourceCatalogError):
        load_live_source_catalog(path)


def test_duplicate_event_mapping_rejected(tmp_path) -> None:
    path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "one",
                    "name": "One",
                    "stream_url": (
                        "https://example.invalid/1.m3u8"
                    ),
                    "provider": "thesportsdb",
                    "provider_event_id": "event-1",
                },
                {
                    "id": "two",
                    "name": "Two",
                    "stream_url": (
                        "https://example.invalid/2.m3u8"
                    ),
                    "provider": "thesportsdb",
                    "provider_event_id": "event-1",
                },
            ]
        },
    )

    with pytest.raises(LiveSourceCatalogError):
        load_live_source_catalog(path)


def test_resource_source_ids_are_backward_compatible(
    tmp_path,
) -> None:
    path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "game",
                    "name": "Legacy Game",
                    "stream_url": (
                        "https://example.invalid/game.m3u8"
                    ),
                    "provider": "thesportsdb",
                    "provider_event_id": "event-1",
                }
            ]
        },
    )

    source = load_live_source_catalog(
        path
    ).sources[0]

    assert source.resource_source_ids == ()
    assert (
        "resource_source_ids"
        not in source.state_dict()
    )


def test_resource_source_ids_preserve_explicit_order_and_serialize(
    tmp_path,
) -> None:
    path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "game",
                    "name": "Resource Game",
                    "stream_url": (
                        "https://example.invalid/game.m3u8"
                    ),
                    "provider": "thesportsdb",
                    "provider_event_id": "event-2",
                    "resource_source_ids": [
                        "xc-4-account",
                        "fallback-account",
                    ],
                }
            ]
        },
    )

    source = load_live_source_catalog(
        path
    ).sources[0]

    assert source.resource_source_ids == (
        "xc-4-account",
        "fallback-account",
    )

    assert source.state_dict()[
        "resource_source_ids"
    ] == [
        "xc-4-account",
        "fallback-account",
    ]


@pytest.mark.parametrize(
    ("resource_source_ids", "message"),
    [
        (
            "xc-4-account",
            "resource_source_ids must be a list",
        ),
        (
            4,
            "resource_source_ids must be a list",
        ),
        (
            {},
            "resource_source_ids must be a list",
        ),
        (
            [""],
            "resource_source_ids entry is required",
        ),
        (
            ["   "],
            "resource_source_ids entry is required",
        ),
        (
            [4],
            "resource_source_ids entry is required",
        ),
        (
            [
                "xc-4-account",
                "xc-4-account",
            ],
            (
                "resource_source_ids must not "
                "contain duplicates"
            ),
        ),
    ],
)
def test_invalid_resource_source_ids_fail_closed(
    tmp_path,
    resource_source_ids,
    message,
) -> None:
    path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "bad-resource",
                    "name": "Bad Resource",
                    "stream_url": (
                        "https://example.invalid/bad.m3u8"
                    ),
                    "provider": "thesportsdb",
                    "provider_event_id": "event-bad",
                    "resource_source_ids": (
                        resource_source_ids
                    ),
                }
            ]
        },
    )

    with pytest.raises(
        LiveSourceCatalogError,
        match=message,
    ):
        load_live_source_catalog(path)


def test_resource_source_ids_round_trip_through_state_dict(
    tmp_path,
) -> None:
    first_path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "game",
                    "name": "Round Trip Game",
                    "stream_url": (
                        "https://example.invalid/game.m3u8"
                    ),
                    "provider": "thesportsdb",
                    "provider_event_id": "event-3",
                    "resource_source_ids": [
                        "primary-account",
                        "secondary-account",
                    ],
                }
            ]
        },
    )

    source = load_live_source_catalog(
        first_path
    ).sources[0]

    second_path = (
        tmp_path
        / "round-trip-live-sources.json"
    )

    second_path.write_text(
        json.dumps(
            {
                "version": 1,
                "sources": [
                    source.state_dict()
                ],
            }
        ),
        encoding="utf-8",
    )

    reloaded = load_live_source_catalog(
        second_path
    ).sources[0]

    assert reloaded == source
    assert reloaded.resource_source_ids == (
        "primary-account",
        "secondary-account",
    )


def test_safe_summary_exposes_resource_source_ids_without_stream_url(
    tmp_path,
) -> None:
    path = write_catalog(
        tmp_path,
        {
            "sources": [
                {
                    "id": "safe-game",
                    "name": "Safe Game",
                    "stream_url": (
                        "https://example.invalid/safe.m3u8"
                    ),
                    "provider": "thesportsdb",
                    "provider_event_id": "event-safe",
                    "resource_source_ids": [
                        "xc-4-account",
                    ],
                }
            ]
        },
    )

    summary = safe_source_summary(
        load_live_source_catalog(
            path
        ).sources[0]
    )

    assert summary[
        "atlas_channel_id"
    ] == "sports-live-safe-game"

    assert summary[
        "resource_source_ids"
    ] == [
        "xc-4-account"
    ]

    assert "stream_url" not in summary
