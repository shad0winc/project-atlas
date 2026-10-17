"""Real archive/schema/journal/controller tests; native apps and UID mapping need CT100."""
import contextlib
import importlib.util
import io
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


support = load('archive_metadata_test', 'scripts/lib/sports-archive-metadata.py')
archive_tests = load('archive_metadata_fixture_test', 'tests/core/test_sports_backup_archive.py')
native = archive_tests.native
fixture = load('archive_metadata_journal_test', 'scripts/diagnostics/sports-recovery-consumption-drill.py')


class ArchiveMetadataTests(unittest.TestCase):
    setUp = archive_tests.ArchiveTests.setUp

    def extracted(self):
        archive = archive_tests.support.publish(native, self.env)
        destination = self.root/'archive-metadata'
        with patch.object(native, 'workspace', return_value=self.root):
            receipt = support.extract(native, archive, self.env, destination)
        return destination, receipt

    def rehearsal(self):
        extracted, receipt = self.extracted()
        run = support.Rehearsal(); run.extracted = extracted; run.archive_sha = receipt['archive_sha256']
        temp = tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp')
        self.addCleanup(temp.cleanup); sandbox = Path(temp.name); fixture.fixture(sandbox)
        return run, sandbox, receipt

    def test_extracts_archive_metadata_bytes_and_binds_one_archive(self):
        extracted, receipt = self.extracted()
        self.assertEqual(support.validate(native, extracted, receipt['archive_sha256']), receipt)
        source = Path(self.env['ATLAS_RUNTIME_CONFIG_DIR'])/'private/sports-metadata-policy/refresh.json'
        self.assertEqual((extracted/'sports-metadata-policy/refresh.json').read_bytes(), source.read_bytes())
        self.assertEqual(set(extracted.iterdir()), {extracted/name for name in (*support.SURFACES, 'METADATA_EXTRACTED.json')})

    def test_prepare_checks_native_and_metadata_archive_binding(self):
        from types import SimpleNamespace
        archive = archive_tests.support.publish(native, self.env)
        for mismatched in (False, True):
            with self.subTest(mismatched=mismatched):
                if mismatched:
                    import shutil
                    shutil.rmtree(self.root/'archive-metadata')
                baseline = self.root/('bad-baseline' if mismatched else 'baseline'); baseline.mkdir(mode=0o700)
                archive_module = SimpleNamespace(roundtrip=lambda *args: archive_tests.support.sha(archive))
                restore_module = SimpleNamespace(load=lambda *args: archive_module)
                def prepare(*args):
                    module = restore_module.load('archive_restore_command', 'scripts/lib/sports-backup-archive.py')
                    digest = module.roundtrip(native, archive, self.env)
                    native.pub.write_json(baseline/'ARCHIVE_RESTORED.json', {'archive_sha256': '0'*64 if mismatched else digest})
                restore_module.prepare_baseline = prepare
                original_load = support.load
                def scoped(name, relative):
                    if relative == 'scripts/lib/sports-archive-restore.py': return restore_module
                    return original_load(name, relative)
                run = support.Rehearsal()
                with patch.object(support, 'load', side_effect=scoped), patch.object(native, 'workspace', return_value=self.root), contextlib.redirect_stdout(io.StringIO()):
                    if mismatched:
                        with self.assertRaises(ValueError): run.prepare_baseline(native, None, baseline, None, None)
                    else:
                        run.prepare_baseline(native, None, baseline, None, None)
                        self.assertEqual(run.archive_sha, archive_tests.support.sha(archive))

    def test_wrong_archive_binding_refused(self):
        extracted, _ = self.extracted()
        with self.assertRaises(ValueError): support.validate(native, extracted, '0'*64)

    def test_bad_archive_refused_before_creating_destination(self):
        archive = archive_tests.support.publish(native, self.env); archive.write_bytes(b'corrupt')
        target = self.root/'archive-metadata'
        with patch.object(native, 'workspace', return_value=self.root):
            with self.assertRaises(ValueError): support.extract(native, archive, self.env, target)
        self.assertFalse(target.exists())

    def test_existing_extraction_preserved(self):
        extracted, _ = self.extracted()
        before = native.pub.digest(extracted, True)
        with patch.object(native, 'workspace', return_value=self.root):
            with self.assertRaises(ValueError): support.extract(native, Path(self.env['ATLAS_BACKUP_DIR'])/'missing', self.env, extracted)
        self.assertEqual(native.pub.digest(extracted, True), before)

    def test_archive_member_limit_refuses_before_member_write(self):
        archive = archive_tests.support.publish(native, self.env)
        target = self.root/'archive-metadata'
        with patch.object(native, 'workspace', return_value=self.root), patch.object(support, 'MAX_MEMBER', 2):
            with self.assertRaises(ValueError): support.extract(native, archive, self.env, target)
        self.assertFalse((target/'sports-metadata/metadata.sqlite').exists())

    def test_tampered_metadata_or_policy_refused_before_journal_mutation(self):
        run, sandbox, _ = self.rehearsal(); before = native.pub.digest(sandbox, True)
        path = run.extracted/'sports-metadata-policy/refresh.json'; path.write_bytes(b'{"version":1,"enabled":true}\n')
        with self.assertRaises(ValueError): run.initialize(native, sandbox)
        self.assertEqual(native.pub.digest(sandbox, True), before)

    def test_install_plan_uses_archive_hashes_and_refuses_second_install(self):
        run, sandbox, receipt = self.rehearsal()
        with contextlib.redirect_stdout(io.StringIO()): run.initialize(native, sandbox)
        plan = native.pub.read_json(sandbox/'transaction/PLAN.json')
        for row in plan['surfaces']:
            if row['surface'] in support.SURFACES:
                self.assertEqual(row['old_sha256'], receipt['surfaces'][row['surface']])
                self.assertEqual(row['new_sha256'], row['old_sha256'])
        with self.assertRaises(ValueError): run.initialize(native, sandbox)
        native.consumer.arm(sandbox)

    def test_exposed_journal_refused_without_changes(self):
        run, sandbox, _ = self.rehearsal(); native.consumer.arm(sandbox)
        before = native.pub.digest(sandbox, True)
        with self.assertRaises(ValueError): run.initialize(native, sandbox)
        self.assertEqual(native.pub.digest(sandbox, True), before)

    def test_metadata_commits_quarantined_archive_bytes_restored_idempotently(self):
        run, sandbox, receipt = self.rehearsal()
        with contextlib.redirect_stdout(io.StringIO()):
            run.initialize(native, sandbox); native.consumer.arm(sandbox); support.metadata.mutate(native, sandbox)
            native.consumer.recover(sandbox); native.consumer.recover(sandbox)
            with patch.object(support.metadata, 'reader_probe') as probe: run.verify(native, sandbox)
            self.assertEqual(probe.call_count, 2)
        for name in support.SURFACES:
            self.assertEqual(native.pub.digest(sandbox/'current'/name, True), receipt['surfaces'][name])
            self.assertNotEqual(native.pub.digest(sandbox/'consumption/quarantine'/name, True), receipt['surfaces'][name])

    def test_semantic_budget_corruption_is_rejected_even_with_updated_receipt_hashes(self):
        extracted, receipt = self.extracted()
        database = extracted/'sports-metadata/metadata.sqlite'
        with sqlite3.connect(database) as connection: connection.execute('UPDATE metadata_attempts SET stamp=999')
        import hashlib
        receipt['members']['sports-metadata/metadata.sqlite'] = hashlib.sha256(database.read_bytes()).hexdigest()
        receipt['surfaces']['sports-metadata'] = native.pub.digest(extracted/'sports-metadata', True)
        native.pub.write_json(extracted/'METADATA_EXTRACTED.json', receipt)
        with self.assertRaises(ValueError): support.validate(native, extracted, receipt['archive_sha256'])

    def test_real_maintenance_controller_accepts_only_after_archive_recovery(self):
        run, sandbox, _ = self.rehearsal(); accepted = []
        with contextlib.redirect_stdout(io.StringIO()):
            run.initialize(native, sandbox); native.consumer.arm(sandbox); support.metadata.mutate(native, sandbox)
            def complete():
                with patch.object(support.metadata, 'reader_probe'): run.verify(native, sandbox)
                accepted.append(True)
            with patch.object(native, 'recover', side_effect=native.consumer.recover), \
                    patch.object(native.fence, 'load', return_value={}), patch.object(native.fence, 'assert_detached'):
                run.recover(native, sandbox, complete)
        self.assertEqual(accepted, [True])

    def test_failed_native_acceptance_keeps_real_controller_held(self):
        run, sandbox, _ = self.rehearsal(); recorded = []
        maintenance = support.load('archive_metadata_failure_test', 'scripts/lib/sports-maintenance-recovery.py')
        original_execute = maintenance.execute
        def execute(*args, **kwargs):
            result = original_execute(*args, **kwargs); recorded.append(result); return result
        maintenance.execute = execute
        with contextlib.redirect_stdout(io.StringIO()):
            run.initialize(native, sandbox); native.consumer.arm(sandbox); support.metadata.mutate(native, sandbox)
            with patch.object(support, 'load', return_value=maintenance), \
                    patch.object(native, 'recover', side_effect=native.consumer.recover), \
                    patch.object(native.fence, 'load', return_value={}), patch.object(native.fence, 'assert_detached'):
                with self.assertRaises(ValueError): run.recover(native, sandbox, lambda: (_ for _ in ()).throw(ValueError('fixture refusal')))
        self.assertFalse(recorded[0]['success'])
        self.assertTrue(recorded[0]['maintenance_retained'] and recorded[0]['lock_retained'])
        self.assertEqual(recorded[0]['events'][-1], 'start')


if __name__ == '__main__': unittest.main()
