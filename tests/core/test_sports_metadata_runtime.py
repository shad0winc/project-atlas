"""Exercise first provision, existing-state preservation and disabled packaging."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import shutil
import sys
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('metadata_runtime', ROOT / 'scripts/lib/sports-metadata-runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class MetadataRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.uid, self.gid = os.geteuid(), os.getegid()
        self.state = self.path / 'private/sports-metadata'

    def provision(self):
        runtime.provision(ROOT, self.path, self.uid, self.gid)

    def test_initial_schema_private_and_no_policy(self):
        self.provision()
        self.assertEqual({p.name for p in self.state.iterdir()}, {'metadata.sqlite', 'metadata.sqlite.lock'})
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        for name in ('metadata.sqlite', 'metadata.sqlite.lock'):
            self.assertEqual(stat.S_IMODE((self.state / name).stat().st_mode), 0o600)
            self.assertEqual((self.state / name).stat().st_uid, self.uid)
        with sqlite3.connect(self.state / 'metadata.sqlite') as db:
            self.assertEqual(db.execute('SELECT version FROM metadata_schema').fetchall(), [(1,)])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metadata_attempts').fetchone(), (0,))
        self.assertFalse((self.state / 'refresh.json').exists())

    def test_second_provision_preserves_alias_and_budget(self):
        self.provision()
        with sqlite3.connect(self.state / 'metadata.sqlite') as db:
            db.execute('INSERT INTO metadata_attempts VALUES (123)')
            db.execute('INSERT INTO metadata_aliases VALUES (?,?,?,?,?,?,?)',
                       ('espn','football/nfl','1','espn','football/nfl','1','a'*64))
        before = (self.state / 'metadata.sqlite').read_bytes()
        self.provision()
        self.assertEqual((self.state / 'metadata.sqlite').read_bytes(), before)

    def test_refuses_missing_runtime_without_creating_it(self):
        missing = self.path / 'missing'
        with self.assertRaises(ValueError):
            runtime.provision(ROOT, missing, self.uid, self.gid)
        self.assertFalse(missing.exists())

    def test_refuses_symlinked_private_directory(self):
        (self.path / 'private').symlink_to(self.path, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.provision()
        self.assertFalse((self.path / 'sports-metadata').exists())

    def test_refuses_public_existing_directory_without_chmod(self):
        self.state.mkdir(parents=True, mode=0o755)
        self.state.chmod(0o755)
        with self.assertRaises(ValueError):
            self.provision()
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o755)

    def test_refuses_unknown_file_without_removing_it(self):
        self.provision()
        extra = self.state / 'unreviewed.json'
        extra.write_text('untouched')
        with self.assertRaises(ValueError):
            self.provision()
        self.assertEqual(extra.read_text(), 'untouched')

    def test_refuses_partial_state_without_repair(self):
        self.provision()
        (self.state / 'metadata.sqlite.lock').unlink()
        before = (self.state / 'metadata.sqlite').read_bytes()
        with self.assertRaises(ValueError):
            self.provision()
        self.assertFalse((self.state / 'metadata.sqlite.lock').exists())
        self.assertEqual((self.state / 'metadata.sqlite').read_bytes(), before)

    def test_refuses_linked_database(self):
        self.provision()
        os.link(self.state / 'metadata.sqlite', self.path / 'other')
        with self.assertRaises(ValueError):
            self.provision()

    def test_bad_schema_is_rejected_without_mutation(self):
        self.provision()
        with sqlite3.connect(self.state / 'metadata.sqlite') as db:
            db.execute('CREATE TABLE unexpected (value)')
        before = (self.state / 'metadata.sqlite').read_bytes()
        with self.assertRaises(ValueError):
            self.provision()
        self.assertEqual((self.state / 'metadata.sqlite').read_bytes(), before)

    @unittest.skipUnless(os.geteuid() == 0, 'writer identity transition requires root')
    def test_nonroot_writer_opens_provisioned_state_at_accessible_mount(self):
        probe = self.path / 'identity-probe'
        probe.touch()
        try:
            os.chown(probe, 23456, 23456)
        except OSError:
            self.skipTest('host user namespace cannot map the test writer identity')
        runtime.provision(ROOT, self.path, 23456, 23456)
        self.assertEqual(self.state.stat().st_uid, 23456)
        for path in self.state.iterdir():
            self.assertEqual((path.stat().st_uid, path.stat().st_gid), (23456,23456))
        # An accessible isolated path models the container's direct bind mount.
        # No shared parent or production permissions are relaxed.
        with tempfile.TemporaryDirectory(prefix='atlas-metadata-mount-') as name:
            outer = Path(name)
            outer.chmod(0o755)
            mounted = outer / 'state'
            shutil.copytree(self.state, mounted)
            for path in (mounted, *mounted.iterdir()):
                os.chown(path, 23456, 23456)
            code = """from pathlib import Path
