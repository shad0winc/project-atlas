import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from atlas.identity import IdentityPaths
from atlas.invitations import InvitationStore
from atlas.registration import RegistrationError, RegistrationResult
from atlas.registration_web import RegistrationPortal


class FakeRegistrationService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def register(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


class RegistrationWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        paths = IdentityPaths(root / "identity")
        self.invitations = InvitationStore(paths, clock=lambda: datetime(2026, 7, 19, tzinfo=timezone.utc))
        self.issue = self.invitations.create(email="friend@example.com")

    def tearDown(self):
        self.temp.cleanup()

    def request(self, app, method, path, query="", form=None, content_type="application/x-www-form-urlencoded"):
        payload = urlencode(form or {}).encode()
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": io.BytesIO(payload),
        }
        captured = {}
        def start(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)
        body = b"".join(app(environ, start)).decode()
        return captured, body

    def test_get_valid_invitation_renders_form_without_exposing_hash(self):
        app = RegistrationPortal(self.invitations, FakeRegistrationService())
        response, body = self.request(app, "GET", "/register", query="token=" + self.issue.token)
        self.assertEqual("200 OK", response["status"])
        self.assertIn("friend@example.com", body)
        self.assertIn(self.issue.token, body)
        self.assertNotIn(self.issue.invitation["token_hash"], body)
        self.assertEqual("no-store", response["headers"]["Cache-Control"])

    def test_invalid_invitation_returns_friendly_gone_page(self):
        app = RegistrationPortal(self.invitations, FakeRegistrationService())
        response, body = self.request(app, "GET", "/register", query="token=bad")
        self.assertEqual("410 Gone", response["status"])
        self.assertIn("invalid invitation token", body)

    def test_password_mismatch_does_not_call_registration_service(self):
        service = FakeRegistrationService()
        app = RegistrationPortal(self.invitations, service)
        response, body = self.request(app, "POST", "/register", form={"token": self.issue.token, "username": "friend", "password": "one", "confirm_password": "two"})
        self.assertEqual("400 Bad Request", response["status"])
        self.assertIn("Passwords do not match", body)
        self.assertEqual([], service.calls)

    def test_success_delegates_to_registration_engine_and_renders_welcome(self):
        result = RegistrationResult(
            invitation={"invite_id": self.issue.invitation["invite_id"]},
            profile={"username": "friend", "display_name": "Friendly User"},
            external_user_id="jf_1",
        )
        service = FakeRegistrationService(result=result)
        app = RegistrationPortal(self.invitations, service, continue_url="/home")
        response, body = self.request(app, "POST", "/register", form={"token": self.issue.token, "username": "friend", "display_name": "Friendly User", "password": "secret", "confirm_password": "secret"})
        self.assertEqual("201 Created", response["status"])
        self.assertIn("Welcome, Friendly User", body)
        self.assertIn('href="/home"', body)
        self.assertEqual("secret", service.calls[0]["password"])

    def test_registration_error_is_rendered_without_password_echo(self):
        service = FakeRegistrationService(error=RegistrationError("username already exists"))
        app = RegistrationPortal(self.invitations, service)
        response, body = self.request(app, "POST", "/register", form={"token": self.issue.token, "username": "friend", "password": "super-secret", "confirm_password": "super-secret"})
        self.assertEqual("400 Bad Request", response["status"])
        self.assertIn("username already exists", body)
        self.assertNotIn("super-secret", body)

    def test_health_and_not_found(self):
        app = RegistrationPortal(self.invitations, FakeRegistrationService())
        response, body = self.request(app, "GET", "/health")
        self.assertEqual("200 OK", response["status"])
        self.assertEqual("healthy\n", body)
        response, _ = self.request(app, "GET", "/missing")
        self.assertEqual("404 Not Found", response["status"])


if __name__ == "__main__":
    unittest.main()
