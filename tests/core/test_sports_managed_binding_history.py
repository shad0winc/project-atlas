"""A removed Atlas binding cannot silently become a legacy channel."""

import ast
import importlib.util
import json
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch
from urllib import parse
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[2]
registry_source = ROOT / "modules/sports/src/dispatcharr_channel_bindings.py"
spec = importlib.util.spec_from_file_location("history_registry", registry_source)
registry_module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = registry_module
spec.loader.exec_module(registry_module)

api_source = ROOT / "modules/sports/src/private_api.py"
tree = ast.parse(api_source.read_text(), filename=str(api_source))
handler = next(item for item in tree.body if isinstance(item, ast.ClassDef)
               and item.name == "Handler")
route = next(item for item in handler.body if isinstance(item, ast.FunctionDef)
             and item.name == "do_GET")
namespace = {"urllib": __import__("urllib"), "HTTPStatus": HTTPStatus,
             "UUID": UUID}
exec(compile(ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[])),
             str(api_source), "exec"), namespace)


class Fixture:
    def __init__(self, identity):
        self.path = "/internal/v1/live-policy-classification/" + identity
        self.status = None
        self.payload = None
    def _live_policy_authorized(self):
        return True
    def _json(self, status, payload):
        self.status, self.payload = status, payload
    def _backend_unavailable(self):
        self.status = HTTPStatus.SERVICE_UNAVAILABLE


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "bindings.json"
        self.registry = registry_module.DispatcharrChannelBindingRegistry(self.path)
        self.first_uuid = str(uuid4())

    def classify(self, identity):
        fixture = Fixture(identity)
        with patch.dict(namespace, {
            "default_dispatcharr_channel_binding_registry": lambda: self.registry,
        }):
            namespace["do_GET"](fixture)
        return fixture

    def test_legacy_migration_preserves_retired_identity(self):
        self.path.write_text(json.dumps({"version": 1, "bindings": {
            "sports-live-1": {"dispatcharr_channel_id": 17,
                              "dispatcharr_channel_uuid": self.first_uuid}}}))
        self.assertEqual(self.classify(self.first_uuid).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)
        with self.assertRaises(registry_module.DispatcharrChannelBindingError):
            self.registry.delete("sports-live-1")
        self.registry.migrate_managed_history()
        managed = self.classify(self.first_uuid)
        self.assertEqual((managed.status, managed.payload["managed"]),
                         (HTTPStatus.OK, True))
        self.assertTrue(self.registry.delete("sports-live-1"))
        self.assertEqual(self.classify(self.first_uuid).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)
        fresh = self.classify(str(uuid4()))
        self.assertEqual((fresh.status, fresh.payload["managed"]),
                         (HTTPStatus.OK, False))
        self.assertIn(self.first_uuid, json.loads(self.path.read_text())["managed_uuids"])

    def test_new_binding_records_history_in_same_document(self):
        self.registry.ensure()
        self.registry.set("sports-live-2", 18, self.first_uuid)
        original_load = self.registry._load
        reads = []
        def counted_load():
            reads.append(1)
            return original_load()
        self.registry._load = counted_load
        self.assertEqual(self.classify(self.first_uuid).payload["managed"], True)
        self.assertEqual(len(reads), 1)
        self.registry._load = original_load
        replacement_uuid = str(uuid4())
        self.registry.set("sports-live-2", 19, replacement_uuid)
        self.assertEqual(self.classify(self.first_uuid).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertEqual(self.classify(replacement_uuid).payload["managed"], True)
        self.registry.delete("sports-live-2")
        self.assertEqual(self.classify(self.first_uuid).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertEqual(self.classify(replacement_uuid).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)

    def test_corrupt_or_missing_history_refuses_classification(self):
        self.registry.ensure()
        self.registry.set("sports-live-2", 18, self.first_uuid)
        document = json.loads(self.path.read_text())
        document["managed_uuids"] = []
        self.path.write_text(json.dumps(document))
        self.assertEqual(self.classify(self.first_uuid).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)
        self.path.unlink()
        self.assertEqual(self.classify(str(uuid4())).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)

    def test_noncanonical_legacy_identity_aborts_migration(self):
        self.path.write_text(json.dumps({"version": 1, "bindings": {
            "sports-live-1": {"dispatcharr_channel_id": 17,
                              "dispatcharr_channel_uuid": self.first_uuid.upper()}}}))
        with self.assertRaises(registry_module.DispatcharrChannelBindingError):
            self.registry.migrate_managed_history()
        self.assertEqual(json.loads(self.path.read_text())["version"], 1)
        self.assertEqual(self.classify(self.first_uuid).status,
                         HTTPStatus.SERVICE_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
