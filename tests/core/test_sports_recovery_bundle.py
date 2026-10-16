"""Prepare and revalidate unified Sports artifacts without live-state writes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
from providers.metadata_store import MetadataStore
from providers.metadata_identity import MetadataIdentityRegistry, SourceIdentity

spec = importlib.util.spec_from_file_location('sports_bundle', ROOT / 'scripts/lib/sports-recovery-bundle.py')
bundle = importlib.util.module_from_spec(spec); spec.loader.exec_module(bundle)


def write(path, raw):
    path.write_bytes(raw); path.chmod(0o600)


class RecoveryBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='project-atlas-restore.', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identities = {'dispatcharr': [1000, 1000], 'dispatcharr_jwt': [0, 0],
                           'teamarr': [0, 0], 'writer': [1000, 1000]}
        write(self.root / 'RECOVERY_FORMAT', b'3\n')
        original = self.root / 'source'; original.mkdir(mode=0o700)
        metadata = original / 'sports-metadata'; metadata.mkdir(mode=0o700)
        self.store = MetadataStore(metadata / 'metadata.sqlite')
        self.alias = SourceIdentity('espn', 'football/nfl', '401872996')
        self.owner = SourceIdentity('thesportsdb', '4391', '2475454')
        MetadataIdentityRegistry(self.store).enroll_verified(self.owner, [self.alias], evidence_sha256='a' * 64)
        with self.store.locked(), self.store.connection() as connection:
            connection.execute('INSERT INTO metadata_attempts VALUES (123)')
        policy = original / 'sports-metadata-policy'; policy.mkdir(mode=0o750); policy.chmod(0o750)
        (policy / 'refresh.json').write_bytes(b'{"version":1,"enabled":false}\n')
        (policy / 'refresh.json').chmod(0o640)
        bundle.helper('metadata-recovery').capture(metadata, self.root / 'metadata-recovery')
        native = self.root / 'backend-recovery'; native.mkdir(mode=0o700)
        for directory in ('dispatcharr', 'teamarr'): (native / directory).mkdir(mode=0o700)
        write(native / 'dispatcharr/database.dump', b'PGDMP-synthetic-artifact-not-a-real-archive')
        write(native / 'dispatcharr/jwt', b'isolated-fixture-identity')
        connection = sqlite3.connect(native / 'teamarr/teamarr.db')
        connection.execute('CREATE TABLE fixture(id INTEGER)'); connection.execute('INSERT INTO fixture VALUES(7)')
        connection.commit(); connection.close(); (native / 'teamarr/teamarr.db').chmod(0o600)
        self.native_manifest('captured')
        self.native_checksums()

    def native_manifest(self, status):
        raw = 'surface\tarchive_path\tstatus\n' + ''.join(
            f'{surface}\t{relative}\t{status}\n' for surface, relative, _ in bundle.NATIVE)
        write(self.root / 'backend-recovery/MANIFEST.tsv', raw.encode())

    def native_checksums(self):
        raw = ''.join(hashlib.sha256((self.root / relative).read_bytes()).hexdigest() + '  ' + relative + '\n'
                      for _, relative, _ in bundle.NATIVE)
        write(self.root / 'backend-recovery/SHA256SUMS', raw.encode())

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns, p.stat().st_mode)
                for p in self.root.rglob('*') if p.is_file()}

    def prepare(self):
        result = bundle.prepare(self.root, self.identities)
        self.addCleanup(shutil.rmtree, result.parent)
        return result

    def test_complete_bundle_preserves_native_identity_metadata_alias_and_budget(self):
        before = self.snapshot()
        result = self.prepare()
        manifest = bundle.validate_bundle(result)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(manifest['ready_for_live_apply'])
        self.assertEqual(manifest['native_backend'], 'captured')
        self.assertEqual(len(manifest['files']), 6)
        self.assertEqual((result / 'dispatcharr/jwt').read_bytes(), b'isolated-fixture-identity')
        with sqlite3.connect((result / 'sports-metadata/metadata.sqlite').as_uri() + '?mode=ro&immutable=1', uri=True) as connection:
            self.assertEqual(connection.execute('SELECT stamp FROM metadata_attempts').fetchall(), [(123.0,)])
            self.assertEqual(connection.execute('SELECT owner_event_id FROM metadata_aliases WHERE provider=?', ('espn',)).fetchone(), ('2475454',))
        records = {row['surface']: row for row in manifest['files']}
        self.assertEqual(records['dispatcharr-database']['state'], 'native-restore-required')
        self.assertEqual(records['metadata-policy']['publish_owner'], [0, 1000])
        self.assertEqual(records['metadata-policy']['publish_mode'], '0640')

    def test_staged_files_remain_operator_private_and_no_ownership_is_applied(self):
        with patch.object(bundle.os, 'chown', side_effect=AssertionError('must not chown')):
            result = self.prepare()
        for path in (result.parent, result, *result.rglob('*')):
            info = path.lstat()
            self.assertEqual(info.st_uid, os.geteuid())
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o700 if path.is_dir() else 0o600)
        self.assertEqual((result / 'sports-metadata/metadata.sqlite.lock').read_bytes(), b'')

    def test_v2_plan_keeps_postgres_jwt_teamarr_and_writer_identities_independent(self):
        result = self.prepare()
        manifest = bundle.validate_bundle(result)
        self.assertEqual(manifest['version'], 2)
        rows = {row['surface']: row for row in manifest['files']}
        for surface, owner in (
            ('dispatcharr-database', [1000, 1000]),
            ('dispatcharr-jwt', [0, 0]),
            ('teamarr-database', [0, 0]),
            ('metadata-database', [1000, 1000]),
            ('metadata-lock', [1000, 1000]),
            ('metadata-policy', [0, 1000]),
        ):
            with self.subTest(surface=surface):
                self.assertEqual(rows[surface]['publish_owner'], owner)
        self.assertEqual(manifest['publish_directories']['sports-metadata-policy'],
                         {'owner': [0, 1000], 'mode': '0750'})
        self.assertTrue(all(path.stat().st_uid == os.geteuid()
                            for path in result.rglob('*')))

    def test_missing_jwt_identity_is_not_guessed_from_postgres(self):
        identities = {key: value for key, value in self.identities.items() if key != 'dispatcharr_jwt'}
        with patch.object(bundle.tempfile, 'mkdtemp') as create:
            with self.assertRaises(bundle.BundleError): bundle.prepare(self.root, identities)
            create.assert_not_called()

    def test_prepared_v1_manifest_requires_regeneration(self):
        result = self.prepare(); path = result / 'BUNDLE.json'
        manifest = json.loads(path.read_bytes()); manifest['version'] = 1
        write(path, json.dumps(manifest).encode())
        with self.assertRaises(bundle.BundleError): bundle.validate_bundle(result)

    def test_jwt_owner_cannot_be_substituted_with_postgres_owner(self):
        result = self.prepare(); path = result / 'BUNDLE.json'
        manifest = json.loads(path.read_bytes())
        for row in manifest['files']:
            if row['surface'] == 'dispatcharr-jwt': row['publish_owner'] = [1000, 1000]
        write(path, json.dumps(manifest).encode())
        with self.assertRaises(bundle.BundleError): bundle.validate_bundle(result)

    def test_absent_native_state_remains_an_explicit_unresolved_action(self):
        native = self.root / 'backend-recovery'
        shutil.rmtree(native / 'dispatcharr'); shutil.rmtree(native / 'teamarr')
        self.native_manifest('absent'); write(native / 'SHA256SUMS', b'')
        result = self.prepare(); manifest = bundle.validate_bundle(result)
        self.assertEqual(manifest['native_backend'], 'absent-unresolved')
        self.assertFalse((result / 'dispatcharr').exists())
        self.assertEqual(len(manifest['files']), 3)
        self.assertFalse(manifest['ready_for_live_apply'])

    def test_legacy_database_only_snapshot_is_not_given_a_guessed_policy(self):
        metadata = self.root / 'metadata-recovery'
        (metadata / 'refresh-policy.json').unlink()
        manifest = json.loads((metadata / 'MANIFEST.json').read_bytes())
        manifest.pop('policy_sha256'); manifest['version'] = 1
        write(metadata / 'MANIFEST.json', json.dumps(manifest).encode())
        bundle.helper('metadata-recovery').validate_staged(metadata)
        with self.assertRaises(bundle.BundleError): self.prepare()

    def test_wrong_format_and_invalid_ownership_plan_fail_before_workspace_creation(self):
        with patch.object(bundle.tempfile, 'mkdtemp', side_effect=AssertionError('no workspace yet')):
            for identities in ({}, {**self.identities, 'writer': [True, 9]}, {**self.identities, 'writer': [-1, 9]}):
                with self.subTest(identities=identities), self.assertRaises(bundle.BundleError):
                    bundle.prepare(self.root, identities)
            write(self.root / 'RECOVERY_FORMAT', b'2\n')
            with self.assertRaises(bundle.BundleError): bundle.prepare(self.root, self.identities)

    def test_partial_native_manifest_is_rejected(self):
        path = self.root / 'backend-recovery/MANIFEST.tsv'
        write(path, path.read_bytes().replace(b'captured', b'absent', 1))
        with self.assertRaises(bundle.BundleError): self.prepare()

    def test_payload_checksum_failure_removes_only_new_workspace(self):
        before = self.snapshot()
        original_copy = bundle.copy_checked
        created = []
        real_mkdtemp = tempfile.mkdtemp
        def make(*args, **kwargs):
            value = real_mkdtemp(*args, **kwargs); created.append(Path(value)); return value
        def corrupt(source, destination, expected, limit):
            return original_copy(source, destination, '0' * 64, limit)
        with patch.object(bundle.tempfile, 'mkdtemp', side_effect=make), patch.object(bundle, 'copy_checked', side_effect=corrupt):
            with self.assertRaises(bundle.BundleError): self.prepare()
        self.assertEqual(len(created), 1)
        self.assertFalse(created[0].exists())
        self.assertEqual(self.snapshot(), before)

    def test_unknown_native_file_and_source_hardlink_are_rejected(self):
        extra = self.root / 'backend-recovery/unreviewed'; write(extra, b'keep')
        with self.assertRaises(bundle.BundleError): self.prepare()
        self.assertEqual(extra.read_bytes(), b'keep'); extra.unlink()
        jwt = self.root / 'backend-recovery/dispatcharr/jwt'
        os.link(jwt, self.root / 'linked-identity')
        with self.assertRaises(bundle.BundleError): self.prepare()

    def test_corrupt_teamarr_with_matching_checksum_is_still_rejected(self):
        write(self.root / 'backend-recovery/teamarr/teamarr.db', b'not SQLite')
        self.native_checksums()
        with self.assertRaises((bundle.BundleError, sqlite3.Error)): self.prepare()

    def test_invalid_policy_with_matching_checksum_is_rejected(self):
        metadata = self.root / 'metadata-recovery'
        write(metadata / 'refresh-policy.json', b'{"version":1,"enabled":true}')
        manifest = json.loads((metadata / 'MANIFEST.json').read_bytes())
        manifest['policy_sha256'] = hashlib.sha256((metadata / 'refresh-policy.json').read_bytes()).hexdigest()
        write(metadata / 'MANIFEST.json', json.dumps(manifest).encode())
        with self.assertRaises(ValueError): self.prepare()

    def test_broken_alias_ownership_with_matching_checksum_is_rejected(self):
        metadata = self.root / 'metadata-recovery'
        with sqlite3.connect(metadata / 'database.sqlite') as connection:
            connection.execute("DELETE FROM metadata_aliases WHERE provider='thesportsdb'")
        manifest = json.loads((metadata / 'MANIFEST.json').read_bytes())
        manifest['database_sha256'] = hashlib.sha256((metadata / 'database.sqlite').read_bytes()).hexdigest()
        write(metadata / 'MANIFEST.json', json.dumps(manifest).encode())
        with self.assertRaises(ValueError): self.prepare()

    def test_native_header_and_empty_identity_are_rejected_even_with_matching_checksums(self):
        dump = self.root / 'backend-recovery/dispatcharr/database.dump'
        original = dump.read_bytes()
        write(dump, b'not PGDMP'); self.native_checksums()
        with self.assertRaises(bundle.BundleError): self.prepare()
        write(dump, original)
        write(self.root / 'backend-recovery/dispatcharr/jwt', b''); self.native_checksums()
        with self.assertRaises(bundle.BundleError): self.prepare()

    def test_changed_source_contract_during_copy_is_rejected(self):
        original = bundle.copy_checked
        def change(source, destination, expected, limit):
            original(source, destination, expected, limit)
            if source.name == 'refresh-policy.json':
                write(self.root / 'metadata-recovery/MANIFEST.json', b'{}')
        with patch.object(bundle, 'copy_checked', side_effect=change):
            with self.assertRaises(bundle.BundleError): self.prepare()

    def test_revalidation_rejects_tampered_missing_extra_and_ready_flag(self):
        result = self.prepare()
        manifest_path = result / 'BUNDLE.json'; raw = manifest_path.read_bytes()
        manifest = json.loads(raw); manifest['ready_for_live_apply'] = True
        write(manifest_path, json.dumps(manifest).encode())
        with self.assertRaises(bundle.BundleError): bundle.validate_bundle(result)
        write(manifest_path, raw)
        extra = result / 'unexpected'; write(extra, b'no')
        with self.assertRaises(bundle.BundleError): bundle.validate_bundle(result)
        extra.unlink()
        (result / 'sports-metadata/metadata.sqlite.lock').unlink()
        with self.assertRaises((bundle.BundleError, OSError)): bundle.validate_bundle(result)

    def test_revalidation_rejects_manifest_traversal_and_duplicate_json_keys(self):
        result = self.prepare(); path = result / 'BUNDLE.json'; raw = path.read_bytes()
        manifest = json.loads(raw); manifest['files'][0]['path'] = '../../outside'
        write(path, json.dumps(manifest).encode())
        with self.assertRaises(bundle.BundleError): bundle.validate_bundle(result)
        write(path, raw[:-2] + b',"version":1}\n')
        with self.assertRaises(bundle.BundleError): bundle.validate_bundle(result)

    def test_destination_root_is_fixed_and_cannot_select_live_paths(self):
        with self.assertRaises(bundle.BundleError):
            bundle.prepare(self.root, self.identities, scratch_parent=Path('/mnt/storage'))
        alternate = self.root / 'not-canonical'; alternate.mkdir(mode=0o700)
        with self.assertRaises(bundle.BundleError): bundle.prepare(alternate, self.identities)

    def test_detached_metadata_validation_does_not_create_sidecars(self):
        result = self.prepare()
        database = result / 'sports-metadata/metadata.sqlite'
        with sqlite3.connect(database) as connection:
            connection.execute('PRAGMA journal_mode=WAL')
        # After final connection close the detached DB has no live WAL file.
        before = {p.name for p in database.parent.iterdir()}
        bundle.helper('metadata-recovery').validate_database(database, immutable=True)
        self.assertEqual({p.name for p in database.parent.iterdir()}, before)


if __name__ == '__main__': unittest.main()
