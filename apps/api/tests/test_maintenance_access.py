"""Real JWT/profile/session API maintenance boundaries with isolated authority doubles."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from atlas.maintenance_control import MaintenanceControlError
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser,TokenType
from atlas_api.auth.service import AuthenticationService
from atlas_api.auth.sessions import RefreshSessionRegistry
from atlas_api.authorization import AuthorizationService
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.dependencies import (get_authentication_service,get_jwt_service,get_user_profile_store,
    get_security_audit_writer,get_maintenance_control_client)
from atlas_api.main import create_app
from atlas_api.security.dependencies import get_authorization_service
from atlas_api.services.maintenance_access import COOKIE,admit_authentication

ORIGIN = 'https://atlas.example.test'
HEADERS = {'Origin':ORIGIN,'X-Atlas-Browser-Session':'1'}
BROWSER = '/api/v1/auth/browser'
STATUS = '/api/v1/admin/maintenance'
GUARD = '/_atlas/maintenance/authorize'


class Profiles:
    def __init__(self):
        self.rows = {name:{'user_id':'usr_' + name,'username':name,'display_name':name,
            'status':'active','roles':[role],'permission_overrides':{'allow':[],'deny':[]}}
            for name,role in (('admin','global_admin'),('legacy','admin'),('member','member'),
                              ('sports','sports_admin'),('custom','custom_all'))}
        self.rows['custom']['permission_overrides']['allow'] = ['*']
    def get_user(self,user_id):
        return self.rows[user_id.removeprefix('usr_')]


class Provider:
    def __init__(self,profiles):
        self.profiles = profiles
    def authenticate(self,username,password):
        row = self.profiles.rows.get(username)
        if row is None or password != 'correct' or row['status'] != 'active':
            return None
        return AuthenticatedUser(row['user_id'],username,username,tuple(row['roles']))


class Control:
    def __init__(self):
        self.enabled = True
        self.recovery = False
        self.pending = False
        self.outage = False
        self.calls = []
    def request(self,operation,*,actor=None):
        if self.outage:
            raise MaintenanceControlError('control_unavailable')
        if operation != 'status':
            self.calls.append((operation,actor))
            if operation == 'disable' and (self.recovery or self.pending):
                raise MaintenanceControlError('recovery_held')
            self.enabled = operation == 'enable'
        return {'enabled':self.enabled,'transition_pending':self.pending,
                'recovery_held':self.recovery,'state_uncertain':False}


class Audit:
    def __init__(self):
        self.fail = False
        self.events = []
    def publish(self,*event):
        if self.fail:
            raise OSError('private audit failure')
        self.events.append(event)


@pytest.fixture
def site(monkeypatch):
    monkeypatch.setenv('ATLAS_JWT_SECRET','s'*48)
    monkeypatch.setenv('ATLAS_BASE_URL',ORIGIN)
    monkeypatch.setenv('ATLAS_MAINTENANCE_CONTROL_SOCKET','/run/atlas-test/control.sock')
    profiles,control,audit = Profiles(),Control(),Audit()
    jwt = JWTService(AtlasAPISettings(jwt_secret='s'*48))
    service = AuthenticationService(Provider(profiles),jwt,admission=lambda user:admit_authentication(user,control))
    app = create_app()
    app.dependency_overrides.update({get_authentication_service:lambda:service,get_jwt_service:lambda:jwt,
        get_user_profile_store:lambda:profiles,get_security_audit_writer:lambda:audit,
        get_maintenance_control_client:lambda:control,get_authorization_service:lambda:AuthorizationService()})
    client = TestClient(app,base_url=ORIGIN)
    yield client,control,profiles,service,jwt,audit
    client.close()


def login(client,name='admin',browser=True):
    return client.post(BROWSER + '/login' if browser else '/api/v1/auth/login',
        headers=HEADERS if browser else {},json={'username':name,'password':'correct'})


def bearer(response):
    return {'Authorization':'Bearer ' + response.json()['access_token']}


@pytest.mark.parametrize('name',['member','sports','custom'])
@pytest.mark.parametrize('browser',[True,False])
def test_ordinary_and_subsystem_signins_do_not_issue_sessions(site,name,browser):
    client,_,_,service,_,_ = site
    response = login(client,name,browser)
    assert response.status_code == 503
    assert service._refresh_sessions.active_count == 0
    assert 'set-cookie' not in response.headers


@pytest.mark.parametrize('name',['admin','legacy'])
def test_admin_browser_cookie_is_separate_secure_and_server_validated(site,name):
    client,*_ = site
    response = login(client,name)
    assert response.status_code == 200
    value = client.cookies.get(COOKIE)
    assert len(value) == 43 and '.' not in value
    cookies = response.headers.get_list('set-cookie')
    bypass = next(item for item in cookies if item.startswith(COOKIE + '='))
    for attribute in ('Path=/','HttpOnly','Secure','SameSite=strict','Max-Age=900'):
        assert attribute in bypass
    assert 'Domain=' not in bypass
    refresh = next(item for item in cookies if item.startswith('__Secure-atlas_refresh='))
    assert 'Path=/api/v1/auth/browser' in refresh
    assert client.get(GUARD).status_code == 204
    assert client.get(STATUS,headers=bearer(response)).status_code == 200


def test_existing_member_access_is_blocked_after_maintenance_is_enabled(site):
    client,control,*_ = site
    control.enabled = False
    response = login(client,'member',False)
    assert response.status_code == 200
    control.enabled = True
    assert client.get('/api/v1/auth/me',headers=bearer(response)).status_code == 503
    assert client.post('/api/v1/auth/refresh',json={'refresh_token':response.json()['refresh_token']}).status_code == 503


@pytest.mark.parametrize('change',['role','disabled','logout','restart','refresh'])
def test_admin_bypass_is_revoked_immediately(site,change):
    client,control,profiles,service,jwt,_ = site
    response = login(client)
    old_cookie = client.cookies.get(COOKIE)
    headers = bearer(response)
    if change == 'role':
        profiles.rows['admin']['roles'] = ['member']
    elif change == 'disabled':
        profiles.rows['admin']['status'] = 'disabled'
    elif change == 'logout':
        assert client.post(BROWSER + '/logout',headers=HEADERS).status_code == 204
    elif change == 'restart':
        service._refresh_sessions = RefreshSessionRegistry()
    else:
        assert client.post(BROWSER + '/refresh',headers=HEADERS).status_code == 200
    client.cookies.clear()
    client.cookies.set(COOKIE,old_cookie)
    assert client.get(GUARD).status_code == 503
    assert client.get(STATUS,headers=headers).status_code == 503


def test_bare_signed_admin_token_without_live_session_does_not_bypass(site):
    client,_,profiles,_,jwt,_ = site
    token = jwt.create_access_token(AuthenticatedUser('usr_admin','admin','admin',('global_admin',)))
    assert client.get(GUARD,headers={'Authorization':'Bearer ' + token}).status_code == 503


@pytest.mark.parametrize('headers',[{'X-Atlas-Maintenance-Admin':'1'},
    {'X-Forwarded-User':'admin'},{'Authorization':'Bearer fabricated'}])
def test_unverified_headers_and_cookies_never_bypass(site,headers):
    client,*_ = site
    client.cookies.set(COOKIE,'x'*43)
    assert client.get(GUARD,headers=headers).status_code == 503


def test_legacy_admin_access_requires_active_refresh_bound_session(site):
    client,_,_,service,jwt,_ = site
    response = login(client,browser=False)
    assert response.status_code == 200
    assert client.get(STATUS,headers=bearer(response)).status_code == 200
    service._refresh_sessions.revoke_subject('usr_admin')
    assert client.get(STATUS,headers=bearer(response)).status_code == 503


@pytest.mark.parametrize('headers',[{}, {'Origin':'https://evil.example.test','X-Atlas-Browser-Session':'1'},
    {'Origin':ORIGIN},{**HEADERS,'Sec-Fetch-Site':'cross-site'}])
def test_controls_require_same_origin_csrf_headers(site,headers):
    client,control,*_ = site
    response = login(client)
    assert client.post(STATUS,headers={**bearer(response),**headers},json={'enabled':True}).status_code == 403
    assert not control.calls


def test_recovery_hold_cannot_be_disabled_and_audit_failure_precedes_mutation(site):
    client,control,_,_,_,audit = site
    response = login(client)
    headers = {**HEADERS,**bearer(response)}
    control.recovery = True
    assert client.post(STATUS,headers=headers,json={'enabled':False}).status_code == 409
    assert control.enabled
    assert control.calls == [('disable','usr_admin')]
    control.calls.clear()
    audit.fail = True
    assert client.post(STATUS,headers=headers,json={'enabled':False}).status_code == 503
    assert not control.calls


def test_authorized_control_changes_maintenance_and_no_cookie_only_api_mutation(site):
    client,control,*_ = site
    response = login(client)
    assert client.post(STATUS,headers=HEADERS,json={'enabled':False}).status_code == 401
    assert not control.calls
    result = client.post(STATUS,headers={**HEADERS,**bearer(response)},json={'enabled':False})
    assert result.status_code == 200 and result.json()['enabled'] is False
    assert control.calls == [('disable','usr_admin')]


@pytest.mark.parametrize('body',[{'enabled':'false'},{'enabled':0},{'enabled':True,'path':'/tmp/x'}])
def test_control_request_schema_is_strict(site,body):
    client,control,*_ = site
    response = login(client)
    assert client.post(STATUS,headers={**HEADERS,**bearer(response)},json=body).status_code == 422
    assert not control.calls


def test_control_service_outage_fails_closed_but_private_health_survives(site):
    client,control,*_ = site
    response = login(client)
    control.outage = True
    assert client.get(GUARD).status_code == 503
    assert client.get(STATUS,headers=bearer(response)).status_code == 503
    assert login(client).status_code == 503
    assert client.get('/api/v1/health').status_code == 200


def test_pending_transition_and_recovery_flag_force_boundary_even_without_enabled_flag(site):
    client,control,*_ = site
    control.enabled = False
    for name in ('pending','recovery'):
        setattr(control,name,True)
        assert client.get(GUARD).status_code == 503
        setattr(control,name,False)


def test_uncertain_control_state_denies_even_existing_admin_bypass(site):
    client,control,*_ = site
    response = login(client)
    original = control.request
    def uncertain(operation,**kwargs):
        state = original(operation,**kwargs)
        state['state_uncertain'] = True
        return state
    control.request = uncertain
    assert client.get(GUARD).status_code == 503
    assert client.get(STATUS,headers=bearer(response)).status_code == 503
    assert login(client).status_code == 503


def test_proxy_can_force_stricter_admission_when_local_marker_is_present(site):
    client,control,*_ = site
    control.enabled = False
    assert client.get(GUARD).status_code == 204
    assert client.get(GUARD,headers={'X-Atlas-Maintenance-Required':'1'}).status_code == 503
    control.enabled = True
    assert client.get(GUARD,headers={'X-Atlas-Maintenance-Required':'0'}).status_code == 503


def test_logout_revokes_even_during_control_outage(site):
    client,control,*_ = site
    response = login(client)
    old_cookie = client.cookies.get(COOKIE)
    control.outage = True
    assert client.post(BROWSER + '/logout',headers=HEADERS).status_code == 204
    control.outage = False
    client.cookies.clear()
    client.cookies.set(COOKIE,old_cookie)
    assert client.get(GUARD).status_code == 503
    assert client.get(STATUS,headers=bearer(response)).status_code == 503
