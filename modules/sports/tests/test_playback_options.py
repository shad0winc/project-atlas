from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest

from dispatcharr_admin import DispatcharrAdminClient
from feed import catalog_feed_games, render_m3u
from live_sources import LiveSourceCatalog, LiveSourceCatalogError, normalize_live_source, safe_source_summary
from live_sources import verify_playback_option


def declaration():
    options = []
    for index, option_id in enumerate(("primary", "backup-1", "backup-2")):
        uuid = str(UUID(int=index + 1))
        options.append({"option_id": option_id, "resource_source_id": f"account-{index + 1}",
            "stream_url": f"http://dispatcharr:9191/proxy/ts/stream/{uuid}",
            "dispatcharr_channel_id": index + 38, "dispatcharr_channel_uuid": uuid,
            "dispatcharr_stream_id": index + 100})
    return {"id": "game", "name": "Panthers vs Lions", "provider": "thesportsdb", "provider_event_id": "123",
        "stream_url": options[0]["stream_url"], "resource_source_ids": [row["resource_source_id"] for row in options],
        "playback_options": options}


def test_three_fixed_routes_publish_distinct_jellyfin_identities_without_duplicate_event_sources():
    source = normalize_live_source(declaration())
    catalog = LiveSourceCatalog((source,))
    assert len(catalog.sources) == 1
    assert catalog.for_event("thesportsdb", "123") == source
    rows = catalog_feed_games([{"id": "event", "name": source.name, "provider": "thesportsdb", "provider_event_id": "123"}], catalog)
    assert [row["_atlas_channel_id"] for row in rows] == ["sports-live-game", "sports-live-game--backup-1", "sports-live-game--backup-2"]
    assert len({row["stream_url"] for row in rows}) == 3
    assert render_m3u(rows).count("#EXTINF:") == 3
    assert catalog_feed_games([], catalog) == []
    assert normalize_live_source(source.state_dict()) == source
    assert "stream_url" not in repr(safe_source_summary(source))
    assert "dispatcharr_channel_uuid" not in repr(safe_source_summary(source))


@pytest.mark.parametrize("change", [
    lambda row: row["playback_options"].append(deepcopy(row["playback_options"][0])),
    lambda row: row["playback_options"][1].update(resource_source_id="account-1"),
    lambda row: row["playback_options"][1].update(stream_url=row["stream_url"]),
    lambda row: row["playback_options"][1].update(dispatcharr_stream_id=True),
    lambda row: row["playback_options"][1].update(dispatcharr_channel_uuid="bad"),
    lambda row: row["playback_options"][1].update(option_id="primary"),
    lambda row: row["playback_options"][1].update(stream_url="http://other.invalid/stream"),
    lambda row: row.update(resource_source_ids=["account-1"]),
])
def test_ambiguous_or_cross_account_routes_are_rejected(change):
    row = declaration()
    change(row)
    with pytest.raises(LiveSourceCatalogError):
        normalize_live_source(row)


class FakeDispatcharr:
    _safe_channel = DispatcharrAdminClient._safe_channel

    def __init__(self, option):
        self._base_url = "http://dispatcharr:9191"
        self.channel = {"id": option.dispatcharr_channel_id, "uuid": option.dispatcharr_channel_uuid,
            "name": "Alternate", "streams": [option.dispatcharr_stream_id]}
        self.stream = {"id": option.dispatcharr_stream_id, "m3u_account": 5, "is_stale": False}
        self.account = SimpleNamespace(account_id=5, enabled=True, credentials_configured=True, configured_max_connections=1)
        self.calls = []

    def _access_token(self):
        return "fixture-only"

    def _json_request(self, method, path, **kwargs):
        assert method == "GET"
        self.calls.append(path)
        return self.stream if "/streams/" in path else self.channel

    def read_account(self, *, account_id):
        assert account_id == 5
        return self.account


