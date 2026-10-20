import copy
import unittest
from atlas.deployment_inspection_semantics import semantic_model, project_probe, LABEL
from atlas.maintenance_control import MaintenanceControlError

def fixture(structured=False):
    mount={'Type':'bind','Source':'/source','Destination':'/data','Mode':'' if structured else 'ro',
           'RW':False,'Propagation':'rprivate'}
    host={'Binds':None if structured else ['/source:/data:ro'],'OomKillDisable':False if structured else None,
          'Privileged':False,'SecurityOpt':['no-new-privileges:true'],'PortBindings':{},'NetworkMode':'network'}
    if structured:host['Mounts']=[{'Type':'bind','Source':'/source','Target':'/data','ReadOnly':True,'BindOptions':{}}]
    return {'name':'/atlas-api','image':'sha256:'+'a'*64,'config':{'Env':['B=2','A=1'],
            'Labels':{'com.docker.compose.project':'atlas-ingress'}},'host_config':host,
            'mounts':[mount],'networks':{'network':{'aliases':['api']}}}

class InspectionSemanticsTests(unittest.TestCase):
    def test_legacy_and_structured_bind_representations_match(self):
        self.assertEqual(semantic_model(fixture()),semantic_model(fixture(True)))
    def test_inputs_are_not_mutated(self):
        row=fixture();before=copy.deepcopy(row);semantic_model(row);self.assertEqual(row,before)
    def test_environment_order_only_is_equivalent(self):
        a=fixture();b=fixture();b['config']['Env'].reverse()
        self.assertEqual(semantic_model(a),semantic_model(b))
    def test_environment_value_or_added_key_remains_visible(self):
        for env in (['B=3','A=1'],['B=2','A=1','C=3']):
            b=fixture();b['config']['Env']=env
            self.assertNotEqual(semantic_model(fixture()),semantic_model(b))
    def test_duplicate_environment_refuses(self):
        b=fixture();b['config']['Env']+=['A=1']
        with self.assertRaises(MaintenanceControlError):semantic_model(b)
    def test_disabled_oom_killer_is_not_normalized_away(self):
        b=fixture();b['host_config']['OomKillDisable']=True
        self.assertNotEqual(semantic_model(fixture()),semantic_model(b))
    def test_numeric_oom_flag_refuses(self):
        b=fixture();b['host_config']['OomKillDisable']=0
        with self.assertRaises(MaintenanceControlError):semantic_model(b)
    def test_readonly_conflict_refuses(self):
        for structured in (False,True):
            b=fixture(structured);b['mounts'][0]['RW']=True
            with self.assertRaises(MaintenanceControlError):semantic_model(b)
    def test_mount_source_or_propagation_conflict_refuses(self):
        for field,value in (('Source','/foreign'),('Propagation','rshared')):
            b=fixture();b['mounts'][0][field]=value
            with self.assertRaises(MaintenanceControlError):semantic_model(b)
    def test_advanced_bind_options_are_not_dropped(self):
        for option in ('CreateMountpoint','NonRecursive','ReadOnlyNonRecursive','ReadOnlyForceRecursive'):
            b=fixture(True);b['host_config']['Mounts'][0]['BindOptions'][option]=False
            with self.assertRaises(MaintenanceControlError):semantic_model(b)
    def test_selinux_or_consistency_modes_require_review(self):
        for flag in ('z','Z','cached','delegated'):
            b=fixture();b['host_config']['Binds']=['/source:/data:ro,'+flag]
            with self.assertRaises(MaintenanceControlError):semantic_model(b)
    def test_undeclared_or_duplicate_effective_mount_refuses(self):
        for kind in ('missing','duplicate'):
            b=fixture()
            if kind=='missing':b['host_config']['Binds']=[]
            else:b['mounts']*=2
            with self.assertRaises(MaintenanceControlError):semantic_model(b)
    def test_host_security_and_ports_remain_visible(self):
        for key,value in (('Privileged',True),('SecurityOpt',[]),('PortBindings',{'80/tcp':[{}]}),('Memory',1024)):
            b=fixture();b['host_config'][key]=value
            self.assertNotEqual(semantic_model(fixture()),semantic_model(b))
    def test_unknown_labels_remain_visible(self):
        b=fixture();b['config']['Labels']['foreign']='value'
        self.assertNotEqual(semantic_model(fixture()),semantic_model(b))
    def test_only_selected_compose_metadata_is_ignored(self):
        b=fixture()
        for key in ('project.environment_file','replace','depends_on'):b['config']['Labels']['com.docker.compose.'+key]='metadata'
        self.assertEqual(semantic_model(fixture()),semantic_model(b))
    def projection_fixture(self):
        row={'Name':'/probe-api','Config':{'Labels':{LABEL:'nonce'}},
            'Mounts':[{'Type':'bind','Source':'/private','Destination':'/data'}],
            'HostConfig':{'NetworkMode':'private-net','Binds':None,
                          'Mounts':[{'Type':'bind','Source':'/private','Target':'/data','ReadOnly':True}], 'PortBindings':{}},
            'NetworkSettings':{'Networks':{'private-net':{'Aliases':['probe-api','api']}}}}
        mapping={'containers':{'api':{'private':'probe-api','original':'atlas-api'}},
                 'binds':[{'role':'api','private':'/private','original':'/production'}],
                 'networks':{'net':{'private':'private-net','original':'atlas-ingress'}},
                 'ports':{'api':[{'mode':'ingress','target':80,'published':'8080','protocol':'tcp'}]}}
        return row,mapping
    def test_projection_translates_both_mount_structures(self):
        row,mapping=self.projection_fixture();before=copy.deepcopy(row);value=project_probe(row,mapping,'api','nonce')
        self.assertEqual(row,before);self.assertEqual(value['Mounts'][0]['Source'],'/production')
        self.assertEqual(value['HostConfig']['Mounts'][0]['Source'],'/production')
        self.assertEqual(value['HostConfig']['PortBindings'],{'80/tcp':[{'HostIp':'','HostPort':'8080'}]})
    def test_projection_refuses_foreign_ownership_or_host_mount(self):
        for kind in ('owner','mount'):
            row,mapping=self.projection_fixture()
            if kind=='owner':row['Config']['Labels'][LABEL]='foreign'
            else:row['HostConfig']['Mounts'][0]['Source']='/foreign'
            with self.assertRaises(MaintenanceControlError):project_probe(row,mapping,'api','nonce')
    def test_projection_refuses_preexisting_ports_or_ranges(self):
        for kind in ('ports','range'):
            row,mapping=self.projection_fixture()
            if kind=='ports':row['HostConfig']['PortBindings']={'80/tcp':[{}]}
            else:mapping['ports']['api'][0]['published']='8080-8081'
            with self.assertRaises(MaintenanceControlError):project_probe(row,mapping,'api','nonce')

if __name__=='__main__':unittest.main()
