from __future__ import annotations

import json
from pathlib import Path

import pytest

from live_sources import (
    LiveSource,
    LiveSourceCatalogError,
    LiveSourceRegistry,
    load_live_source_catalog,
    safe_source_summary,
)


def event_source(
    source_id: str = "event-one",
    *,
    event_id: str = "event-1",
) -> LiveSource:
    return LiveSource(
        source_id=source_id,
        name="Atlas Event",
        stream_url=(
            "http://atlas-dispatcharr:9191/"
            "proxy/ts/stream/"
            "00000000-0000-0000-0000-000000000001"
        ),
        provider="thesportsdb",
        provider_event_id=event_id,
    )


def test_registry_ensure_creates_v1_state_mode_600(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-sources.json"
    registry = LiveSourceRegistry(path)

    registry.ensure()

    assert path.is_file()
    assert not path.is_symlink()
    assert path.stat().st_mode & 0o777 == 0o600

    assert json.loads(
        path.read_text(encoding="utf-8")
    ) == {
        "version": 1,
        "sources": [],
    }

    assert registry.lock_path.is_file()
    assert (
        registry.lock_path.stat().st_mode
        & 0o777
    ) == 0o600


def test_registry_add_load_and_delete_round_trip(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-sources.json"
    registry = LiveSourceRegistry(path)

    source = event_source()

    assert registry.add(source) == source

    loaded = registry.list_sources()

    assert loaded == (source,)

    catalog = load_live_source_catalog(path)

    assert (
        catalog.for_event(
            "TheSportsDB",
            "event-1",
        )
        == source
    )

    summary = safe_source_summary(
        loaded[0]
    )

    assert summary == {
        "id": "event-one",
        "name": "Atlas Event",
        "provider": "thesportsdb",
        "provider_event_id": "event-1",
        "standalone": False,
    }

    assert "stream_url" not in summary
    assert "proxy/ts/stream" not in repr(
        summary
    )

    assert registry.delete(
        "event-one"
    ) is True

    assert registry.list_sources() == ()

    assert registry.delete(
        "event-one"
    ) is False


def test_registry_set_updates_by_source_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-sources.json"
    registry = LiveSourceRegistry(path)

    registry.add(
        event_source()
    )

    changed = LiveSource(
        source_id="event-one",
        name="Updated Atlas Event",
        stream_url=(
            "http://atlas-dispatcharr:9191/"
            "proxy/ts/stream/"
            "00000000-0000-0000-0000-000000000002"
        ),
        provider="thesportsdb",
        provider_event_id="event-2",
    )

    assert registry.set(
        changed
    ) == changed

    assert registry.list_sources() == (
        changed,
    )


def test_registry_rejects_duplicate_event_mapping(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-sources.json"
    registry = LiveSourceRegistry(path)

    registry.add(
        event_source(
            "one",
            event_id="same-event",
        )
    )

    with pytest.raises(
        LiveSourceCatalogError
    ):
        registry.add(
            event_source(
                "two",
                event_id="same-event",
            )
        )

    assert [
        item.source_id
        for item
        in registry.list_sources()
    ] == ["one"]


def test_registry_set_cannot_create_duplicate_event_mapping(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-sources.json"
    registry = LiveSourceRegistry(path)

    registry.add(
        event_source(
            "one",
            event_id="event-1",
        )
    )

    registry.add(
        event_source(
            "two",
            event_id="event-2",
        )
    )

    conflicting = event_source(
        "two",
        event_id="event-1",
    )

    with pytest.raises(
        LiveSourceCatalogError
    ):
        registry.set(conflicting)

    assert {
        item.source_id: (
            item.provider_event_id
        )
        for item
        in registry.list_sources()
    } == {
        "one": "event-1",
        "two": "event-2",
    }


def test_registry_rejects_symlink_state(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"

    target.write_text(
        '{"version":1,"sources":[]}\n',
        encoding="utf-8",
    )

    path = tmp_path / "live-sources.json"

    path.symlink_to(target)

    registry = LiveSourceRegistry(path)

    with pytest.raises(
        LiveSourceCatalogError
    ):
        registry.ensure()


def test_versionless_reader_compatibility(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.json"

    path.write_text(
        json.dumps(
            {
                "sources": [
                    event_source().state_dict()
                ]
            }
        ),
        encoding="utf-8",
    )

    catalog = load_live_source_catalog(
        path
    )

    assert [
        source.source_id
        for source
        in catalog.sources
    ] == ["event-one"]


def test_invalid_state_version_fails_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-sources.json"

    path.write_text(
        json.dumps(
            {
                "version": 999,
                "sources": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        LiveSourceCatalogError
    ):
        load_live_source_catalog(
            path
        )
