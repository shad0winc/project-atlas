import json
from types import SimpleNamespace
import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from atlas.jellyfin_live_streams import LiveStreamOwnershipError
from atlas.sports_resource_pool import SportsResourcePool
from atlas.sports_session_registry import SportsSessionRegistry
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.playback_capabilities import PlaybackCapabilityService, PlaybackCapabilityError
from atlas_api.routes.v1 import sports_playback as routes


def setup(tmp_path):
    now = [100.0]
    sessions = SportsSessionRegistry(tmp_path / "sessions.json", clock=lambda: now[0])
    pool = SportsResourcePool(tmp_path / "pool.json", clock=lambda: now[0],
        sharing_bindings={("game", "account"): "a" * 64})
    def admit(user):
        lease = pool.acquire(user_id=user, target_id="game", candidate_source_ids=("account",),
                             capacities={"account": 1}, user_limit=1)
        return sessions.admit(user_id=user, target_id="game", limit=1, resource_lease_id=lease.lease_id)
    first, second = admit("first"), admit("second")
    capabilities = PlaybackCapabilityService(AtlasAPISettings(jwt_secret="r" * 64))
    token = capabilities.create_live_release(user_id=first.user_id, session_id=first.session_id,
                                             target_id=first.target_id, lease_id=first.resource_lease_id)
    calls = []
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[routes.get_sports_session_registry] = lambda: sessions
    app.dependency_overrides[routes.get_sports_resource_pool] = lambda: pool
    app.dependency_overrides[routes.get_playback_capability_service] = lambda: capabilities
    app.dependency_overrides[routes.get_playback_service] = lambda: SimpleNamespace(
        release_live_stream=lambda **kw: calls.append(kw))
    def no_login():
        raise HTTPException(status_code=401, detail="Login unavailable")
    app.dependency_overrides[routes.require_sports_read] = no_login
    return now, sessions, pool, first, second, capabilities, token, calls, TestClient(app)


def release(client, record, token):
    return client.delete("/api/v1/sports/live/sessions/" + record.session_id + "/release-capability",
                         headers={"X-Atlas-Live-Release-Capability": token})


def test_release_without_login_after_expiry_preserves_other_viewer(tmp_path):
    now, sessions, pool, first, second, caps, token, calls, client = setup(tmp_path)
    now[0] += 1000
    assert client.delete("/api/v1/sports/live/sessions/" + first.session_id).status_code == 401
    assert release(client, first, token).status_code == 204
    assert calls == [{"session_id": first.session_id, "user_id": "first"}]
    assert set(json.loads(sessions.path.read_bytes())["sessions"]) == {second.session_id}
    assert set(json.loads(pool.path.read_bytes())["leases"]) == {second.resource_lease_id}
    assert release(client, first, token).status_code == 404
    assert len(calls) == 1


@pytest.mark.parametrize("claim,value", [("sub", "second"), ("session", "wrong"),
    ("target", "wrong"), ("lease", "wrong"), ("target", None), ("lease", 123),
    ("aud", "atlas-playback-session"), ("kind", "playback_session"),
    ("exp", 1)])
def test_changed_scope_is_rejected_before_provider_actions(tmp_path, claim, value):
    now, sessions, pool, first, second, caps, token, calls, client = setup(tmp_path)
    payload = jwt.decode(token, options={"verify_signature": False})
    payload[claim] = value
    changed = jwt.encode(payload, "r" * 64, algorithm="HS256")
    before = sessions.path.read_bytes(), pool.path.read_bytes()
    assert release(client, first, changed).status_code in (401, 404)
    assert not calls
    assert (sessions.path.read_bytes(), pool.path.read_bytes()) == before


def test_bad_signature_missing_token_and_wrong_session_are_denied(tmp_path):
    now, sessions, pool, first, second, caps, token, calls, client = setup(tmp_path)
    payload = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(payload, "s" * 64, algorithm="HS256")
    assert release(client, first, forged).status_code == 401
    assert release(client, second, token).status_code == 401
    assert client.delete("/api/v1/sports/live/sessions/" + first.session_id + "/release-capability").status_code == 422
    assert not calls


def test_uncertain_close_preserves_records(tmp_path):
    now, sessions, pool, first, second, caps, token, calls, client = setup(tmp_path)
    def blocked(**kw):
        raise LiveStreamOwnershipError("uncertain close")
    client.app.dependency_overrides[routes.get_playback_service] = lambda: SimpleNamespace(release_live_stream=blocked)
    before = sessions.path.read_bytes(), pool.path.read_bytes()
    assert release(client, first, token).status_code == 503
    assert (sessions.path.read_bytes(), pool.path.read_bytes()) == before


def test_release_token_cannot_bootstrap_stream_or_renew_session(tmp_path):
    now, sessions, pool, first, second, caps, token, calls, client = setup(tmp_path)
    with pytest.raises(PlaybackCapabilityError):
        caps.exchange_bootstrap(token)
    with pytest.raises(PlaybackCapabilityError):
        caps.authorize_session(token, request_uri="/videos/item/master.m3u8")
    headers={"Authorization": "Bearer " + token}
    assert client.post("/api/v1/sports/live/sessions/" + first.session_id + "/heartbeat", headers=headers).status_code == 401
    assert client.get("/api/v1/sports/live/game/session", headers=headers).status_code == 401
    assert not calls


def test_authenticated_open_issues_bound_cleanup_credential(tmp_path):
    from apps.api.tests.test_sports_shared_admission_route import integrated_harness, start
    harness, pool, current, checks = integrated_harness(tmp_path)
    capabilities = PlaybackCapabilityService(AtlasAPISettings(jwt_secret="r" * 64))
    harness.client.app.dependency_overrides[routes.get_playback_capability_service] = lambda: capabilities
    response = start(harness)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    session_id = response.headers["X-Atlas-Live-Session-ID"]
    claims = capabilities.authorize_live_release(response.headers["X-Atlas-Live-Release-Capability"], session_id=session_id)
    registry = harness.client.app.dependency_overrides[routes.get_sports_session_registry]()
    record = registry.read_owned_record(session_id=session_id, user_id=claims["sub"])
    assert claims["target"] == record.target_id
    assert claims["lease"] == record.resource_lease_id
