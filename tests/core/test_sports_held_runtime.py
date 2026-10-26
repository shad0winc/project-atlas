"""Held provenance has separate authority semantics and grants no acceptance."""
from contextlib import contextmanager
from pathlib import Path
import copy, json, types, unittest
from unittest.mock import patch
from tests.core import test_sports_provenance_extension as foundation

M=foundation.M

class HeldRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=foundation.SportsProvenanceTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.record=self.fixture.record;self.S=M.sports_extension_module();self.I=M.extension_module()
        patch.object(M,'extension_module',return_value=self.I).start()
        self.ext=json.loads((self.record/'sports-runtime-extension.json').read_bytes())
        self.proof=dict(schema_version=1,scope='held-sports-provenance-only',transaction='fixture-held-transaction',
            base_publication=self.fixture.base.name,candidate_publication=self.record.name,
            candidate_manifest_sha256=M.digest(self.record/'MANIFEST.sha256'),current_publication=self.fixture.base.name,
            hold_context_sha256='a'*64,maintenance_sha256='b'*64,hold_marker_path='/var/lib/atlas-sports-cutover/fixture-held-transaction/held',
            hold_marker_sha256='c'*64,authority_dropin_path='/etc/systemd/system/atlas-maintenance-control.service.d/90-atlas-sports-cutover.conf')
        self.locked=False;self.calls=[]
        @contextmanager
        def exclusion():
            self.locked=True;self.calls.append('lock')
            try:yield
            finally:self.calls.append('unlock');self.locked=False
        def hold():
            self.assertTrue(self.locked);self.calls.append('hold');return copy.deepcopy(self.proof)
        def configuration(role,row):
            self.assertTrue(self.locked);self.calls.append(role);return True
        self.context=types.SimpleNamespace(exclusion=exclusion,verify_hold=hold,verify_configuration=configuration)
        self.rows={}
        for role,name in (('backend','atlas-dispatcharr'),('writer','atlas-sports-writer')):
            self.rows[name]=dict(Id=('1' if role=='backend' else '2')*64,Image=self.ext['components'][role]['image_id'],Name='/'+name,
                Config={'Env':[]},HostConfig={},RestartCount=0,Mounts=[],NetworkSettings={'Networks':{'atlas':{'Aliases':[name]}}},
                State={'Running':True,'Health':{'Status':'healthy'},'Pid':123,'StartedAt':'fixture'})
        self.rows['atlas-sports-controller']=copy.deepcopy(self.rows['atlas-sports-writer'])
        self.rows['atlas-sports-controller']['Name']='/atlas-sports-controller'
        self.authority=patch.object(self.S,'check_held_authority',return_value={'held':True}).start();self.addCleanup(patch.stopall)
        self.ingress=patch.object(self.I,'_check_live_components',side_effect=lambda m,r,check:check()).start()
        self.sports=patch.object(M,'_check_sports_live').start()
        self.backend=patch.object(self.S.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)).start()
        patch.object(M,'inspect',side_effect=lambda name:copy.deepcopy(self.rows[name])).start()

    def check(self):return self.S.check_live_held(M,self.record,self.context)
    def refuse(self):
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):self.check()

    def test_success_is_locked_read_only_provenance_without_acceptance(self):
        result=self.check()
        self.assertEqual(self.calls[0],'lock');self.assertEqual(self.calls[-1],'unlock')
        self.assertFalse(result['runtime_acceptance_granted']);self.assertFalse(result['production_execution_authorized'])
        self.assertFalse(result['public_reopen_performed']);self.assertEqual(result['manifest_sha256'],self.proof['candidate_manifest_sha256'])
        self.ingress.assert_called_once();self.sports.assert_called_once()
        args=self.backend.call_args.args[0]
        self.assertEqual(args[:5],['docker','exec','-i','atlas-dispatcharr','python'])
        self.assertNotIn('django.setup',args[-1])

    def test_successor_current_is_also_permitted_under_same_hold(self):
        self.proof['current_publication']=self.record.name;self.check()

    def test_ordinary_live_path_still_refuses_before_query(self):
        with self.assertRaisesRegex(ValueError,'pending held Sports adapter'):M.check_live(self.record)
        self.backend.assert_not_called()

    def test_missing_host_adapter_refuses(self):
        self.context.verify_hold=None;self.refuse();self.backend.assert_not_called()

    def test_boolean_hold_proof_refuses(self):
        self.context.verify_hold=lambda:True;self.refuse();self.backend.assert_not_called()

    def test_scope_and_manifest_cannot_be_substituted(self):
        for key,value in [('scope','production-authorized'),('candidate_manifest_sha256','0'*64),
                ('candidate_publication','another'),('current_publication','unrelated'),('base_publication','another')]:
            with self.subTest(key=key):
                original=self.proof[key];self.proof[key]=value;self.refuse();self.proof[key]=original
        self.backend.assert_not_called()

    def test_context_pin_and_path_mapping_refuse(self):
        for key,value in [('hold_context_sha256',True),('hold_marker_path','/tmp/held'),('authority_dropin_path','/tmp/unit')]:
            with self.subTest(key=key):
                original=self.proof[key];self.proof[key]=value;self.refuse();self.proof[key]=original
        self.backend.assert_not_called()

    def test_context_change_during_inspection_refuses(self):
        def changed(*args):self.proof['maintenance_sha256']='e'*64
        self.sports.side_effect=changed;self.refuse()

    def test_lost_exclusion_or_hold_error_propagates_and_unlocks(self):
        def failed():raise ValueError('hold lost')
        self.context.verify_hold=failed;self.refuse();self.assertEqual(self.calls[-1],'unlock')

    def test_configuration_requires_exact_true(self):
        self.context.verify_configuration=lambda *args:1;self.refuse();self.backend.assert_not_called()

    def test_effective_image_and_name_drift_refuse(self):
        for key,value in [('Image','sha256:'+'0'*64),('Name','/other')]:
            original=self.rows['atlas-dispatcharr'][key];self.rows['atlas-dispatcharr'][key]=value
            self.refuse();self.rows['atlas-dispatcharr'][key]=original
        self.backend.assert_not_called()

    def test_unhealthy_paused_and_restarting_refuse(self):
        state=self.rows['atlas-dispatcharr']['State']
        for key,value in [('Running',False),('Paused',True),('Restarting',True),('OOMKilled',True),('Health',{'Status':'starting'}),('Pid',0)]:
            before=copy.deepcopy(state);state[key]=value;self.refuse();state.clear();state.update(before)
        self.backend.assert_not_called()

    def test_container_restart_and_network_drift_refuse(self):
        for kind in ('restart','network','config'):
            row=copy.deepcopy(self.rows['atlas-dispatcharr'])
            def changed(*args):
                if kind=='restart':self.rows['atlas-dispatcharr']['RestartCount']+=1
                elif kind=='network':self.rows['atlas-dispatcharr']['NetworkSettings']['Networks'].clear()
                else:self.rows['atlas-dispatcharr']['Config']['Env']=['SECRET=changed']
            self.sports.side_effect=changed;self.refuse();self.rows['atlas-dispatcharr']=row

    def test_controller_restart_mid_inspection_refuses(self):
        self.sports.side_effect=lambda *args:self.rows['atlas-sports-controller'].update(RestartCount=1)
        self.refuse()

    def test_mount_reordering_is_not_configuration_drift(self):
        row=self.rows['atlas-dispatcharr'];row['Mounts']=[{'Destination':'/one'},{'Destination':'/two'}]
        self.sports.side_effect=lambda *args:row['Mounts'].reverse();self.check()

    def test_backend_installed_file_failure_refuses(self):
        self.backend.return_value=types.SimpleNamespace(returncode=1);self.refuse()

    def test_ingress_or_controller_failure_prevents_backend_probe(self):
        for callback in (self.ingress,self.sports):
            callback.side_effect=ValueError('source differs');self.refuse();callback.side_effect=None
        self.backend.assert_not_called()

    def test_record_changed_mid_inspection_refuses(self):
        def changed(*args):(self.record/'sports-release-gate.json').write_bytes(b'{}')
        self.sports.side_effect=changed;self.refuse()

    def test_backend_probe_pins_only_native_installed_map(self):
        self.check();kwargs=self.backend.call_args.kwargs
        self.assertEqual(json.loads(kwargs['input']),self.ext['components']['backend']['installed_file_sha256'])
        self.assertTrue(kwargs['capture_output']);self.assertEqual(kwargs['timeout'],90)

class HeldAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.fixture=foundation.SportsProvenanceTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.S=M.sports_extension_module();self.I=M.extension_module();self.record=self.fixture.record
        patch.object(M,'extension_module',return_value=self.I).start()
        self.ext=json.loads((self.record/'ingress-runtime-extension.json').read_bytes())
        self.proof={'transaction':'fixture','hold_context_sha256':'a'*64,'hold_marker_path':'/marker','authority_dropin_path':'/dropin'}
        self.marker=json.dumps({'transaction':'fixture','context_sha256':'a'*64}).encode()
        self.proof['hold_marker_sha256']=self.S.hashlib.sha256(self.marker).hexdigest()
        self.files={'/marker':self.marker,'/dropin':b'[Unit]\nConditionPathExists=!/marker\n',
            self.ext['authority']['unit_path']:(self.record/'maintenance-authority.service').read_bytes()}
        self.properties={'LoadState':'loaded','ActiveState':'inactive','SubState':'dead','MainPID':'0',
            'FragmentPath':self.ext['authority']['unit_path'],'DropInPaths':'/dropin','NeedDaemonReload':'no',
            'WorkingDirectory':self.ext['caddy']['immutable_source'],'User':'root','Group':'20000'}
        patch.object(self.S,'held_file',side_effect=lambda name:self.files[name]).start()
        patch.object(self.I,'service_properties',side_effect=lambda:copy.deepcopy(self.properties)).start()
        self.unix=b'Num RefCount Protocol Flags Type St Inode Path\n'
        real_read=M.read
        patch.object(M,'read',side_effect=lambda p:self.unix if p==Path('/proc/net/unix') else real_read(p)).start()
        self.addCleanup(patch.stopall)
    def check(self):return self.S.check_held_authority(M,self.record,self.proof)
    def refuse(self):
        with self.assertRaises(ValueError):self.check()
    def test_native_inactive_authority_accepts_exact_marker_and_unit(self):self.check()
    def test_active_authority_or_pid_or_stale_manager_refuses(self):
        for key,value in [('ActiveState','active'),('MainPID','123'),('NeedDaemonReload','yes'),('DropInPaths','/foreign /dropin')]:
            original=self.properties[key];self.properties[key]=value;self.refuse();self.properties[key]=original
    def test_marker_condition_or_unit_substitution_refuses(self):
        for name in self.files:
            original=self.files[name];self.files[name]=b'changed';self.refuse();self.files[name]=original
    def test_same_marker_hash_cannot_claim_another_context(self):
        self.proof['hold_context_sha256']='0'*64;self.refuse()
    def test_stale_control_socket_listener_refuses(self):
        self.unix+=('0000 2 0 00010000 0001 01 123 '+self.ext['authority']['socket']+'\n').encode();self.refuse()
    def test_unrelated_socket_does_not_block(self):
        self.unix+=b'0000 2 0 00010000 0001 01 123 /unrelated\n';self.check()

if __name__=='__main__':unittest.main()
