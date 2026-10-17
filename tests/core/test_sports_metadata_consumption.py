"""Actual metadata schema, identity, cache/budget and policy undo contracts."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


metadata = load('metadata_consumption_test', 'scripts/lib/sports-metadata-consumption.py')
native = load('metadata_native_test', 'scripts/lib/sports-native-consumption.py')
fixture = load('metadata_journal_fixture', 'scripts/diagnostics/sports-recovery-consumption-drill.py')
component = load('metadata_component_test', 'scripts/diagnostics/sports-native-consumption-drill.py')


class MetadataConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp')
        self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        fixture.fixture(self.root)
        with contextlib.redirect_stdout(io.StringIO()): metadata.initialize(native, self.root)

    def arm_and_mutate(self):
        native.consumer.arm(self.root)
        with contextlib.redirect_stdout(io.StringIO()): metadata.mutate(native, self.root)

    def test_real_schema_and_synthetic_aliases_validate(self):
        metadata.check(native, self.root/'transaction/old', 'old')
        metadata.check(native, self.root/'current', 'new')
        original = native.pub.read_json(self.root/'transaction/PLAN.json')
        for row in original['surfaces']:
            if row['surface'] in {'sports-metadata', 'sports-metadata-policy'}:
                self.assertNotEqual(row['old_sha256'], row['new_sha256'])

    def test_committed_metadata_quarantined_and_old_records_restored(self):
        self.arm_and_mutate(); native.consumer.recover(self.root); native.consumer.recover(self.root)
        metadata.check(native, self.root/'current', 'old')
        metadata.check(native, self.root/'consumption/quarantine', 'consumed')
        with patch.object(metadata, 'reader_probe') as probe, contextlib.redirect_stdout(io.StringIO()):
            metadata.verify(native, self.root)
            self.assertEqual(probe.call_count, 2)

    def test_initialization_refuses_exposed_journal(self):
        native.consumer.arm(self.root)
        with self.assertRaises(ValueError): metadata.initialize(native, self.root)

    def test_verified_old_alias_is_not_reassigned_during_mutation(self):
        self.arm_and_mutate()
        store = metadata.MetadataStore(self.root/'current/sports-metadata/metadata.sqlite')
        from providers.metadata_identity import MetadataIdentityConflict
        with self.assertRaises(MetadataIdentityConflict): metadata.alias(store, '999999', '401999991')

    def test_budget_and_hold_tampering_are_detected(self):
        self.arm_and_mutate()
        path = self.root/'current/sports-metadata/metadata.sqlite'
        with sqlite3.connect(path) as connection: connection.execute('UPDATE metadata_attempts SET stamp=999')
        with self.assertRaises(ValueError): metadata.check(native, self.root/'current', 'consumed')

    def test_enabled_or_extra_policy_fields_rejected(self):
        path = self.root/'current/sports-metadata-policy/refresh.json'
        for raw in (b'{"version":1,"enabled":true}', b'{"version":1,"enabled":false,"routes":[]}'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError): metadata.check(native, self.root/'current', 'new')

    def test_metadata_reader_does_not_change_journal_bytes(self):
        before = native.pub.digest(self.root/'current/sports-metadata', True)
        metadata.check(native, self.root/'current', 'new')
        self.assertEqual(native.pub.digest(self.root/'current/sports-metadata', True), before)

    def test_lock_and_sidecar_strays_are_held(self):
        path = self.root/'current/sports-metadata/metadata.sqlite-wal'
        path.write_bytes(b'stray'); path.chmod(0o600)
        with self.assertRaises(ValueError): metadata.check(native, self.root/'current', 'new')

    def test_metadata_extension_requires_complete_callable_hooks(self):
        for hooks in ({}, {'initialize': None}, {'initialize': lambda *a: None, 'mutate': lambda *a: None, 'verify': lambda *a: None}):
            with self.subTest(keys=list(hooks)), self.assertRaises(RuntimeError): component.run(metadata_hooks=hooks)

    @unittest.skipUnless(os.geteuid() == 0 and os.getegid() == 0, 'CT identity conversion')
    def test_uid1000_reader_on_mapped_metadata_and_policy_copies(self):
        # Probe mapping support before the actual reader test. Never turn a
        # reader validation failure into a skip once ownership is supported.
        probe = self.root/'uid-probe'; probe.write_bytes(b''); probe.chmod(0o600)
        try: os.chown(probe, 1000, 1000)
        except OSError as error:
            if error.errno in (1, 22): self.skipTest('UID mapping unavailable; CT100 executes reader acceptance')
            raise
        metadata.reader_probe(native, self.root/'current', 'new')


if __name__ == '__main__': unittest.main()
