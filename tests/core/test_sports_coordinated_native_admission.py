"""Admission contract tests with explicit Docker/ownership simulation, no native boot claim."""
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path)
 result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
admission=load('native_admission_tests','scripts/lib/sports-coordinated-native-admission.py')
previous=load('native_admission_fixtures','tests/core/test_sports_coordinated_recovery.py')
c=admission.c


@contextmanager
def fixture():
 with previous.fixture() as (root,maps),tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.',dir='/tmp') as tmp:
  lifecycle=Path(tmp);lifecycle.chmod(0o700)
  identifier='1'*32
  apps={'dispatcharr':{'id':'2'*64,'started_at':'2026-10-18T01:00:00Z'},
   'teamarr':{'id':'3'*64,'started_at':'2026-10-18T01:00:00Z'}}
  ledger={'stage':'armed','identifier':identifier,'apps':apps,'binding':{'plan':'4'*64,'exposure':'5'*64}}
  volumes={role:lifecycle/role for role in apps}
  for path in volumes.values():path.mkdir(mode=0o700)
  references={role:set() for role in apps}
  def names(i,role):
   c.require(i==identifier);return role+'-app',role+'-volume'
  def refs(volume):return references[volume.removesuffix('-volume')]
  def detached(value):
   c.require(value==ledger and ledger['stage']=='detached' and not any(references.values()))
  copy=Mock(side_effect=lambda source,target,directory=False,source_owner=None,target_owner=None:c.pub.copy(source,target,directory))
  native=SimpleNamespace(volume_path=lambda i,role:volumes[role],copy_tree=copy,
   consumer=SimpleNamespace(scoped=c.core.consumer.scoped),workspace=Mock(),
   fence=SimpleNamespace(IMAGES={role:role for role in apps},names=names,references=refs,
    load=lambda path:deepcopy(ledger),volume=Mock(),inspect_app=Mock(side_effect=lambda i,role,target,epoch:(epoch,True)),
    assert_detached=Mock(side_effect=detached)))
  c.core.resume(root);c.arm(root)
  with patch.object(admission,'module',return_value=native),patch.object(admission,'controller_identity',return_value=(0,0)):
   yield SimpleNamespace(root=root,maps=maps,lifecycle=lifecycle,identifier=identifier,apps=apps,
    ledger=ledger,volumes=volumes,references=references,native=native,copy=copy)


def start(f):
 admission.materialize(f.native,f.root,f.identifier)
 for role,epoch in f.apps.items():f.references[role].add(epoch['id'])
 c.pub.write_json(f.lifecycle/'DOCKER_LIFECYCLE.json',f.ledger)
 admission.bound(f.native,f.root,f.lifecycle,f.identifier)


def stop(f):
 f.ledger['stage']='detached'
 for value in f.references.values():value.clear()
 c.pub.write_json(f.lifecycle/'DOCKER_LIFECYCLE.json',f.ledger)
 admission.mark_detached(f.native,f.root)


