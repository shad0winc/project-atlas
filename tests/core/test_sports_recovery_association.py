"""Bind real prepared bundle files to native receipts; stub only PG commands."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


association = load('sports_association', ROOT / 'scripts/lib/sports-recovery-association.py')
fixture_module = load('association_bundle_fixture', Path(__file__).with_name('test_sports_recovery_bundle.py'))
bundle = fixture_module.bundle
postgres = association.helper('sports-postgres-prepare')


class RecoveryAssociationTests(unittest.TestCase):
    def setUp(self):
        fixture = fixture_module.RecoveryBundleTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.bundle_root = fixture.prepare()
        self.fixture = fixture
        self.pg_temp = tempfile.TemporaryDirectory(prefix='project-atlas-pg-prepare.', dir='/tmp')
        self.addCleanup(self.pg_temp.cleanup)
        self.pg_root = Path(self.pg_temp.name)
        for name in ('cold-cluster', 'restored-cluster'):
            cluster = self.pg_root / name
            cluster.mkdir(mode=0o700)
            fixture_module.write(cluster / 'PG_VERSION', b'17\n')
            fixture_module.write(cluster / 'fixture-data', name.encode())
        shutil.copyfile(self.bundle_root / 'dispatcharr/database.dump', self.pg_root / 'database.dump')
        (self.pg_root / 'database.dump').chmod(0o600)
        self.pg_receipt = {
            'version': 1, 'state': 'native-prepared-not-live-ready', 'postgres_major': '17',
            'source_dump_sha256': postgres.archive_digest(self.pg_root / 'database.dump'),
            'source_cold_cluster_sha256': postgres.cluster_digest(self.pg_root / 'cold-cluster'),
            'application_database': 'atlas_app', 'admin_role': 'atlas_admin',
            'global_roles_preserved': True, 'database_properties_preserved': True,
            'table_set_verified': True, 'cluster_stopped': True, 'ready_for_live_apply': False,
            'prepared_cluster_sha256': postgres.cluster_digest(self.pg_root / 'restored-cluster'),
        }
        self.write_pg_receipt()
        resolver = patch.object(association, 'helper', side_effect=lambda name:
            {'sports-recovery-bundle': bundle, 'sports-postgres-prepare': postgres}[name])
        resolver.start(); self.addCleanup(resolver.stop)
        tools = patch.object(postgres, 'tools_for', return_value=('17', {'pg_controldata': Path('/fixed/pg_controldata'), 'pg_ctl': Path('/fixed/pg_ctl')}))
        tools.start(); self.addCleanup(tools.stop)
        commands = patch.object(postgres, 'command', return_value=b'Database cluster state:               shut down\n')
        self.commands = commands.start(); self.addCleanup(commands.stop)

    def write_pg_receipt(self):
        fixture_module.write(self.pg_root / 'PREPARED.json', json.dumps(self.pg_receipt).encode())

    def associate(self):
        result = association.associate(self.bundle_root, self.pg_root,
                                       database='atlas_app', admin_role='atlas_admin')
        self.addCleanup(shutil.rmtree, result)
        return result

    def snapshot(self):
        return {str(path): (path.read_bytes(), path.stat().st_mode, path.stat().st_uid,
                            path.stat().st_mtime_ns)
                for root in (self.bundle_root, self.pg_root)
                for path in root.rglob('*') if path.is_file()}

    def test_association_binds_complete_validated_inputs_without_editing_them(self):
        before = self.snapshot()
        workspace = self.associate()
        receipt = association.validate_association(workspace)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(receipt['ready_for_live_apply'])
        self.assertEqual(receipt['state'], 'associated-not-live-ready')
        self.assertEqual(receipt['bundle_document_sha256'],
                         hashlib.sha256((self.bundle_root / 'BUNDLE.json').read_bytes()).hexdigest())
        self.assertEqual(receipt['postgres_document_sha256'],
                         hashlib.sha256((self.pg_root / 'PREPARED.json').read_bytes()).hexdigest())
        self.assertEqual(workspace.stat().st_mode & 0o777, 0o700)
        self.assertEqual((workspace / 'ASSOCIATION.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(workspace.stat().st_uid, os.geteuid())
        self.assertTrue(self.commands.call_args_list)
        self.assertTrue(all(call.args[0][0] == '/fixed/pg_controldata'
                            for call in self.commands.call_args_list))

    def test_wrong_reviewed_database_or_admin_is_rejected(self):
        for database, admin in (('wrong_db', 'atlas_admin'), ('atlas_app', 'wrong_admin')):
            with self.subTest(database=database), self.assertRaises(association.AssociationError):
                association.associate(self.bundle_root, self.pg_root, database=database, admin_role=admin)

    def test_two_individually_valid_preparations_with_different_dumps_cannot_associate(self):
        fixture_module.write(self.pg_root / 'database.dump', b'PGDMP-different-valid-header-fixture')
        self.pg_receipt['source_dump_sha256'] = postgres.archive_digest(self.pg_root / 'database.dump')
        self.write_pg_receipt()
        postgres.validate_prepared(self.pg_root)
        with self.assertRaises(association.AssociationError): self.associate()

    def test_absent_native_bundle_is_unresolved_and_cannot_associate(self):
        shutil.rmtree(self.fixture.root / 'backend-recovery/dispatcharr')
        shutil.rmtree(self.fixture.root / 'backend-recovery/teamarr')
        self.fixture.native_manifest('absent')
        fixture_module.write(self.fixture.root / 'backend-recovery/SHA256SUMS', b'')
        self.bundle_root = self.fixture.prepare()
        self.assertEqual(bundle.validate_bundle(self.bundle_root)['native_backend'], 'absent-unresolved')
        with self.assertRaises(association.AssociationError): self.associate()

    def test_each_associated_artifact_is_revalidated(self):
        workspace = self.associate()
        for relative in ('dispatcharr/jwt', 'teamarr/teamarr.db',
                         'sports-metadata/metadata.sqlite', 'sports-metadata-policy/refresh.json'):
            path = self.bundle_root / relative
            before = path.read_bytes()
            try:
                path.write_bytes(before + b'tampered')
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    association.validate_association(workspace)
            finally:
                path.write_bytes(before)

    def test_cold_and_prepared_cluster_changes_invalidate_association(self):
        workspace = self.associate()
        for name in ('cold-cluster', 'restored-cluster'):
            path = self.pg_root / name / 'fixture-data'
            before = path.read_bytes()
            try:
                path.write_bytes(b'changed')
                with self.subTest(name=name), self.assertRaises(postgres.PrepareError):
                    association.validate_association(workspace)
            finally:
                path.write_bytes(before)

    def test_changed_valid_ownership_plan_invalidates_old_association(self):
        workspace = self.associate()
        path = self.bundle_root / 'BUNDLE.json'
        manifest = json.loads(path.read_bytes())
        manifest['ownership_plan']['dispatcharr'] = [321, 321]
        for row in manifest['files']:
            if row['surface'] == 'dispatcharr-database': row['publish_owner'] = [321, 321]
        path.write_text(json.dumps(manifest))
        bundle.validate_bundle(self.bundle_root)
        with self.assertRaises(association.AssociationError): association.validate_association(workspace)

    def test_running_cluster_invalidates_association(self):
        workspace = self.associate()
        fixture_module.write(self.pg_root / 'restored-cluster/postmaster.pid', b'123')
        with self.assertRaises(postgres.PrepareError): association.validate_association(workspace)

    def test_independent_jwt_ownership_change_invalidates_prior_association(self):
        workspace = self.associate()
        path = self.bundle_root / 'BUNDLE.json'
        manifest = json.loads(path.read_bytes())
        manifest['ownership_plan']['dispatcharr_jwt'] = [123, 456]
        for row in manifest['files']:
            if row['surface'] == 'dispatcharr-jwt': row['publish_owner'] = [123, 456]
        path.write_text(json.dumps(manifest))
        bundle.validate_bundle(self.bundle_root)
        with self.assertRaises(association.AssociationError): association.validate_association(workspace)

    def test_mutation_between_observations_removes_only_own_new_workspace(self):
        before = self.snapshot()
        real_observe = association.observe
        observations = 0
        made = []
        real_mkdtemp = tempfile.mkdtemp
        def make(**kwargs):
            result = real_mkdtemp(**kwargs); made.append(Path(result)); return result
        def changing(*args, **kwargs):
            nonlocal observations
            result = real_observe(*args, **kwargs); observations += 1
            if observations == 2: result['source_dump_sha256'] = 'f' * 64
            return result
        with patch.object(association.tempfile, 'mkdtemp', side_effect=make), patch.object(association, 'observe', side_effect=changing):
            with self.assertRaises(association.AssociationError): self.associate()
        self.assertEqual(len(made), 1)
        self.assertFalse(made[0].exists())
        self.assertEqual(before, self.snapshot())

    def test_receipt_live_flag_duplicate_keys_and_extra_files_are_rejected(self):
        workspace = self.associate()
        path = workspace / 'ASSOCIATION.json'
        before = path.read_bytes()
        for raw in (before.replace(b'"ready_for_live_apply": false', b'"ready_for_live_apply": true'),
                    b'{"version":1,' + before[1:]):
            path.write_bytes(raw)
            with self.assertRaises(ValueError): association.validate_association(workspace)
        path.write_bytes(before)
        fixture_module.write(workspace / 'extra', b'')
        with self.assertRaises(association.AssociationError): association.validate_association(workspace)

    def test_symlinked_input_or_association_document_is_rejected(self):
        workspace = self.associate()
        path = workspace / 'ASSOCIATION.json'
        raw = path.read_bytes(); path.unlink()
        alternate = workspace / 'alternate'; fixture_module.write(alternate, raw)
        path.symlink_to(alternate)
        with self.assertRaises(ValueError): association.validate_association(workspace)
        path.unlink(); alternate.unlink(); fixture_module.write(path, raw)
        dump = self.bundle_root / 'dispatcharr/database.dump'
        raw = dump.read_bytes(); dump.unlink()
        dump.symlink_to(self.pg_root / 'database.dump')
        with self.assertRaises(ValueError): association.validate_association(workspace)


if __name__ == '__main__':
    unittest.main()
