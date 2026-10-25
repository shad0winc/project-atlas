import fcntl
import os
from pathlib import Path
import tempfile
import unittest

from atlas.deployment_publication_completion import PublicationCompletion, digest, encoded, identity, read
from atlas.maintenance_control import MaintenanceAuthority, MaintenanceControlError


class PublicationCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.publication='fixture-publication'
        maintenance=self.root/'maintenance';maintenance.mkdir()
        journal=self.root/'deployments/publication-journals'/self.publication;journal.mkdir(parents=True)
        (maintenance/'enabled').write_bytes(b'fixture-maintenance\n')
        (self.root/'deployments/current').write_bytes((self.publication+'\n').encode())
        intent=b'fixture original publication intent\n';(journal/'intent.json').write_bytes(intent)
        for name in ('owner-archive-intent.json','owner-archive-completed.json'):(journal/name).write_bytes(name.encode())
        marker=maintenance/'publication-pending';marker.write_bytes(encoded(dict(publication_id=self.publication,intent_sha256=digest(intent))))
        raw,info=read(marker)
        self.plan=dict(schema_version=1,publication_id=self.publication,marker=identity(info,raw),
            maintenance_flag_sha256=digest((maintenance/'enabled').read_bytes()),
            archive_intent_sha256=digest((journal/'owner-archive-intent.json').read_bytes()),
            archive_completed_sha256=digest((journal/'owner-archive-completed.json').read_bytes()))
        self.fd=os.open(self.root/'deployment-scheduler.lock',os.O_CREAT|os.O_RDWR,0o600)
        self.addCleanup(os.close,self.fd);fcntl.flock(self.fd,fcntl.LOCK_EX)
        self.engine=PublicationCompletion(self.root,self.publication,self.fd)
        self.admission={'fixture':True};self.calls=[]

    def admit(self,plan,admission,state):
        self.assertEqual(plan,self.plan);self.assertEqual(admission,self.admission)
        self.calls.append(state['phase'])

    def complete(self):
        return self.engine.complete(self.plan,self.admission,admit=self.admit)

    def test_success_preserves_inode_flag_and_retains_control_fence(self):
        state=self.complete()
        self.assertEqual(state['phase'],'completed-maintenance-handoff-pending')
        self.assertFalse(self.engine.live.exists())
        raw,info=read(self.engine.archived);self.assertEqual(identity(info,raw),self.plan['marker'])
        self.assertTrue(self.engine.pending.is_file())
        self.assertEqual((self.root/'maintenance/enabled').read_bytes(),b'fixture-maintenance\n')
        fcntl.flock(self.fd,fcntl.LOCK_UN)
        with self.assertRaises(MaintenanceControlError):
            MaintenanceAuthority(self.root).change(False,actor='fixture',source='cli')

    def test_interruption_recovery_at_each_checkpoint(self):
        for phase in ('intent-durable','control-fence-durable','marker-renamed','marker-parents-durable','completion-durable'):
            with self.subTest(phase=phase):
                # Independent real filesystem and flock fixture for each interruption.
                other=PublicationCompletionTests();other.setUp()
                try:
                    def stop(actual):
                        if actual==phase:raise RuntimeError('fixture interruption')
                    other.engine.checkpoint=stop
                    with self.assertRaises(RuntimeError):other.complete()
                    self.assertTrue((other.root/'maintenance/enabled').is_file())
                    other.engine.checkpoint=lambda phase:None
                    self.assertEqual(other.complete()['phase'],'completed-maintenance-handoff-pending')
                finally:other.doCleanups()

    def test_refusal_before_intent_does_not_move_marker(self):
        def refuse(*args):raise MaintenanceControlError('fixture refusal')
        with self.assertRaises(MaintenanceControlError):self.engine.complete(self.plan,self.admission,admit=refuse)
        self.assertTrue(self.engine.live.exists());self.assertFalse(self.engine.folder.exists())

    def test_refusal_after_durable_fence_keeps_marker_and_hold(self):
        calls=[]
        def refuse(plan,admission,state):
            calls.append(state)
            if len(calls)==2:raise MaintenanceControlError('fixture expired')
        with self.assertRaises(MaintenanceControlError):self.engine.complete(self.plan,self.admission,admit=refuse)
        self.assertTrue(self.engine.live.exists());self.assertTrue(self.engine.pending.exists())

    def test_changed_admission_cannot_adopt_existing_intent(self):
        self.complete()
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.plan,{'other':True})

    def test_nonexclusive_descriptor_is_rejected(self):
        fcntl.flock(self.fd,fcntl.LOCK_UN)
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.plan,self.admission)

    def test_existing_control_transition_is_not_overwritten(self):
        self.engine.pending.write_bytes(b'other-operation\n')
        with self.assertRaises(MaintenanceControlError):self.complete()
        self.assertEqual(self.engine.pending.read_bytes(),b'other-operation\n')
        self.assertTrue(self.engine.live.exists())

    def test_generic_hold_repair_cannot_clear_completion_fence(self):
        self.complete()
        original=self.engine.pending.read_bytes()
        fcntl.flock(self.fd,fcntl.LOCK_UN)
        with self.assertRaisesRegex(MaintenanceControlError,'publication_completion_requires_host_handoff'):
            MaintenanceAuthority(self.root).recover_hold(actor='fixture')
        self.assertEqual(self.engine.pending.read_bytes(),original)
        self.assertTrue((self.root/'maintenance/enabled').is_file())

    def test_marker_symlink_and_duplicate_location_are_rejected(self):
        self.complete()
        self.engine.live.symlink_to(self.engine.archived)
        with self.assertRaises(MaintenanceControlError):self.engine.inspect(self.plan,self.admission)


if __name__=='__main__':unittest.main()
