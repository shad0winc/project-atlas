"""Signed video scope plus live Atlas session and current role during maintenance."""
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Depends, Request

from tests.test_maintenance_access import site, login, bearer, BROWSER, HEADERS
from tests.test_sports_live_release_capability import setup as release_setup, release
from atlas_api.auth.maintenance_sessions import MaintenanceSessions
from atlas_api.auth.models import TokenType
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.dependencies import get_maintenance_control_client
from atlas_api.playback_capabilities import PlaybackCapabilityService, PlaybackCapabilityError
from atlas_api.routes import playback_gateway
from atlas_api.services.maintenance_access import install_maintenance_middleware
from atlas_api.services.maintenance_playback import issue_maintenance_media_binding

STREAM = '/videos/' + 'a' * 32 + '/master.m3u8'
BOOTSTRAP = '/_atlas/playback/bootstrap'
AUTHORIZE = '/_atlas/playback/authorize'


@pytest.fixture
def media(site, monkeypatch):
    client, control, profiles, auth, jwt_service, audit = site
    capabilities = PlaybackCapabilityService(AtlasAPISettings(jwt_secret='s' * 48))
    monkeypatch.setattr(playback_gateway, '_capabilities', lambda: capabilities)
    monkeypatch.setenv('ATLAS_JELLYFIN_API_KEY', 'fixture-private-key')

    @client.app.get('/api/v1/test-maintenance-media-binding')
    def binding(reference=Depends(issue_maintenance_media_binding)):
        return {'reference': reference}
    return client, control, profiles, auth, jwt_service, capabilities


def video(media, name='admin', *, subject=None, bound=True):
    client, control, profiles, auth, jwt_service, capabilities = media
    response = login(client, name, browser=False)
    assert response.status_code == 200
    claims = jwt_service.decode_token(response.json()['access_token'], expected_type=TokenType.ACCESS)
    reference = client.get('/api/v1/test-maintenance-media-binding', headers=bearer(response))
    assert reference.status_code == 200
    token = capabilities.create_bootstrap(user_id=subject or claims.subject,
        playable_target_id='a' * 32, stream_path=STREAM,
        maintenance_binding=reference.json()['reference'] if bound else None)
    return token, response


def bootstrap(client, token):
    return client.post(BOOTSTRAP, headers={'Authorization': 'Bearer ' + token})


def authorize(client, *, uri=STREAM, token=None):
    if token is not None:
        client.cookies.clear()
        client.cookies.set('atlas_playback', token)
    value = token if token is not None else client.cookies.get('atlas_playback', '')
    # The proxy forwards the Cookie received on /videos/... to its internal
    # authorization subrequest; a direct client would otherwise omit it here.
    return client.get(AUTHORIZE, headers={'X-Forwarded-Uri': uri,
        'Cookie':'atlas_playback=' + value})


@pytest.mark.parametrize('name', ['admin', 'legacy'])
def test_live_admin_video_binding_survives_exchange_and_stays_video_scoped(media, name):
    client, control, profiles, auth, jwt_service, caps = media
    token, response = video(media, name)
    claims = caps.inspect_bootstrap(token)
    reference = claims['maintenance_binding']
    assert len(reference) == 64 and claims['sub'] not in reference
    assert bootstrap(client, token).status_code == 200
    session = client.cookies.get('atlas_playback')
    signed = caps.authorize_session(session, request_uri=STREAM)
    assert signed['maintenance_binding'] == reference
    assert authorize(client).status_code == 200
    assert authorize(client, uri='/videos/' + 'b' * 32 + '/main.m3u8').status_code == 503
    # A transport cookie never authorizes the general API or origin bypass.
    client.cookies.clear()
    client.cookies.set('atlas_playback', session)
    assert client.get('/_atlas/maintenance/authorize').status_code == 503
    assert client.get('/_atlas/maintenance/closed-origin').status_code == 503


@pytest.mark.parametrize('name', ['member', 'sports', 'custom'])
def test_preexisting_nonadmin_video_is_denied_when_maintenance_starts(media, name):
    client, control, *_ = media
    control.enabled = False
    token, _ = video(media, name)
    assert bootstrap(client, token).status_code == 200
    session = client.cookies.get('atlas_playback')
    assert authorize(client).status_code == 200
    control.enabled = True
    assert bootstrap(client, token).status_code == 503
    assert authorize(client, token=session).status_code == 503


