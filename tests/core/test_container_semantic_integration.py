"""The action adapter itself must use the tested semantic model."""
import copy
import unittest
from pathlib import Path
from atlas.deployment_component_containers import container_model, container_observation
from atlas.maintenance_control import MaintenanceControlError
from tests.core.test_component_container_adapter import row

class ContainerSemanticIntegrationTests(unittest.TestCase):
    def fixture(self):return row('caddy','rollback',Path('/generation'))
    def structured(self,value):
        value=copy.deepcopy(value)
        value['HostConfig']['Binds']=None
        value['HostConfig']['Mounts']=[{'Type':'bind','Source':m['Source'],'Target':m['Destination'],
            'ReadOnly':not m['RW'],'BindOptions':{}} for m in value['Mounts']]
        for mount in value['Mounts']:mount['Mode']=''
        return value
    def test_action_observation_accepts_environment_order_only(self):
        a=self.fixture();a['Config']['Env']=['B=2','A=1'];b=copy.deepcopy(a);b['Config']['Env'].reverse()
        self.assertEqual(container_observation(a),container_observation(b))
    def test_action_observation_accepts_structured_bind_equivalence(self):
        a=self.fixture();self.assertEqual(container_observation(a),container_observation(self.structured(a)))
    def test_action_observation_refuses_inconsistent_effective_readonly(self):
        a=self.structured(self.fixture());a['Mounts'][0]['RW']=True
        with self.assertRaises(MaintenanceControlError):container_observation(a)
    def test_action_observation_keeps_environment_and_security_drift(self):
        a=self.fixture()
        for kind in ('environment','security','propagation'):
            b=copy.deepcopy(a)
            if kind=='environment':b['Config']['Env'].append('FOREIGN=1')
            elif kind=='security':b['HostConfig']['SecurityOpt']=[]
            else:
                b['HostConfig']['Binds']=[b['Mounts'][0]['Source']+':/etc/caddy:ro,rshared']
                b['Mounts'][0]['Propagation']='rshared'
            self.assertNotEqual(container_model(a),container_model(b))
    def test_action_observation_refuses_duplicate_environment(self):
        a=self.fixture();a['Config']['Env']=['A=1','A=1']
        with self.assertRaises(MaintenanceControlError):container_model(a)
    def test_action_observation_handles_unset_oom_but_keeps_true(self):
        a=self.fixture();a['HostConfig']['OomKillDisable']=None;b=copy.deepcopy(a);b['HostConfig']['OomKillDisable']=False
        self.assertEqual(container_model(a),container_model(b))
        b['HostConfig']['OomKillDisable']=True;self.assertNotEqual(container_model(a),container_model(b))
    def test_process_restart_still_changes_observation_identity(self):
        a=self.fixture();b=copy.deepcopy(a);b['State']['Pid']+=1
        self.assertEqual(container_observation(a)['fingerprint'],container_observation(b)['fingerprint'])
        self.assertNotEqual(container_observation(a)['identity'],container_observation(b)['identity'])
    def test_inspection_model_is_idempotent(self):
        from atlas.deployment_inspection_semantics import semantic_model
        a=container_model(self.fixture());self.assertEqual(semantic_model(a),a)

if __name__=='__main__':unittest.main()