class NativeAdmissionTests(unittest.TestCase):
 def test_copy_mapping_binding_detach_capture_and_rollback(self):
  with fixture() as f:
   with c.writer(f.root):start(f);stop(f)
   self.assertEqual(f.copy.call_args_list[0].args[3:],((0,0),(1000,1000)))
   self.assertEqual(f.copy.call_args_list[1].kwargs,{'source_owner':(0,0)})
   self.assertEqual(admission.barrier(f.root),c.pub.digest(f.root/'consumption/NATIVE_DETACHED.json'))
   capture=f.lifecycle/'captured';capture.mkdir(mode=0o700)
   for name in c.NATIVE:
    source=f.maps[1][name];c.pub.copy(source,capture/name,name=='dispatcharr-db')
    path=capture/name/'payload' if name=='dispatcharr-db' else capture/name
    path.write_text('native-committed-'+name)
   receipt={'version':1,'marker':'native-consumer-committed','copied_wal':False,
    'ledger_sha256':c.pub.digest(f.lifecycle/'DOCKER_LIFECYCLE.json'),
    'surfaces':{name:c.core.tree_hash(capture/name,name) for name in c.NATIVE}}
   c.pub.write_json(capture/'CAPTURE.json',receipt)
   admission.begin_capture(f.native,f.root,capture)
   c.finish_import(f.root,lambda:admission.barrier(f.root))
   c.recover(f.root,lambda:admission.barrier(f.root))
   tx,directory,plan,control,state=c.load(f.root)
   self.assertEqual(state,'reverted');self.assertEqual(c.positions(f.root,tx,directory,c.seal_rows(directory,plan)),[2]*21)

 def test_non_root_controller_refused_before_inspection_or_copy(self):
  with fixture() as f,patch.object(admission,'controller_identity',return_value=(1000,1000)):
   with self.assertRaises(ValueError):admission.materialize(f.native,f.root,f.identifier)
   f.copy.assert_not_called()

 def test_wrong_native_source_rejected_before_any_volume_copy(self):
  with fixture() as f:
   (f.root/'current/dispatcharr-jwt').write_text('tampered')
   with c.writer(f.root),self.assertRaises(ValueError):admission.materialize(f.native,f.root,f.identifier)
   f.copy.assert_not_called()
   self.assertFalse((f.root/'consumption/NATIVE_INTENT.json').exists())

 def test_nonempty_or_referenced_volume_refuses_before_copy(self):
  for kind in ('nonempty','referenced'):
   with self.subTest(kind=kind),fixture() as f:
    if kind=='nonempty':
     path=f.volumes['teamarr']/'existing';path.write_text('occupied');path.chmod(0o600)
    else:f.references['teamarr'].add('9'*64)
    with c.writer(f.root),self.assertRaises(ValueError):admission.materialize(f.native,f.root,f.identifier)
    f.copy.assert_not_called()

 def test_running_missing_detach_or_rebound_epoch_refuses_recovery_barrier(self):
  for kind in ('running','missing-detach','epoch','ledger'):
   with self.subTest(kind=kind),fixture() as f:
    with c.writer(f.root):
     start(f)
     if kind!='missing-detach':stop(f)
    if kind=='running':f.references['dispatcharr'].add(f.apps['dispatcharr']['id'])
    elif kind=='epoch':f.ledger['apps']['teamarr']['started_at']='changed'
    elif kind=='ledger':c.pub.write_json(f.lifecycle/'DOCKER_LIFECYCLE.json',dict(f.ledger,extra=True))
    with self.assertRaises((ValueError,OSError)):admission.barrier(f.root)

 def test_capture_receipt_must_match_bound_lifecycle_and_each_native_hash(self):
  with fixture() as f:
   with c.writer(f.root):start(f);stop(f)
   capture=f.lifecycle/'captured';capture.mkdir(mode=0o700)
   for name in c.NATIVE:c.pub.copy(f.maps[1][name],capture/name,name=='dispatcharr-db')
   receipt={'version':1,'marker':'native-consumer-committed','copied_wal':False,
    'ledger_sha256':c.pub.digest(f.lifecycle/'DOCKER_LIFECYCLE.json'),
    'surfaces':{name:c.core.tree_hash(capture/name,name) for name in c.NATIVE}}
   for kind in ('ledger','surface','marker'):
    bad=deepcopy(receipt)
    if kind=='ledger':bad['ledger_sha256']='a'*64
    elif kind=='surface':bad['surfaces']['teamarr-db']='a'*64
    else:bad['marker']='after-dump'
    c.pub.write_json(capture/'CAPTURE.json',bad)
    with self.subTest(kind=kind),self.assertRaises(ValueError):admission.begin_capture(f.native,f.root,capture)
   self.assertFalse((f.root/'consumption/IMPORT.json').exists())

 def test_native_component_hooks_hold_lease_through_detach_then_import(self):
  module=load('native_hook_integration','scripts/lib/sports-coordinated-consumption-acceptance.py')
  with fixture() as f:
   def armed(path,identifier):
    for role,epoch in f.apps.items():f.references[role].add(epoch['id'])
    c.pub.write_json(f.lifecycle/'DOCKER_LIFECYCLE.json',f.ledger)
   def detached(path):
    f.ledger['stage']='detached'
    for value in f.references.values():value.clear()
    c.pub.write_json(f.lifecycle/'DOCKER_LIFECYCLE.json',f.ledger)
   f.native.materialize=Mock();original=f.native.materialize
   f.native.import_writes=Mock();f.native.fence.arm=Mock(side_effect=armed);f.native.fence.detach=Mock(side_effect=detached)
   rehearsal=module.Rehearsal();rehearsal.root=f.root;rehearsal.installed=True;rehearsal.legacy=f.lifecycle
   def fresh(root,operation,boundary='',expected=0):
    if expected in (1,91):return
    getattr(module.c,operation)(root,lambda:module.admission.barrier(root))
   with patch.object(module.admission,'module',return_value=f.native),patch.object(module.admission,'controller_identity',return_value=(0,0)),patch.object(module,'fresh',side_effect=fresh):
    try:
     native=rehearsal.wrap_native(f.native)
     native.materialize(next(iter(f.maps[1].values())).parent,f.identifier)
     self.assertIsNotNone(rehearsal.write_lease);original.assert_not_called()
     native.fence.arm(f.lifecycle,f.identifier);native.fence.detach(f.lifecycle)
     self.assertIsNone(rehearsal.write_lease)
     captured=f.lifecycle/'captured';captured.mkdir(mode=0o700)
     for name in c.NATIVE:c.pub.copy(f.maps[1][name],captured/name,name=='dispatcharr-db')
     c.pub.write_json(captured/'CAPTURE.json',{'version':1,'marker':'native-consumer-committed','copied_wal':False,
      'ledger_sha256':c.pub.digest(f.lifecycle/'DOCKER_LIFECYCLE.json'),
      'surfaces':{name:c.core.tree_hash(captured/name,name) for name in c.NATIVE}})
     native.import_writes(f.lifecycle,captured)
     self.assertTrue(rehearsal.imported);self.assertEqual(module.c.load(f.root)[-1],'imported')
    finally:
     if rehearsal.write_lease is not None:rehearsal.write_lease.__exit__(None,None,None)
     if rehearsal.native is not None:rehearsal.restore_native()

 def test_parent_cannot_recover_without_completed_native_import(self):
  module=load('admission_composition_guard','scripts/lib/sports-coordinated-consumption-acceptance.py')
  rehearsal=module.Rehearsal()
  with self.assertRaises(ValueError):rehearsal.recover(None,Path('/tmp/invalid'),lambda:None)

 def test_cleanup_restores_loader_and_patched_native_methods(self):
  module=load('admission_cleanup_guard','scripts/lib/sports-coordinated-consumption-acceptance.py')
  rehearsal=module.Rehearsal();component=SimpleNamespace(load=lambda *args:SimpleNamespace())
  original=component.load;rehearsal.attach(component)
  self.assertIsNot(component.load,original)
  rehearsal.cleanup(component);self.assertIs(component.load,original)

