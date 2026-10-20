import copy,fcntl,hashlib,json,os,unittest
from pathlib import Path
from types import SimpleNamespace
from tests.core import test_authority_service_adapter as fixture
from atlas.deployment_component_admission import HeldInitialPlan,reviewed_target
from atlas.deployment_component_rollout import digest
from atlas.maintenance_control import MaintenanceControlError

class AdmissionTests(unittest.TestCase):
 def setUp(self):
  self.case=fixture.AuthorityServiceAdapterTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
  c=self.case;c.unit.staging.unlink()
  self.record=c.root/'offline';self.record.mkdir()
  for role in ('api','portal'):(self.record/('ingress-'+role+'-build.Dockerfile')).write_bytes((role+' recipe').encode())
  (self.record/'maintenance-authority.service').write_bytes(c.proposal.read_bytes())
  (self.record/'ingress-application-source.tar.gz').write_bytes(c.generation.archive.read_bytes())
  self.ext={'source_archive_commit':c.generation.commit,'source_tree':c.generation.tree,'released_commit':'e'*40,
   'authority':{'unit_path':str(c.unit.target),'socket':'/run/atlas-maintenance-control/control.sock'},
   'images':{'api':{'image_id':'sha256:'+'7'*64},'portal':{'image_id':'sha256:'+'8'*64}},
   'caddy':{'image_id':'sha256:'+'3'*64,'immutable_source':str(c.generation.target),
    'binds':{'/etc/caddy':{'rw':False,'subdirectory':'infra/caddy'},'/srv':{'rw':False,'subdirectory':'infra/caddy/site'}}}}
  rollback={role:{'image':'sha256:'+char*64,'config':{'Labels':{},'Env':[]},'host_config':{'Mounts':[]},'mounts':[]}
   for role,char in (('api','1'),('portal','2'),('caddy','3'))}
  for target in ('/etc/caddy','/srv'):
   rollback['caddy']['host_config']['Mounts'].append({'Source':'/old'+target,'Target':target,'ReadOnly':True})
   rollback['caddy']['mounts'].append({'Source':'/old'+target,'Destination':target,'RW':False})
  self.probe=SimpleNamespace(extension=self.ext,record=self.record,target_fingerprint='c'*64,
     check_binding=lambda:True,removed=lambda:True,observe=lambda:{'fingerprint':'absent','identity':'absent'})
  class Backend:
   def __init__(self):self.calls=0
   def image(self,image):return image
   def inventory(self):
    self.calls+=1
    return [{'Id':'a'*64,'Name':'/unrelated','Image':'sha256:'+'b'*64,'Config':{},'HostConfig':{},'RestartCount':0,
             'Mounts':[],'State':{},'NetworkSettings':{'Networks':{}}}]
  class Containers:
   def __init__(self,outer):
    self.generation=c.generation.target
    self.models={'rollback':rollback,'target':reviewed_target(rollback,outer.ext,outer.record)}
    self.fingerprints={mode:{role:digest(model) for role,model in rows.items()} for mode,rows in self.models.items()}
    self.recipes={}
    for mode in ('target','rollback'):
     path=c.root/'assets'/(mode+'-recipe');self.recipes[mode]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    self.backend=Backend()
   def observe(self,role):return {'fingerprint':self.fingerprints['rollback'][role],'identity':digest(role+'-original')}
   def deny(self,*args):raise AssertionError('Mutation called during admission')
   apply=rollback=confirm=verify=source_inactive=deny
  self.containers=Containers(self)
  self.plan=HeldInitialPlan(c.root,'original-failed',c.stream.fileno(),generation=c.generation,unit=c.unit,probe=self.probe,containers=self.containers)
 def inspect(self,current='original-baseline'):
  return self.plan.inspect('rollout-admission-private',current,self.case.plan['protected'])
 def test_derive_native_six_surface_plan_without_journal_unit_or_runtime_mutation(self):
  result=self.inspect()
  self.assertEqual([e['name'] for e in result['plan']['surfaces']],['source','authority-unit','authority-service','api','portal','caddy'])
  self.assertTrue(result['unit_preparation_required']);self.assertFalse(result['production_rollout_execution_admitted'])
  self.assertFalse(self.case.unit.staging.exists());self.assertFalse(self.case.unit.target.exists())
  self.assertFalse(self.plan.engine._paths('rollout-admission-private').exists());self.case.assert_boundary()
 def test_real_shared_exclusive_flock_required(self):
  fcntl.flock(self.case.stream,fcntl.LOCK_UN)
  with self.assertRaisesRegex(MaintenanceControlError,'exclusive_parent'):self.inspect()
  fcntl.flock(self.case.stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def test_foreign_original_owner_refuses(self):
  self.plan.engine.identifier='foreign'
  with self.assertRaisesRegex(MaintenanceControlError,'owner_mismatch'):self.inspect()
 def test_already_staged_or_installed_unit_refuses_initial_plan(self):
  self.case.unit.prepare(held_guard=self.case.held)
  with self.assertRaisesRegex(MaintenanceControlError,'namespace_not_unprepared'):self.inspect()
 def test_published_generation_refuses_initial_plan(self):
  self.case.generation.publish(held_guard=self.case.held)
  with self.assertRaisesRegex(MaintenanceControlError,'archive_differs'):self.inspect()
 def test_unreviewed_target_privilege_or_environment_change_refuses(self):
  self.containers.models['target']['api']['host_config']['Privileged']=True
  with self.assertRaisesRegex(MaintenanceControlError,'target_delta'):self.inspect()
 def test_wrong_current_pointer_refuses(self):
  with self.assertRaisesRegex(MaintenanceControlError,'current_pointer'):self.inspect('other-baseline')
 def test_current_profile_not_matching_rollback_refuses(self):
  self.containers.observe=lambda role:{'fingerprint':'f'*64,'identity':'d'*64}
  with self.assertRaisesRegex(MaintenanceControlError,'rollback_profile'):self.inspect()
 def test_existing_authority_refuses(self):
  self.probe.observe=lambda:{'fingerprint':'f'*64,'identity':'a'*64}
  with self.assertRaisesRegex(MaintenanceControlError,'authority_not_absent'):self.inspect()
 def test_unrelated_inventory_drift_refuses(self):
  original=self.containers.backend.inventory
  def inventory():
   value=original()
   if self.containers.backend.calls>1:value[0]['RestartCount']=1
   return value
  self.containers.backend.inventory=inventory
  with self.assertRaisesRegex(MaintenanceControlError,'inventory_changed'):self.inspect()
 def test_changed_unit_record_refuses(self):
  (self.record/'maintenance-authority.service').write_bytes(b'different')
  with self.assertRaisesRegex(MaintenanceControlError,'unit_record'):self.inspect()
 def test_admission_exposes_no_action_methods(self):
  for method in ('apply','rollback','confirm','verify','source_inactive'):
   with self.assertRaisesRegex(RuntimeError,'cannot execute'):getattr(self.plan,method)('api')
if __name__=='__main__':unittest.main()
