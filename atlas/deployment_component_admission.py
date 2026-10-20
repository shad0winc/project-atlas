"""Read-only initial held plan derivation from verified native observations.

No journal preparation, source publication, unit staging, service actions, Docker
mutations, pointer publication or owner release is exposed by this module.
"""
from __future__ import annotations
import copy,hashlib,os
from pathlib import Path
from atlas.deployment_component_rollout import ComponentRollout,SURFACES,digest,require
from atlas.deployment_component_source import GenerationRolloutAdapter
from atlas.deployment_publication_journal import read_file
from atlas.deployment_component_containers import ROLES,inventory_fingerprint

def reviewed_target(rollback,extension,record):
    """Reproduce only the already-reviewed image/socket/immutable-Caddy delta."""
    expected=copy.deepcopy(rollback)
    labels={'io.project-atlas.archive-source-commit':extension['source_archive_commit'],
       'io.project-atlas.source-tree':extension['source_tree'],
       'org.opencontainers.image.revision':extension['released_commit'],
       'org.opencontainers.image.source':'https://github.com/shad0winc/project-atlas'}
    for role in ('api','portal'):
        expected[role]['image']=extension['images'][role]['image_id']
        expected[role]['config']['Labels'].update(labels|{
          'io.project-atlas.build-recipe-sha256':read_file(Path(record)/('ingress-'+role+'-build.Dockerfile'))})
    socket=str(Path(extension['authority']['socket']).parent)
    api=expected['api'];env=dict(item.split('=',1) for item in api['config']['Env'])
    require('ATLAS_MAINTENANCE_CONTROL_SOCKET' not in env,'admission_existing_socket_environment')
    env['ATLAS_MAINTENANCE_CONTROL_SOCKET']=extension['authority']['socket']
    api['config']['Env']=[key+'='+env[key] for key in sorted(env)]
    api['host_config']['Mounts'].append({'Type':'bind','Source':socket,'Target':socket,
      'ReadOnly':True,'BindOptions':{'Propagation':'rprivate'}})
    api['host_config']['Mounts'].sort(key=lambda item:item['Target'])
    api['mounts'].append({'Type':'bind','Source':socket,'Destination':socket,'Mode':'ro','RW':False,'Propagation':'rprivate'})
    api['mounts'].sort(key=lambda item:item['Destination'])
    for destination,item in extension['caddy']['binds'].items():
        require(item['rw'] is False,'admission_caddy_bind_writable')
        source=str(Path(extension['caddy']['immutable_source'])/item['subdirectory'])
        for rows,key in ((expected['caddy']['mounts'],'Destination'),(expected['caddy']['host_config']['Mounts'],'Target')):
            selected=[row for row in rows if row[key]==destination]
            require(len(selected)==1,'admission_caddy_bind_coverage_differs');selected[0]['Source']=source
    require(expected['caddy']['image']==extension['caddy']['image_id'],'admission_caddy_image_changed')
    return expected