class SemanticCompositionTests(unittest.TestCase):
 def test_actual_metadata_and_registry_consumers_validate_post_write_quarantine(self):
  module=load('post_write_semantic_composition','scripts/lib/sports-coordinated-consumption-acceptance.py')
  cc=module.c
  import uuid,shutil
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   parent=Path(tmp);parent.chmod(0o700);source=parent/'source';source.mkdir(mode=0o700)
   native=SimpleNamespace(pub=module.pub)
   module.metadata.create(native,source,'new')
   registries=parent/'registries';registries.mkdir(mode=0o700)
   module.previous.registry.populate({relative:registries/relative for name,relative,requirement,kind in module.previous.registry.SURFACES})
   sources={name:source/name for name in ('sports-metadata','sports-metadata-policy')}
   for name in cc.NATIVE:
    path=source/name
    if name=='dispatcharr-db':path.mkdir(mode=0o700);leaf=path/'unit-payload'
    else:leaf=path
    leaf.write_text('baseline');leaf.chmod(0o600);sources[name]=path
   for name,relative,requirement,kind in module.previous.registry.SURFACES:sources['registry-'+name]=registries/relative
   root=Path('/tmp')/('project-atlas-coordinated-recovery.'+uuid.uuid4().hex);root.mkdir(mode=0o700)
   try:
    cc.core.initialize(root,sources,sources,'a'*64);cc.core.resume(root);cc.arm(root)
    adapter=SimpleNamespace(pub=module.pub,consumer=SimpleNamespace(writer=cc.writer))
    module.metadata.mutate(adapter,root)
    with cc.writer(root) as current:module.registry_mutate(current)
    cc.pub.write_json(root/'consumption/NATIVE_DETACHED.json',{'unit_simulation':True})
    barrier=lambda:cc.pub.digest(root/'consumption/NATIVE_DETACHED.json')
    cc.begin_import(root,{name:sources[name] for name in cc.NATIVE},'b'*64,barrier)
    cc.finish_import(root,barrier);cc.recover(root,barrier)
    module.registry_check(root/'current');module.registry_check(root/'consumption/quarantine')
    module.metadata.check(native,root/'current','new');module.metadata.check(native,root/'consumption/quarantine','consumed')
   finally:shutil.rmtree(root)

if __name__=='__main__':unittest.main()
