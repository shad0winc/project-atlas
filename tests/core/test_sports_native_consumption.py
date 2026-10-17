"""Native cold-copy normalization, SQLite sidecars and guarded import recovery."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


native = load('native_test', 'scripts/lib/sports-native-consumption.py')
fixture = load('native_fixture', 'scripts/diagnostics/sports-recovery-consumption-drill.py')


class ShapeTests(unittest.TestCase):
    def test_generated_native_probe_programs_parse(self):
        import ast
        drill = load('native_probe_programs', 'scripts/diagnostics/sports-native-consumption-drill.py')
        for change, consumed in ((False, False), (True, True), (False, True)):
            ast.parse(drill.pg_code(change, consumed))
            ast.parse(drill.team_code(change, consumed))

    def test_links_hardlinks_unsafe_modes_and_bounds_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); file = root/'file'; file.write_bytes(b'abc'); file.chmod(0o600)
            self.assertEqual(native.shape(file)['.'][:2], ['file', 3])
            (root/'link').symlink_to(file)
            with self.assertRaises(ValueError): native.shape(root/'link')
            os.link(file, root/'hard')
            with self.assertRaises(ValueError): native.shape(file)
            (root/'hard').unlink(); file.chmod(0o666)
            with self.assertRaises(ValueError): native.shape(file)
            file.chmod(0o600)
            with patch.object(native, 'MAX_BYTES', 2), self.assertRaises(ValueError): native.shape(file)

    def test_copy_preserves_bytes_and_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'source'; source.mkdir(mode=0o700)
            (source/'a').write_bytes(b'abc'); (source/'a').chmod(0o600)
            owner = (os.geteuid(), os.getegid())
            native.copy_tree(source, root/'copy', True, owner, owner)
            self.assertEqual(native.shape(source, True), native.shape(root/'copy', True))
            with self.assertRaises(ValueError): native.copy_tree(source, root/'copy', True, owner, owner)

    def test_volume_path_refuses_user_namespace_or_wrong_mountpoint(self):
        import json
        for invalid in ('userns', 'mountpoint', 'reference'):
            with self.subTest(invalid=invalid):
                def command(*args):
                    if args[0] == 'info':
                        return json.dumps({'DockerRootDir': '/var/lib/docker',
                            'SecurityOptions': ['name=userns'] if invalid == 'userns' else []})
                    return json.dumps([{'Mountpoint': '/production' if invalid == 'mountpoint'
                        else '/var/lib/docker/volumes/owned/_data'}])
                with patch.object(native.fence, 'volume', return_value='owned'), patch.object(native.fence, 'command', command), \
                     patch.object(native, 'parents_safe'), patch.object(Path, 'is_dir', return_value=True), \
                     patch.object(native.fence, 'references', return_value={'foreign'} if invalid == 'reference' else set()):
                    with self.assertRaises(ValueError): native.volume_path('a'*32, 'teamarr')


@unittest.skipUnless(os.geteuid() == 0 and os.getegid() == 0, 'CT root ownership integration')
class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp')
        self.root = Path(self.temp.name); fixture.fixture(self.root)
        self.work = Path('/tmp')/('project-atlas-native-consumption.'+uuid.uuid4().hex); self.work.mkdir(mode=0o700)
        self.addCleanup(self.temp.cleanup)
        import shutil
        self.addCleanup(shutil.rmtree, self.work)
        self.ledger = {'stage': 'detached'}
        self.patches = [patch.object(native.fence, 'load', return_value=self.ledger),
            patch.object(native.fence, 'assert_detached')]
        for item in self.patches: item.start(); self.addCleanup(item.stop)
        native.pub.write_json(self.root/'DOCKER_LIFECYCLE.json', self.ledger)

    def baseline(self):
        baseline = self.work/'baseline'; baseline.mkdir(mode=0o700)
        for name in native.NATIVE:
            native.copy_tree(self.root/'transaction/old'/name, baseline/name, name == 'dispatcharr-db', (0, 0))
        native.install_baseline(self.root, baseline); native.consumer.arm(self.root)
        return baseline

    def captured(self):
        captured = self.work/'captured'; captured.mkdir(mode=0o700)
        fixture.mutate(self.root)
        for name in native.NATIVE:
            native.copy_tree(self.root/'current'/name, captured/name, name == 'dispatcharr-db', (0, 0))
        receipt = {'version': 1, 'marker': 'native-consumer-committed', 'copied_wal': True,
            'ledger_sha256': native.consumer.document_sha(self.root/'DOCKER_LIFECYCLE.json'),
            'surfaces': {name: native.pub.digest(captured/name, name == 'dispatcharr-db') for name in native.NATIVE}}
        native.pub.write_json(captured/'CAPTURE.json', receipt)
        return captured

    def test_normalize_native_pg_ownership_and_restore_it(self):
        source = self.work/'pg'; source.mkdir(mode=0o700); (source/'PG_VERSION').write_bytes(b'17\n')
        (source/'PG_VERSION').chmod(0o600)
        try:
            for path in (source, source/'PG_VERSION'): os.chown(path, 1000, 1000)
        except OSError as error:
            if error.errno in (1, 22): self.skipTest('runtime cannot assign UID 1000; CT100 runs this case')
            raise
        normalized = self.work/'normalized'; native.copy_tree(source, normalized, True, (1000, 1000))
        self.assertEqual(normalized.stat().st_uid, 0)
        target = self.work/'restored'; native.copy_tree(normalized, target, True, (0, 0), (1000, 1000))
        self.assertEqual((target/'PG_VERSION').stat().st_uid, 1000)
        self.assertEqual(native.shape(source, True), native.shape(target, True))

    def test_wal_only_commit_is_in_detached_snapshot_and_source_unchanged(self):
        source = self.work/'sqlite'; source.mkdir(mode=0o700)
        db = source/'teamarr.db'; conn = sqlite3.connect(db)
        try:
            conn.execute('PRAGMA journal_mode=WAL'); conn.execute('PRAGMA wal_autocheckpoint=0')
            conn.execute('CREATE TABLE atlas_teamarr_probe(id INTEGER PRIMARY KEY, marker TEXT)')
            conn.execute("INSERT INTO atlas_teamarr_probe VALUES(1,'after-dump')"); conn.commit()
            for path in source.iterdir(): path.chmod(0o600)
            before = native.cold_set(source)
            self.assertTrue(native.sqlite_snapshot(source, self.work/'snapshot.db', 'after-dump'))
            self.assertEqual(native.cold_set(source), before)
            # The source handle remains open only to retain WAL for this unit
            # fixture. Real capture requires the verified detached Docker fence.
        finally: conn.close()

    def test_hot_or_orphan_sidecars_are_refused(self):
        source = self.work/'sqlite'; source.mkdir(mode=0o700)
        (source/'teamarr.db').write_bytes(b'synthetic'); (source/'teamarr.db').chmod(0o600)
        for suffix in ('-journal', '-shm'):
            path = source/('teamarr.db'+suffix); path.write_bytes(b'bad'); path.chmod(0o600)
            with self.assertRaises(ValueError): native.cold_set(source)
            path.unlink()

    def test_import_recover_twice_quarantines_actual_imported_bytes(self):
        self.baseline(); captured = self.captured()
        native.import_writes(self.root, captured)
        native.recover(self.root); native.recover(self.root)
        fixture.verify(self.root, native.pub.read_json(self.root/'transaction/PLAN.json')['surfaces'])
        receipt = native.pub.read_json(captured/'CAPTURE.json')
        for name in native.NATIVE:
            self.assertEqual(native.pub.digest(self.root/'consumption/quarantine'/name, name == 'dispatcharr-db'), receipt['surfaces'][name])

    def test_partial_import_holds_native_recovery(self):
        self.baseline(); captured = self.captured()
        original = native.copy_tree
        def fail(source, target, *args, **kwargs):
            if target == self.root/'current/dispatcharr-jwt': raise OSError('copy interrupted')
            return original(source, target, *args, **kwargs)
        with patch.object(native, 'copy_tree', fail), self.assertRaises(OSError): native.import_writes(self.root, captured)
        with patch.object(native.consumer, 'recover') as recover:
            with self.assertRaises(ValueError): native.recover(self.root)
            recover.assert_not_called()

    def test_tampered_import_receipt_or_sealed_content_holds(self):
        self.baseline(); captured = self.captured(); native.import_writes(self.root, captured)
        (self.root/'current/dispatcharr-jwt').write_bytes(b'not-captured-native-bytes')
        with patch.object(native.consumer, 'recover') as recover:
            with self.assertRaises(ValueError): native.recover(self.root)
            recover.assert_not_called()
        self.assertEqual(native.consumer.status(self.root/'consumption'), 'sealed')

    def test_missing_fence_blocks_import_and_recovery(self):
        self.baseline(); captured = self.captured()
        with patch.object(native.fence, 'assert_detached', side_effect=ValueError('not detached')):
            with self.assertRaises(ValueError): native.import_writes(self.root, captured)
            self.assertFalse((self.root/'NATIVE_IMPORT').exists())
            with self.assertRaises(ValueError): native.recover(self.root)


if __name__ == '__main__': unittest.main()
