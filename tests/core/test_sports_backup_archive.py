"""Real backup command/validators with synthetic registry records and unit native bytes."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


support = load('archive_command_test', 'scripts/lib/sports-backup-archive.py')
native = load('archive_native_test', 'scripts/lib/sports-native-consumption.py')


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atlas-archive-test.', dir='/tmp')
        self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.control = tempfile.TemporaryDirectory(prefix='atlas-backup-archive.', dir='/tmp')
        self.addCleanup(self.control.cleanup)
        project = self.root/'source'; project.mkdir(mode=0o700)
        for name in support.PROJECT_FILES:
            path = project/name; path.write_text('1.0.0-rc.1\n' if name=='VERSION' else 'synthetic source fixture\n'); path.chmod(0o600)
        for name in support.PROJECT_DIRS:
            path = project/name; path.mkdir(mode=0o700); (path/'fixture.txt').write_text('synthetic fixture\n'); (path/'fixture.txt').chmod(0o600)
        dump = self.root/'database.dump'; dump.write_bytes(b'PGDMP-explicit-unit-format-header-not-a-native-dump'); dump.chmod(0o600)
        jwt = self.root/'jwt'; jwt.write_bytes(b'isolated-unit-identity'); jwt.chmod(0o600)
        database = self.root/'teamarr.db'
        connection = sqlite3.connect(database); connection.execute('CREATE TABLE probe(marker TEXT)'); connection.execute("INSERT INTO probe VALUES('unit-only')"); connection.commit(); connection.close(); database.chmod(0o600)
        files = {support.BACKEND[0][1]: dump, support.BACKEND[1][1]: jwt, support.BACKEND[2][1]: database}
        with contextlib.redirect_stdout(io.StringIO()):
            self.env = support.setup(native, self.control.name, files, project_source=project)

    def test_real_command_publishes_complete_format3_and_roundtrips_metadata(self):
        archive = support.publish(native, self.env)
        self.assertEqual(support.roundtrip(native, archive, self.env), support.sha(archive))
        with tarfile.open(archive) as source:
            manifest = source.extractfile('RECOVERY_MANIFEST.tsv').read().decode()
            self.assertEqual(len(manifest.splitlines()), 18)
            self.assertIn('identity-invitations\tstate/identity/invitations\toptional\tabsent-optional', manifest)
        self.assertTrue(support.validate(archive, self.env))

    def test_bad_native_checksum_prevents_publication_and_cleans_partial_state(self):
        path = Path(self.env['NATIVE_PAYLOAD'])/support.BACKEND[0][1]
        path.write_bytes(b'PGDMP-corrupted-after-checksums')
        with self.assertRaises(ValueError): support.publish(native, self.env)
        self.assertEqual(list(Path(self.env['ATLAS_BACKUP_DIR']).iterdir()), [])
        self.assertFalse(list(Path(self.env['ATLAS_PROJECT_DIR']).glob('.atlas-backup-*.tmp')))

    def test_missing_required_registry_file_prevents_publication(self):
        Path(self.env['ATLAS_SCHEDULER_STATE_FILE']).unlink()
        with self.assertRaises(ValueError): support.publish(native, self.env)
        self.assertEqual(list(Path(self.env['ATLAS_BACKUP_DIR']).iterdir()), [])

    def test_modified_archive_backend_is_rejected_by_actual_validator(self):
        archive = support.publish(native, self.env)
        changed = Path(self.control.name)/'tampered.tar.gz'
        with tarfile.open(archive) as original, tarfile.open(changed, 'w:gz') as target:
            for item in original:
                raw = original.extractfile(item).read() if item.isfile() else None
                if item.name == 'backend-recovery/dispatcharr/jwt': raw = b'changed-unit-identity'; item.size = len(raw)
                target.addfile(item, io.BytesIO(raw) if raw is not None else None)
        self.assertFalse(support.validate(changed, self.env))

    def test_late_validation_failure_removes_partial_before_publication(self):
        # Inject refusal only at the final archive gate; actual tar creation runs.
        script = support.SHELL.replace('    atlas_sports_backend_recovery_capture() {',
            '    atlas_backup_recovery_validate_archive() { return 1; }\n'
            '    atlas_sports_backend_recovery_capture() {')
        result = support.shell(script, self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(Path(self.env['ATLAS_BACKUP_DIR']).iterdir()), [])
        self.assertFalse(list(Path(self.env['ATLAS_PROJECT_DIR']).glob('.atlas-backup-*.tmp')))

    def test_symlink_native_artifact_is_refused(self):
        payload = Path(self.env['NATIVE_PAYLOAD'])/support.BACKEND[1][1]
        payload.unlink(); payload.symlink_to(self.root/'jwt')
        with self.assertRaises(ValueError): support.publish(native, self.env)
        self.assertFalse(Path(self.env['ATLAS_BACKUP_DIR']).exists())

    def test_missing_export_packaging_inputs_use_explicit_private_scaffolding(self):
        source = self.root/'source'
        for name in ('.env.example', 'VERSION', 'CHANGELOG.md', 'docker-compose.sports.yml'):
            (source/name).unlink()
        shutil.rmtree(source/'config')
        module = source/'modules/sports'; module.mkdir(mode=0o700)
        (module/'docker-compose.yml').write_text('synthetic module compose\n')
        (module/'docker-compose.yml').chmod(0o600)
        target = self.root/'project-copy'; target.mkdir(mode=0o700)
        support.copy_project(native, source, target)
        self.assertEqual((target/'VERSION').read_text(), '1.0.0-rc.1\n')
        self.assertEqual((target/'docker-compose.sports.yml').read_text(), 'synthetic module compose\n')
        self.assertTrue((target/'config/archive-fixture.json').is_file())
        self.assertTrue((target/'docs/ARCHIVE_FIXTURE_NOTE.md').is_file())
        self.assertFalse((source/'VERSION').exists())


if __name__ == '__main__': unittest.main()
