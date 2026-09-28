"""The Sports writer classifies bound channel UUIDs without a legacy fallback."""

import ast
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4
import urllib


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "modules/sports/src/private_api.py"
tree = ast.parse(SOURCE.read_text())
handler = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == "Handler")
route = next(node for node in handler.body
             if isinstance(node, ast.FunctionDef) and node.name == "do_GET")
namespace = {
    "urllib": urllib, "HTTPStatus": HTTPStatus, "UUID": UUID,
    "default_dispatcharr_channel_binding_registry": lambda: SimpleNamespace(
        path=SimpleNamespace(is_file=lambda: True), list_bindings=lambda: ()),
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[])),
             str(SOURCE), "exec"), namespace)


class Fixture:
    def __init__(self, channel_uuid, authorized=True):
        self.path = "/internal/v1/live-policy-classification/" + channel_uuid
        self.authorized = authorized
        self.responses = []
        self.backend_failed = False

    def _live_policy_authorized(self):
        return self.authorized

    def _json(self, status, payload):
        self.responses.append((status, payload))

    def _backend_unavailable(self):
        self.backend_failed = True


def test_classification_requires_policy_auth_and_matches_one_binding():
    identity = str(uuid4())
    fixture = Fixture(identity, authorized=False)
    with patch.dict(namespace, {"default_dispatcharr_channel_binding_registry":
            lambda: (_ for _ in ()).throw(AssertionError("unauthorized read"))}):
        namespace["do_GET"](fixture)
    assert fixture.responses[0][0] == HTTPStatus.UNAUTHORIZED

    binding = SimpleNamespace(dispatcharr_channel_uuid=identity)
    fixture = Fixture(identity)
    with patch.dict(namespace, {"default_dispatcharr_channel_binding_registry":
            lambda: SimpleNamespace(path=SimpleNamespace(is_file=lambda: True),
                list_bindings=lambda: (binding,))}):
        namespace["do_GET"](fixture)
    assert fixture.responses == [(HTTPStatus.OK,
        {"channel_uuid": identity, "managed": True})]

    fixture = Fixture(identity)
    namespace["do_GET"](fixture)
    assert fixture.responses == [(HTTPStatus.OK,
        {"channel_uuid": identity, "managed": False})]


def test_classification_blocks_missing_corrupt_ambiguous_binding_state():
    identity = str(uuid4())
    binding = SimpleNamespace(dispatcharr_channel_uuid=identity)
    variants = (
        SimpleNamespace(path=SimpleNamespace(is_file=lambda: False),
                        list_bindings=lambda: ()),
        SimpleNamespace(path=SimpleNamespace(is_file=lambda: True),
                        list_bindings=lambda: (binding, binding)),
        SimpleNamespace(path=SimpleNamespace(is_file=lambda: True),
                        list_bindings=lambda: (_ for _ in ()).throw(ValueError())),
    )
    for registry in variants:
        fixture = Fixture(identity)
        with patch.dict(namespace, {"default_dispatcharr_channel_binding_registry":
                lambda: registry}):
            namespace["do_GET"](fixture)
        assert fixture.backend_failed
        assert not fixture.responses

    for invalid in (identity.upper(), identity + "/other", "bad"):
        fixture = Fixture(invalid)
        namespace["do_GET"](fixture)
        assert fixture.responses[0][0] == HTTPStatus.BAD_REQUEST
