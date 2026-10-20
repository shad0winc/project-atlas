"""Full held journal with private source/unit files and file-backed Docker/systemd fixtures."""
import copy,json,os,signal,subprocess,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from atlas.deployment_component_containers import ComponentContainerActions,DockerBackend,container_model,container_observation,pinned_recipe,ROLES,DOCKER
from atlas.deployment_component_rollout import ComponentRollout,digest
from atlas.deployment_component_source import GenerationRolloutAdapter
from atlas.deployment_authority_unit import AuthorityUnitRolloutAdapter
from atlas.deployment_authority_service import AuthorityServiceRolloutAdapter
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_authority_service_adapter as service_fixture


def row(role,mode,generation):
    ident=digest({'role':role,'mode':mode})
    image='sha256:'+({'api':'a','portal':'b','caddy':'c'}[role] if mode=='rollback' or role=='caddy' else {'api':'d','portal':'e'}[role])*64
    mounts=[]
    if role=='caddy':
        source=str(generation/'infra/caddy') if mode=='target' else '/old/canonical/infra/caddy'
        mounts=[{'Type':'bind','Source':source,'Destination':'/etc/caddy','Mode':'ro','RW':False,'Propagation':'rprivate'}]
    return {'Id':ident,'Name':'/atlas-'+role,'Image':image,'RestartCount':0,
      'Config':{'Hostname':ident[:12],'Image':image,'User':'atlas' if role=='api' else '',
       'Env':['MODE='+mode],'Cmd':['fixture'],'Entrypoint':None,'WorkingDir':'/fixture',
       'Labels':{'com.docker.compose.project':'atlas-ingress','com.docker.compose.service':role,
          'com.docker.compose.container-number':'1','com.docker.compose.oneoff':'False',
          'com.docker.compose.config-hash':mode+'-fixture','com.docker.compose.image':image},
       'Healthcheck':{'Test':['CMD','true']}},
      'HostConfig':{'Privileged':False,'SecurityOpt':['no-new-privileges:true'],'ReadonlyRootfs':role=='caddy',
        'Binds':[m['Source']+':'+m['Destination']+':ro' for m in mounts],'PortBindings':{},'CapAdd':None,'CapDrop':None,'NetworkMode':'atlas-private',
        'RestartPolicy':{'Name':'unless-stopped','MaximumRetryCount':0},'GroupAdd':None,'Tmpfs':None},
      'Mounts':mounts,'NetworkSettings':{'Networks':{'atlas-private':{'Aliases':['atlas-'+role,role,ident[:12]],
        'IPAddress':'172.31.0.2','EndpointID':ident,'Links':None,'IPAMConfig':None,'DriverOpts':None}}},
      'State':{'Running':True,'Paused':False,'Restarting':False,'Dead':False,'OOMKilled':False,
        'Pid':123,'StartedAt':'2026-10-20T00:00:00Z','FinishedAt':'0001-01-01T00:00:00Z',
        'Health':{'Status':'healthy','Log':[]}}}


