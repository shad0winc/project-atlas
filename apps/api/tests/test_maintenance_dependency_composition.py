"""Maintenance admission through actual factories, profile storage, JWT and routes.
Only external Jellyfin authentication and host control transport are test doubles.
Authentication/profile/JWT factories are deliberately not overridden.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.custom_roles import CustomRoleDefinition, CustomRoleStore
from atlas.maintenance_control import MaintenanceControlError
from atlas.maintenance_control_server import MaintenanceClient
from atlas_api import dependencies as dependencies
from atlas_api.auth.provider import JellyfinAuthenticationClient
from atlas_api.main import create_app

ORIGIN = 'https://atlas.factory.test'
BROWSER = {'Origin': ORIGIN, 'X-Atlas-Browser-Session': '1'}


class Control:
    enabled = True
    outage = False
    def request(self, operation, *, actor=None):
        assert operation == 'status'
        if self.outage:
            raise MaintenanceControlError('control_unavailable')
        return {'enabled': self.enabled, 'transition_pending': False,
                'recovery_held': False, 'state_uncertain': False}


@pytest.fixture
def composed(tmp_path, monkeypatch):
    dependencies.clear_dependency_caches()
    roles_path = tmp_path / 'custom_roles.json'
    for name, value in {
        'ATLAS_JWT_SECRET': 'factory-test-only-' * 4,
        'ATLAS_BASE_URL': ORIGIN,
        'ATLAS_USERS_DIR': str(tmp_path / 'users'),
        'ATLAS_IDENTITY_DIR': str(tmp_path / 'identity'),
        'ATLAS_CUSTOM_ROLES_PATH': str(roles_path),
        'ATLAS_SECURITY_AUDIT_PATH': str(tmp_path / 'events.jsonl'),
        'ATLAS_MAINTENANCE_CONTROL_SOCKET': '/run/private-factory/control.sock',
        'ATLAS_IDENTITY_WRITER_URL': 'http://unused-identity.fixture.test',
        'ATLAS_IDENTITY_WRITER_TOKEN': 'fixture-only-no-network',
        'ATLAS_SMTP_HOST': 'unused-smtp.fixture.test',
        'ATLAS_SMTP_SENDER': 'atlas@factory.test',
    }.items():
        monkeypatch.setenv(name, value)
    (tmp_path / 'events.jsonl').touch(mode=0o600)
    custom = CustomRoleStore(roles_path)
    custom.initialize()
    custom.create(CustomRoleDefinition('custom_all', 'Fixture broad grants',
                                      'Broad grants must not imply global administration', frozenset({'*'}), True))
    profiles = dependencies.get_user_profile_store()
    ids = {}
    for number, (name, role) in enumerate((('admin', 'global_admin'), ('legacy', 'admin'),
                                         ('member', 'member'), ('sports', 'sports_admin'),
                                         ('custom', 'custom_all')), 1):
        jellyfin_id = f'{number:032x}'
        profiles.create_user(name, roles=[role], jellyfin_user_id=jellyfin_id)
        ids[name] = jellyfin_id
    def authenticate(self, username, password):
        if username in ids and password == 'correct':
            return {'Id': ids[username], 'Name': username}
        return None
    monkeypatch.setattr(JellyfinAuthenticationClient, 'authenticate', authenticate)
    control = Control()
    monkeypatch.setattr(MaintenanceClient, 'request',
                        lambda self, operation, actor=None: control.request(operation, actor=actor))
    app = create_app()
    assert not app.dependency_overrides
    client = TestClient(app, base_url=ORIGIN)
    try:
        yield client, control, profiles
    finally:
        client.close()
        dependencies.clear_dependency_caches()


def login(client, name, browser):
    return client.post('/api/v1/auth/browser/login' if browser else '/api/v1/auth/login',
                       headers=BROWSER if browser else {}, json={'username': name, 'password': 'correct'})


@pytest.mark.parametrize('name', ('member', 'sports', 'custom'))
@pytest.mark.parametrize('browser', (False, True))
def test_factory_rejects_non_global_admin_before_issuing_sessions(composed, name, browser):
    client, _, _ = composed
    response = login(client, name, browser)
    assert response.status_code == 503
    assert 'access_token' not in response.json()
    assert 'set-cookie' not in response.headers
    assert dependencies.get_refresh_session_registry().active_count == 0


@pytest.mark.parametrize('name', ('admin', 'legacy'))
def test_factory_global_admin_has_live_server_validated_browser_session(composed, name):
    client, _, _ = composed
    response = login(client, name, True)
    assert response.status_code == 200
    assert dependencies.get_refresh_session_registry().active_count == 1
    assert client.get('/_atlas/maintenance/authorize').status_code == 204
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert client.get('/api/v1/admin/maintenance', headers=headers).status_code == 200


def test_factory_blocks_existing_member_refresh_without_consuming_session(composed):
    client, control, _ = composed
    control.enabled = False
    issued = login(client, 'member', False)
    assert issued.status_code == 200
    refresh = issued.json()['refresh_token']
    control.enabled = True
    response = client.post('/api/v1/auth/refresh', json={'refresh_token': refresh})
    assert response.status_code == 503
    assert 'access_token' not in response.json()
    assert dependencies.get_refresh_session_registry().active_count == 1
    control.enabled = False
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': refresh}).status_code == 200


@pytest.mark.parametrize('browser', (False, True))
def test_factory_authority_outage_does_not_issue_admin_sessions(composed, browser):
    client, control, _ = composed
    control.outage = True
    assert login(client, 'admin', browser).status_code == 503
    assert dependencies.get_refresh_session_registry().active_count == 0


def test_password_recovery_factory_constructs_and_handles_unknown_email(composed, tmp_path):
    # Actual constructor and orchestration; an unknown address never calls SMTP
    # or the identity writer. The previous misplaced argument raises TypeError.
    service = dependencies.get_password_recovery_service()
    service.request_reset('unknown@factory.test')
    assert 'security.identity.password_recovery_requested' in (tmp_path / 'events.jsonl').read_text()
