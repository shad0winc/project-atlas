"""Real unit files and source transitions; service/container operations are fixtures."""
import hashlib,os,signal,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from atlas.deployment_authority_unit import AuthorityUnitArtifact, AuthorityUnitRolloutAdapter
from atlas.deployment_component_rollout import ComponentRollout, SURFACES
from atlas.deployment_component_source import GenerationRolloutAdapter
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_component_source_adapter as source_fixture


def sha(raw):return hashlib.sha256(raw).hexdigest()


class RuntimeFixture(source_fixture.RuntimeFixture):
    def __init__(self,root,plan):
        super().__init__(root,plan);self.authority_stopped=True
    def authority_inactive(self):
        import json
        state=json.loads(self.state.read_bytes())
        service=next(e for e in self.plan['surfaces'] if e['name']=='authority-service')
        return self.authority_stopped and state['authority-service']['fingerprint']==service['before']['fingerprint']
    def verify(self,mode):
        import json
        state=json.loads(self.state.read_bytes())
        return self.verification and all(state[e['name']]['fingerprint']==
          (e['after'] if mode=='apply' else e['before']['fingerprint']) for e in self.plan['surfaces']
          if e['name'] not in ('source','authority-unit'))


class AuthorityUnitAdapterTests(unittest.TestCase):
    assert_boundary=source_fixture.SourceAdapterTests.assert_boundary
    writable=source_fixture.SourceAdapterTests.writable
    held=source_fixture.SourceAdapterTests.held
    def setUp(self):
        source_fixture.SourceAdapterTests.setUp(self)
        self.unit_directory=self.root/'systemd';self.unit_directory.mkdir(mode=0o700)
        self.proposal=self.root/'assets/authority.service'
        self.unit_bytes=b'[Unit]\nDescription=Private authority fixture\n[Service]\nExecStart=/usr/bin/false\n'
        self.proposal.write_bytes(self.unit_bytes)
        self.unit=AuthorityUnitArtifact(self.proposal,sha(self.unit_bytes),'unit-private',unit_directory=self.unit_directory)
        self.unit.prepare(held_guard=self.held)
        self.plan['rollout_id']='rollout-unit-private'
        self.plan['artifacts']['authority-unit']={'path':str(self.proposal),'sha256':sha(self.unit_bytes)}
        self.plan['surfaces'][1]['after']=self.unit.target_fingerprint
        self.runtime=RuntimeFixture(self.root,self.plan)
        self.inner=AuthorityUnitRolloutAdapter(self.unit,self.runtime,held_guard=self.held)
        self.adapter=GenerationRolloutAdapter(self.generation,self.inner,held_guard=self.held)
        self.engine=ComponentRollout(self.root,'original-failed',self.stream.fileno(),adapter=self.adapter)
        self.engine.prepare('rollout-unit-private',self.plan)
    def run_rollout(self,*,rollback=False):return self.engine.run('rollout-unit-private',rollback=rollback)
    def state(self):return self.engine.inspect_rollout('rollout-unit-private')
    def kill_unit(self,point,*,rollback=False):
        child=os.fork()
        if child==0:
            def hook(phase):
                if phase==point:os.kill(os.getpid(),signal.SIGKILL)
            self.unit.checkpoint=hook
            try:self.run_rollout(rollback=rollback)
            except BaseException:os._exit(3)
            os._exit(4)
        _,status=os.waitpid(child,0)
        self.assertTrue(os.WIFSIGNALED(status),status);self.assertEqual(os.WTERMSIG(status),signal.SIGKILL)
    def test_full_source_and_unit_roundtrip_preserves_inodes_and_evidence(self):
        source_inode=self.generation.staging.stat().st_ino;unit_inode=self.unit.staging.stat().st_ino
        self.assertTrue(self.run_rollout()['verified_held'])
        self.assertEqual(self.unit.target.stat().st_ino,unit_inode)
        self.assertEqual(self.unit.target.read_bytes(),self.unit_bytes)
        self.assertEqual(self.unit.target.stat().st_mode&0o777,0o644)
        self.assertEqual([a['surface'] for a in self.runtime.actions()],list(SURFACES[2:]))
        self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertFalse(self.unit.target.exists());self.assertEqual(self.unit.retained.stat().st_ino,unit_inode)
        self.assertEqual(self.generation.retained.stat().st_ino,source_inode)
        self.assertEqual([a['surface'] for a in self.runtime.actions()][4:],list(reversed(SURFACES[2:])))
        self.assertEqual(self.unit.retained.read_bytes(),self.unit_bytes)
    def test_interrupted_unit_publish_is_confirmed_before_journal_completion(self):
        self.kill_unit('unit-publish-renamed')
        self.assertEqual(self.state()['pending_outcome'],'applied')
        calls=[];original=self.unit._file
        def file(path,*,flush=False):
            if flush:calls.append(path)
            return original(path,flush=flush)
        with patch.object(self.unit,'_file',side_effect=file):self.assertTrue(self.run_rollout()['verified_held'])
        self.assertIn(self.unit.target,calls);self.assertEqual(len(self.runtime.actions()),4)
    def test_direction_change_confirms_visible_unit_before_reverse_rename(self):
        self.kill_unit('unit-publish-renamed')
        calls=[];original=self.unit._file
        def file(path,*,flush=False):
            if flush:calls.append(path)
            return original(path,flush=flush)
        with patch.object(self.unit,'_file',side_effect=file):self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertEqual(calls[0],self.unit.target);self.assertEqual(calls[-1],self.unit.retained)
        self.assertEqual(self.runtime.actions(),[])
    def test_interrupted_unit_retention_is_confirmed_without_restarting_services(self):
        self.run_rollout();self.kill_unit('unit-retain-renamed',rollback=True)
        self.assertEqual(self.state()['pending_outcome'],'applied')
        calls=[];original=self.unit._file
        def file(path,*,flush=False):
            if flush:calls.append(path)
            return original(path,flush=flush)
        with patch.object(self.unit,'_file',side_effect=file):self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertIn(self.unit.retained,calls);self.assertEqual(len(self.runtime.actions()),8)
    def test_fsync_uncertainty_preserves_unit_intent_and_blocks_later_actions(self):
        self.kill_unit('unit-publish-renamed')
        original=self.unit._file
        def file(path,*,flush=False):
            if flush:raise OSError('fixture fsync failure')
            return original(path,flush=flush)
        with patch.object(self.unit,'_file',side_effect=file),self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.state()['completed_surfaces'],['source']);self.assertEqual(self.runtime.actions(),[])
        self.assertTrue(self.run_rollout()['verified_held'])
    def test_active_authority_blocks_retention_and_source_removal(self):
        self.run_rollout();self.runtime.authority_stopped=False
        with self.assertRaisesRegex(MaintenanceControlError,'inactive_context_unproven'):self.run_rollout(rollback=True)
        self.assertTrue(self.unit.target.exists());self.assertTrue(self.generation.target.exists())
        self.runtime.authority_stopped=True;self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
    def test_unit_final_namespace_collision_is_preserved_and_refused(self):
        self.unit.target.write_bytes(b'foreign unit\n')
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.unit.target.read_bytes(),b'foreign unit\n');self.assertEqual(self.runtime.actions(),[])
    def test_symlink_and_hardlink_unit_files_are_refused(self):
        # Remove only this private fixture's prepared staging file.
        self.unit.staging.unlink();self.unit.staging.symlink_to(self.proposal)
        with self.assertRaises((MaintenanceControlError,OSError)):self.unit.inspect()
        self.unit.staging.unlink();os.link(self.proposal,self.unit.staging)
        with self.assertRaises(MaintenanceControlError):self.unit.inspect()
    def test_unit_mode_or_bytes_drift_is_refused(self):
        self.unit.staging.chmod(0o600)
        with self.assertRaises(MaintenanceControlError):self.unit.inspect()
        self.unit.staging.chmod(0o644);self.unit.staging.write_bytes(b'foreign\n')
        with self.assertRaises(MaintenanceControlError):self.unit.inspect()
    def test_missing_or_multiple_namespaces_are_not_repaired(self):
        self.unit.staging.unlink()
        with self.assertRaises(MaintenanceControlError):self.unit.inspect()
        self.unit.staging.write_bytes(self.unit_bytes);self.unit.retained.write_bytes(self.unit_bytes)
        with self.assertRaises(MaintenanceControlError):self.unit.prepare(held_guard=self.held)
        self.assertTrue(self.unit.retained.exists())
    def test_preparation_is_exact_idempotent_and_does_not_install_unit(self):
        inode=self.unit.staging.stat().st_ino
        self.unit.prepare(held_guard=self.held)
        self.assertEqual(self.unit.staging.stat().st_ino,inode);self.assertFalse(self.unit.target.exists())
        self.assertEqual(self.runtime.actions(),[])
    def test_partial_preparation_is_retained_and_refuses_retry(self):
        artifact=AuthorityUnitArtifact(self.proposal,sha(self.unit_bytes),'partial-unit',unit_directory=self.unit_directory)
        child=os.fork()
        if child==0:
            artifact.checkpoint=lambda phase:os.kill(os.getpid(),signal.SIGKILL) if phase=='unit-staging-created' else None
            artifact.prepare(held_guard=self.held);os._exit(4)
        _,status=os.waitpid(child,0);self.assertTrue(os.WIFSIGNALED(status))
        inode=artifact.staging.stat().st_ino
        with self.assertRaises(MaintenanceControlError):artifact.prepare(held_guard=self.held)
        self.assertEqual(artifact.staging.stat().st_ino,inode);self.assertEqual(artifact.staging.read_bytes(),b'')
    def test_proposal_mutation_refuses_before_unit_publication(self):
        self.proposal.write_bytes(b'changed proposal\n')
        with self.assertRaises(MaintenanceControlError):self.unit.publish(held_guard=self.held)
        self.assertFalse(self.unit.target.exists())
    def test_lost_hold_or_incomplete_runtime_adapter_refuses(self):
        with self.assertRaises(MaintenanceControlError):self.unit.publish(held_guard=lambda:False)
        with self.assertRaises(MaintenanceControlError):AuthorityUnitRolloutAdapter(self.unit,object(),held_guard=self.held)
        self.assertFalse(self.unit.target.exists())
    def test_rollback_without_published_unit_refuses(self):
        with self.assertRaises(MaintenanceControlError):self.unit.retain(held_guard=self.held,inactive_guard=lambda:True)
        self.assertTrue(self.unit.staging.exists())
    def test_retained_unit_cannot_be_republished_under_old_plan(self):
        self.run_rollout();self.run_rollout(rollback=True)
        with self.assertRaises(MaintenanceControlError):self.unit.publish(held_guard=self.held)
        self.assertTrue(self.unit.retained.exists())
    def test_accepted_proposal_bytes_roundtrip_in_private_directory(self):
        supplied=os.environ.get('ATLAS_UNIT_PROPOSAL_FIXTURE')
        raw=Path(supplied).read_bytes() if supplied else self.unit_bytes
        proposal=self.root/'assets/accepted.service';proposal.write_bytes(raw)
        with tempfile.TemporaryDirectory(dir=self.root) as folder:
            artifact=AuthorityUnitArtifact(proposal,sha(raw),'accepted-proposal',unit_directory=folder)
            artifact.prepare(held_guard=self.held);artifact.publish(held_guard=self.held)
            self.assertEqual(artifact.target.read_bytes(),raw)
            artifact.retain(held_guard=self.held,inactive_guard=lambda:True)
            self.assertEqual(artifact.retained.read_bytes(),raw)
    def test_foreign_unit_appearing_at_rename_is_never_overwritten(self):
        self.unit.checkpoint=lambda phase:self.unit.target.write_bytes(b'foreign-race\n') if phase=='before-unit-publish-rename' else None
        with self.assertRaises(OSError):self.unit.publish(held_guard=self.held)
        self.assertEqual(self.unit.target.read_bytes(),b'foreign-race\n')
        self.assertEqual(self.unit.staging.read_bytes(),self.unit_bytes)
    def test_foreign_retained_unit_appearing_at_rename_is_never_overwritten(self):
        self.unit.publish(held_guard=self.held)
        self.unit.checkpoint=lambda phase:self.unit.retained.write_bytes(b'foreign-retained\n') if phase=='before-unit-retain-rename' else None
        with self.assertRaises(OSError):self.unit.retain(held_guard=self.held,inactive_guard=lambda:True)
        self.assertEqual(self.unit.retained.read_bytes(),b'foreign-retained\n')
        self.assertEqual(self.unit.target.read_bytes(),self.unit_bytes)
    def test_directory_flush_failure_keeps_pending_until_explicit_confirmation(self):
        with patch('atlas.deployment_authority_unit.sync_directory',side_effect=OSError('fixture directory fsync')):
            with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.state()['pending_outcome'],'applied')
        self.assertEqual(self.state()['completed_surfaces'],['source'])
        self.assertEqual(self.runtime.actions(),[])
        self.assertTrue(self.run_rollout()['verified_held'])
    def test_complete_staging_before_directory_flush_can_resume_exactly(self):
        artifact=AuthorityUnitArtifact(self.proposal,sha(self.unit_bytes),'complete-staging',unit_directory=self.unit_directory)
        def hook(phase):
            if phase=='unit-staging-file-durable':raise OSError('fixture interrupted directory flush')
        artifact.checkpoint=hook
        with self.assertRaises(OSError):artifact.prepare(held_guard=self.held)
        inode=artifact.staging.stat().st_ino;artifact.checkpoint=lambda phase:None
        self.assertEqual(artifact.prepare(held_guard=self.held)['namespace'],'staged')
        self.assertEqual(artifact.staging.stat().st_ino,inode)
