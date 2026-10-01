"""Browser-session HTTP tests using real JWT rotation and revocation."""
import pytest
from fastapi.testclient import TestClient

from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.auth.service import AuthenticationService
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.dependencies import (
    get_authentication_service, get_jwt_service,
    get_user_profile_store, get_security_audit_writer,
)
from atlas_api.main import create_app

ORIGIN = "https://atlas.example.test"
HEADERS = {"Origin": ORIGIN, "X-Atlas-Browser-Session": "1"}
COOKIE = "__Secure-atlas_refresh"
BASE = "/api/v1/auth/browser"


class Provider:
    def authenticate(self, username, password):
        if password != "correct":
            return None
        return AuthenticatedUser("usr_test", username, username, ("member",))


class Profiles:
    active = True
    def get_user(self, user_id):
        return {
            "user_id": user_id, "username": "member", "display_name": "Member",
            "status": "active" if self.active else "disabled", "roles": ["member"],
            "permission_overrides": {"allow": [], "deny": []},
        }


@pytest.fixture
def browser(monkeypatch):
    monkeypatch.setenv("ATLAS_JWT_SECRET", "s" * 48)
    monkeypatch.setenv("ATLAS_BASE_URL", ORIGIN)
    jwt = JWTService(AtlasAPISettings(jwt_secret="s" * 48))
    service = AuthenticationService(Provider(), jwt)
    profiles = Profiles()
    app = create_app()
    app.dependency_overrides[get_authentication_service] = lambda: service
    app.dependency_overrides[get_jwt_service] = lambda: jwt
    app.dependency_overrides[get_user_profile_store] = lambda: profiles
    app.dependency_overrides[get_security_audit_writer] = lambda: None
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, service, profiles


def login(client):
    return client.post(BASE + "/login", headers=HEADERS,
                       json={"username": "member", "password": "correct"})


def test_login_returns_only_access_token_and_private_cookie(browser):
    client, _, _ = browser
    response = login(client)
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    cookie = response.headers["set-cookie"]
    for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Path=" + BASE, "Max-Age="):
        assert attribute in cookie
    assert "Domain=" not in cookie
    assert response.headers["cache-control"] == "no-store"


def test_rotation_rejects_old_cookie(browser):
    client, _, _ = browser
    login(client)
    old = client.cookies.get(COOKIE)
    response = client.post(BASE + "/refresh", headers=HEADERS)
    assert response.status_code == 200
    assert client.cookies.get(COOKIE) != old
    client.cookies.clear()
    client.cookies.set(COOKIE, old)
    replay = client.post(BASE + "/refresh", headers=HEADERS)
    assert replay.status_code == 401
    assert "Max-Age=0" in replay.headers["set-cookie"]


def test_logout_revokes_session_and_clears_cookie(browser):
    client, _, _ = browser
    login(client)
    old = client.cookies.get(COOKIE)
    response = client.post(BASE + "/logout", headers=HEADERS)
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    client.cookies.clear()
    client.cookies.set(COOKIE, old)
    assert client.post(BASE + "/refresh", headers=HEADERS).status_code == 401


@pytest.mark.parametrize("action", ["login", "refresh", "logout"])
@pytest.mark.parametrize("headers", [
    {}, {"Origin": "https://evil.example.test", "X-Atlas-Browser-Session": "1"},
    {"Origin": ORIGIN}, {**HEADERS, "Sec-Fetch-Site": "cross-site"},
])
def test_csrf_rejection_does_not_change_cookie(browser, action, headers):
    client, _, _ = browser
    login(client)
    old = client.cookies.get(COOKIE)
    response = client.post(BASE + "/" + action, headers=headers,
                           json={"username": "member", "password": "correct"} if action == "login" else None)
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert client.cookies.get(COOKIE) == old
    assert client.post(BASE + "/refresh", headers=HEADERS).status_code == 200


def test_disabled_user_cannot_restore(browser):
    client, _, profiles = browser
    login(client)
    profiles.active = False
    assert client.post(BASE + "/refresh", headers=HEADERS).status_code == 401


def test_api_restart_requires_login(browser):
    client, service, _ = browser
    login(client)
    service._refresh_sessions = type(service._refresh_sessions)()
    assert client.post(BASE + "/refresh", headers=HEADERS).status_code == 401


def test_missing_cookie_and_repeated_logout(browser):
    client, _, _ = browser
    assert client.post(BASE + "/refresh", headers=HEADERS).status_code == 401
    assert client.post(BASE + "/logout", headers=HEADERS).status_code == 204
    assert client.post(BASE + "/logout", headers=HEADERS).status_code == 204


def test_invalid_login_does_not_issue_cookie(browser):
    client, _, _ = browser
    response = client.post(BASE + "/login", headers=HEADERS,
                           json={"username": "member", "password": "wrong"})
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
