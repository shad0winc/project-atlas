"""A read-only history API cannot reopen completion or waive successor admission."""
from pathlib import Path
import unittest
from atlas.deployment_publication_completion import digest, identity, read
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_publication_maintenance_handoff as handoff

class SuccessorContinuityTests(unittest.TestCase):
    def setUp(self):
        self.f=handoff.HandoffTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.handoff()
        self.engine=self.f.engine;self.root=self.f.f.root;self.successor='sports-successor-fixture'
        records=self.root/'deployments/records'
        for name in (self.engine.publication,self.successor):
            p=records/name;p.mkdir(parents=True);(p/'MANIFEST.sha256').write_bytes((name+'-fixture-manifest\n').encode())
        self.proof=dict(previous_publication=self.engine.publication,successor_publication=self.successor,
            previous_manifest_sha256=digest((records/self.engine.publication/'MANIFEST.sha256').read_bytes()),
            successor_manifest_sha256=digest((records/self.successor/'MANIFEST.sha256').read_bytes()))
        self.calls=[]
        self.protected={str(p):identity(*reversed(read(p))) for p in self.engine.folder.iterdir() if p.is_file()}
        self.protected[str(self.engine.maintenance/'enabled')]=identity(*reversed(read(self.engine.maintenance/'enabled')))
        (self.root/'deployments/current').write_text(self.successor+'\n')
    def verify(self,previous,current):
        self.assertEqual((previous,current),(self.engine.publication,self.successor));self.calls.append('verified');return dict(self.proof)
    def inspect(self,verify=None):
        return self.engine.inspect_completed_history(self.f.f.plan,self.f.f.admission,self.successor,verify_successor=verify or self.verify)
    def test_archived_completion_is_verified_without_mutating_fences_or_flag(self):
        result=self.inspect();self.assertEqual(self.calls,['verified','verified'])
        self.assertEqual(result['phase'],'completed-maintenance-held');self.assertFalse(result['runtime_acceptance_granted'])
        self.assertFalse(result['production_execution_authorized']);self.assertFalse(result['public_reopen_permitted'])
        for name,expected in self.protected.items():self.assertEqual(identity(*reversed(read(Path(name)))),expected)
        self.assertFalse(self.engine.live.exists());self.assertFalse(self.engine.pending.exists())
    def test_normal_inspect_complete_and_handoff_do_not_adopt_successor(self):
        for callback in (lambda:self.engine.inspect(self.f.f.plan,self.f.f.admission),self.f.f.complete,self.f.handoff):
            with self.assertRaises(MaintenanceControlError):callback()
        self.assertFalse(self.engine.live.exists());self.assertFalse(self.engine.pending.exists())
    def test_bare_boolean_admission_is_not_a_successor_proof(self):
        with self.assertRaises(MaintenanceControlError):self.inspect(lambda *args:True)
    def test_wrong_manifest_or_successor_proof_refuses(self):
        for key,value in (('previous_publication','another-base'),('successor_publication','another-successor'),
                          ('previous_manifest_sha256','0'*64),('successor_manifest_sha256','0'*64)):
            proof=dict(self.proof);proof[key]=value
            with self.assertRaises(MaintenanceControlError):self.inspect(lambda *args:proof)
    def test_pointer_changed_during_verification_refuses(self):
        def change(*args):
            (self.root/'deployments/current').write_text('another-current\n');return dict(self.proof)
        with self.assertRaises(MaintenanceControlError):self.inspect(change)
    def test_incomplete_handoff_cannot_be_adopted_as_history(self):
        self.engine.handoff_completed.unlink()
        with self.assertRaises(MaintenanceControlError):self.inspect()
    def test_changed_archive_marker_refuses(self):
        self.engine.archived.write_bytes(b'changed')
        with self.assertRaises(MaintenanceControlError):self.inspect()
    def test_history_requires_inherited_exclusion(self):
        import fcntl
        fcntl.flock(self.f.f.fd,fcntl.LOCK_UN)
        with self.assertRaises(MaintenanceControlError):self.inspect()

if __name__=='__main__':unittest.main()