def fixture():
    source = normalize_live_source(declaration())
    option = source.playback_options[1]
    resource = SimpleNamespace(source_id=option.resource_source_id, enabled=True, backend_reference="5", max_connections=1)
    return source, resource, FakeDispatcharr(option)


def resources(source, selected):
    return tuple(selected if route.resource_source_id == selected.source_id else
        SimpleNamespace(source_id=route.resource_source_id, enabled=True, backend_reference=str(account), max_connections=1)
        for route, account in zip(source.playback_options, (2, 5, 6)))


def test_current_stream_account_and_single_stream_route_are_verified_before_use():
    source, resource, client = fixture()
    result = verify_playback_option(source, "backup-1", resources(source, resource), client)
    assert result == source.playback_options[1].safe_dict(source.atlas_channel_id)
    resource.backend_reference = "dispatcharr:m3u:5"
    assert verify_playback_option(source, "backup-1", resources(source, resource), client) == result


@pytest.mark.parametrize("change", [
    lambda resource, client: client.channel.update(streams=[101, 102]),
    lambda resource, client: client.channel.update(uuid=str(UUID(int=999))),
    lambda resource, client: client.stream.update(m3u_account=6),
    lambda resource, client: client.stream.update(is_stale=True),
    lambda resource, client: setattr(resource, "enabled", False),
    lambda resource, client: setattr(resource, "max_connections", 2),
    lambda resource, client: setattr(client.account, "enabled", False),
    lambda resource, client: setattr(client, "_base_url", "http://different.invalid"),
])
def test_route_or_capacity_drift_blocks_the_option(change):
    source, resource, client = fixture()
    change(resource, client)
    with pytest.raises(LiveSourceCatalogError):
        verify_playback_option(source, "backup-1", resources(source, resource), client)


def test_two_resource_names_cannot_disguise_the_same_provider_account():
    source, selected, client = fixture()
    records = resources(source, selected)
    records[2].backend_reference = "5"
    with pytest.raises(LiveSourceCatalogError):
        verify_playback_option(source, "backup-1", records, client)
    assert not client.calls


def test_worker_does_not_overwrite_verified_routes_with_stale_slot_name_discovery(monkeypatch):
    import worker
    source = normalize_live_source(declaration())
    monkeypatch.setattr(worker, "should_surface_game", lambda *args: True)
    def unexpected(**kwargs):
        pytest.fail("Verified route must not be automatically reprovisioned")
    monkeypatch.setattr(worker, "resolve_event_live_source_content", unexpected)
    registry = SimpleNamespace(list_sources=lambda: (source,))
    assert worker.run_live_source_provisioning_pipeline(
        [{"provider": "thesportsdb", "provider_event_id": "123"}],
        dispatcharr=object(), sources=(object(),), live_sources=registry, bindings=object(),
    ) == 0


def test_private_verification_requires_authentication_and_withholds_failure_details(monkeypatch):
    import private_api
    source, resource, client = fixture()
    handler = private_api.Handler.__new__(private_api.Handler)
    handler.path = "/internal/v1/live-playback-option?atlas_channel_id=sports-live-game&option_id=backup-1"
    replies = []
    handler._json = lambda code, payload: replies.append((code, payload))
    registry_reads = []
    def registry():
        registry_reads.append(True)
        return SimpleNamespace(list_sources=lambda: (source,))
    monkeypatch.setattr(private_api, "default_live_source_registry", registry)
    handler._require_auth = lambda: False
    handler.do_GET()
    assert not registry_reads and not replies
    handler._require_auth = lambda: True
    handler._source_store = lambda: SimpleNamespace(load=lambda: resources(source, resource))
    monkeypatch.setattr(DispatcharrAdminClient, "from_environment", lambda: client)
    handler.do_GET()
    assert replies[-1] == (200, {"option": source.playback_options[1].safe_dict(source.atlas_channel_id)})
    client.stream["m3u_account"] = 6
    handler.do_GET()
    assert replies[-1] == (503, {"error": "Playback option is unavailable."})
