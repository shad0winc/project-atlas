"""Exercise the staged private API's dedicated read-only credential check."""

import ast
import hmac
import os
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.parse

path = Path(__file__).resolve().parents[2] / "modules/sports/src/private_api.py"
tree = ast.parse(path.read_text())
handler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Handler")
method = next(node for node in handler.body if isinstance(node, ast.FunctionDef)
              and node.name == "_live_policy_authorized")
isolated = ast.Module(body=[method], type_ignores=[])
ast.fix_missing_locations(isolated)
namespace = {"os": os, "hmac": hmac}
exec(compile(isolated, str(path), "exec"), namespace)
authorized = namespace["_live_policy_authorized"]
route = next(node for node in handler.body if isinstance(node, ast.FunctionDef)
             and node.name == "do_GET")
route_namespace = {
    "urllib": urllib,
    "HTTPStatus": HTTPStatus,
    "claims_for_channel": lambda **kwargs: (SimpleNamespace(to_mapping=lambda: {"source_id": "fixture"}),),
    "default_dispatcharr_channel_binding_registry": lambda: SimpleNamespace(list_bindings=lambda: ()),
    "default_live_source_registry": lambda: SimpleNamespace(list_sources=lambda: ()),
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[])),
             str(path), "exec"), route_namespace)
do_get = route_namespace["do_GET"]


class AuthTests(unittest.TestCase):
    def test_dedicated_token_cannot_equal_writer_token(self):
        token = "p" * 40
        headers = {"Authorization": "Bearer " + token}
        with patch.dict(os.environ, {"ATLAS_SPORTS_LIVE_POLICY_TOKEN": token,
                                  "ATLAS_SPORTS_WRITER_TOKEN": "w" * 40}):
            self.assertTrue(authorized(SimpleNamespace(headers=headers)))
            self.assertFalse(authorized(SimpleNamespace(headers={"Authorization": "Bearer " + "w" * 40})))
        with patch.dict(os.environ, {"ATLAS_SPORTS_LIVE_POLICY_TOKEN": token,
                                  "ATLAS_SPORTS_WRITER_TOKEN": token}):
            self.assertFalse(authorized(SimpleNamespace(headers=headers)))
        with patch.dict(os.environ, {"ATLAS_SPORTS_LIVE_POLICY_TOKEN": "short",
                                  "ATLAS_SPORTS_WRITER_TOKEN": "w" * 40}):
            self.assertFalse(authorized(SimpleNamespace(headers={"Authorization": "Bearer short"})))

    def test_route_uses_dedicated_auth_before_writer_and_returns_claims(self):
        class Fixture:
            path = "/internal/v1/live-policy/9af2de8b-3e2d-49fc-aa8c-abbd67634290"
            responses = []
            _live_policy_authorized = lambda self: True
            _require_auth = lambda self: self.fail("writer auth used")
            _source_store = lambda self: SimpleNamespace(load=lambda: ())

            def _json(self, status, payload):
                self.responses.append((status, payload))

        fixture = Fixture()
        do_get(fixture)
        self.assertEqual(fixture.responses, [(HTTPStatus.OK, {"claims": [{"source_id": "fixture"}]})])

        fixture.responses = []
        fixture._live_policy_authorized = lambda: False
        do_get(fixture)
        self.assertEqual(fixture.responses[0][0], HTTPStatus.UNAUTHORIZED)

        fixture.responses = []
        fixture._live_policy_authorized = lambda: True
        fixture.path += "?unexpected=1"
        do_get(fixture)
        self.assertEqual(fixture.responses[0][0], HTTPStatus.BAD_REQUEST)


if __name__ == "__main__":
    unittest.main()
