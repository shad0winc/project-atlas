"""Standalone discovery must not masquerade as scheduled events or open streams."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock
from atlas_api.dependencies import get_jwt_service, get_user_profile_store, get_security_audit_writer
from atlas_api.routes.v1.sports import router, get_sports_api_service, require_sports_read
from atlas_api.services.live_channel_discovery import discover_live_channels
from atlas_api.services.sports import SportsWriterTransportError

CHANNEL = {"id": "nfl-redzone", "atlas_channel_id": "sports-live-nfl-redzone", "name": "NFL RedZone", "standalone": True, "provider": None, "provider_event_id": None, "resource_source_ids": ["account-one"]}
BINDING = {"atlas_channel_id": "sports-live-nfl-redzone", "jellyfin_item_id": "private-item"}

class Service:
    def __init__(self):
        self.calls = []
        self.fail = False
    def list_live_sources(self):
        self.calls.append("catalog")
        if self.fail:
            raise SportsWriterTransportError("private internal information")
        return [dict(CHANNEL, stream_url="private-url"), {"standalone": False}]
    def list_live_tv_bindings(self):
        self.calls.append("bindings")
        return [BINDING]

def client(service, authenticated=True):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_sports_api_service] = lambda: service
    if authenticated:
        app.dependency_overrides[require_sports_read] = lambda: object()
    else:
        app.dependency_overrides[get_jwt_service] = lambda: object()
        app.dependency_overrides[get_user_profile_store] = lambda: object()
        app.dependency_overrides[get_security_audit_writer] = lambda: Mock()
    return TestClient(app)

def test_catalog_discovery_excludes_event_and_private_fields():
    service = Service()
    response = client(service).get("/api/v1/sports/live-channels")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"channels": [{"atlas_channel_id": "sports-live-nfl-redzone", "name": "NFL RedZone", "playback_configured": True}]}
    assert service.calls == ["catalog", "bindings"]

def test_endpoint_requires_authentication():
    service = Service()
    response = client(service, authenticated=False).get("/api/v1/sports/live-channels")
    assert response.status_code in (401, 403)
    assert service.calls == []

def test_transport_failure_does_not_claim_empty_catalog_or_leak_details():
    service = Service()
    service.fail = True
    response = client(service).get("/api/v1/sports/live-channels")
    assert response.status_code == 503
    assert "private" not in response.text

def test_missing_binding_is_setup_pending():
    assert discover_live_channels([CHANNEL], [])[0]["playback_configured"] is False

def test_empty_standalone_catalog_is_valid():
    assert discover_live_channels([{"standalone": False}], []) == []

@pytest.mark.parametrize("change", [
    {"atlas_channel_id": "wrong-channel"}, {"name": ""},
    {"provider": "thesportsdb", "provider_event_id": "invented-event"},
])
def test_invalid_identity_fails_closed(change):
    with pytest.raises(ValueError):
        discover_live_channels([dict(CHANNEL, **change)], [])

def test_duplicate_channel_identity_fails_closed():
    with pytest.raises(ValueError):
        discover_live_channels([CHANNEL, CHANNEL], [])

def test_duplicate_binding_fails_closed():
    with pytest.raises(ValueError):
        discover_live_channels([CHANNEL], [BINDING, BINDING])
