"""Real SIGKILL/redo over Atlas metadata journals; PG bytes are unit fixtures."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


interruption = load('combined_interruption_test', 'scripts/lib/sports-consumption-interruption.py')
native = load('interruption_native_test', 'scripts/lib/sports-native-consumption.py')
fixture = load('interruption_fixture', 'scripts/diagnostics/sports-recovery-consumption-drill.py')
component = load('interruption_component', 'scripts/diagnostics/sports-native-consumption-drill.py')


@unittest.skipUnless(hasattr(os, 'fork'), 'Linux fork process-death rehearsal')
class InterruptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp')
        self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name); fixture.fixture(self.root)
        self.output = contextlib.redirect_stdout(io.StringIO()); self.output.__enter__(); self.addCleanup(self.output.__exit__, None, None, None)
        interruption.metadata.initialize(native, self.root); native.consumer.arm(self.root)
        interruption.metadata.mutate(native, self.root)
        with native.consumer.writer(self.root) as current:
            with (current/'dispatcharr-db/state.bin').open('ab') as stream: stream.write(b'-unit-native-change')
        ledger = {'stage': 'detached'}; native.pub.write_json(self.root/'DOCKER_LIFECYCLE.json', ledger)
        directory = self.root/'NATIVE_IMPORT'; directory.mkdir(mode=0o700); (directory/'previous').mkdir(mode=0o700)
        native.pub.write_json(directory/'STATUS.json', {'state': 'imported'})
        native.pub.write_json(directory/'RECEIPT.json', {
            'ledger_sha256': native.consumer.document_sha(self.root/'DOCKER_LIFECYCLE.json'),
            'surfaces': {name: native.pub.digest(self.root/'current'/name, name == 'dispatcharr-db') for name in native.NATIVE}})
        for item in (patch.object(native.fence, 'load', return_value=ledger), patch.object(native.fence, 'assert_detached')):
            item.start(); self.addCleanup(item.stop)
        with native.consumer.file_lock(self.root/'docker-lifecycle.lock'): pass

    def test_all_fifteen_sigkill_boundaries_recover_twice(self):
        interruption.recover(native, self.root)
        audit = native.pub.read_json(self.root/'INTERRUPTION.json')
        self.assertEqual(audit['boundaries'], list(interruption.boundaries(native)))
        self.assertEqual(len(audit['boundaries']), 15)
        interruption.metadata.check(native, self.root/'current', 'old')
        interruption.metadata.check(native, self.root/'consumption/quarantine', 'consumed')
        self.assertEqual(native.consumer.status(self.root/'consumption'), 'reverted')

    def test_normal_exit_is_not_counted_as_checkpoint_death(self):
        before = native.pub.digest(self.root, True)
        with patch.object(interruption, 'child_recover', lambda *args: None):
            with self.assertRaises(ValueError): interruption.recover(native, self.root)
        self.assertEqual(native.pub.digest(self.root, True), before)
        self.assertFalse((self.root/'INTERRUPTION.json').exists())

    def test_partial_import_is_held_before_clone_recovery(self):
        native.pub.write_json(self.root/'NATIVE_IMPORT/STATUS.json', {'state': 'importing'})
        with self.assertRaises(ValueError): interruption.recover(native, self.root)
        self.assertEqual(native.consumer.status(self.root/'consumption'), 'open')
        self.assertFalse((self.root/'INTERRUPTION.json').exists())

    def test_active_cooperative_writer_blocks_source_copy(self):
        with native.consumer.writer(self.root):
            with self.assertRaises(BlockingIOError): interruption.recover(native, self.root)
        self.assertEqual(native.consumer.status(self.root/'consumption'), 'open')

    def test_existing_audit_is_preserved_and_not_replayed(self):
        native.pub.write_json(self.root/'INTERRUPTION.json', {'preserve': True})
        with self.assertRaises(ValueError): interruption.recover(native, self.root)
        self.assertEqual(native.pub.read_json(self.root/'INTERRUPTION.json'), {'preserve': True})

    def test_callback_requires_complete_metadata_mode(self):
        with self.assertRaises(RuntimeError): component.run(recover_journal=lambda *args: None)
        with self.assertRaises(RuntimeError): component.run(recover_journal='not-callable')
        names = interruption.boundaries(native)
        self.assertEqual(len(names), len(set(names)))
        for surface in native.pub.SURFACES:
            self.assertIn('quarantine:'+surface, names); self.assertIn('restore:'+surface, names)


if __name__ == '__main__': unittest.main()
