from __future__ import annotations

from atlas_api.services.sports import SportsWriterBackedAPIService


def _service() -> SportsWriterBackedAPIService:
    return SportsWriterBackedAPIService(
        base_url="http://sports-writer.invalid:8003",
        token="test-token",
    )


def test_get_live_tv_binding_uses_exact_identity() -> None:
    service = _service()
    calls: list[tuple[object, ...]] = []

    def request(method, path, payload=None):
        calls.append((method, path, payload))
        return {
            "binding": {
                "atlas_channel_id": "sports-event-1",
                "jellyfin_item_id": "jellyfin-1",
            }
        }

    service._request = request  # type: ignore[method-assign]

    assert service.get_live_tv_binding(
        atlas_channel_id="sports-event-1"
    ) == {
        "atlas_channel_id": "sports-event-1",
        "jellyfin_item_id": "jellyfin-1",
    }

    assert calls == [
        (
            "GET",
            "/internal/v1/live-tv/bindings?"
            "atlas_channel_id=sports-event-1",
            None,
        )
    ]


def test_set_live_tv_binding_sends_only_ids() -> None:
    service = _service()
    calls: list[tuple[object, ...]] = []

    def request(method, path, payload=None):
        calls.append((method, path, payload))
        return {
            "binding": {
                "atlas_channel_id": payload["atlas_channel_id"],
                "jellyfin_item_id": payload["jellyfin_item_id"],
            }
        }

    service._request = request  # type: ignore[method-assign]

    assert service.set_live_tv_binding(
        atlas_channel_id="sports-event-1",
        jellyfin_item_id="jellyfin-1",
    ) == {
        "atlas_channel_id": "sports-event-1",
        "jellyfin_item_id": "jellyfin-1",
    }

    assert calls[0][0] == "POST"
    assert calls[0][1] == "/internal/v1/live-tv/bindings"
    assert set(calls[0][2]) == {
        "atlas_channel_id",
        "jellyfin_item_id",
    }


def test_remove_live_tv_binding_encodes_channel_id() -> None:
    service = _service()

    def request(method, path, payload=None):
        assert method == "DELETE"
        assert path == (
            "/internal/v1/live-tv/bindings/"
            "sports-event%2Fspecial"
        )
        assert payload is None
        return {"removed": True}

    service._request = request  # type: ignore[method-assign]

    assert service.remove_live_tv_binding(
        atlas_channel_id="sports-event/special"
    ) is True