class DockerFixture:
    def __init__(self,root,templates):
        self.root,self.templates=root,templates
        self.state=root/'docker-state.json';self.log=root/'docker-actions.jsonl'
        values=[copy.deepcopy(templates['rollback'][role]) for role in ROLES]
        unrelated=row('api','rollback',Path('/unrelated'));unrelated['Name']='/unrelated'
        unrelated['Id']='f'*64;unrelated['Config']['Labels']={};values.append(unrelated)
        self.put(values);self.log.write_bytes(b'')
        self.missing_image=False;self.missing_dependency=False;self.fail_after_replace=False;self.mutate_other=False
        self.before_action=None;self.unhealthy_after_replace=False
    def put(self,values):
        tmp=self.state.with_suffix('.tmp');tmp.write_text(json.dumps(values));os.replace(tmp,self.state)
    def inventory(self):return json.loads(self.state.read_bytes())
    def image(self,reference):
        if self.missing_image:raise MaintenanceControlError('fixture image missing')
        return reference
    def dependencies(self,model):
        if self.missing_dependency:raise MaintenanceControlError('fixture dependency missing')
        return True
    def recreate(self,recipe,role):
        if self.before_action:self.before_action()
        mode=Path(recipe).stem;values=self.inventory()
        replacement=copy.deepcopy(self.templates[mode][role]);replacement['Id']=digest({'nonce':os.urandom(16).hex()})
        replacement['Config']['Hostname']=replacement['Id'][:12]
        replacement['NetworkSettings']['Networks']['atlas-private']['Aliases']=['atlas-'+role,role,replacement['Id'][:12]]
        replacement['State']['Pid']=456
        if self.unhealthy_after_replace:replacement['State']['Health']['Status']='unhealthy'
        values=[replacement if value['Name']=='/atlas-'+role else value for value in values]
        if self.mutate_other:values[-1]['RestartCount']+=1
        self.put(values)
        with self.log.open('ab') as output:
            output.write((json.dumps({'mode':mode,'role':role})+'\n').encode());output.flush();os.fsync(output.fileno())
        return not self.fail_after_replace
    def actions(self):return [json.loads(line) for line in self.log.read_text().splitlines()]


