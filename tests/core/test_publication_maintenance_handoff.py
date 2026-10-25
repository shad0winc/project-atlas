"""Real filesystem and exclusion tests; no production admission is implied."""
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import unittest

from atlas.deployment_publication_completion import read,identity,encoded
from atlas.maintenance_control import MaintenanceAuthority,MaintenanceControlError

ROOT=Path(__file__).resolve().parents[2]
fixture_path=ROOT/'tests/core/test_publication_completion.py'
if not fixture_path.exists():
    fixture_path=ROOT.parent/'implementation/tests/core/test_publication_completion.py'
spec=importlib.util.spec_from_file_location('publication_handoff_fixture',fixture_path)
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PublicationCompletionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.complete();self.engine=self.f.engine;self.admission={'host_fixture':True};self.calls=[]
        self.original={p.name:p.read_bytes() for p in self.engine.folder.iterdir()}
        self.flag=identity(*reversed(read(self.engine.maintenance/'enabled')))
        self.fence=identity(*reversed(read(self.engine.pending)))
    def admit(self,plan,completion_admission,handoff_admission,state):
        self.assertEqual(plan,self.f.plan);self.assertEqual(completion_admission,self.f.admission)
        self.assertEqual(handoff_admission,self.admission);self.calls.append(state['phase'])
    def handoff(self):
        return self.engine.handoff(self.f.plan,self.f.admission,handoff_admission=self.admission,admit=self.admit)
    def test_success_preserves_enabled_and_both_archived_fences(self):
        result=self.handoff()
        self.assertEqual(result['phase'],'completed-maintenance-held')
        self.assertFalse(result['maintenance_handoff_pending']);self.assertFalse(result['public_reopen_permitted'])
        self.assertEqual(self.calls,['completed-maintenance-handoff-pending','handoff-intent-durable-fence-live','handoff-fence-archived-needs-completion'])
        self.assertEqual(identity(*reversed(read(self.engine.maintenance/'enabled'))),self.flag)
        self.assertEqual(identity(*reversed(read(self.engine.handoff_fence))),self.fence)
        self.assertFalse(self.engine.pending.exists());self.assertFalse(self.engine.live.exists())
        for name,raw in self.original.items():self.assertEqual((self.engine.folder/name).read_bytes(),raw)
    def test_native_status_returns_ordinary_enabled_maintenance_after_handoff(self):
        self.handoff();status=MaintenanceAuthority(self.f.root).status()
        self.assertEqual(status,{'enabled':True,'transition_pending':False,'recovery_held':False,'state_uncertain':False})
    def test_refusal_before_intent_preserves_original_fence(self):
        def refuse(*args):raise RuntimeError('refused')
        with self.assertRaises(RuntimeError):self.engine.handoff(self.f.plan,self.f.admission,handoff_admission=self.admission,admit=refuse)
        self.assertFalse(self.engine.handoff_intent.exists());self.assertTrue(self.engine.pending.exists())
    def test_refusal_at_second_callback_keeps_owned_live_fence(self):
        def refuse(*args):
            self.admit(*args)
            if len(self.calls)==2:raise RuntimeError('refused')
        with self.assertRaises(RuntimeError):self.engine.handoff(self.f.plan,self.f.admission,handoff_admission=self.admission,admit=refuse)
        self.assertTrue(self.engine.pending.exists());self.assertFalse(self.engine.handoff_fence.exists())
    def test_refusal_after_move_keeps_enabled_and_recoverable_phase(self):
        def refuse(*args):
            self.admit(*args)
            if len(self.calls)==3:raise RuntimeError('refused')
        with self.assertRaises(RuntimeError):self.engine.handoff(self.f.plan,self.f.admission,handoff_admission=self.admission,admit=refuse)
        self.assertEqual(self.engine.inspect(self.f.plan,self.f.admission)['phase'],'handoff-fence-archived-needs-completion')
        self.assertTrue((self.engine.maintenance/'enabled').exists())
    def test_interruption_at_each_checkpoint_can_resume_same_admission(self):
        for phase in ('handoff-intent-durable','handoff-fence-renamed','handoff-parents-durable','handoff-completion-durable'):
            with self.subTest(phase=phase):
                other=HandoffTests();other.setUp()
                try:
                    def stop(actual):
                        if actual==phase:raise RuntimeError('fixture interruption')
                    other.engine.checkpoint=stop
                    with self.assertRaises(RuntimeError):other.handoff()
                    self.assertTrue((other.engine.maintenance/'enabled').is_file())
                    other.engine.checkpoint=lambda phase:None
                    self.assertEqual(other.handoff()['phase'],'completed-maintenance-held')
                finally:other.doCleanups()
    def test_completion_retry_cannot_recreate_fence_after_handoff_started(self):
        def stop(phase):
            if phase=='handoff-fence-renamed':raise RuntimeError('stop')
        self.engine.checkpoint=stop
        with self.assertRaises(RuntimeError):self.handoff()
        with self.assertRaises(MaintenanceControlError):self.f.complete()
        self.assertFalse(self.engine.pending.exists())
    def test_completion_retry_cannot_recreate_fence_after_handoff_completed(self):
        self.handoff()
        with self.assertRaises(MaintenanceControlError):self.f.complete()
        self.assertFalse(self.engine.pending.exists())
    def test_changed_handoff_admission_cannot_adopt_durable_intent(self):
        self.handoff();self.admission={'foreign':True}
        with self.assertRaises(MaintenanceControlError):self.handoff()
    def test_changed_completion_admission_is_rejected(self):
        self.handoff()
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.f.plan,{'foreign':True})
    def test_replaced_enabled_inode_is_rejected_even_with_identical_bytes(self):
        self.handoff();path=self.engine.maintenance/'enabled';replacement=path.with_name('replacement')
        replacement.write_bytes(path.read_bytes());replacement.replace(path)
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.f.plan,self.f.admission)
    def test_duplicate_control_fence_is_rejected(self):
        self.handoff();self.engine.pending.write_bytes(self.engine.handoff_fence.read_bytes())
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.f.plan,self.f.admission)
    def test_missing_archived_control_fence_is_rejected(self):
        self.handoff();self.engine.handoff_fence.unlink()
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.f.plan,self.f.admission)
    def test_handoff_receipt_tampering_is_rejected(self):
        self.handoff();self.engine.handoff_completed.write_bytes(b'{}\n')
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.f.plan,self.f.admission)
    def test_shared_parent_descriptor_is_rejected(self):
        fcntl.flock(self.f.fd,fcntl.LOCK_UN);fcntl.flock(self.f.fd,fcntl.LOCK_SH)
        with self.assertRaises(MaintenanceControlError):self.handoff()
    def test_ordinary_disable_still_blocks_before_handoff(self):
        fcntl.flock(self.f.fd,fcntl.LOCK_UN)
        with self.assertRaises(MaintenanceControlError):MaintenanceAuthority(self.f.root).change(False,actor='fixture',source='cli')
    def test_unknown_completion_folder_entry_is_rejected(self):
        (self.engine.folder/'foreign').write_bytes(b'')
        with self.assertRaises(MaintenanceControlError):self.handoff()

if __name__=='__main__':unittest.main()
