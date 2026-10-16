"""Policy persistence, writer permissions and complete recovery archive evidence."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
sys.path.insert(0, str(ROOT / 'tests/core'))
import test_backup_storage_safety as backup_fixtures


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts/lib' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = helper('sports-metadata-policy')
runtime = helper('sports-metadata-runtime')
recovery = helper('metadata-recovery')
ENABLED = {'version': 1, 'enabled': True, 'routes': ['football/nfl'],
           'hourly_budget': 96, 'current_ttl': 60, 'past_ttl': 3600,
           'future_ttl': 3600, 'directory_ttl': 3600, 'tick_seconds': 1,
           'generation': 'isolated-test'}


class MetadataPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.uid, self.gid = os.geteuid(), os.getegid()
        self.config = self.root / 'private/sports-metadata-policy'
        self.state = self.root / 'private/sports-metadata'

    def provision(self):
        runtime.provision(ROOT, self.root, self.uid, self.gid)

    def read(self):
        return policy.read_directory(self.config, self.uid, self.gid)

    def install_enabled(self):
        path = self.config / 'refresh.json'
        path.write_text(json.dumps(ENABLED))
        path.chmod(0o640)
        return path

    def capture(self):
        stage = self.root / 'snapshot'
        stage.mkdir(mode=0o700)
        destination = stage / 'metadata-recovery'
        self.assertTrue(recovery.capture(self.state, destination))
        return destination

    def test_default_policies_are_disabled_and_create_no_attempts(self):
        self.provision()
        self.assertEqual(self.read(), policy.DISABLED_POLICY)
        self.assertIsNone(policy.validate_bytes(self.read()))
        import sqlite3
        with sqlite3.connect(self.state / 'metadata.sqlite') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM metadata_attempts').fetchone(), (0,))
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o750)
        self.assertEqual(stat.S_IMODE((self.config / 'refresh.json').stat().st_mode), 0o640)

    def test_update_preserves_enabled_policy_bytes_inode_and_mode(self):
        self.provision()
        path = self.install_enabled()
        before = path.read_bytes(), path.stat().st_ino, path.stat().st_mode
        self.provision()
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mode), before)
        self.assertEqual(policy.validate_bytes(self.read()).generation, 'isolated-test')

    def test_existing_corrupt_policy_is_not_repaired_or_overwritten(self):
        self.provision()
        path = self.config / 'refresh.json'
        path.write_bytes(b'{broken')
        with self.assertRaises(ValueError):
            self.provision()
        self.assertEqual(path.read_bytes(), b'{broken')

    def test_incomplete_or_unknown_policy_directory_is_rejected(self):
        self.provision()
        extra = self.config / 'unreviewed'
        extra.write_bytes(b'preserve')
        with self.assertRaises(ValueError):
            self.provision()
        self.assertEqual(extra.read_bytes(), b'preserve')
        extra.unlink()
        (self.config / 'refresh.json').unlink()
        with self.assertRaises(ValueError):
            self.provision()
        self.assertEqual(list(self.config.iterdir()), [])

    def test_symlinks_and_hardlinks_are_rejected(self):
        self.provision()
        path = self.config / 'refresh.json'
        outside = self.root / 'outside'
        path.rename(outside)
        path.symlink_to(outside)
        with self.assertRaises((ValueError, OSError)):
            self.read()
        path.unlink()
        os.link(outside, path)
        with self.assertRaises(ValueError):
            self.read()

    def test_policy_directory_symlink_is_rejected(self):
        self.provision()
        actual = self.root / 'saved'
        self.config.rename(actual)
        self.config.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.provision()
        self.assertTrue((actual / 'refresh.json').exists())

    def test_unsafe_file_and_directory_permissions_are_not_repaired(self):
        self.provision()
        path = self.config / 'refresh.json'
        for mode in (0o600, 0o644, 0o660):
            path.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.provision()
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
        path.chmod(0o640)
        self.config.chmod(0o770)
        with self.assertRaises(ValueError):
            self.provision()
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o770)

    def test_schema_and_budget_use_worker_validation(self):
        for raw in (b'{"version":1,"enabled":false,"enabled":true}',
                    b'{"version":true,"enabled":false}',
                    b'{"version":1,"enabled":false,"extra":1}',
                    b' ' * 16385, b'',
                    json.dumps({**ENABLED, 'hourly_budget': 1}).encode(),
                    json.dumps({**ENABLED, 'routes': ['wrestling/wwe']}).encode()):
            with self.subTest(raw=raw[:90]), self.assertRaises(ValueError):
                policy.validate_bytes(raw)

    def test_initial_policy_failure_leaves_no_published_partial_policy(self):
        runtime.provision_state(ROOT, self.root, self.uid, self.gid)
        with patch.object(runtime.os, 'rename', side_effect=OSError('isolated')):
            with self.assertRaises(OSError):
                runtime.provision_policy(ROOT, self.root, self.uid, self.gid)
        self.assertFalse(self.config.exists())
        self.assertEqual({p.name for p in self.config.parent.iterdir()}, {'sports-metadata'})

    def test_policy_without_database_cannot_silently_downgrade_backup(self):
        self.provision()
        shutil.rmtree(self.state)
        destination = self.root / 'metadata-recovery'
        with self.assertRaises(ValueError):
            recovery.capture(self.state, destination)
        self.assertFalse(destination.exists())

    def test_snapshot_preserves_exact_enabled_policy_with_checksum(self):
        self.provision()
        path = self.install_enabled()
        raw = path.read_bytes()
        destination = self.capture()
        manifest = json.loads((destination / 'MANIFEST.json').read_bytes())
        self.assertEqual(manifest['version'], 2)
        self.assertEqual(manifest['policy_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual((destination / 'refresh-policy.json').read_bytes(), raw)
        self.assertEqual(stat.S_IMODE((destination / 'refresh-policy.json').stat().st_mode), 0o600)
        path.write_bytes(policy.DISABLED_POLICY)
        recovery.validate_staged(destination)
        self.assertEqual((destination / 'refresh-policy.json').read_bytes(), raw)

    def test_policy_tampering_missing_policy_and_invalid_schema_fail(self):
        self.provision()
        destination = self.capture()
        path = destination / 'refresh-policy.json'
        raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            recovery.validate_staged(destination)
        path.unlink()
        with self.assertRaises(ValueError):
            recovery.validate_staged(destination)
        path.write_bytes(b'{"version":1,"enabled":true}')
        path.chmod(0o600)
        manifest_path = destination / 'MANIFEST.json'
        manifest = json.loads(manifest_path.read_bytes())
        manifest['policy_sha256'] = recovery.digest(path)
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            recovery.validate_staged(destination)

    def test_legacy_manifest_does_not_accept_unchecksummed_policy(self):
        self.provision()
        shutil.rmtree(self.config)
        destination = self.capture()
        self.assertEqual(json.loads((destination / 'MANIFEST.json').read_bytes())['version'], 1)
        recovery.validate_staged(destination)
        (destination / 'refresh-policy.json').write_bytes(policy.DISABLED_POLICY)
        with self.assertRaises(ValueError):
            recovery.validate_staged(destination)

    def test_invalid_present_policy_prevents_snapshot_publication(self):
        self.provision()
        (self.config / 'refresh.json').write_bytes(b'broken')
        stage = self.root / 'snapshot'
        stage.mkdir(mode=0o700)
        with self.assertRaises(ValueError):
            recovery.capture(self.state, stage / 'metadata-recovery')
        self.assertEqual(list(stage.iterdir()), [])

    def test_complete_backup_archive_includes_policy_and_stages_safely(self):
        project, backups = backup_fixtures._make_project(self.root)
        runtime_root = Path(backup_fixtures._recovery_environment(project)['ATLAS_RUNTIME_CONFIG_DIR'])
        runtime_root.mkdir(parents=True, exist_ok=True)
        runtime.provision(ROOT, runtime_root, self.uid, self.gid)
        result = backup_fixtures._run_backup(project, backups)
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = next(backups.glob('atlas-*.tar.gz'))
        recovery.validate_archive(archive)
        with tarfile.open(archive) as source:
            self.assertEqual(source.extractfile('RECOVERY_FORMAT').read(), b'3\n')
            self.assertEqual(source.extractfile('metadata-recovery/refresh-policy.json').read(), policy.DISABLED_POLICY)
        command = 'source "$REGISTRY"; atlas_backup_recovery_stage_archive "$ARCHIVE" /tmp'
        result = subprocess.run(['bash', '-eu', '-o', 'pipefail', '-c', command],
            env={**os.environ, **backup_fixtures._recovery_environment(project),
                 'ATLAS_PROJECT_DIR': str(project), 'REGISTRY': str(ROOT / 'scripts/lib/backup-recovery.sh'),
                 'ARCHIVE': str(archive)}, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        staged = Path(result.stdout.strip())
        self.addCleanup(shutil.rmtree, staged)
        recovery.validate_staged(staged / 'metadata-recovery')

    def test_invalid_installed_policy_blocks_complete_backup_publication(self):
        project, backups = backup_fixtures._make_project(self.root)
        runtime_root = Path(backup_fixtures._recovery_environment(project)['ATLAS_RUNTIME_CONFIG_DIR'])
        runtime_root.mkdir(parents=True, exist_ok=True)
        runtime.provision(ROOT, runtime_root, self.uid, self.gid)
        (runtime_root / 'private/sports-metadata-policy/refresh.json').write_bytes(b'broken')
        result = backup_fixtures._run_backup(project, backups)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(backups.glob('atlas-*.tar.gz')), [])
        self.assertEqual(list(backups.glob('*.partial')), [])

    def test_archive_rejects_duplicate_or_linked_policy(self):
        self.provision()
        destination = self.capture()
        for linked in (False, True):
            archive_path = self.root / ('linked.tar.gz' if linked else 'duplicate.tar.gz')
            with tarfile.open(archive_path, 'w:gz') as archive:
                archive.add(destination, arcname='metadata-recovery')
                if linked:
                    info = tarfile.TarInfo('metadata-recovery/refresh-policy.json')
                    info.type = tarfile.SYMTYPE
                    info.linkname = '/tmp/unrelated'
                    archive.addfile(info)
                else:
                    archive.add(destination / 'refresh-policy.json', arcname='metadata-recovery/refresh-policy.json')
            with self.subTest(linked=linked), self.assertRaises(ValueError):
                recovery.validate_archive(archive_path)

    def test_compose_policy_is_writer_only_readonly_bind(self):
        data = yaml.safe_load((ROOT / 'stack/ingress.yml').read_text())
        writer = data['services']['sports-writer']
        mounts = [v for v in writer['volumes'] if isinstance(v, dict) and v['target'] == '/srv/sports-metadata-policy']
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0], {'type': 'bind',
            'source': '${ATLAS_RUNTIME_CONFIG_DIR:-/mnt/storage/configs/atlas}/private/sports-metadata-policy',
            'target': '/srv/sports-metadata-policy', 'read_only': True,
            'bind': {'create_host_path': False}})
        self.assertEqual(writer['environment']['ATLAS_SPORTS_METADATA_REFRESH_FILE'], '/srv/sports-metadata-policy/refresh.json')
        self.assertEqual(writer['expose'], ['8003'])
        for name, service in data['services'].items():
            if name != 'sports-writer':
                self.assertNotIn('sports-metadata-policy', json.dumps(service.get('volumes', [])))

    @unittest.skipUnless(os.geteuid() == 0, 'nonroot permission check requires root')
    def test_nonroot_writer_reads_but_cannot_replace_policy(self):
        probe = self.root / 'identity-probe'
        probe.touch()
        try:
            os.chown(probe, 23456, 23456)
        except OSError:
            self.skipTest('host user namespace cannot map the test writer identity')
        runtime.provision(ROOT, self.root, 23456, 23456)
        source = self.root / 'private/sports-metadata-policy'
        with tempfile.TemporaryDirectory(prefix='atlas-policy-mount-') as directory:
            parent = Path(directory)
            parent.chmod(0o755)
            mounted = parent / 'policy'
            shutil.copytree(source, mounted)
            os.chown(mounted, 0, 23456)
            os.chown(mounted / 'refresh.json', 0, 23456)
            code = '''from pathlib import Path
import os, sys
from providers.metadata_refresh import load_refresh_policy
root = Path(sys.argv[1])
assert load_refresh_policy(root / 'refresh.json') is None
for action in (lambda: (root / 'refresh.json').write_text('changed'),
               lambda: (root / 'refresh.json').unlink(),
               lambda: (root / 'new.json').write_text('changed')):
    try: action()
    except PermissionError: pass
    else: raise AssertionError('writer changed server policy')
'''
            result = subprocess.run([sys.executable, '-B', '-c', code, str(mounted)],
                user=23456, group=23456, extra_groups=[], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