class ComponentContainerAdapterTests(unittest.TestCase):
    assert_boundary=service_fixture.AuthorityServiceAdapterTests.assert_boundary
    writable=service_fixture.AuthorityServiceAdapterTests.writable
    held=service_fixture.AuthorityServiceAdapterTests.held
    def setUp(self):
        service_fixture.AuthorityServiceAdapterTests.setUp(self)
        self.templates={mode:{role:row(role,mode,self.generation.target) for role in ROLES} for mode in ('target','rollback')}
        self.models={mode:{role:container_model(value) for role,value in values.items()} for mode,values in self.templates.items()}
        self.backend=DockerFixture(self.root,self.templates)
        self.unrelated=digest(self.backend.inventory()[-1])
        self.recipes={}
        for mode in ('target','rollback'):
            raw={'name':'atlas-ingress','services':{role:{'container_name':'atlas-'+role,'image':'placeholder'} for role in ROLES}}
            value=pinned_recipe(json.dumps(raw).encode(),{role:self.models[mode][role]['image'] for role in ROLES})
            file=self.root/'assets'/(mode+'.json');file.write_text(json.dumps(value))
            self.recipes[mode]={'path':str(file),'sha256':digest_bytes(file.read_bytes())}
        self.containers=ComponentContainerActions(self.recipes,self.models,self.generation.target,
            held_guard=self.held,unrelated_guard=self.unrelated_guard,backend=self.backend,runtime_root=self.root)
        self.plan['rollout_id']='rollout-container-private'
        self.plan['artifacts']['target-recipe']=self.recipes['target'];self.plan['artifacts']['rollback-recipe']=self.recipes['rollback']
        for entry in self.plan['surfaces']:
            if entry['name'] in ROLES:
                role=entry['name'];entry['before']=container_observation(self.templates['rollback'][role])
                entry['after']=self.containers.fingerprints['target'][role]
        self.service_adapter=AuthorityServiceRolloutAdapter(self.lifecycle,self.containers,held_guard=self.held)
        self.inner=AuthorityUnitRolloutAdapter(self.unit,self.service_adapter,held_guard=self.held)
        self.adapter=GenerationRolloutAdapter(self.generation,self.inner,held_guard=self.held)
        self.engine=ComponentRollout(self.root,'original-failed',self.stream.fileno(),adapter=self.adapter)
        self.engine.prepare('rollout-container-private',self.plan)
    def unrelated_guard(self):return digest(self.backend.inventory()[-1])==self.unrelated
    def run_rollout(self,*,rollback=False):return self.engine.run('rollout-container-private',rollback=rollback)
    def state(self):return self.engine.inspect_rollout('rollout-container-private')
    def kill_after(self,role,*,rollback=False):
        child=os.fork()
        if child==0:
            phase=('rollback' if rollback else 'apply')+':'+role+':after-action'
            self.engine.checkpoint=lambda point:os.kill(os.getpid(),signal.SIGKILL) if point==phase else None
            try:self.run_rollout(rollback=rollback)
            except BaseException:os._exit(3)
            os._exit(4)
        _,status=os.waitpid(child,0);self.assertTrue(os.WIFSIGNALED(status),status)
        self.assertEqual(os.WTERMSIG(status),signal.SIGKILL)
    def test_full_held_apply_and_reverse_restore_use_only_three_roles(self):
        self.assertTrue(self.run_rollout()['verified_held'])
        self.assertEqual([value['role'] for value in self.backend.actions()],list(ROLES))
        self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertEqual([value['role'] for value in self.backend.actions()][3:],list(reversed(ROLES)))
        self.assertTrue(self.generation.retained.exists());self.assertTrue(self.unit.retained.exists())
        self.assertFalse(self.systemd.get()['active']);self.assertFalse(self.systemd.get()['loaded'])
        self.assertTrue(self.unrelated_guard())
    def test_interrupted_api_replacement_adopts_without_repeat(self):
        self.kill_after('api');self.assertEqual(self.state()['pending_outcome'],'applied')
        self.assertTrue(self.run_rollout()['verified_held'])
        self.assertEqual([v['role'] for v in self.backend.actions()].count('api'),1)
    def test_interrupted_portal_replacement_adopts_without_repeat(self):
        self.kill_after('portal');self.assertTrue(self.run_rollout()['verified_held'])
        self.assertEqual([v['role'] for v in self.backend.actions()].count('portal'),1)
    def test_interrupted_caddy_replacement_can_reverse_without_repeating_forward(self):
        self.kill_after('caddy');self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertEqual(len([v for v in self.backend.actions() if v['mode']=='target' and v['role']=='caddy']),1)
    def test_interrupted_reverse_caddy_adopts_without_repeat(self):
        self.run_rollout();self.kill_after('caddy',rollback=True)
        self.assertTrue(self.run_rollout(rollback=True)['verified_held'])
        self.assertEqual(len([v for v in self.backend.actions() if v['mode']=='rollback' and v['role']=='caddy']),1)
    def test_uncertain_command_result_keeps_intent_and_adopts_verified_target(self):
        self.backend.fail_after_replace=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.state()['pending_outcome'],'applied')
        self.backend.fail_after_replace=False;self.assertTrue(self.run_rollout()['verified_held'])
        self.assertEqual([v['role'] for v in self.backend.actions()].count('api'),1)
    def test_unhealthy_target_does_not_receive_completion_or_blind_rollback(self):
        self.backend.unhealthy_after_replace=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        count=len(self.backend.actions())
        with self.assertRaises(MaintenanceControlError):self.run_rollout(rollback=True)
        self.assertEqual(len(self.backend.actions()),count);self.assertTrue(self.generation.target.exists())
    def test_missing_container_refuses_without_recreate(self):
        self.backend.put([v for v in self.backend.inventory() if v['Name']!='/atlas-api'])
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.backend.actions(),[])
    def test_missing_local_image_or_dependency_refuses_before_recreate(self):
        self.backend.missing_image=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.backend.missing_image=False;self.backend.missing_dependency=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.backend.actions(),[])
    def test_unrelated_runtime_change_refuses_completion(self):
        self.backend.mutate_other=True
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(len(self.backend.actions()),1)
        self.assertTrue(self.generation.target.exists())
    def test_completed_container_process_restart_refuses_forward_and_rollback(self):
        self.run_rollout();values=self.backend.inventory();values[0]['RestartCount']+=1;self.backend.put(values)
        count=len(self.backend.actions())
        for rollback in (False,True):
            with self.assertRaises(MaintenanceControlError):self.run_rollout(rollback=rollback)
        self.assertEqual(len(self.backend.actions()),count)
    def test_model_detects_environment_mount_network_and_host_control_drift(self):
        original=self.backend.inventory()
        for field in ('env','mount','network','host'):
            values=copy.deepcopy(original);value=values[0]
            if field=='env':value['Config']['Env'].append('FOREIGN=1')
            elif field=='mount':value['Mounts'].append({'Type':'bind','Source':'/foreign','Destination':'/foreign','RW':True})
            elif field=='network':value['NetworkSettings']['Networks']['foreign']={}
            else:value['HostConfig']['ReadonlyRootfs']=True
            self.backend.put(values)
            with self.subTest(field=field),self.assertRaises(MaintenanceControlError):self.run_rollout()
            self.assertEqual(self.backend.actions(),[])
        self.backend.put(original)
    def test_duplicate_compose_role_and_foreign_project_refuse(self):
        original=self.backend.inventory();values=copy.deepcopy(original)
        extra=copy.deepcopy(values[0]);extra['Id']='0'*64;extra['Name']='/duplicate-api';values.append(extra)
        self.backend.put(values)
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        values=copy.deepcopy(original);values[0]['Config']['Labels']['com.docker.compose.project']='foreign';self.backend.put(values)
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.backend.actions(),[])
    def test_generation_mounted_by_unrelated_container_blocks_source_retention(self):
        self.run_rollout();values=self.backend.inventory()
        values[-1]['Mounts']=[{'Type':'bind','Source':str(self.generation.target),'Destination':'/other','RW':False}]
        self.backend.put(values);self.unrelated=digest(values[-1])
        with self.assertRaisesRegex(MaintenanceControlError,'generation_still_mounted'):self.run_rollout(rollback=True)
        self.assertTrue(self.generation.target.exists())
    def test_recipe_change_refuses_before_commands(self):
        Path(self.recipes['target']['path']).write_text('{}')
        with self.assertRaises(MaintenanceControlError):self.run_rollout()
        self.assertEqual(self.backend.actions(),[])
    def test_models_are_copied_and_privileged_profiles_refused(self):
        original=self.models['target']['api']['config']['Env'][:]
        self.models['target']['api']['config']['Env'].append('FOREIGN=1')
        self.assertEqual(self.containers.models['target']['api']['config']['Env'],original)
        self.models['target']['api']['host_config']['Privileged']=True
        with self.assertRaises(MaintenanceControlError):ComponentContainerActions(self.recipes,self.models,self.generation.target,
            held_guard=self.held,unrelated_guard=self.unrelated_guard,backend=self.backend,runtime_root=self.root)
    def test_unknown_role_never_reaches_backend(self):
        for method in (self.containers.apply,self.containers.rollback,self.containers.observe):
            with self.assertRaises(MaintenanceControlError):method('identity-writer')
        self.assertEqual(self.backend.actions(),[])
    def test_backend_recreate_command_is_local_scoped_waited_and_forbids_build_pull(self):
        backend=DockerBackend();recipe=Path(self.recipes['target']['path'])
        with patch.object(backend,'_run',return_value=b'') as run:self.assertTrue(backend.recreate(recipe,'api'))
        args,kwargs=run.call_args;command=args[0]
        self.assertEqual(command[-1],'api');self.assertIn('--no-deps',command);self.assertIn('--no-build',command)
        self.assertEqual(command[command.index('--pull')+1],'never');self.assertIn('--force-recreate',command)
        self.assertEqual(command[command.index('--env-file')+1],'/dev/null');self.assertEqual(kwargs['timeout'],120)
        self.assertNotIn('--remove-orphans',command);self.assertNotIn('--renew-anon-volumes',command)
    def test_backend_executor_uses_clean_environment_without_shell(self):
        with patch('atlas.deployment_component_containers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'[]')) as run:
            self.assertEqual(DockerBackend._run(['image','inspect','sha256:'+'a'*64]),b'[]')
        args,kwargs=run.call_args;self.assertEqual(args[0][:3],list(DOCKER));self.assertNotIn('shell',kwargs)
        self.assertNotIn('DOCKER_HOST',kwargs['env']);self.assertNotIn('COMPOSE_FILE',kwargs['env'])
        self.assertEqual(kwargs['timeout'],30)
    def test_timeout_or_nonzero_executor_result_is_uncertain_without_raw_output(self):
        for error in (OSError('private'),subprocess.TimeoutExpired(['docker'],30)):
            with patch('atlas.deployment_component_containers.subprocess.run',side_effect=error),self.assertRaisesRegex(MaintenanceControlError,'command_uncertain'):
                DockerBackend._run(['container','inspect','a'*64])
        with patch('atlas.deployment_component_containers.subprocess.run',return_value=SimpleNamespace(returncode=1)),self.assertRaises(MaintenanceControlError):
            DockerBackend._run(['container','inspect','a'*64])
    def test_recipe_pinning_changes_only_images_and_bind_creation_policy(self):
        raw={'name':'atlas-ingress','services':{role:{'container_name':'atlas-'+role,'image':'alias',
             'environment':{'LITERAL':'a$$b'},'volumes':[{'type':'bind','source':'/fixture','target':'/fixture','bind':{'create_host_path':True}}]} for role in ROLES}}
        images={role:self.models['target'][role]['image'] for role in ROLES};value=pinned_recipe(json.dumps(raw).encode(),images)
        for role in ROLES:
            self.assertEqual(value['services'][role]['image'],images[role])
            self.assertFalse(value['services'][role]['volumes'][0]['bind']['create_host_path'])
            self.assertEqual(value['services'][role]['environment'],raw['services'][role]['environment'])
    def test_dynamic_recipe_hooks_services_tags_and_interpolation_refuse(self):
        raw=json.loads(Path(self.recipes['target']['path']).read_bytes());images={r:self.models['target'][r]['image'] for r in ROLES}
        for kind in ('hook','build','service','interpolation','tag'):
            value=copy.deepcopy(raw);refs=dict(images)
            if kind=='hook':value['services']['api']['post_start']=[{'command':'foreign'}]
            elif kind=='build':value['services']['api']['build']='.'
            elif kind=='service':value['services']['writer']={}
            elif kind=='interpolation':value['services']['api']['environment']={'FOREIGN':'${OVERRIDE}'}
            else:refs['api']='mutable:tag'
            with self.subTest(kind=kind),self.assertRaises(MaintenanceControlError):pinned_recipe(json.dumps(value).encode(),refs)
    def test_health_log_churn_does_not_change_container_identity(self):
        value=copy.deepcopy(self.templates['rollback']['api']);before=container_observation(value)
        value['State']['Health']['Log'].append({'Output':'routine health check'})
        self.assertEqual(container_observation(value),before)

    def test_execution_recipe_treats_named_networks_and_volumes_as_existing_only(self):
        raw=json.loads(Path(self.recipes['target']['path']).read_bytes())
        raw['networks']={'default':{'name':'atlas-private','driver':'bridge','ipam':{'config':[]}}}
        raw['volumes']={'data':{'name':'atlas-data','driver':'local'}}
        images={role:self.models['target'][role]['image'] for role in ROLES}
        value=pinned_recipe(json.dumps(raw).encode(),images)
        self.assertEqual(value['networks']['default'],{'name':'atlas-private','external':True})
        self.assertEqual(value['volumes']['data'],{'name':'atlas-data','external':True})
    def test_unreviewed_config_resources_and_unsafe_network_names_refuse(self):
        original=json.loads(Path(self.recipes['target']['path']).read_bytes())
        images={role:self.models['target'][role]['image'] for role in ROLES}
        raw=copy.deepcopy(original);raw['configs']={'dynamic':{'file':'/foreign'}}
        with self.assertRaises(MaintenanceControlError):pinned_recipe(json.dumps(raw).encode(),images)
        raw=copy.deepcopy(original);raw['networks']={'default':{'name':'--foreign'}}
        with self.assertRaises(MaintenanceControlError):pinned_recipe(json.dumps(raw).encode(),images)


def digest_bytes(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()
