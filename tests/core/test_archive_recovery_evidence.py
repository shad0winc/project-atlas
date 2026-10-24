"""Distinct fresh recovery receipts; real native flocks and owner moves.

Admission callbacks below are explicitly fixture-only. CI, external admission
and production driver provenance are never conferred by these tests.
"""
import hashlib
import json
import os
import unittest
from unittest.mock import patch
from atlas.deployment_archive_recovery_evidence import ArchiveRecoveryEvidence
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_private_archive_evidence as fixtures


class ArchiveRecoveryEvidenceTests(unittest.TestCase):
    reseal=fixtures.PrivateArchiveEvidenceTests.reseal; shell=fixtures.PrivateArchiveEvidenceTests.shell; check_hold=fixtures.PrivateArchiveEvidenceTests.check_hold; logs=fixtures.PrivateArchiveEvidenceTests.logs
    setUpFixture=fixtures.PrivateArchiveEvidenceTests.setUpFixture; tearDown=fixtures.PrivateArchiveEvidenceTests.tearDown; probe=fixtures.PrivateArchiveEvidenceTests.probe
    snapshot=fixtures.PrivateArchiveEvidenceTests.snapshot

    def setUp(self):
        fixtures.PrivateArchiveEvidenceTests.setUp(self)
        self.recovery=ArchiveRecoveryEvidence(self.validator)
        self.original={p.name:p.read_bytes() for p in (self.folder/'private-attempts'/self.attempt).iterdir()}

    def make_journal(self, stage='owner_archive_directory_moved', declared=True):
        if declared:self.admission['recovery_evidence']=self.recovery.declaration('reconciliation-new',self.pin)
        def interrupt(phase):
            if phase==stage:raise OSError('fixture interruption')
        self.archiver.checkpoint=interrupt
        if stage:
            with self.assertRaises(MaintenanceControlError):
                self.archiver.archive('reconciliation-new',self.pin,self.admission,admit=lambda *args:None)
        else:self.archiver.archive('reconciliation-new',self.pin,self.admission,admit=lambda *args:None)
        self.archiver.checkpoint=lambda phase:None
        self.intent_pin=hashlib.sha256((self.folder/'owner-archive-intent.json').read_bytes()).hexdigest()

    def start(self):
        return self.recovery.start('reconciliation-new',self.pin,self.intent_pin,self.source,self.providers)

    def finish(self,path):
        return self.recovery.finish('reconciliation-new',path.name,self.pin,self.intent_pin)

    def validate(self,path):
        return self.recovery.validate('reconciliation-new',path.name,self.pin,self.intent_pin,hashlib.sha256((path/'receipt.json').read_bytes()).hexdigest())

    def preserved(self):
        self.assertEqual((self.folder/'owner-preservation.json').read_bytes(),self.plan_raw)
        self.assertEqual({p.name:p.read_bytes() for p in (self.folder/'private-attempts'/self.attempt).iterdir()},self.original)
        self.assertEqual(hashlib.sha256((self.folder/'owner-archive-intent.json').read_bytes()).hexdigest(),self.intent_pin)

    def test_unjournaled_owner_live_refuses_before_attempt(self):
        before=self.snapshot()
        with self.assertRaises(MaintenanceControlError):
            self.recovery.start('reconciliation-new',self.pin,'0'*64,self.source,self.providers)
        self.assertEqual(self.snapshot(),before)

    def test_undeclared_recovery_refuses_without_retrofitting_intent(self):
        self.make_journal(declared=False);before=self.snapshot()
        with self.assertRaises(MaintenanceControlError):self.start()
        self.assertEqual(self.snapshot(),before);self.preserved()

    def test_all_three_journaled_phases_have_distinct_readonly_acceptance(self):
        for stage,expected in (('owner_archive_intent_durable','intent-durable-owner-live'),('owner_archive_directory_moved','moved-needs-parent-sync'),(None,'archived')):
            with self.subTest(phase=expected):
                if self.target.exists():self.target.rename(self.owner.parent)
                for name in ('owner-archive-intent.json','owner-archive-completed.json'):(self.folder/name).unlink(missing_ok=True)
                self.make_journal(stage);path=self.start();self.logs(path);self.finish(path);before=self.snapshot();value=self.validate(path)
                self.assertEqual(value['scope'],'fresh-held-archive-recovery-evidence');self.assertTrue(value['accepted_recovery'])
                self.assertEqual(value['owner_phase']['phase'],expected);self.assertNotIn('accepted_private',value)
                for key in ('original_receipts_rewritten','archive_permission_granted','owner_release_permitted','public_reopen_permitted','ci_acceptance_proven','external_admission_proven'):self.assertIs(value[key],False)
                self.assertNotIn('SUPER_SECRET',json.dumps(value));self.assertEqual(self.snapshot(),before);self.preserved()

    def test_expired_original_private_is_not_refreshed_by_new_recovery(self):
        self.make_journal()
        with patch('atlas.deployment_private_archive_evidence.time.time',return_value=10**12):
            with self.assertRaises(MaintenanceControlError):self.validator.validate('reconciliation-new',self.attempt,self.receipt_sha,self.pin)
        path=self.start();self.logs(path);self.finish(path);self.assertTrue(self.validate(path)['accepted_recovery']);self.preserved()

    def test_expired_recovery_cannot_finish_or_validate(self):
        self.make_journal();path=self.start();self.logs(path)
        self.recovery.maximum_age=3600
        with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.recovery.maximum_age=300
        with patch('atlas.deployment_archive_recovery_evidence.time.time',return_value=10**12):
            with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.assertFalse((path/'receipt.json').exists());self.finish(path);before=self.snapshot()
        with patch('atlas.deployment_archive_recovery_evidence.time.monotonic',return_value=10**12):
            with self.assertRaises(MaintenanceControlError):self.validate(path)
        self.assertEqual(self.snapshot(),before);self.preserved()

    def test_failed_warn_or_forged_verify_gates_never_publish_acceptance(self):
        self.make_journal();path=self.start()
        for stage,text in (('doctor','  WARN runtime: bad\nOverall Status: HEALTHY\n'),('verify','FAIL fixture\nOverall Status: PASS\n')):
            self.logs(path);(path/(stage+'.log')).write_text(text)
            with self.assertRaises(MaintenanceControlError):self.finish(path)
            self.assertFalse((path/'receipt.json').exists())
        self.logs(path);(path/'runtime.exit').write_text('1\n')
        with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.assertFalse((path/'receipt.json').exists());self.preserved()

    def test_runtime_source_provider_and_boot_drift_refuse(self):
        self.make_journal();path=self.start();self.logs(path)
        self.rows[0]['RestartCount']+=1
        with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.rows[0]['RestartCount']-=1
        with patch.object(self.acceptance,'_boot',return_value='0'*64):
            with self.assertRaises(MaintenanceControlError):self.finish(path)
        extra=self.source/'foreign.py';extra.write_text('foreign=True\n')
        try:
            with self.assertRaises(MaintenanceControlError):self.finish(path)
        finally:extra.unlink()
        raw=self.providers.read_bytes();value=json.loads(raw);value['fixture']['status']='unhealthy';self.providers.write_text(json.dumps(value))
        try:
            with self.assertRaises(MaintenanceControlError):self.finish(path)
        finally:self.providers.write_bytes(raw)
        self.assertFalse((path/'receipt.json').exists());self.preserved()

    def test_native_phase_change_during_gates_refuses(self):
        self.make_journal('owner_archive_intent_durable');path=self.start();self.logs(path)
        self.archiver.archive('reconciliation-new',self.pin,self.admission,admit=lambda *args:None)
        with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.assertFalse((path/'receipt.json').exists());self.preserved()

    def test_wrong_inherited_fd_refuses_and_leaves_parent_exclusion(self):
        self.make_journal();original=self.acceptance.inherited_fd
        with self.archiver.lock.open('rb') as other:
            self.acceptance.inherited_fd=other.fileno()
            try:
                with self.assertRaises(MaintenanceControlError):self.start()
            finally:self.acceptance.inherited_fd=original
        self.archiver.inspect('reconciliation-new',self.pin);self.preserved()

    def test_wrong_intent_pin_and_extra_attempt_entry_refuse(self):
        self.make_journal()
        with self.assertRaises(MaintenanceControlError):self.recovery.start('reconciliation-new',self.pin,'0'*64,self.source,self.providers)
        path=self.start();self.logs(path);extra=path/'foreign';extra.write_text('preserve')
        with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.assertEqual(extra.read_text(),'preserve');self.preserved()

    def test_receipt_and_log_tampering_refuse_without_overwrite(self):
        self.make_journal();path=self.start();self.logs(path);self.finish(path);raw=(path/'receipt.json').read_bytes()
        value=json.loads(raw);value['archive_permission_granted']=True;(path/'receipt.json').write_text(json.dumps(value))
        with self.assertRaises(MaintenanceControlError):self.validate(path)
        (path/'receipt.json').write_bytes(raw);(path/'verify.log').write_text('changed\nOverall Status: PASS\n')
        with self.assertRaises(MaintenanceControlError):self.validate(path)
        with self.assertRaises((MaintenanceControlError,FileExistsError)):self.finish(path)
        self.assertEqual((path/'receipt.json').read_bytes(),raw);self.preserved()

    def test_recovery_module_provenance_is_bound(self):
        self.make_journal();path=self.start();self.logs(path)
        with patch.object(self.recovery,'_implementation',return_value={'recovery_sha256':'0'*64,'policy_sha256':'0'*64}):
            with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.assertFalse((path/'receipt.json').exists());self.preserved()

    def test_fsync_failure_leaves_originals_and_no_accepted_receipt(self):
        self.make_journal();path=self.start();self.logs(path)
        with patch('os.fsync',side_effect=OSError('fixture durability failure')):
            with self.assertRaises(MaintenanceControlError):self.finish(path)
        self.assertFalse((path/'receipt.json').exists());self.preserved()
        self.finish(path);before=self.snapshot()
        with patch('os.fsync',side_effect=OSError('fixture visible receipt flush failure')):
            with self.assertRaises(MaintenanceControlError):self.validate(path)
        self.assertEqual(self.snapshot(),before);self.assertTrue(self.validate(path)['accepted_recovery'])


if __name__=='__main__':unittest.main()
