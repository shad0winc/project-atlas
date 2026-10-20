"""Actual source transitions under the real inherited flock and rollout journal."""
import hashlib,io,json,os,signal,tarfile,unittest
from unittest.mock import patch
from atlas.deployment_component_rollout import ComponentRollout, SURFACES
from atlas.deployment_component_source import GenerationRolloutAdapter
from atlas.deployment_immutable_generation import ImmutableGeneration, tree_oid
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_component_rollout_journal as journal_fixture
from tests.core.test_component_rollout_journal import FixtureAdapter


def sha(raw):return hashlib.sha256(raw).hexdigest()


class RuntimeFixture(FixtureAdapter):
    def __init__(self, root, plan):
        super().__init__(root,plan);self.inactive=True;self.confirm_error=False
    def source_inactive(self):
        if not self.inactive:return False
        state=json.loads(self.state.read_bytes())
        return all(state[e['name']]['fingerprint']==e['before']['fingerprint']
                   for e in self.plan['surfaces'] if e['name']!='source')
    def confirm(self,name,mode,expected):
        if self.confirm_error:raise OSError('fixture-confirmation-failure')
        return self.observe(name)
    def verify(self,mode):
        state=json.loads(self.state.read_bytes())
        return self.verification and all(state[e['name']]['fingerprint']==
            (e['after'] if mode=='apply' else e['before']['fingerprint'])
            for e in self.plan['surfaces'] if e['name']!='source')


