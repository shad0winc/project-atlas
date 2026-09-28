"""Exercise a bounded Xtream observation with a fake transport."""

import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.parse

import test_atlas_verified_policy_adapter as adapter_fixture

sys.modules["apps.m3u.atlas_verified_policy_adapter"] = adapter_fixture.adapter_module
path = Path(__file__).resolve().parents[1] / "apps/m3u/provider_capacity_observation.py"
spec = importlib.util.spec_from_file_location("staged_capacity_observation", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Response:
    status = 200

    def __init__(self, body):
        self.body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.body.close()

    def read(self, limit):
        return self.body.read(limit)


class Opener:
    def __init__(self, body=None, error=None):
        self.body = body
        self.error = error
        self.calls = 0

    def open(self, request, timeout):
        self.calls += 1
        self.timeout = timeout
        self.request = request
        if self.error:
            raise self.error
        return Response(self.body)


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.account = type("Account", (), {
            "id": 31, "get_user_agent_string": lambda self: "AtlasFixture/1.0",
        })()
        self.credentials = ("https://example.test/xc", "effective-user", "effective-password")

    def test_effective_login_bound_limit_and_observation_time(self):
        body = json.dumps({"user_info": {"status": "Active", "max_connections": "3",
                                         "active_cons": "1"}}).encode()
        opener = Opener(body)
        result = module.XtreamCapacityReader(opener=opener, clock=lambda: 1001)(
            self.account, self.credentials)
        self.assertEqual((result.account_id, result.status, result.max_connections,
                          result.active_connections, result.observed_at_unix),
                         (31, "active", 3, 1, 1001))
        self.assertEqual(opener.timeout, 3.0)
        self.assertEqual(opener.request.get_header("User-agent"), "AtlasFixture/1.0")
        parsed = urllib.parse.urlsplit(opener.request.full_url)
        self.assertEqual(parsed.path, "/xc/player_api.php")
        self.assertEqual(urllib.parse.parse_qs(parsed.query)["username"], ["effective-user"])
        self.assertEqual(urllib.parse.parse_qs(parsed.query)["password"], ["effective-password"])

    def test_invalid_and_unbounded_evidence_fails_closed(self):
        for user_info in (
            {"status": "Expired", "max_connections": "1", "active_cons": "0"},
            {"status": "active", "max_connections": "0", "active_cons": "0"},
            {"status": "active", "max_connections": True, "active_cons": "0"},
            {"status": "active", "max_connections": "unknown", "active_cons": "0"},
            {"status": "active", "max_connections": "1", "active_cons": "2"},
            {"status": "active", "max_connections": "1"},
        ):
            opener = Opener(json.dumps({"user_info": user_info}).encode())
            with self.subTest(user_info=user_info), self.assertRaises(
                module.VerifiedLivePolicyUnavailable
            ):
                module.XtreamCapacityReader(opener=opener)(self.account, self.credentials)

    def test_redirect_and_transport_error_hide_credential_url(self):
        opener = Opener(error=urllib.error.URLError("https://example.test/?password=secret"))
        with self.assertRaises(module.VerifiedLivePolicyUnavailable) as failure:
            module.XtreamCapacityReader(opener=opener)(self.account, self.credentials)
        self.assertNotIn("secret", str(failure.exception))
        self.assertNotIn("effective-password", str(failure.exception))
        redirect = module._NoRedirect()
        with self.assertRaises(module.VerifiedLivePolicyUnavailable):
            redirect.redirect_request(None, None, 302, "redirect", {}, "https://elsewhere.test/")

    def test_response_is_size_bounded(self):
        opener = Opener(b"x" * 65537)
        with self.assertRaises(module.VerifiedLivePolicyUnavailable):
            module.XtreamCapacityReader(opener=opener)(self.account, self.credentials)

    def test_ambiguous_provider_limit_is_rejected(self):
        opener = Opener(b'{"user_info":{"status":"active","max_connections":"1","max_connections":"9","active_cons":"0"}}')
        with self.assertRaises(module.VerifiedLivePolicyUnavailable):
            module.XtreamCapacityReader(opener=opener)(self.account, self.credentials)


if __name__ == "__main__":
    unittest.main()
