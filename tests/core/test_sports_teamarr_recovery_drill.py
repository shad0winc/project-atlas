"""Real SQLite/WAL fixture checks; Docker lifecycle boundaries remain mocked."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


helper = load('teamarr_fixture', ROOT / 'scripts/lib/sports-teamarr-recovery-drill.py')
driver = load('teamarr_driver', ROOT / 'scripts/diagnostics/sports-teamarr-recovery-drill.py')


class TeamarrFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed()

    def seed(self, *, wal=False):
        path = self.root / helper.DATABASE
        if path.exists(): path.unlink()
        snapshot = self.root / helper.SNAPSHOT
        if snapshot.exists(): snapshot.unlink()
        connection = sqlite3.connect(path)
        if wal:
            connection.execute('PRAGMA journal_mode=WAL'); connection.execute('PRAGMA wal_autocheckpoint=0')
        connection.execute('CREATE TABLE atlas_teamarr_probe(id INTEGER PRIMARY KEY,marker TEXT NOT NULL)')
        connection.execute("INSERT INTO atlas_teamarr_probe VALUES(1,'snapshot')"); connection.commit()
        backup = sqlite3.connect(snapshot); connection.backup(backup); backup.close()
        connection.execute("UPDATE atlas_teamarr_probe SET marker='after-dump'"); connection.commit()
        if wal:
            self.addCleanup(connection.close)
        else: connection.close()

    def hashes(self):
        return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode)
                for p in self.root.iterdir() if p.is_file()}

    def test_stopped_copy_validation_preserves_original_files(self):
        before = self.hashes()
        receipt = helper.capture(self.root, 'after-dump')
        self.assertEqual(self.hashes(), before)
        self.assertTrue(receipt['cold_set_valid'])
        self.assertTrue(receipt['cold_set_unchanged'])

    def test_committed_wal_rows_are_copied_instead_of_silently_ignored(self):
        self.seed(wal=True)
        before = self.hashes()
        self.assertIn(helper.DATABASE + '-wal', before)
        self.assertTrue(helper.capture(self.root, 'after-dump')['copied_wal'])
        self.assertEqual(self.hashes(), before)

    def test_restored_snapshot_is_private_and_old_database_is_preserved(self):
        before = helper.inventory(self.root)
        snapshot_hash = helper.file_hash(self.root / helper.SNAPSHOT)
        receipt = helper.restore_fixture(self.root)
        self.assertTrue(receipt['restored_snapshot'])
        self.assertEqual(helper.inventory(self.root / 'atlas-drill-rollback'), before)
        self.assertEqual(helper.file_hash(self.root / helper.SNAPSHOT), snapshot_hash)
        self.assertEqual((self.root / helper.DATABASE).stat().st_mode & 0o777, 0o600)
        helper.validate_database(self.root / helper.DATABASE, 'snapshot', immutable=True)
        self.assertTrue(helper.capture(self.root, 'snapshot')['cold_set_valid'])

    def test_hot_rollback_journal_is_rejected_without_mutation(self):
        (self.root / (helper.DATABASE + '-journal')).write_bytes(b'synthetic-hot-journal')
        before = self.hashes()
        with self.assertRaises(helper.DrillError): helper.capture(self.root, 'after-dump')
        self.assertEqual(self.hashes(), before)

    def test_corrupt_database_wrong_marker_and_corrupt_snapshot_are_rejected(self):
        for name in (helper.DATABASE, helper.SNAPSHOT):
            path = self.root / name; raw = path.read_bytes()
            try:
                path.write_bytes(b'not sqlite')
                with self.subTest(name=name), self.assertRaises((helper.DrillError, sqlite3.DatabaseError)):
                    helper.capture(self.root, 'after-dump')
            finally: path.write_bytes(raw)
        with self.assertRaises(helper.DrillError): helper.capture(self.root, 'wrong-marker')

    def test_links_hardlinks_and_unsafe_permissions_are_rejected(self):
        path = self.root / helper.DATABASE; raw = path.read_bytes(); path.unlink()
        path.symlink_to(self.root / helper.SNAPSHOT)
        with self.assertRaises(helper.DrillError): helper.capture(self.root, 'after-dump')
        path.unlink(); path.write_bytes(raw)
        os.link(path, self.root / 'hardlink')
        with self.assertRaises(helper.DrillError): helper.capture(self.root, 'after-dump')
        (self.root / 'hardlink').unlink(); path.chmod(0o666)
        with self.assertRaises(helper.DrillError): helper.capture(self.root, 'after-dump')

    def test_existing_rollback_or_incoming_refuses_retry_without_overwrite(self):
        for name in ('atlas-drill-rollback', '.atlas-drill-incoming.db'):
            path = self.root / name; path.write_bytes(b'retain-me')
            try:
                with self.subTest(name=name), self.assertRaises(helper.DrillError): helper.restore_fixture(self.root)
                self.assertEqual(path.read_bytes(), b'retain-me')
            finally: path.unlink()

    def test_size_bound_and_changed_source_are_rejected(self):
        with patch.object(helper, 'LIMIT', 1):
            with self.assertRaises(helper.DrillError): helper.capture(self.root, 'after-dump')
        real_inventory = helper.inventory; count = [0]
        def changing(root):
            value = real_inventory(root); count[0] += 1
            if count[0] > 1: value[helper.DATABASE] = ('f' * 64, 0o600, 0, 0)
            return value
        with patch.object(helper, 'inventory', side_effect=changing):
            with self.assertRaises(helper.DrillError): helper.capture(self.root, 'after-dump')

    def test_helper_scope_and_error_output_are_closed(self):
        for uid, flag in ((1000, '1'), (0, '0')):
            with patch.object(helper.os, 'geteuid', return_value=uid), patch.dict(os.environ, {'ATLAS_TEAMARR_DRILL': flag}):
                with self.assertRaises(helper.DrillError): helper.run('capture')
        output = io.StringIO()
        with patch.object(helper, 'run', side_effect=RuntimeError('synthetic-sensitive-detail')), contextlib.redirect_stderr(output):
            self.assertEqual(helper.main('capture'), 1)
        self.assertEqual(output.getvalue(), 'TEAMARR_FIXTURE_HELPER=FAIL\n')


class TeamarrDriverTests(unittest.TestCase):
    def test_app_safety_flags_and_helpers_mount_only_owned_volume(self):
        base = Mock(); base.container_options.return_value = ['--network=none', '--restart=no']
        args = driver.app_arguments(base, 'app', 'owned', 'id')
        for value in ('SCHEDULER=off', 'DRY_RUN=true', 'SKIP_CACHE_REFRESH=1', 'PORT=9195', '--cap-drop=ALL', '--user=0:0'):
            self.assertIn(value, args)
        self.assertEqual(args[-1], driver.IMAGE)
        for mode in ('capture', 'capture-restored', 'restore-fixture'):
            args = driver.helper_arguments(base, 'helper', 'owned', 'id', 'bootstrap', mode)
            mount = args[args.index('--mount') + 1]
            self.assertEqual('readonly,' in mount, mode != 'restore-fixture')
            self.assertTrue(mount.startswith('type=volume,source=owned,destination=/source,'))
            self.assertIn('--read-only', args)
            self.assertFalse(any('type=bind' in value or '/mnt/' in value for value in args))
        with self.assertRaises(RuntimeError): driver.helper_arguments(base, 'h', 'v', 'i', 'b', 'other')

    def test_killed_running_or_oom_container_cannot_pass_stop(self):
        good = {'Status': 'exited', 'Running': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}
        base = Mock()
        for change in ({'Running': True}, {'Pid': 123}, {'ExitCode': 137}, {'OOMKilled': True}, {'Status': 'running'}):
            base.owned_container.return_value = {'State': {**good, **change}}
            with self.subTest(change=change), self.assertRaises(RuntimeError): driver.stop(base, 'app', 'id', 'v')
        base.owned_container.return_value = {'State': good}
        driver.stop(base, 'app', 'id', 'v')

    def test_helper_attestation_rejects_wrong_owned_mount_or_network(self):
        good = {'Image': driver.IMAGE, 'Config': {'Labels': {driver.LABEL: 'id'}, 'User': '0:0'},
            'HostConfig': {'ReadonlyRootfs': True, 'NetworkMode': 'none', 'Privileged': False, 'PortBindings': {}},
            'Mounts': [{'Type': 'volume', 'Name': 'v', 'Destination': '/source', 'RW': False}]}
        base = Mock()
        for field in ('volume', 'type', 'rw', 'network', 'label'):
            item = json.loads(json.dumps(good))
            if field == 'volume': item['Mounts'][0]['Name'] = 'production'
            if field == 'type': item['Mounts'][0]['Type'] = 'bind'
            if field == 'rw': item['Mounts'][0]['RW'] = True
            if field == 'network': item['HostConfig']['NetworkMode'] = 'host'
            if field == 'label': item['Config']['Labels'][driver.LABEL] = 'other'
            base.inspect.return_value = item
            with self.subTest(field=field), self.assertRaises(RuntimeError): driver.inspect_helper(base, 'h', 'id', 'v', 'capture')

    def test_health_and_marker_queries_are_fixed_and_local(self):
        self.assertIn("'127.0.0.1',9195", driver.READY)
        self.assertIn("'GET','/health'", driver.READY)
        self.assertIn("'scheduler_enabled':False,'dry_run':True", driver.READY)
        for marker in ('snapshot', 'after-dump'): compile(driver.marker_code(marker), '<marker>', 'exec')
        with self.assertRaises(RuntimeError): driver.marker_code("';DROP TABLE x")

    def test_pinned_helper_and_utility_sources_match(self):
        text = (ROOT / 'scripts/diagnostics/sports-teamarr-recovery-drill.py').read_text()
        for path in (ROOT / 'scripts/lib/sports-teamarr-recovery-drill.py', ROOT / 'scripts/diagnostics/sports-cold-copy-drill.py'):
            self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), text)


if __name__ == '__main__': unittest.main()