import os, sys
from providers.metadata_store import MetadataStore
assert os.geteuid() == 23456 and os.getegid() == 23456
store = MetadataStore(Path(sys.argv[1]) / 'metadata.sqlite')
with store.locked(), store.connection() as connection:
    connection.execute('INSERT INTO metadata_attempts VALUES (456)')
"""
            result = subprocess.run(
                [sys.executable, '-B', '-c', code, str(mounted)],
                user=23456, group=23456, extra_groups=[],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            with sqlite3.connect(mounted / 'metadata.sqlite') as db:
                self.assertEqual(db.execute('SELECT stamp FROM metadata_attempts').fetchall(), [(456.0,)])

    def test_initialization_failure_does_not_publish_partial_state(self):
        with patch('providers.metadata_store.MetadataStore', side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError):
                self.provision()
        self.assertFalse(self.state.exists())
        self.assertEqual(list((self.path / 'private').iterdir()), [])

    def test_compose_identity_uses_build_args_without_printing_document(self):
        result = subprocess.CompletedProcess([], 0, json.dumps({'services': {'sports-writer': {'build': {'args': {'PUID':'1234','PGID':'5678'}}, 'environment': {'SECRET':'never print'}}}}).encode(), b'')
        with patch.object(runtime.subprocess, 'run', return_value=result) as call:
            self.assertEqual(runtime.writer_identity(ROOT), (1234,5678))
        self.assertIn('--format', call.call_args.args[0])

    def test_compose_failure_and_root_writer_are_rejected(self):
        for result in (subprocess.CompletedProcess([], 1, b'', b'secret'),
                       subprocess.CompletedProcess([], 0, b'{"services":{"sports-writer":{"build":{"args":{"PUID":"0","PGID":"1"}}}}}', b'')):
            with self.subTest(code=result.returncode), patch.object(runtime.subprocess, 'run', return_value=result):
                with self.assertRaises(ValueError):
                    runtime.writer_identity(ROOT)

    def test_default_policy_and_mount_are_disabled_and_narrow(self):
        from providers.metadata_refresh import load_refresh_policy
        self.assertIsNone(load_refresh_policy(ROOT / 'modules/sports/config/metadata-refresh.disabled.json'))
        dockerfile = (ROOT / 'modules/sports/Dockerfile.private-api').read_text()
        self.assertIn('COPY modules/sports/config/metadata-refresh.disabled.json /srv/sports/metadata-refresh.disabled.json', dockerfile)
        compose = (ROOT / 'stack/ingress.yml').read_text().split('  sports-writer:\n',1)[1].split('\n  identity-writer:',1)[0]
        self.assertIn('stop_grace_period: 35s', compose)
        self.assertIn('create_host_path: false', compose)
        self.assertIn('target: /srv/sports-metadata', compose)
        self.assertIn('ATLAS_SPORTS_METADATA_REFRESH_FILE: /srv/sports/metadata-refresh.disabled.json', compose)
        self.assertNotIn('target: /mnt/storage/configs/atlas/private', compose)

    def test_update_provisions_after_doctor_before_backup(self):
        body = (ROOT / 'scripts/commands/update.sh').read_text().split('atlas_update_execute_locked()',1)[1]
        self.assertLess(body.index('pre-update doctor failed'), body.index('atlas_sports_metadata_runtime_provision'))
        self.assertLess(body.index('atlas_sports_metadata_runtime_provision'), body.index('atlas_command_backup --notes'))
        self.assertLess(body.index('atlas_sports_metadata_runtime_provision'), body.index('atlas_command_maintenance enable'))


if __name__ == '__main__':
    unittest.main()
