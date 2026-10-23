"""Real inherited flock, native publication/plan and Linux directory rename.

Admission is an explicit refusing/accepting fixture, never production authority.
"""
import hashlib
import json
import os
import signal
import unittest
from unittest.mock import patch

from atlas.deployment_owner_archive import OwnerArchive
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_owner_preservation_plan as preservation


class OwnerArchiveTests(unittest.TestCase):
    reseal = preservation.OwnerPreservationTests.reseal
    shell = preservation.OwnerPreservationTests.shell
    check_hold = preservation.OwnerPreservationTests.check_hold
    logs = preservation.OwnerPreservationTests.logs

    def setUp(self):
        preservation.OwnerPreservationTests.setUp(self)
        path = self.plan.prepare('reconciliation-new', self.attempt, self.receipt_sha)
        self.plan_raw = path.read_bytes()
        self.pin = hashlib.sha256(self.plan_raw).hexdigest()
        self.archiver = OwnerArchive(self.root, 'update-failed', self.stream.fileno())
        self.target = self.folder / 'original-update.lock'
        self.admission = {'fixture_only': 'separate promoted-driver admission required'}
        self.calls = []
        self.marker_raw = self.archiver.publication_pending.read_bytes()
        self.flag_raw = self.archiver.flag.read_bytes()

    def tearDown(self):
        # Restore only the isolated fixture so the existing native test teardown
        # can prove the same inode/bytes and exclusion. Production has no reverse.
        if self.target.exists() and not self.owner.parent.exists():
            self.target.rename(self.owner.parent)
        self.assertEqual(self.archiver.publication_pending.read_bytes(), self.marker_raw)
        self.assertEqual(self.archiver.flag.read_bytes(), self.flag_raw)
        self.assertEqual((self.folder / 'owner-preservation.json').read_bytes(), self.plan_raw)
        preservation.OwnerPreservationTests.tearDown(self)

    def admit(self, evidence, phase):
        self.assertEqual(evidence, self.admission)
        self.calls.append(phase)

    def archive(self, **kwargs):
        return self.archiver.archive('reconciliation-new', self.pin, self.admission,
                                     admit=kwargs.get('admit', self.admit))

    def inspect(self):
        return self.archiver.inspect('reconciliation-new', self.pin)

    def test_whole_directory_identity_preserved_maintenance_and_marker_closed(self):
        self.assertEqual(self.inspect()['phase'], 'owner-live')
        value = self.archive()
        self.assertEqual(value['phase'], 'archived')
        self.assertFalse(value['ordinary_reopening_permitted'])
        self.assertFalse(self.owner.parent.exists())
        self.assertEqual(self.target.stat().st_ino, self.lock_inode)
        self.assertEqual((self.target / 'owner').stat().st_ino, self.owner_inode)
        self.assertEqual((self.target / 'owner').read_bytes(), self.owner_raw)
        self.assertEqual(self.calls, ['owner-live', 'owner-live'])
        self.assertTrue(self.archiver.status()['transition_pending'])
        self.assertTrue(self.archiver.status()['enabled'])
        self.assertFalse(self.archiver.status()['recovery_held'])
        from atlas.maintenance_control import MaintenanceAuthority
        # The inherited EX flock also excludes an ordinary control invocation.
        with self.assertRaises(MaintenanceControlError):
            MaintenanceAuthority(self.root).change(False, actor='fixture', source='cli')

    def test_inspection_does_not_write_or_grant_permission(self):
        before = {str(p): p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}
        self.inspect()
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.folder.rglob('*') if p.is_file()})
        self.assertFalse((self.folder / 'owner-archive-intent.json').exists())

    def test_admission_refusal_prevents_move_and_freshness_not_inferred_from_plan(self):
        def refuse(*args):
            raise MaintenanceControlError('fixture_fresh_admission_required')
        with self.assertRaises(MaintenanceControlError):
            self.archive(admit=refuse)
        self.assertEqual(self.inspect()['phase'], 'owner-live')
        with self.assertRaises(MaintenanceControlError):
            self.archive(admit=None)
        for value in (False, True):
            with self.assertRaises(MaintenanceControlError):
                self.archive(admit=lambda *args: value)
        self.assertFalse((self.folder / 'owner-archive-intent.json').exists())

    def test_second_admission_refusal_preserves_durable_intent_and_live_owner(self):
        def refuse_second(evidence, phase):
            self.admit(evidence, phase)
            if len(self.calls) == 2:
                raise MaintenanceControlError('fixture_admission_expired')
        with self.assertRaises(MaintenanceControlError):
            self.archive(admit=refuse_second)
        self.assertEqual(self.inspect()['phase'], 'intent-durable-owner-live')
        self.assertEqual(self.archive()['phase'], 'archived')

    def test_explicit_retry_requires_same_admission_even_when_completed(self):
        self.archive()
        intent = (self.folder / 'owner-archive-intent.json').read_bytes()
        self.assertEqual(self.archive()['phase'], 'archived')
        self.assertEqual(self.calls[-2:], ['archived', 'archived'])
        self.admission['changed'] = True
        with self.assertRaises(MaintenanceControlError):
            self.archive()
        self.assertEqual((self.folder / 'owner-archive-intent.json').read_bytes(), intent)

    def test_changed_owner_inventory_and_wrong_plan_pin_refuse(self):
        with self.assertRaises(MaintenanceControlError):
            self.archiver.inspect('reconciliation-new', '0' * 64)
        extra = self.owner.parent / 'foreign'
        extra.write_text('preserve')
        with self.assertRaises(MaintenanceControlError):
            self.archive()
        self.assertEqual(extra.read_text(), 'preserve')
        extra.unlink()
        mode = self.owner.stat().st_mode & 0o777
        self.owner.chmod(0o600 if mode != 0o600 else 0o644)
        with self.assertRaises(MaintenanceControlError):
            self.archive()
        self.owner.chmod(mode)

    def test_foreign_or_symlink_archive_is_preserved_and_never_overwritten(self):
        self.target.mkdir()
        (self.target / 'foreign').write_text('preserve')
        with self.assertRaises(MaintenanceControlError):
            self.archive()
        self.assertEqual((self.target / 'foreign').read_text(), 'preserve')
        (self.target / 'foreign').unlink()
        self.target.rmdir()
        self.target.symlink_to(self.owner.parent, target_is_directory=True)
        with self.assertRaises(MaintenanceControlError):
            self.archive()
        self.assertTrue(self.target.is_symlink())
        self.target.unlink()

    def test_corrupt_partial_intent_preserved(self):
        path = self.folder / 'owner-archive-intent.json'
        path.write_bytes(b'{partial')
        with self.assertRaises((ValueError, MaintenanceControlError)):
            self.archive()
        self.assertEqual(path.read_bytes(), b'{partial')

    def test_unjournaled_move_and_both_locations_missing_refuse(self):
        self.owner.parent.rename(self.target)
        with self.assertRaises(MaintenanceControlError):
            self.inspect()
        temporary = self.folder / 'unclassified-owner'
        self.target.rename(temporary)
        try:
            with self.assertRaises(MaintenanceControlError):
                self.inspect()
        finally:
            temporary.rename(self.target)

    def test_context_mutation_in_callback_refuses_before_move(self):
        def mutate(*args):
            self.current.write_text('foreign\n')
        try:
            with self.assertRaises(MaintenanceControlError):
                self.archive(admit=mutate)
            self.assertTrue(self.owner.exists())
        finally:
            self.current.write_bytes(self.old_current)

    def test_wrong_inherited_descriptor_refuses_even_if_other_fd_owns_flock(self):
        with self.archiver.lock.open('rb') as unrelated:
            bad = OwnerArchive(self.root, 'update-failed', unrelated.fileno())
            with self.assertRaises(MaintenanceControlError):
                bad.inspect('reconciliation-new', self.pin)
        self.assertEqual(self.inspect()['phase'], 'owner-live')

    def test_fsync_failure_after_move_classifies_and_explicit_retry_flushes(self):
        from atlas import deployment_owner_archive as archive_module
        original = archive_module.sync_directory
        def fail_after_move(path):
            if self.target.exists():
                raise OSError('fixture fsync')
            return original(path)
        with patch.object(archive_module, 'sync_directory', side_effect=fail_after_move):
            with self.assertRaises(MaintenanceControlError):
                self.archive()
        self.assertEqual(self.inspect()['phase'], 'moved-needs-parent-sync')
        self.assertFalse((self.folder / 'owner-archive-completed.json').exists())
        self.assertEqual(self.archive()['phase'], 'archived')

    def test_noreplace_rename_preserves_destination_created_after_admission(self):
        from atlas import deployment_owner_archive as archive_module
        original = archive_module._rename_directory
        def race(source, destination):
            destination.mkdir()
            (destination / 'foreign').write_text('preserve')
            return original(source, destination)
        try:
            with patch.object(archive_module, '_rename_directory', side_effect=race):
                with self.assertRaises(MaintenanceControlError):
                    self.archive()
            self.assertEqual((self.target / 'foreign').read_text(), 'preserve')
            self.assertTrue(self.owner.exists())
        finally:
            (self.target / 'foreign').unlink()
            self.target.rmdir()

    def test_visible_intent_flush_failure_never_moves_owner(self):
        from atlas import deployment_owner_archive as archive_module
        with patch.object(archive_module, 'sync_directory', side_effect=OSError('fixture fsync')):
            with self.assertRaises(MaintenanceControlError):
                self.archive()
        self.assertEqual(self.inspect()['phase'], 'intent-durable-owner-live')
        self.assertEqual(self.archive()['phase'], 'archived')

    def test_modified_completion_is_not_overwritten(self):
        self.archive()
        path = self.folder / 'owner-archive-completed.json'
        raw = path.read_bytes()
        path.write_bytes(b'{partial')
        with self.assertRaises((ValueError, MaintenanceControlError)):
            self.archive()
        self.assertEqual(path.read_bytes(), b'{partial')
        path.write_bytes(raw)

    def test_unexpected_journal_entry_is_preserved_and_refused(self):
        path = self.folder / 'foreign'
        path.write_text('preserve')
        with self.assertRaises(MaintenanceControlError):
            self.archive()
        self.assertEqual(path.read_text(), 'preserve')
        path.unlink()

    def test_sigkill_at_each_phase_is_inspectable_and_explicitly_resumable(self):
        stages = [('owner_archive_intent_durable', 'intent-durable-owner-live'),
                  ('owner_archive_directory_moved', 'moved-needs-parent-sync'),
                  ('owner_archive_parents_durable', 'moved-needs-parent-sync'),
                  ('owner_archive_completed_durable', 'archived')]
        for stage, expected in stages:
            with self.subTest(stage=stage):
                # Reset isolated fixture between independent interruption cases.
                if self.target.exists():
                    self.target.rename(self.owner.parent)
                for name in ('owner-archive-intent.json', 'owner-archive-completed.json'):
                    (self.folder / name).unlink(missing_ok=True)
                pid = os.fork()
                if pid == 0:
                    def kill(phase):
                        if phase == stage:
                            os.kill(os.getpid(), signal.SIGKILL)
                    self.archiver.checkpoint = kill
                    try:
                        self.archive()
                    finally:
                        os._exit(96)
                _, status = os.waitpid(pid, 0)
                self.assertTrue(os.WIFSIGNALED(status))
                self.assertEqual(self.inspect()['phase'], expected)
                self.assertEqual(self.archive()['phase'], 'archived')


if __name__ == '__main__':
    unittest.main()
