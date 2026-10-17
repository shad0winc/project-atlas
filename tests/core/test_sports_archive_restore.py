"""Archive extraction and baseline provenance; native PG preparation requires CT100."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


restore = load('restore_archive_test', 'scripts/lib/sports-archive-restore.py')
archive_tests = load('restore_archive_fixture', 'tests/core/test_sports_backup_archive.py')
strict_tests = load('restore_strict_fixture', 'tests/core/test_sports_strict_consumption.py')


class ExtractionTests(unittest.TestCase):
    setUp = archive_tests.ArchiveTests.setUp

    def test_extracts_exact_three_native_members_and_binds_archive_sha(self):
        archive = archive_tests.support.publish(archive_tests.native, self.env)
        destination = self.root/'archive-extracted'
        with patch.object(archive_tests.native, 'workspace', return_value=self.root):
            receipt = restore.extract(archive_tests.native, archive, self.env, destination)
        self.assertEqual(set(path.name for path in destination.iterdir()), set(restore.MEMBERS)|{'EXTRACTED.json'})
        self.assertEqual(receipt['archive_sha256'], archive_tests.support.sha(archive))
        for name, member in restore.MEMBERS.items():
            self.assertEqual(restore.sha(destination/name), restore.sha(Path(self.env['NATIVE_PAYLOAD'])/member))

    def test_existing_extraction_is_preserved(self):
        archive = archive_tests.support.publish(archive_tests.native, self.env)
        destination = self.root/'archive-extracted'; destination.mkdir(mode=0o700)
        (destination/'keep').write_text('preserve')
        with patch.object(archive_tests.native, 'workspace', return_value=self.root):
            with self.assertRaises(ValueError): restore.extract(archive_tests.native, archive, self.env, destination)
        self.assertEqual((destination/'keep').read_text(), 'preserve')

    def test_corrupt_archive_is_rejected_before_destination_creation(self):
        archive = archive_tests.support.publish(archive_tests.native, self.env)
        archive.write_bytes(b'not-an-archive')
        destination = self.root/'archive-extracted'
        with patch.object(archive_tests.native, 'workspace', return_value=self.root):
            with self.assertRaises(ValueError): restore.extract(archive_tests.native, archive, self.env, destination)
        self.assertFalse(destination.exists())

    def test_member_size_limit_holds_without_writing_member(self):
        archive = archive_tests.support.publish(archive_tests.native, self.env)
        destination = self.root/'archive-extracted'
        with patch.object(archive_tests.native, 'workspace', return_value=self.root), patch.object(restore, 'MAX_MEMBER', 2):
            with self.assertRaises(ValueError): restore.extract(archive_tests.native, archive, self.env, destination)
        self.assertEqual(list(destination.iterdir()), [])


class PromotionTests(unittest.TestCase):
    def setUp(self):
        strict_tests.StrictTests.setUp(self)
        strict_tests.strict.promote(strict_tests.native, self.baseline, self.prepared, strict_tests.receipt())
        self.candidate = self.work/'archive-candidate'; self.candidate.mkdir(mode=0o700)
        (self.candidate/'dispatcharr-db').mkdir(mode=0o700)
        (self.candidate/'dispatcharr-db/probe').write_bytes(b'unit-cluster-prepared-from-extracted-dump')
        (self.candidate/'dispatcharr-db/probe').chmod(0o600)
        for name in ('dispatcharr-jwt', 'teamarr-db'):
            (self.candidate/name).write_bytes((self.baseline/name).read_bytes()); (self.candidate/name).chmod(0o600)
        self.proof = {'version': 1, 'scope': 'synthetic-archive-prepared-native-baseline',
            'archive_sha256': 'd'*64, 'dump_sha256': 'b'*64, 'helper_receipt': strict_tests.receipt(),
            'surfaces': {name: self.pub.digest(self.candidate/name, name=='dispatcharr-db') for name in strict_tests.native.NATIVE},
            'production_state_access': False, 'live_restore_enabled': False}
        self.pub.write_json(self.candidate/'PROVENANCE.json', self.proof)

    def test_promotes_all_three_archive_units_and_preserves_previous_capture(self):
        before = (self.baseline/'CAPTURE.json').read_bytes()
        old = {name: self.pub.digest(self.baseline/name, name=='dispatcharr-db') for name in strict_tests.native.NATIVE}
        restore.promote(strict_tests.native, self.baseline, self.candidate)
        self.assertEqual((self.baseline/'PRE_ARCHIVE_CAPTURE.json').read_bytes(), before)
        for name in strict_tests.native.NATIVE:
            self.assertEqual(self.pub.digest(self.baseline/'PRE_ARCHIVE'/name, name=='dispatcharr-db'), old[name])
            self.assertEqual(self.pub.digest(self.baseline/name, name=='dispatcharr-db'), self.proof['surfaces'][name])
        capture = self.pub.read_json(self.baseline/'CAPTURE.json')
        self.assertEqual(capture['archive_restore_sha256'], strict_tests.native.consumer.document_sha(self.baseline/'ARCHIVE_RESTORED.json'))

    def test_invalid_provenance_or_surface_hash_refused_before_mutation(self):
        import copy
        for kind in ('production', 'dump-binding', 'surface'):
            with self.subTest(kind=kind):
                proof = copy.deepcopy(self.proof)
                if kind == 'production': proof['production_state_access'] = True
                elif kind == 'dump-binding': proof['dump_sha256'] = 'f'*64
                else: proof['surfaces']['dispatcharr-db'] = '0'*64
                self.pub.write_json(self.candidate/'PROVENANCE.json', proof)
                before = self.pub.digest(self.baseline, True)
                with self.assertRaises(ValueError): restore.promote(strict_tests.native, self.baseline, self.candidate)
                self.assertEqual(self.pub.digest(self.baseline, True), before)

    def test_existing_archive_audit_is_not_overwritten(self):
        self.pub.write_json(self.baseline/'ARCHIVE_RESTORED.json', {'keep': True})
        before = self.pub.digest(self.baseline, True)
        with self.assertRaises(ValueError): restore.promote(strict_tests.native, self.baseline, self.candidate)
        self.assertEqual(self.pub.digest(self.baseline, True), before)


if __name__ == '__main__': unittest.main()
