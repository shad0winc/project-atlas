import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "modules/sports/src"))

from source_lifecycle import SourceLifecycleError, SourceLifecycleStore, SportsSource


class CredentialRealmLifecycleTests(unittest.TestCase):
    def source(self, **changes):
        payload = {
            "source_id": "sample-account", "display_name": "Sample account",
            "kind": "licensed_subscription", "enabled": False,
            "priority": 100, "max_connections": 1,
            "backend_reference": "dispatcharr:m3u:5",
        }
        payload.update(changes)
        return SportsSource.from_mapping(payload)

    def test_legacy_source_loads_without_granting_realm(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(json.dumps({"version": 1, "sources": [
                {"source_id": "sample-account", "display_name": "Sample account",
                 "kind": "licensed_subscription", "enabled": True,
                 "priority": 100, "max_connections": 1}
            ]}))
            source, = SourceLifecycleStore(path).load()
            self.assertIsNone(source.credential_realm)

    def test_explicit_realm_roundtrips_in_store(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SourceLifecycleStore(Path(directory) / "sources.json")
            store.write((self.source(credential_realm="license-a"),))
            source, = store.load()
            self.assertEqual(source.credential_realm, "license-a")
            self.assertEqual(source.to_mapping()["credential_realm"], "license-a")

    def test_invalid_realm_rejected(self):
        for realm in ("", "UpperCase", "has space", "bad_id", "a" * 129, 1):
            with self.subTest(realm=realm):
                with self.assertRaises(SourceLifecycleError):
                    self.source(credential_realm=realm)


if __name__ == "__main__":
    unittest.main()
