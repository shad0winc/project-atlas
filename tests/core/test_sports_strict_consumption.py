"""Strict baseline promotion and explicit rehearsal extension contracts."""
import ast
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


strict = load('strict_test', 'scripts/lib/sports-strict-consumption.py')
native = load('strict_native', 'scripts/lib/sports-native-consumption.py')
component = load('strict_component', 'scripts/diagnostics/sports-native-consumption-drill.py')


def receipt():
    return {'version': 1, 'scope': 'synthetic-dispatcharr-only', 'mode': 'prepare',
        'cold_source_unchanged': True, 'restored_cluster_stopped': True,
        'production_state_access': False, 'live_restore_enabled': False,
        'source_sha256': 'a'*64, 'dump_sha256': 'b'*64}


class StrictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name); self.baseline = self.work/'baseline'; self.baseline.mkdir(mode=0o700)
        self.pub = native.pub
        def write(path, data): path.write_bytes(data); path.chmod(0o600)
        (self.baseline/'dispatcharr-db').mkdir(mode=0o700)
        write(self.baseline/'dispatcharr-db/probe', b'raw-after-dump')
        write(self.baseline/'dispatcharr-jwt', b'synthetic-identity')
        write(self.baseline/'teamarr-db', b'synthetic-teamarr')
        self.prepared = self.baseline/'strict-incoming'; self.prepared.mkdir(mode=0o700)
        write(self.prepared/'probe', b'restored-dump-snapshot')
        self.capture = {'version': 1, 'marker': 'after-dump', 'copied_wal': False, 'ledger_sha256': 'c'*64,
            'surfaces': {name: self.pub.digest(self.baseline/name, name == 'dispatcharr-db') for name in native.NATIVE}}
        self.pub.write_json(self.baseline/'CAPTURE.json', self.capture)
        self.scope = patch.object(native, 'workspace', return_value=self.work)
        self.scope.start(); self.addCleanup(self.scope.stop)

    def test_promote_changes_only_pg_and_retains_raw_capture(self):
        before = (self.baseline/'CAPTURE.json').read_bytes()
        strict.promote(native, self.baseline, self.prepared, receipt())
        self.assertEqual((self.baseline/'COLD_CAPTURE.json').read_bytes(), before)
        self.assertEqual((self.baseline/'COLD_CLUSTER/probe').read_bytes(), b'raw-after-dump')
        self.assertEqual((self.baseline/'dispatcharr-db/probe').read_bytes(), b'restored-dump-snapshot')
        changed = self.pub.read_json(self.baseline/'CAPTURE.json')
        self.assertNotEqual(changed['surfaces']['dispatcharr-db'], self.capture['surfaces']['dispatcharr-db'])
        for name in ('dispatcharr-jwt', 'teamarr-db'):
            self.assertEqual(changed['surfaces'][name], self.capture['surfaces'][name])
        self.assertEqual(changed['strict_preparation_sha256'], native.consumer.document_sha(self.baseline/'STRICT_PREPARED.json'))
        doc = self.pub.read_json(self.baseline/'STRICT_PREPARED.json')
        self.assertEqual(doc['raw_capture_sha256'], native.consumer.document_sha(self.baseline/'COLD_CAPTURE.json'))
        self.assertEqual(doc['native_receipt'], receipt())

    def test_bad_receipts_rejected_before_promotion(self):
        for key, value in [('version', True), ('mode', 'verify'), ('cold_source_unchanged', False),
                ('restored_cluster_stopped', False), ('production_state_access', True),
                ('live_restore_enabled', True), ('dump_sha256', 'bad')]:
            with self.subTest(key=key):
                invalid = receipt(); invalid[key] = value
                with self.assertRaises(ValueError): strict.promote(native, self.baseline, self.prepared, invalid)
        self.assertFalse((self.baseline/'COLD_CLUSTER').exists())

    def test_tampered_raw_capture_is_held(self):
        (self.baseline/'dispatcharr-jwt').write_bytes(b'tampered')
        with self.assertRaises(ValueError): strict.promote(native, self.baseline, self.prepared, receipt())
        self.assertFalse((self.baseline/'COLD_CLUSTER').exists())

    def test_unchanged_cluster_is_not_strict_preparation(self):
        (self.prepared/'probe').write_bytes(b'raw-after-dump')
        with self.assertRaises(ValueError): strict.promote(native, self.baseline, self.prepared, receipt())

    def test_preexisting_promotion_audit_holds_without_overwrite(self):
        (self.baseline/'STRICT_PREPARED.json').write_bytes(b'preserve-me')
        with self.assertRaises(ValueError): strict.promote(native, self.baseline, self.prepared, receipt())
        self.assertEqual((self.baseline/'STRICT_PREPARED.json').read_bytes(), b'preserve-me')
        self.assertFalse((self.baseline/'COLD_CLUSTER').exists())

    def test_strict_probe_accepts_only_reviewed_baseline_markers(self):
        for marker in ('after-dump', 'snapshot'):
            for change, consumed in ((False, False), (True, True), (False, True)):
                text = component.pg_code(change, consumed, marker); ast.parse(text)
                if marker == 'snapshot': self.assertNotIn("=='after-dump'", text)
        with self.assertRaises(RuntimeError): component.pg_code(baseline='foreign-marker')

    def test_extension_requires_checkpoint_callback_and_snapshot_together(self):
        cases = [{'expected_head': 'a'*40}, {'prepare_baseline': lambda *args: None},
            {'expected_head': 'a'*40, 'prepare_baseline': lambda *args: None},
            {'expected_head': 'not-a-hash', 'prepare_baseline': lambda *args: None, 'pg_baseline_marker': 'snapshot'}]
        for kwargs in cases:
            with self.subTest(kwargs=list(kwargs)), self.assertRaises(RuntimeError): component.run(**kwargs)

    def test_failure_during_promotion_never_reports_complete_capture(self):
        original = self.pub.move
        def fail(source, target):
            if source == self.prepared: raise OSError('interrupted')
            original(source, target)
        with patch.object(self.pub, 'move', fail), self.assertRaises(OSError):
            strict.promote(native, self.baseline, self.prepared, receipt())
        self.assertFalse((self.baseline/'STRICT_PREPARED.json').exists())
        self.assertTrue((self.baseline/'COLD_CLUSTER').exists())


if __name__ == '__main__': unittest.main()
