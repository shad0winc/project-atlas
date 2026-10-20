"""Strict external-network placeholder normalization; no Docker calls."""
import copy,unittest
from atlas.deployment_component_containers import validate_execution_render,ROLES
from atlas.maintenance_control import MaintenanceControlError


class ExecutionRenderComparisonTests(unittest.TestCase):
    def setUp(self):
        self.images={role:'sha256:'+str(index+1)*64 for index,role in enumerate(ROLES)}
        self.previous={'name':'atlas-ingress','services':{role:{'container_name':'atlas-'+role,'image':'old-alias',
            'environment':{'LITERAL':'keep$exact'},'volumes':[{'type':'bind','source':'/fixture','target':'/fixture',
            'bind':{'create_host_path':True}}]} for role in ROLES},
            'networks':{name:{'name':name,'external':True} for name in ('atlas-ingress','atlas-backend','atlas-identity')}}
        self.actual=copy.deepcopy(self.previous)
        for role in ROLES:
            self.actual['services'][role]['image']=self.images[role]
            self.actual['services'][role]['volumes'][0]['bind']={}
        for value in self.actual['networks'].values():value['ipam']={}
    def test_exactly_empty_external_ipam_maps_and_missing_false_bind_default_pass(self):
        before=copy.deepcopy(self.previous);actual=copy.deepcopy(self.actual)
        self.assertTrue(validate_execution_render(self.previous,self.actual,self.images))
        self.assertEqual(self.previous,before);self.assertEqual(self.actual,actual)
    def test_nonempty_ipam_allocations_or_driver_settings_are_refused(self):
        for ipam in ({'config':[{'subnet':'192.0.2.0/24'}]},{'driver':'default'},{'options':{}},{'config':[]}):
            value=copy.deepcopy(self.actual);value['networks']['atlas-ingress']['ipam']=ipam
            with self.subTest(ipam=ipam),self.assertRaises(MaintenanceControlError):
                validate_execution_render(self.previous,value,self.images)
    def test_nonmapping_ipam_is_not_treated_as_empty(self):
        for ipam in (None,[],False,0,''):
            value=copy.deepcopy(self.actual);value['networks']['atlas-ingress']['ipam']=ipam
            with self.subTest(ipam=ipam),self.assertRaises(MaintenanceControlError):
                validate_execution_render(self.previous,value,self.images)
    def test_network_membership_names_and_external_policy_remain_exact(self):
        for kind in ('name','external','extra','missing'):
            value=copy.deepcopy(self.actual)
            if kind=='name':value['networks']['atlas-ingress']['name']='foreign'
            elif kind=='external':value['networks']['atlas-ingress']['external']=False
            elif kind=='extra':value['networks']['foreign']={'name':'foreign','external':True}
            else:value['networks'].pop('atlas-identity')
            with self.subTest(kind=kind),self.assertRaises(MaintenanceControlError):
                validate_execution_render(self.previous,value,self.images)
    def test_environment_image_and_bind_changes_remain_refused(self):
        for kind in ('environment','image','bind','bind-true','bind-numeric'):
            value=copy.deepcopy(self.actual);service=value['services']['api']
            if kind=='environment':service['environment']['LITERAL']='changed'
            elif kind=='image':service['image']='mutable:tag'
            elif kind=='bind':service['volumes'][0]['source']='/foreign'
            elif kind=='bind-true':service['volumes'][0]['bind']['create_host_path']=True
            else:service['volumes'][0]['bind']['create_host_path']=0
            with self.subTest(kind=kind),self.assertRaises(MaintenanceControlError):
                validate_execution_render(self.previous,value,self.images)
    def test_unknown_service_or_unreviewed_field_is_refused(self):
        for kind in ('service','field'):
            value=copy.deepcopy(self.actual)
            if kind=='service':value['services']['other']={}
            else:value['services']['portal']['privileged']=True
            with self.subTest(kind=kind),self.assertRaises(MaintenanceControlError):
                validate_execution_render(self.previous,value,self.images)
