"""Isolated authenticated Atlas source-claim client checks."""

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

path = Path(__file__).resolve().parents[1] / "apps/m3u/atlas_policy_claims.py"
spec = importlib.util.spec_from_file_location("staged_atlas_policy_claims", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Response:
    status = 200
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, limit):
        return self.payload[:limit]


class Opener:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        return Response(self.payload)


class ClaimClientTests(unittest.TestCase):
    def setUp(self):
        self.uuid = str(uuid4())
        self.rows = [dict(channel_uuid=self.uuid, source_id="source-5",
                          account_id=5, configured_max_connections=1,
                          credential_realm="evestv2",
                          provider="thesportsdb", provider_event_id="42"),
                     dict(channel_uuid=self.uuid, source_id="source-6",
                          account_id=6, configured_max_connections=1,
                          credential_realm="evestv3",
                          provider="thesportsdb", provider_event_id="42")]
        self.opener = Opener(json.dumps({"claims": self.rows}).encode())
        self.client = module.AtlasPolicyClaimClient(
            origin="http://atlas-sports-controller:9000",
            token="internal-test-token-012345678901234567890", opener=self.opener,
        )

    def test_exact_account_and_secret_safe_wire_contract(self):
        claim = self.client.for_account(self.uuid, 6)
        self.assertEqual((claim.account_id, claim.configured_max_connections), (6, 1))
        self.assertEqual(claim.credential_realm, "evestv3")
        request, timeout = self.opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 3.0)
        self.assertEqual(request.full_url,
                         "http://atlas-sports-controller:9000/internal/v1/live-policy/" + self.uuid)
        self.assertNotIn("internal-test-token", repr(claim))

    def test_fail_closed_on_mismatch_duplicate_and_oversize(self):
        bad = (
            {"claims": [dict(self.rows[0], channel_uuid=str(uuid4()))]},
            {"claims": [self.rows[0], dict(self.rows[1], account_id=5)]},
            {"claims": []},
            {"claims": [dict(self.rows[0], configured_max_connections=0)]},
            {"claims": [dict(self.rows[0], credential_realm="EVESTV2")]},
            {"claims": [dict(self.rows[0], credential_realm="bad/realm")]},
            {"claims": [{key: value for key, value in self.rows[0].items()
                         if key != "credential_realm"}]},
            {"claims": [dict(self.rows[0], provider_event_id="different"), self.rows[1]]},
        )
        for body in bad:
            with self.subTest(body=list(body)):
                self.opener.payload = json.dumps(body).encode()
                with self.assertRaises(module.AtlasPolicyUnavailable):
                    self.client.fetch(self.uuid)
        self.opener.payload = b"x" * 65537
        with self.assertRaises(module.AtlasPolicyUnavailable):
            self.client.fetch(self.uuid)
        self.opener.payload = b'{"claims":[],"claims":[]}'
        with self.assertRaises(module.AtlasPolicyUnavailable):
            self.client.fetch(self.uuid)

    def test_unrelated_account_and_invalid_origin_rejected(self):
        with self.assertRaises(module.AtlasPolicyUnavailable):
            self.client.for_account(self.uuid, 7)
        with self.assertRaises(module.AtlasPolicyUnavailable):
            module.AtlasPolicyClaimClient(origin="http://user:pass@host/",
                token="internal-test-token-012345678901234567890")
        with self.assertRaises(module.AtlasPolicyUnavailable):
            module._NoRedirect().redirect_request(
                None, None, 302, "redirect", {}, "http://other.invalid/"
            )


if __name__ == "__main__":
    unittest.main()