@pytest.mark.parametrize('change', ['role', 'disabled', 'logout', 'refresh', 'restart', 'expiry'])
def test_admin_media_revokes_with_original_login_and_current_profile(media, change):
    client, control, profiles, auth, jwt_service, caps = media
    token, response = video(media)
    assert bootstrap(client, token).status_code == 200
    session = client.cookies.get('atlas_playback')
    if change == 'role':
        profiles.rows['admin']['roles'] = ['member']
    elif change == 'disabled':
        profiles.rows['admin']['status'] = 'disabled'
    elif change == 'logout':
        auth._refresh_sessions.revoke_subject('usr_admin')
    elif change == 'refresh':
        assert client.post('/api/v1/auth/refresh', json={'refresh_token':response.json()['refresh_token']}).status_code == 200
    elif change == 'restart':
        auth._maintenance_sessions = MaintenanceSessions(auth._refresh_sessions.active_session)
    else:
        auth._maintenance_sessions.clock = lambda: 2 ** 40
    assert bootstrap(client, token).status_code == 503
    assert authorize(client, token=session).status_code == 503


@pytest.mark.parametrize('kind', ['unbound', 'subject', 'signature', 'release', 'access', 'cookie'])
def test_wrong_credential_or_binding_cannot_preview(media, kind):
    client, control, profiles, auth, jwt_service, caps = media
    token, response = video(media, subject='usr_member' if kind == 'subject' else None,
                            bound=kind != 'unbound')
    if kind == 'signature':
        claims = jwt.decode(token, options={'verify_signature':False})
        token = jwt.encode(claims, 'wrong' * 12, algorithm='HS256')
    elif kind == 'release':
        token = caps.create_live_release(user_id='usr_admin', session_id='session', target_id='target', lease_id='lease')
    elif kind == 'access':
        token = response.json()['access_token']
    elif kind == 'cookie':
        assert login(client).status_code == 200
        token = 'fabricated'
    assert bootstrap(client, token).status_code == 503


def test_forced_local_marker_and_authority_outage_fail_closed(media):
    client, control, *_ = media
    control.enabled = False
    token, _ = video(media, 'member')
    assert client.post(BOOTSTRAP, headers={'Authorization':'Bearer ' + token,
        'X-Atlas-Maintenance-Required':'1'}).status_code == 503
    control.outage = True
    assert bootstrap(client, token).status_code == 503
    assert client.get('/_atlas/maintenance/closed-origin').status_code == 503


def test_raw_origin_is_closed_for_admin_and_only_known_off_returns_204(media):
    client, control, *_ = media
    response = login(client)
    assert client.get('/_atlas/maintenance/closed-origin', headers=bearer(response)).status_code == 503
    control.enabled = False
    assert client.get('/_atlas/maintenance/closed-origin').status_code == 204
    control.pending = True
    assert client.get('/_atlas/maintenance/closed-origin').status_code == 503


def test_unbound_normal_mode_capability_keeps_legacy_behavior(media):
    client, control, *_ = media
    control.enabled = False
    token, _ = video(media, bound=False)
    assert bootstrap(client, token).status_code == 200
    assert authorize(client).status_code == 200
    control.enabled = True
    assert authorize(client).status_code == 503


def test_opaque_bindings_are_bounded_and_pruned_without_exposing_access_ids():
    now = [10]
    active = [True]
    sessions = MaintenanceSessions(lambda *_:active[0], clock=lambda:now[0])
    sessions.bind_access('access-id', 'subject', 20, 'refresh-id', 50)
    reference = sessions.issue_media('access-id', 'subject')
    assert sessions.issue_media('access-id', 'subject') == reference
    assert len(sessions.media) == 1
    assert 'access-id' not in reference and 'refresh-id' not in reference
    assert sessions.media_subject(reference) == 'subject'
    assert sessions.media_subject('f' * 64) is None
    now[0] = 20
    assert sessions.media_subject(reference) is None
    with pytest.raises(ValueError):
        sessions.issue_media('access-id', 'subject')


@pytest.mark.parametrize('value', ['', 'f' * 63, 'g' * 64, 123])
def test_malformed_binding_is_not_minted(media, value):
    caps = media[-1]
    with pytest.raises(PlaybackCapabilityError):
        caps.create_bootstrap(user_id='usr_admin', playable_target_id='a' * 32,
                              stream_path=STREAM, maintenance_binding=value)


@pytest.mark.parametrize('outage', [False, True])
def test_scoped_release_drains_only_owned_session_during_hold_or_outage(tmp_path, outage):
    _, sessions, pool, first, second, caps, token, calls, client = release_setup(tmp_path)
    class Control:
        def request(self, operation):
            if outage:
                raise RuntimeError('private outage')
            return dict(enabled=True, transition_pending=False, recovery_held=True, state_uncertain=False)
    client.app.dependency_overrides[get_maintenance_control_client] = lambda: Control()
    install_maintenance_middleware(client.app)
    assert client.delete('/api/v1/sports/live/sessions/' + first.session_id).status_code == 503
    assert release(client, second, token).status_code == 401
    assert not calls
    assert release(client, first, token).status_code == 204
    assert calls == [{'session_id':first.session_id, 'user_id':first.user_id}]
    assert sessions.path.exists() and second.session_id in sessions.path.read_text()
    assert client.post('/api/v1/sports/live/sessions/' + first.session_id + '/release-capability').status_code == 503
