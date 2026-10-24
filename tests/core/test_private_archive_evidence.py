"""Real native owner phases and historical-style private receipt validation.

Only Docker inventory/provider records are explicit local fixtures. Native
flocks, source Git, publication records, receipts and Linux owner renames are
real. Fixture admission is never production CI/external admission authority.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import unittest
from unittest.mock import patch

from atlas.deployment_private_archive_evidence import PrivateArchiveEvidence
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_owner_archive as archive_fixture


class PrivateArchiveEvidenceTests(unittest.TestCase):
    reseal = archive_fixture.OwnerArchiveTests.reseal
    shell = archive_fixture.OwnerArchiveTests.shell
    check_hold = archive_fixture.OwnerArchiveTests.check_hold
    logs = archive_fixture.OwnerArchiveTests.logs
    setUpFixture = archive_fixture.OwnerArchiveTests.setUp
    tearDown = archive_fixture.OwnerArchiveTests.tearDown

    def setUp(self):
        self.setUpFixture()
        self.validator = PrivateArchiveEvidence(self.acceptance, owner_probe=self.probe)

    def probe(self, publication, preservation_sha256):
        return self.archiver.inspect(publication, preservation_sha256)

    def validate(self):
        return self.validator.validate('reconciliation-new', self.attempt, self.receipt_sha, self.pin)

    def admit(self, evidence, phase):
        self.assertEqual(evidence, self.admission)
        result = self.validate()
        self.assertFalse(result['archive_permission_granted'])
        self.calls.append(result['owner_phase'])

    def archive(self):
        return self.archiver.archive('reconciliation-new', self.pin, self.admission, admit=self.admit)

    def inspect(self):
        return self.archiver.inspect('reconciliation-new', self.pin)

    def snapshot(self):
        return {str(path.relative_to(self.folder)):path.read_bytes()
                for path in self.folder.rglob('*') if path.is_file()}

    def interrupt(self, stage):
        def fail(phase):
            if phase == stage:
                raise OSError('fixture interruption')
        self.archiver.checkpoint = fail
        with self.assertRaises(MaintenanceControlError):
            self.archive()
        self.archiver.checkpoint = lambda phase:None

    def rewrite_receipt(self, change):
        path = self.folder / 'private-attempts' / self.attempt / 'receipt.json'
        value = json.loads(path.read_bytes());change(value)
        path.write_text(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n')
        self.receipt_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    def test_owner_live_proof_is_readonly_without_release_permission(self):
        before = self.snapshot();value = self.validate()
        self.assertEqual(value['owner_phase'],'owner-live')
        self.assertTrue(value['accepted_private'])
        for key in ('archive_permission_granted','owner_release_permitted','public_reopen_permitted',
                    'ci_acceptance_proven','external_admission_proven','full_rollout_inspection_proven',
                    'receipt_rewritten','owner_archive_performed'):
            self.assertIs(value[key],False)
        self.assertEqual(self.snapshot(),before)
        self.assertNotIn('SUPER_SECRET',json.dumps(value))

    def test_native_archive_revalidates_after_intent_appears(self):
        self.assertEqual(self.archive()['phase'],'archived')
        self.assertEqual(self.calls,['owner-live','intent-durable-owner-live'])
        self.assertEqual(self.validate()['owner_phase'],'archived')

    def test_owner_live_context_matches_original_native_validator(self):
        receipt=self.acceptance.validate('reconciliation-new',self.attempt,self.receipt_sha)
        from atlas.deployment_publication_journal import encoded
        value=self.validate()
        self.assertEqual(value['private_context_sha256'],hashlib.sha256(encoded(receipt['context'])).hexdigest())

    def test_new_private_attempt_preserves_old_receipt_and_original_plan(self):
        parent=self.folder/'private-attempts';old=parent/self.attempt
        old_bytes={p.name:p.read_bytes() for p in old.iterdir()}
        fresh=self.acceptance.start('reconciliation-new',self.source,self.providers)
        self.logs(fresh);receipt=self.acceptance.finish('reconciliation-new',fresh.name)
        self.attempt=fresh.name;self.receipt_sha=hashlib.sha256(receipt.read_bytes()).hexdigest()
        self.assertEqual(self.validate()['attempt'],fresh.name)
        self.assertEqual(self.archive()['phase'],'archived')
        self.assertEqual({p.name:p.read_bytes() for p in old.iterdir()},old_bytes)
        self.assertEqual((self.folder/'owner-preservation.json').read_bytes(),self.plan_raw)

    def test_durable_intent_phase_validates_and_resumes(self):
        self.interrupt('owner_archive_intent_durable')
        self.assertEqual(self.inspect()['phase'],'intent-durable-owner-live')
        # The original owner-live collector rejects new archive journal entries.
        with self.assertRaises(MaintenanceControlError):
            self.acceptance.validate('reconciliation-new',self.attempt,self.receipt_sha)
        before=self.snapshot();self.assertEqual(self.validate()['owner_phase'],'intent-durable-owner-live')
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.archive()['phase'],'archived')

    def test_moved_phase_validates_without_owner_live_replay(self):
        self.interrupt('owner_archive_directory_moved')
        self.assertEqual(self.inspect()['phase'],'moved-needs-parent-sync')
        self.acceptance._snapshot=lambda *args:(_ for _ in ()).throw(AssertionError('owner-live replay'))
        self.acceptance.validate=lambda *args:(_ for _ in ()).throw(AssertionError('owner-live replay'))
        before=self.snapshot();value=self.validate()
        self.assertEqual(value['owner_phase'],'moved-needs-parent-sync')
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.archive()['phase'],'archived')

    def test_expired_receipt_cannot_resume_moved_owner_or_refresh_evidence(self):
        self.interrupt('owner_archive_directory_moved');before=self.snapshot()
        with patch('atlas.deployment_private_archive_evidence.time.time',return_value=10**12):
            with self.assertRaises(MaintenanceControlError):self.validate()
            with self.assertRaises(MaintenanceControlError):self.archive()
        self.assertEqual(self.snapshot(),before)
        self.assertFalse((self.folder/'owner-archive-completed.json').exists())

    def test_completed_phase_still_requires_fresh_private_receipt(self):
        self.archive();before=self.snapshot()
        with patch('atlas.deployment_private_archive_evidence.time.monotonic',return_value=10**12):
            with self.assertRaises(MaintenanceControlError):self.validate()
        self.assertEqual(self.snapshot(),before)

    def test_each_sigkill_boundary_remains_validatable_without_rewrite(self):
        stages=(('owner_archive_intent_durable','intent-durable-owner-live'),
                ('owner_archive_directory_moved','moved-needs-parent-sync'),
                ('owner_archive_parents_durable','moved-needs-parent-sync'),
                ('owner_archive_completed_durable','archived'))
        for stage,phase in stages:
            with self.subTest(stage=stage):
                if self.target.exists():self.target.rename(self.owner.parent)
                for name in ('owner-archive-intent.json','owner-archive-completed.json'):
                    (self.folder/name).unlink(missing_ok=True)
                pid=os.fork()
                if pid==0:
                    self.archiver.checkpoint=lambda value:os.kill(os.getpid(),signal.SIGKILL) if value==stage else None
                    try:self.archive()
                    finally:os._exit(96)
                _,status=os.waitpid(pid,0);self.assertTrue(os.WIFSIGNALED(status))
                before=self.snapshot();self.assertEqual(self.validate()['owner_phase'],phase)
                self.assertEqual(self.snapshot(),before)
                self.assertEqual(self.archive()['phase'],'archived')

    def test_boolean_or_missing_owner_probe_refuses(self):
        with self.assertRaises(MaintenanceControlError):PrivateArchiveEvidence(self.acceptance,owner_probe=None)
        for value in (True,False,{},None):
            self.validator.owner_probe=lambda *args:value
            with self.assertRaises(MaintenanceControlError):self.validate()

    def test_owner_phase_change_during_validation_refuses(self):
        calls=[]
        def changed(*args):
            value=self.probe(*args);calls.append(value)
            if len(calls)>1:value['phase']='archived'
            return value
        self.validator.owner_probe=changed
        with self.assertRaises(MaintenanceControlError):self.validate()

    def test_unrelated_flock_fd_refuses_and_does_not_unlock_parent(self):
        original=self.acceptance.inherited_fd
        with self.archiver.lock.open('rb') as stream:
            self.acceptance.inherited_fd=stream.fileno()
            try:
                with self.assertRaises(MaintenanceControlError):self.validate()
            finally:self.acceptance.inherited_fd=original
        self.assertEqual(self.inspect()['phase'],'owner-live')

    def test_wrong_private_or_preservation_pin_refuses(self):
        for private,plan in (('0'*64,self.pin),(self.receipt_sha,'0'*64)):
            with self.assertRaises(MaintenanceControlError):
                self.validator.validate('reconciliation-new',self.attempt,private,plan)

    def test_reboot_and_clock_rollback_refuse(self):
        with patch.object(self.acceptance,'_boot',return_value='0'*64):
            with self.assertRaises(MaintenanceControlError):self.validate()
        with patch('atlas.deployment_private_archive_evidence.time.time',return_value=0):
            with self.assertRaises(MaintenanceControlError):self.validate()

    def test_nan_and_boolean_receipt_times_refuse(self):
        path=self.folder/'private-attempts'/self.attempt/'receipt.json';raw=path.read_bytes();pin=self.receipt_sha
        try:
            for value in (float('nan'),float('inf'),True):
                self.rewrite_receipt(lambda row:row.update(elapsed_seconds=value))
                with self.assertRaises(MaintenanceControlError):self.validate()
                path.write_bytes(raw);self.receipt_sha=pin
        finally:path.write_bytes(raw);self.receipt_sha=pin

    def test_context_runtime_restart_and_mount_drift_refuse(self):
        self.rows[0]['RestartCount']+=1
        with self.assertRaises(MaintenanceControlError):self.validate()
        self.rows[0]['RestartCount']-=1;self.rows[0]['Mounts'][0]['RW']=True
        with self.assertRaises(MaintenanceControlError):self.validate()

    def test_provider_unhealthy_refuses(self):
        raw=self.providers.read_bytes();value=json.loads(raw);value['fixture']['status']='unhealthy';self.providers.write_text(json.dumps(value))
        try:
            with self.assertRaises(MaintenanceControlError):self.validate()
        finally:self.providers.write_bytes(raw)

    def test_current_change_refuses(self):
        self.current.write_text('foreign\n')
        try:
            with self.assertRaises(MaintenanceControlError):self.validate()
        finally:self.current.write_bytes(self.old_current)

    def test_untracked_source_refuses(self):
        path=self.source/'foreign.py';path.write_text('foreign=True\n')
        try:
            with self.assertRaises(MaintenanceControlError):self.validate()
        finally:path.unlink()

    def test_logs_and_extra_attempt_file_refuse_without_deletion(self):
        path=self.folder/'private-attempts'/self.attempt;log=path/'verify.log';raw=log.read_bytes();log.write_bytes(raw+b'changed\n')
        try:
            with self.assertRaises(MaintenanceControlError):self.validate()
        finally:log.write_bytes(raw)
        extra=path/'foreign';extra.write_text('preserve')
        try:
            with self.assertRaises(MaintenanceControlError):self.validate()
            self.assertEqual(extra.read_text(),'preserve')
        finally:extra.unlink()

    def test_forged_receipt_log_pin_does_not_bypass_gate_semantics(self):
        path=self.folder/'private-attempts'/self.attempt;log=path/'doctor.log';raw=log.read_bytes();receipt=(path/'receipt.json').read_bytes();pin=self.receipt_sha
        log.write_text('  WARN runtime: bad\nOverall Status: HEALTHY\n')
        self.rewrite_receipt(lambda value:value['stages']['doctor'].update(log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        try:
            with self.assertRaises(MaintenanceControlError):self.validate()
        finally:log.write_bytes(raw);(path/'receipt.json').write_bytes(receipt);self.receipt_sha=pin

    def test_mutation_in_second_context_probe_is_detected(self):
        original=self.acceptance._runtime;calls=[]
        def changed(record):
            result=original(record);calls.append(result)
            if len(calls)==2:result['atlas-fixture']['restarts']+=1
            return result
        self.acceptance._runtime=changed
        with self.assertRaises(MaintenanceControlError):self.validate()


if __name__=='__main__':unittest.main()
