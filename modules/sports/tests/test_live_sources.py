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
