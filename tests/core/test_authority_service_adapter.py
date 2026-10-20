"""Journal/service command contracts with file-backed systemd fixtures, not host systemd."""
import copy,json,os,signal,subprocess,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from atlas.deployment_authority_service import AuthorityServiceLifecycle, AuthorityServiceRolloutAdapter, NativeAuthorityProbe, AuthoritySocketNotReady
from atlas.deployment_authority_unit import AuthorityUnitRolloutAdapter, UNIT_NAME
from atlas.deployment_component_rollout import ComponentRollout,digest
from atlas.deployment_component_source import GenerationRolloutAdapter
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_authority_unit_adapter as unit_fixture

ABSENT={'fingerprint':'absent','identity':'absent'}


class Components(unit_fixture.RuntimeFixture):
    def verify(self,mode):
        state=json.loads(self.state.read_bytes())
        return self.verification and all(state[e['name']]['fingerprint']==
          (e['after'] if mode=='apply' else e['before']['fingerprint']) for e in self.plan['surfaces']
          if e['name'] in ('api','portal','caddy'))


class SystemdFixture:
    """State and command log survive a killed controller; no subprocess is launched."""
    def __init__(self,root,unit,generation):
        self.root,self.unit,self.generation=root,unit,generation
        self.state=root/'systemd-state.json';self.log=root/'systemd-commands.jsonl'
        self.state.write_text(json.dumps({'active':False,'identity':None,'loaded':False}))
        self.log.write_bytes(b'');self.unsafe=False;self.fail_after_start=False;self.socket_pending=0
        self.target_fingerprint=digest({'unit':unit.target_fingerprint,'source':str(generation.target)})
        self.before_command=None
    def get(self):return json.loads(self.state.read_bytes())
    def put(self,state):
        path=self.state.with_suffix('.tmp');path.write_text(json.dumps(state));os.replace(path,self.state)
    def preflight(self,*,require_unit=False):
        if self.unsafe:raise MaintenanceControlError('fixture override or enabled unit')
        if require_unit and self.unit.inspect()['namespace']!='published':raise MaintenanceControlError('fixture unit absent')
        if self.before_command:
            callback=self.before_command;self.before_command=None;callback()
        return self.get()
    def observe(self):
        self.preflight();state=self.get()
        if not state['active']:return dict(ABSENT)
        if self.socket_pending:
            self.socket_pending-=1;raise AuthoritySocketNotReady('fixture socket pending')
        if self.unit.inspect()['namespace']!='published' or self.generation.inspect()['namespace']!='published':
            raise MaintenanceControlError('fixture live authority source or unit missing')
        return {'fingerprint':self.target_fingerprint,'identity':state['identity']}
    def removed(self):return not self.unit.target.exists() and not self.get()['loaded'] and self.observe()==ABSENT
    def execute(self,command):
        prefix=['/usr/bin/systemctl','--system','--no-ask-password','--no-pager']
        assert command[:4]==prefix
        operation=command[4]
        assert operation in ('daemon-reload','start','stop')
        assert command[5:]==([] if operation=='daemon-reload' else [UNIT_NAME])
        with self.log.open('ab') as output:
            output.write((json.dumps(command)+'\n').encode());output.flush();os.fsync(output.fileno())
        state=self.get()
        if operation=='daemon-reload':state['loaded']=self.unit.target.exists()
        elif operation=='start':state.update(active=True,identity=digest({'nonce':os.urandom(16).hex()}))
        else:state.update(active=False,identity=None)
        self.put(state)
        return not (self.fail_after_start and operation=='start')
    def commands(self):return [json.loads(line) for line in self.log.read_text().splitlines()]