class SourceAdapterTests(unittest.TestCase):
    assert_boundary=journal_fixture.ComponentRolloutTests.assert_boundary
    def setUp(self):
        journal_fixture.ComponentRolloutTests.setUp(self)
        self.addCleanup(self.writable)
        (self.root/'deployments/repairs').mkdir(mode=0o700)
        self.archive=self.root/'assets/application.tar.gz'
        contents={'atlas/example.py':(b'pass\n',0o644),'scripts/run':(b'#!/bin/sh\n',0o755)}
        commit='a'*40
        with tarfile.open(self.archive,'w:gz',format=tarfile.PAX_FORMAT,pax_headers={'comment':commit}) as archive:
            for name,(raw,mode) in contents.items():
                member=tarfile.TarInfo(name);member.mode=mode;member.size=len(raw);archive.addfile(member,io.BytesIO(raw))
        tree=tree_oid({name:{'oid':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                      'executable':bool(mode&0o111)} for name,(raw,mode) in contents.items()})
        self.generation=ImmutableGeneration(self.root,'source-private',self.archive,sha(self.archive.read_bytes()),commit,tree)
        self.generation.prepare()
        self.plan['generation']=str(self.generation.target)
        self.plan['artifacts']['source-archive']={'path':str(self.archive),'sha256':sha(self.archive.read_bytes())}
        self.runtime=RuntimeFixture(self.root,self.plan)
        self.adapter=GenerationRolloutAdapter(self.generation,self.runtime,held_guard=self.held)
        self.plan['surfaces'][0]['after']=self.adapter.target_fingerprint
        self.engine=ComponentRollout(self.root,'original-failed',self.stream.fileno(),adapter=self.adapter)
        self.engine.prepare('rollout-private',self.plan)
    def writable(self):
        for parent,dirs,files in os.walk(self.root):
            os.chmod(parent,0o700)
    def held(self):
        return all(path.read_bytes()==raw and path.stat().st_ino==inode
                   for path,(raw,inode) in self.boundary.items())
    def state(self):return self.engine.inspect_rollout('rollout-private')
    def kill_at(self,point,*,rollback=False,generation=False):
        child=os.fork()
        if child==0:
            def hook(phase):
                if phase==point:os.kill(os.getpid(),signal.SIGKILL)
            if generation:self.generation.checkpoint=hook
            else:self.engine.checkpoint=hook
            try:self.engine.run('rollout-private',rollback=rollback)
            except BaseException:os._exit(3)
            os._exit(4)
        _,status=os.waitpid(child,0)
        self.assertTrue(os.WIFSIGNALED(status),status)
        self.assertEqual(os.WTERMSIG(status),signal.SIGKILL)
    def test_real_source_publish_and_retained_rollback_keep_same_inode_and_owner(self):
        inode=self.generation.staging.stat().st_ino
        self.assertTrue(self.engine.run('rollout-private')['verified_held'])
        self.assertEqual(self.generation.target.stat().st_ino,inode)
        self.assertEqual([v['surface'] for v in self.runtime.actions()],list(SURFACES[1:]))
        result=self.engine.run('rollout-private',rollback=True)
        self.assertTrue(result['verified_held']);self.assertFalse(result['owner_release_permitted'])
        self.assertEqual(self.generation.retained.stat().st_ino,inode)
        self.assertFalse(self.generation.target.exists());self.assertTrue(self.generation.marker.exists())
        self.assertEqual([v['surface'] for v in self.runtime.actions()][5:],list(reversed(SURFACES[1:])))
    def test_kill_after_source_rename_adopts_only_after_reflush(self):
        self.kill_at('source-renamed',generation=True)
        self.assertEqual(self.state()['pending_outcome'],'applied')
        flushed=[]
        original=self.generation._flush
        def flush(path):flushed.append(path);return original(path)
        with patch.object(self.generation,'_flush',side_effect=flush):
            self.assertTrue(self.engine.run('rollout-private')['verified_held'])
        self.assertIn(self.generation.target,flushed)
        self.assertEqual(len(self.runtime.actions()),5)
    def test_reverse_request_after_interrupted_source_publish_confirms_before_retaining(self):
        self.kill_at('source-renamed',generation=True)
        flushed=[];original=self.generation._flush
        def flush(path):flushed.append(path);return original(path)
        with patch.object(self.generation,'_flush',side_effect=flush):
            self.assertTrue(self.engine.run('rollout-private',rollback=True)['verified_held'])
        self.assertEqual(flushed[0],self.generation.target)
        self.assertEqual(flushed[-1],self.generation.retained)
        self.assertEqual(self.runtime.actions(),[])
    def test_confirmation_fsync_failure_keeps_pending_and_refuses_blind_completion(self):
        self.kill_at('source-renamed',generation=True)
        with patch.object(self.generation,'_flush',side_effect=OSError('fixture fsync error')):
            with self.assertRaises(MaintenanceControlError):self.engine.run('rollout-private')
        self.assertEqual(self.state()['pending_outcome'],'applied')
        self.assertEqual(self.state()['completed_surfaces'],[])
        self.assertEqual(self.runtime.actions(),[])
        self.assertTrue(self.engine.run('rollout-private')['verified_held'])
    def test_retain_kill_is_reflushed_and_adopted_without_deleting_source(self):
        self.engine.run('rollout-private')
        self.kill_at('source-retained-renamed',rollback=True,generation=True)
        self.assertEqual(self.state()['pending_outcome'],'applied')
        flushed=[];original=self.generation._flush
        def flush(path):flushed.append(path);return original(path)
        with patch.object(self.generation,'_flush',side_effect=flush):
            self.assertTrue(self.engine.run('rollout-private',rollback=True)['verified_held'])
        self.assertIn(self.generation.retained,flushed)
        self.assertTrue(self.generation.retained.exists())
    def test_live_source_reference_blocks_retention_and_preserves_pending(self):
        self.engine.run('rollout-private');self.runtime.inactive=False
        with self.assertRaisesRegex(MaintenanceControlError,'inactive_context_unproven'):
            self.engine.run('rollout-private',rollback=True)
        self.assertTrue(self.generation.target.exists());self.assertFalse(self.generation.retained.exists())
        self.runtime.inactive=True
        self.assertTrue(self.engine.run('rollout-private',rollback=True)['verified_held'])
    def test_foreign_final_namespace_refuses_without_runtime_action(self):
        self.generation.target.mkdir(mode=0o555)
        with self.assertRaises(MaintenanceControlError):self.engine.run('rollout-private')
        self.assertEqual(self.runtime.actions(),[])
    def test_source_mutation_refuses_even_with_published_namespace(self):
        self.kill_at('source-renamed',generation=True)
        file=self.generation.target/'atlas/example.py';file.chmod(0o644);file.write_bytes(b'other\n');file.chmod(0o444)
        with self.assertRaises(MaintenanceControlError):self.engine.run('rollout-private')
        self.assertEqual(self.runtime.actions(),[])
    def test_runtime_confirmation_failure_never_marks_surface_complete(self):
        self.runtime.confirm_error=True
        with self.assertRaises(MaintenanceControlError):self.engine.run('rollout-private')
        self.assertEqual(self.state()['completed_surfaces'],['source'])
        self.runtime.confirm_error=False
        self.assertTrue(self.engine.run('rollout-private')['verified_held'])
        self.assertEqual(len(self.runtime.actions()),5)
    def test_runtime_confirmation_identity_change_refuses(self):
        self.runtime.confirm=lambda *args:{'fingerprint':'f'*64,'identity':'e'*64}
        with self.assertRaises(MaintenanceControlError):self.engine.run('rollout-private')
        self.assertEqual(self.state()['completed_surfaces'],['source'])
    def test_lost_hold_blocks_source_and_runtime_actions(self):
        self.adapter.held_guard=lambda:False
        with self.assertRaises(MaintenanceControlError):self.engine.run('rollout-private')
        self.assertFalse(self.generation.target.exists());self.assertEqual(self.runtime.actions(),[])
    def test_incomplete_runtime_adapter_is_rejected_before_source_publication(self):
        with self.assertRaises(MaintenanceControlError):
            GenerationRolloutAdapter(self.generation,object(),held_guard=self.held)
        self.assertFalse(self.generation.target.exists())
    def test_unknown_surface_and_mode_refuse(self):
        for method in (self.adapter.observe,self.adapter.apply,self.adapter.rollback):
            with self.assertRaises(MaintenanceControlError):method('identity-writer')
        with self.assertRaises(MaintenanceControlError):self.adapter.verify('reopen')
        self.assertFalse(self.generation.target.exists())
