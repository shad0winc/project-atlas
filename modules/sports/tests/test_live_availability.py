from __future__ import annotations

from types import SimpleNamespace

import private_api


class FakeCatalog:
    def __init__(self, source) -> None:
        self.source = source

    def for_event(self, provider: str, provider_event_id: str):
        assert provider == "thesportsdb"
        assert provider_event_id == "event-001"
        return self.source


class FakeBindings:
    def __init__(self, item_id: str | None) -> None:
        self.item_id = item_id
        self.calls: list[str] = []

    def resolve(self, atlas_channel_id: str) -> str | None:
        self.calls.append(atlas_channel_id)
        return self.item_id


def test_live_availability_is_false_without_authorized_source(monkeypatch) -> None:
    monkeypatch.setattr(
        private_api,
        "load_live_source_catalog",
        lambda: FakeCatalog(None),
    )
    bindings = FakeBindings("jf-should-not-be-read")
    monkeypatch.setattr(
        private_api,
        "default_live_tv_binding_registry",
        lambda: bindings,
    )

    result = private_api._live_availability(
        "thesportsdb",
        "event-001",
    )

    assert result == {
        "available": False,
        "atlas_channel_id": None,
    }
    assert bindings.calls == []


def test_live_availability_is_false_without_exact_binding(monkeypatch) -> None:
    source = SimpleNamespace(atlas_channel_id="sports-live-source-001")
    monkeypatch.setattr(
        private_api,
        "load_live_source_catalog",
        lambda: FakeCatalog(source),
    )
    bindings = FakeBindings(None)
    monkeypatch.setattr(
        private_api,
        "default_live_tv_binding_registry",
        lambda: bindings,
    )

    result = private_api._live_availability(
        "thesportsdb",
        "event-001",
    )

    assert result == {
        "available": False,
        "atlas_channel_id": None,
    }
    assert bindings.calls == ["sports-live-source-001"]


def test_live_availability_exposes_only_bound_atlas_channel(monkeypatch) -> None:
    source = SimpleNamespace(
        atlas_channel_id="sports-live-source-001",
        stream_url="https://example.invalid/private.m3u8?token=secret",
    )
    monkeypatch.setattr(
        private_api,
        "load_live_source_catalog",
        lambda: FakeCatalog(source),
    )
    bindings = FakeBindings("jf-private-item-id")
    monkeypatch.setattr(
        private_api,
        "default_live_tv_binding_registry",
        lambda: bindings,
    )

    result = private_api._live_availability(
        "thesportsdb",
        "event-001",
    )

    assert result == {
        "available": True,
        "atlas_channel_id": "sports-live-source-001",
    }
    rendered = repr(result).lower()
    assert "stream" not in rendered
    assert "secret" not in rendered
    assert "jellyfin" not in rendered
    assert "jf-private" not in rendered