class HeldInitialPlan:
    def __init__(self,runtime_root,owner,inherited_fd,*,generation,unit,probe,containers):
        self.root=Path(runtime_root);self.owner=owner;self.generation=generation
        self.unit,self.probe,self.containers=unit,probe,containers
        self.engine=ComponentRollout(self.root,owner,inherited_fd,adapter=self)
    @staticmethod
    def denied(*args,**kwargs):raise RuntimeError('Initial admission cannot execute rollout or publication actions')
    apply=rollback=confirm=verify=source_inactive=denied
    def boundary(self):
        self.engine._hold()
        flag=self.root/'maintenance/enabled';info=flag.lstat()
        return {'owner':self.engine._owner_snapshot(),'current':read_file(self.root/'deployments/current'),
                'flag':{'sha256':read_file(flag),'device':info.st_dev,'inode':info.st_ino,
                        'mode':info.st_mode,'uid':info.st_uid,'gid':info.st_gid}}
    def unit_absent(self):
        require(self.unit.target==Path(self.probe.extension['authority']['unit_path']),
                'admission_unit_path_differs')
        self.unit._proposal()
        require(all(not path.exists() and not path.is_symlink() for path in
                (self.unit.target,self.unit.staging,self.unit.retained)),'admission_unit_namespace_not_unprepared')
        return {'fingerprint':'absent','identity':'absent'}
    def observe(self,name):
        require(name in SURFACES,'admission_surface_unknown')
        if name=='source':
            require(self.generation.inspect()['namespace']=='staged','admission_generation_not_staged')
            return {'fingerprint':'absent','identity':'absent'}
        if name=='authority-unit':return self.unit_absent()
        if name=='authority-service':
            value=self.probe.observe();require(value=={'fingerprint':'absent','identity':'absent'},'admission_authority_not_absent')
            return value
        return self.containers.observe(name)
    def inspect(self,rollout,expected_current,protected):
        with self.engine._exclusive():
            initial=self.boundary()
            require(read_file(self.root/'deployments/current',limit=256)==(expected_current+'\n').encode(),
                    'admission_current_pointer_differs')
            self.probe.check_binding();extension=self.probe.extension
            require(self.generation.target==Path(extension['caddy']['immutable_source'])
                    and self.generation.root==self.root
                    and self.generation.commit==extension['source_archive_commit']
                    and self.generation.tree==extension['source_tree'],'admission_generation_identity_differs')
            state=self.generation.inspect()
            require(state['namespace']=='staged'
                    and self.generation.archive_sha256==read_file(self.probe.record/'ingress-application-source.tar.gz'),
                    'admission_generation_archive_differs')
            require(self.unit.sha256==read_file(self.probe.record/'maintenance-authority.service'),
                    'admission_unit_record_differs')
            require(self.containers.generation==self.generation.target,'admission_container_generation_differs')
            require(self.containers.models['target']==reviewed_target(self.containers.models['rollback'],extension,self.probe.record),
                    'admission_target_delta_differs')
            require(self.probe.removed() is True,'admission_authority_manager_not_absent')
            initial_inventory=inventory_fingerprint(self.containers.backend.inventory())
            for role in ROLES:
                require(self.containers.backend.image(self.containers.models['target'][role]['image'])==
                        self.containers.models['target'][role]['image'],'admission_target_image_missing')
                # Network and bind prerequisites are checked by actions immediately
                # before recreation. Future source/socket binds do not exist yet.
            before={name:self.observe(name) for name in SURFACES}
            require(all(before[role]['fingerprint']==self.containers.fingerprints['rollback'][role] for role in ROLES),
                    'admission_current_runtime_not_rollback_profile')
            source=GenerationRolloutAdapter(self.generation,self.containers,held_guard=lambda:self.boundary()==initial)
            targets={'source':source.target_fingerprint,'authority-unit':self.unit.target_fingerprint,
                     'authority-service':self.probe.target_fingerprint,**self.containers.fingerprints['target']}
            plan={'schema_version':1,'rollout_id':rollout,'original_owner':self.owner,'expected_current':expected_current,
              'generation':str(self.generation.target),
              'artifacts':{'source-archive':{'path':str(self.generation.archive),'sha256':self.generation.archive_sha256},
                  'target-recipe':dict(self.containers.recipes['target']),
                  'rollback-recipe':dict(self.containers.recipes['rollback']),
                  'authority-unit':{'path':str(self.unit.proposal),'sha256':self.unit.sha256}},
              'protected':dict(protected),'surfaces':[{'name':name,'before':before[name],'after':targets[name]} for name in SURFACES]}
            self.engine._plan(plan,rollout)
            require(read_file(self.root/'deployments/current',limit=256)==(expected_current+'\n').encode(),
                    'admission_current_pointer_differs')
            require(not self.engine._paths(rollout).exists() and not self.engine._paths(rollout).is_symlink(),
                    'admission_rollout_journal_already_present')
            require({name:self.observe(name) for name in SURFACES}==before,'admission_observation_changed')
            require(inventory_fingerprint(self.containers.backend.inventory())==initial_inventory,'admission_inventory_changed')
            self.probe.check_binding();require(self.boundary()==initial,'admission_held_boundary_changed')
            return {'plan':plan,'plan_sha256':digest(plan),'source_file_count':state['file_count'],
                    'unit_preparation_required':True,'production_rollout_execution_admitted':False,
                    'journal_created':False,'owner_release_permitted':False,'publication_permitted':False,
                    'public_reopen_permitted':False}
