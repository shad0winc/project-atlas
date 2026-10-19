"""Real immutable ownership plan under inherited flock; never retires a lock."""
import hashlib
import json
import os
import signal
import unittest
from unittest.mock import patch

from atlas.deployment_owner_preservation import OwnerPreservationPlan
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_private_acceptance_binding as binding


class OwnerPreservationTests(unittest.TestCase):
    reseal=binding.PrivateAcceptanceBindingTests.reseal
    shell=binding.PrivateAcceptanceBindingTests.shell
    check_hold=binding.PrivateAcceptanceBindingTests.check_hold
    logs=binding.PrivateAcceptanceBindingTests.logs

    def setUp(self):
        binding.PrivateAcceptanceBindingTests.setUp(self)
        attempt=self.acceptance.start('reconciliation-new',self.source,self.providers)
        self.logs(attempt)
        receipt=self.acceptance.finish('reconciliation-new',attempt.name)
        self.attempt=attempt.name;self.receipt_sha=hashlib.sha256(receipt.read_bytes()).hexdigest()
        self.plan=OwnerPreservationPlan(self.root,'update-failed',self.stream.fileno())
        # Use the actual collector loaded from the temporary clean canonical tree,
        # as in binding tests; only Docker inspect remains an external fixture.
        self.plan._source=self.acceptance._source
        self.plan._command=self.acceptance._command
        self.lock_inode=self.owner.parent.stat().st_ino;self.owner_inode=self.owner.stat().st_ino
        self.old_current=self.current.read_bytes()

    def tearDown(self):
        self.assertEqual(self.owner.parent.stat().st_ino,self.lock_inode)
        self.assertEqual(self.owner.stat().st_ino,self.owner_inode)
        self.assertEqual(self.current.read_bytes(),self.old_current)
        self.check_hold()
        binding.PrivateAcceptanceBindingTests.tearDown(self)

    def prepare(self):return self.plan.prepare('reconciliation-new',self.attempt,self.receipt_sha)

    def test_plan_binds_exact_owner_inventory_and_private_receipt_without_permission(self):
        path=self.prepare();raw=path.read_bytes();plan=json.loads(raw)
        self.assertEqual(plan['private_receipt_sha256'],self.receipt_sha)
        self.assertEqual(plan['original_lock_inventory']['directory']['inode'],self.lock_inode)
        self.assertEqual(plan['original_lock_inventory']['files']['owner']['inode'],self.owner_inode)
        for name in ('owner_release_permitted','ci_acceptance_proven','public_acceptance_proven','ordinary_reopening_permitted'):
            self.assertIs(plan[name],False)
        self.assertEqual(plan['archive_method_required'],'same-filesystem-whole-directory-rename-with-parent-fsync')
        self.assertFalse((self.folder/'original-update.lock').exists())
        self.assertEqual(self.prepare().read_bytes(),raw)
        self.assertEqual(self.plan.inspect_plan('reconciliation-new',self.attempt,self.receipt_sha),plan)

    def test_wrong_receipt_pin_and_stale_receipt_refuse_before_plan(self):
        with self.assertRaises(MaintenanceControlError):self.plan.prepare('reconciliation-new',self.attempt,'0'*64)
        with patch('atlas.deployment_private_acceptance.time.time',return_value=10**12):
            with self.assertRaises(MaintenanceControlError):self.prepare()
        self.assertFalse((self.folder/'owner-preservation.json').exists())

    def test_unexpected_lock_entry_is_preserved_and_refused(self):
        extra=self.owner.parent/'unexpected';extra.write_text('retain me')
        with self.assertRaises(MaintenanceControlError):self.prepare()
        self.assertEqual(extra.read_text(),'retain me');extra.unlink()
        self.assertFalse((self.folder/'owner-preservation.json').exists())

    def test_changed_owner_and_owner_mode_refuse(self):
        self.owner.write_bytes(self.owner_raw+b'changed=yes\n')
        with self.assertRaises(MaintenanceControlError):self.prepare()
        self.owner.write_bytes(self.owner_raw)
        old=self.owner.stat().st_mode & 0o777;self.owner.chmod(0o600 if old!=0o600 else 0o644)
        with self.assertRaises(MaintenanceControlError):self.prepare()
        self.owner.chmod(old)

    def test_existing_foreign_or_partial_plan_is_not_replaced(self):
        target=self.folder/'owner-preservation.json';target.write_bytes(b'{partial')
        with self.assertRaises(MaintenanceControlError):self.prepare()
        self.assertEqual(target.read_bytes(),b'{partial')

    def test_missing_held_boundary_refuses_even_after_private_success(self):
        path=self.folder/'held-boundary.json';raw=path.read_bytes();path.unlink()
        with self.assertRaises(MaintenanceControlError):self.prepare()
        path.write_bytes(raw)
        self.assertFalse((self.folder/'owner-preservation.json').exists())

    def test_replacement_runtime_invalidates_prepared_plan(self):
        path=self.prepare();raw=path.read_bytes();self.rows[0]['Id']='c'*64
        with self.assertRaises(MaintenanceControlError):self.plan.inspect_plan('reconciliation-new',self.attempt,self.receipt_sha)
        self.assertEqual(path.read_bytes(),raw)

    def test_unflushed_plan_failure_preserves_owner_and_can_retry_exact_bytes(self):
        from atlas import deployment_held_publication as held
        original=held.create_once
        def failed(path,raw):
            original(path,raw)
            if path.name=='owner-preservation.json':raise OSError('fixture fsync uncertainty')
        with patch.object(held,'create_once',side_effect=failed):
            with self.assertRaises(MaintenanceControlError):self.prepare()
        self.check_hold();self.assertTrue(self.prepare().is_file())

    def test_abrupt_exit_after_durable_plan_keeps_owner_and_exact_resume(self):
        pid=os.fork()
        if pid==0:
            self.plan.checkpoint=lambda stage:os.kill(os.getpid(),signal.SIGKILL)
            try:self.prepare()
            finally:os._exit(96)
        _,status=os.waitpid(pid,0);self.assertTrue(os.WIFSIGNALED(status));self.check_hold()
        path=self.prepare();before=path.read_bytes();self.assertEqual(self.prepare().read_bytes(),before)

    def test_inherited_exclusion_is_required(self):
        with (self.root/'deployment-scheduler.lock').open('rb') as unrelated:
            bad=OwnerPreservationPlan(self.root,'update-failed',unrelated.fileno())
            with self.assertRaises(MaintenanceControlError):bad.prepare('reconciliation-new',self.attempt,self.receipt_sha)
        self.assertFalse((self.folder/'owner-preservation.json').exists())


if __name__=='__main__':unittest.main()