class AuthorityServiceAdapterTests(unittest.TestCase):
    assert_boundary=unit_fixture.AuthorityUnitAdapterTests.assert_boundary
    writable=unit_fixture.AuthorityUnitAdapterTests.writable
    held=unit_fixture.AuthorityUnitAdapterTests.held
    def setUp(self):
        unit_fixture.AuthorityUnitAdapterTests.setUp(self)
        self.plan['rollout_id']='rollout-service-private'
        self.systemd=SystemdFixture(self.root,self.unit,self.generation)
        self.plan['surfaces'][2]['before']=dict(ABSENT)
        self.plan['surfaces'][2]['after']=self.systemd.target_fingerprint
        self.components=Components(self.root,self.plan)
        self.lifecycle=AuthorityServiceLifecycle(self.systemd,held_guard=self.held,execute=self.systemd.execute,startup_timeout=0.2)
        self.service_adapter=AuthorityServiceRolloutAdapter(self.lifecycle,self.components,held_guard=self.held)
        self.inner=AuthorityUnitRolloutAdapter(self.unit,self.service_adapter,held_guard=self.held)
        self.adapter=GenerationRolloutAdapter(self.generation,self.inner,held_guard=self.held)
        self.engine=ComponentRollout(self.root,'original-failed',self.stream.fileno(),adapter=self.adapter)
        self.engine.prepare('rollout-service-private',self.plan)
    def run_rollout(self,*,rollback=False):return self.engine.run('rollout-service-private',rollback=rollback)
    def state(self):return self.engine.inspect_rollout('rollout-service-private')
    def kill_at(self,point,*,rollback=False,unit=False):
        child=os.fork()
        if child==0:
            def hook(phase):
                if phase==point:os.kill(os.getpid(),signal.SIGKILL)
            if unit:self.unit.checkpoint=hook
            else:self.engine.checkpoint=hook
            try:self.run_rollout(rollback=rollback)
            except BaseException:os._exit(3)
            os._exit(4)
        _,status=os.waitpid(child,0)
        self.assertTrue(os.WIFSIGNALED(status),status);self.assertEqual(os.WTERMSIG(status),signal.SIGKILL)
    def test_full_held_rollout_and_reverse_order_restore_manager_after_unit_retention(self):
        self.assertTrue(self.run_rollout()['verified_held'])
        self.assertTrue(self.systemd.get()['active']);self.assertTrue(self.systemd.get()['loaded'])
        self.assertEqual([a['surface'] for a in self.components.actions()],['api','portal','caddy'])
        self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertFalse(self.systemd.get()['active']);self.assertFalse(self.systemd.get()['loaded'])
        self.assertTrue(self.unit.retained.exists());self.assertTrue(self.generation.retained.exists())
        self.assertEqual([command[4] for command in self.systemd.commands()],['daemon-reload','start','stop','daemon-reload'])
        self.assertEqual([a['surface'] for a in self.components.actions()][3:],['caddy','portal','api'])
    def test_kill_after_start_before_completion_adopts_without_second_start(self):
        self.kill_at('apply:authority-service:after-action')
        self.assertEqual(self.state()['pending_outcome'],'applied')
        identity=self.systemd.get()['identity']
        self.assertTrue(self.run_rollout()['verified_held']);self.assertEqual(self.systemd.get()['identity'],identity)
        self.assertEqual([c[4] for c in self.systemd.commands()].count('start'),1)
    def test_kill_after_stop_adopts_without_second_stop(self):
        self.run_rollout();self.kill_at('rollback:authority-service:after-action',rollback=True)
        self.assertEqual(self.state()['pending_outcome'],'applied')
        self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertEqual([c[4] for c in self.systemd.commands()].count('stop'),1)
    def test_kill_after_unit_retention_reloads_manager_on_resume(self):
        self.run_rollout();self.kill_at('unit-retain-renamed',rollback=True,unit=True)
        self.assertTrue(self.systemd.get()['loaded']);self.assertFalse(self.systemd.get()['active'])
        self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertFalse(self.systemd.get()['loaded'])
    def test_start_result_uncertain_leaves_intent_then_adopts_exact_active_target(self):
        self.systemd.fail_after_start=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.state()['pending_outcome'],'applied')
        self.assertEqual(self.components.actions(),[])
        self.systemd.fail_after_start=False
        self.assertTrue(self.run_rollout()['verified_held'])
        self.assertEqual([c[4] for c in self.systemd.commands()].count('start'),1)
    def test_process_identity_drift_after_completion_refuses_forward_and_rollback(self):
        self.run_rollout();state=self.systemd.get();state['identity']='f'*64;self.systemd.put(state)
        before=self.systemd.commands()
        for rollback in (False,True):
            with self.assertRaises(MaintenanceControlError):self.run_rollout(rollback=rollback)
        self.assertEqual(self.systemd.commands(),before)
    def test_override_preflight_refuses_before_any_systemd_action(self):
        self.systemd.unsafe=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.systemd.commands(),[])
    def test_incomplete_probe_or_component_adapter_refuses(self):
        with self.assertRaises(MaintenanceControlError):AuthorityServiceLifecycle(object(),held_guard=self.held)
        with self.assertRaises(MaintenanceControlError):AuthorityServiceRolloutAdapter(self.lifecycle,object(),held_guard=self.held)
    def test_unknown_operation_never_executes(self):
        for operation in ('restart','enable','disable','kill','daemon-reexec'):
            with self.assertRaises(MaintenanceControlError):self.lifecycle._command(operation,expected=ABSENT)
        self.assertEqual(self.systemd.commands(),[])
    def test_fixed_command_executor_has_bounded_timeout_and_clean_environment(self):
        command=['/usr/bin/systemctl','--system','--no-ask-password','--no-pager','start',UNIT_NAME]
        with patch('atlas.deployment_authority_service.subprocess.run',return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(AuthorityServiceLifecycle._execute(command))
        args,kwargs=run.call_args
        self.assertEqual(args[0],command);self.assertEqual(kwargs['timeout'],30)
        self.assertEqual(set(kwargs['env']),{'PATH','LANG','SYSTEMD_PAGER','SYSTEMD_COLORS'})
        self.assertNotIn('shell',kwargs)
    def test_executor_failure_or_timeout_is_refused_without_exposing_output(self):
        command=['/usr/bin/systemctl','--system','--no-ask-password','--no-pager','stop',UNIT_NAME]
        for error in (OSError('private details'),subprocess.TimeoutExpired(command,30)):
            with patch('atlas.deployment_authority_service.subprocess.run',side_effect=error),self.assertRaisesRegex(MaintenanceControlError,'command_uncertain'):
                AuthorityServiceLifecycle._execute(command)
        with patch('atlas.deployment_authority_service.subprocess.run',return_value=SimpleNamespace(returncode=1)),self.assertRaises(MaintenanceControlError):
            AuthorityServiceLifecycle._execute(command)
    def test_completed_lifecycle_confirmation_does_not_repeat_start_or_reload(self):
        self.run_rollout();expected=self.lifecycle.observe();before=self.systemd.commands()
        self.assertEqual(self.lifecycle.confirm('apply',expected),expected)
        self.assertTrue(self.run_rollout()['verified_held']);self.assertEqual(self.systemd.commands(),before)
    def test_foreign_active_identity_is_not_stopped(self):
        self.run_rollout();original=self.systemd.observe
        self.systemd.observe=lambda:{'fingerprint':'e'*64,'identity':'d'*64}
        before=self.systemd.commands()
        with self.assertRaises(MaintenanceControlError):self.lifecycle.rollback()
        self.assertEqual(self.systemd.commands(),before);self.systemd.observe=original
    def test_identity_change_between_stop_preflight_and_command_refuses(self):
        self.run_rollout();before=self.systemd.commands();expected=self.lifecycle.observe()
        changed=dict(expected,identity='a'*64)
        # The command performs another complete observation immediately before execution.
        with patch.object(self.lifecycle,'observe',return_value=changed),self.assertRaises(MaintenanceControlError):
            self.lifecycle._command('stop',expected=expected)
        self.assertEqual(self.systemd.commands(),before)
    def test_missing_listener_can_wait_but_contract_errors_are_not_retried(self):
        self.run_rollout();state=self.systemd.get();state.update(active=False,identity=None);self.systemd.put(state)
        original=self.systemd.execute
        def execute(command):
            result=original(command)
            if command[4]=='start':self.systemd.socket_pending=1
            return result
        self.lifecycle.execute=execute;self.lifecycle.apply()
        self.assertEqual(self.lifecycle.observe()['fingerprint'],self.systemd.target_fingerprint)
        self.systemd.observe=lambda:(_ for _ in ()).throw(MaintenanceControlError('fixture process credentials differ'))
        with self.assertRaisesRegex(MaintenanceControlError,'credentials differ'):self.lifecycle.apply()
    def test_listener_timeout_preserves_active_result_for_review(self):
        self.lifecycle.startup_timeout=0
        original=self.systemd.execute
        def execute(command):
            result=original(command)
            if command[4]=='start':self.systemd.socket_pending=100
            return result
        self.lifecycle.execute=execute
        with self.assertRaisesRegex(MaintenanceControlError,'socket_startup_timeout'):self.run_rollout()
        self.assertTrue(self.systemd.get()['active']);self.assertEqual(self.components.actions(),[])
    def test_retained_unit_confirmation_must_prove_manager_removed(self):
        self.run_rollout();self.systemd.removed=lambda:False
        with self.assertRaisesRegex(MaintenanceControlError,'manager_removal_not_proven'):self.run_rollout(rollback=True)
        self.assertTrue(self.unit.retained.exists());self.assertTrue(self.generation.target.exists())
    def test_source_stays_published_if_service_or_unit_removal_is_uncertain(self):
        self.run_rollout();self.systemd.unsafe=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout(rollback=True)
        self.assertTrue(self.generation.target.exists());self.assertTrue(self.unit.target.exists())
    def test_native_probe_rejects_wrong_unit_socket_or_source_paths(self):
        ext={'authority':{'unit_path':'/etc/systemd/system/other.service','socket':'/run/atlas-maintenance-control/control.sock'},
             'caddy':{'immutable_source':'/mnt/storage/configs/atlas/deployments/repairs/example/source'}}
        with self.assertRaises(MaintenanceControlError):NativeAuthorityProbe({},None,self.root,ext)
    def native_probe_fixture(self):
        # No executable is launched by this probe fixture; query is supplied below.
        self.enterContext(patch('atlas.deployment_authority_service.shutil.which',return_value='/usr/bin/systemctl'))
        probe=object.__new__(NativeAuthorityProbe)
        probe.unit=self.unit.target;probe.socket=self.root/'runtime-authority/control.sock'
        probe.source=self.generation.target;probe.record=self.root/'assets';probe.reader=None
        probe.unit_sha256=self.unit.sha256;probe.target_fingerprint='b'*64
        probe.lookup_roots=(self.unit_directory,)
        props={'LoadState':'not-found','ActiveState':'inactive','SubState':'dead','FragmentPath':'',
               'DropInPaths':'','NeedDaemonReload':'no','MainPID':'0'}
        probe.verifier={'service_properties':lambda:copy.deepcopy(props),'query':lambda args:b'disabled\n'}
        return probe,props
    def test_native_probe_inactive_boundary_and_stale_socket_parent(self):
        probe,props=self.native_probe_fixture()
        self.assertEqual(probe.observe(),ABSENT)
        probe.socket.parent.mkdir(mode=0o700)
        with self.assertRaisesRegex(MaintenanceControlError,'inactive_boundary'):probe.observe()
    def test_native_probe_shadow_units_and_generic_dropins_refuse_before_query(self):
        probe,props=self.native_probe_fixture()
        other=self.root/'other-systemd';other.mkdir(mode=0o700)
        probe.lookup_roots=(other,)
        shadow=other/UNIT_NAME;shadow.write_text('foreign')
        with self.assertRaisesRegex(MaintenanceControlError,'shadow_unit'):probe.preflight()
        shadow.unlink();(other/'service.d').mkdir(mode=0o700)
        with self.assertRaisesRegex(MaintenanceControlError,'dropin_path'):probe.preflight()
    def test_native_probe_effective_dropin_or_enabled_unit_refuses(self):
        probe,props=self.native_probe_fixture();props['DropInPaths']='foreign.conf'
        with self.assertRaisesRegex(MaintenanceControlError,'effective_unit'):probe.preflight()
        props['DropInPaths']='';probe.verifier['query']=lambda args:b'enabled\n'
        with self.assertRaisesRegex(MaintenanceControlError,'enablement'):probe.preflight()
    def test_native_probe_remote_bus_environment_refuses(self):
        probe,props=self.native_probe_fixture()
        with patch.dict(os.environ,{'DBUS_SYSTEM_BUS_ADDRESS':'unix:path=/private/foreign-bus'}),self.assertRaisesRegex(MaintenanceControlError,'environment_overridden'):
            probe.preflight()
    def test_native_probe_inactive_property_change_refuses(self):
        probe,props=self.native_probe_fixture();calls=[0]
        def properties():
            calls[0]+=1;value=dict(props)
            if calls[0]>1:value['MainPID']='123'
            return value
        probe.verifier['service_properties']=properties
        with self.assertRaisesRegex(MaintenanceControlError,'inactive_identity_changed'):probe.observe()
    def test_native_probe_requires_full_native_verifier_for_active_identity(self):
        probe,props=self.native_probe_fixture();self.unit.publish(held_guard=self.held)
        props.update(LoadState='loaded',ActiveState='active',SubState='running',MainPID='123',FragmentPath=str(probe.unit))
        probe.socket.parent.mkdir(mode=0o700);probe.socket.write_bytes(b'private fixture; verifier is mocked')
        called=[]
        def verified(reader,record,ext):called.append('verified');return dict(props)
        probe.extension={};probe.verifier['verify_authority']=verified
        # Installed unit ownership checks are exercised by the unit tests; this
        # fixture isolates delegation and service/socket incarnation binding.
        with patch.object(probe,'preflight',side_effect=lambda:dict(props)):
            first=probe.observe();second=probe.observe()
            self.assertEqual(first,second);self.assertEqual(called,['verified','verified'])
            props['MainPID']='124'
            self.assertNotEqual(first['identity'],probe.observe()['identity'])
    def test_direct_executor_rejects_arbitrary_commands_before_subprocess(self):
        with patch('atlas.deployment_authority_service.subprocess.run') as run:
            for command in (['/bin/sh','-c','anything'],['/usr/bin/systemctl','restart','other.service']):
                with self.assertRaises(MaintenanceControlError):AuthorityServiceLifecycle._execute(command)
            run.assert_not_called()
    def test_service_hold_loss_refuses_before_commands(self):
        self.lifecycle.held_guard=lambda:False
        with self.assertRaises(MaintenanceControlError):self.lifecycle.apply()
        self.assertEqual(self.systemd.commands(),[])
