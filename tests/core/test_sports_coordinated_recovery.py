"""Fresh-interpreter death tests for the private twenty-one-unit journal."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[2]
ENTRY=ROOT/'scripts/lib/sports-coordinated-recovery.py'
spec=importlib.util.spec_from_file_location('coordinated_tests',ENTRY)
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
PROOF={'registry':True,'native':True,'metadata':True}
CHILD=r'''
import importlib.util,os,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('fresh_coordinator',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.checkpoint=lambda name:os._exit(91) if name==sys.argv[4] else None
if sys.argv[4]=='partial-copy':
 original=m.pub.copy
 def interrupted_copy(source,target,directory=False):
  if target.name.endswith('.preparing'):
   if directory:target.mkdir(mode=0o700);target=target/'incomplete'
   target.write_bytes(b'incomplete');target.chmod(0o600);os._exit(91)
  return original(source,target,directory)
 m.pub.copy=interrupted_copy
if sys.argv[3]=='accept':m.accept(Path(sys.argv[2]),lambda *args:{'registry':True,'native':True,'metadata':True})
else:getattr(m,sys.argv[3])(Path(sys.argv[2]))
'''

@contextmanager
def fixture():
 with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
  base=Path(temporary);maps=[]
  for generation in ('old','new'):
   parent=base/generation;parent.mkdir(mode=0o700);sources={}
   for name in support.UNITS:
    path=parent/name
    if name in support.DIRECTORIES:path.mkdir(mode=0o700);leaf=path/'payload'
    else:leaf=path
    leaf.write_text(generation+':'+name);leaf.chmod(0o600);sources[name]=path
   maps.append(sources)
  root=Path('/tmp')/('project-atlas-coordinated-recovery.'+uuid.uuid4().hex)
  root.mkdir(mode=0o700)
  try:
   support.initialize(root,*maps,'a'*64)
   yield root,maps
  finally:shutil.rmtree(root)


def child(root,operation,boundary='',expected=0):
 result=subprocess.run([sys.executable,'-B','-c',CHILD,str(ENTRY),str(root),operation,boundary],
  capture_output=True,timeout=30)
 if result.returncode!=expected:
  raise AssertionError((operation,boundary,result.returncode,result.stderr.decode()[-1800:]))


def verify(root,which):
 tx,plan,control,state=support.journal(root)
 support.current_hashes(root,plan,which)
 if control['admission']!='held':raise AssertionError('admission released early')


class CoordinatorTests(unittest.TestCase):
 def test_publish_accept_read_and_repeat_are_bound_to_all_twenty_one(self):
  with fixture() as (root,maps):
   child(root,'resume');verify(root,'new')
   with self.assertRaises(ValueError):support.ready(root)
   child(root,'accept');self.assertEqual(support.ready(root),'new')
   child(root,'resume');child(root,'accept')
   with support.reader(root) as current:self.assertEqual(len(list(current.iterdir())),21)
   with self.assertRaises(ValueError):support.abort(root)

 def test_death_at_every_apply_and_abort_rename_and_directory_sync(self):
  # Both directions are recovered by fresh interpreters from on-disk evidence.
  for operation,prefixes,generation in (('resume',('old:','new:'),'new'),('abort',('undo-new:','undo-old:'),'old')):
   for name in support.UNITS:
    for prefix in prefixes:
     for point in ('before:','renamed:','source-synced:','moved:'):
      boundary=point+prefix+name
      with self.subTest(operation=operation,boundary=boundary),fixture() as (root,maps):
       if operation=='abort':child(root,'resume')
       child(root,operation,boundary,91)
       child(root,operation);child(root,operation);verify(root,generation)

 def test_death_during_each_prepared_copy_and_commit_can_resume_or_abort(self):
  for name in support.UNITS:
   for point in ('copy:','renamed:prepare:'):
    for direction in ('resume','abort'):
     with self.subTest(name=name,point=point,direction=direction),fixture() as (root,maps):
      child(root,'resume',point+name,91);child(root,direction)
      verify(root,'new' if direction=='resume' else 'old')
      child(root,'accept');self.assertEqual(support.ready(root),'new' if direction=='resume' else 'old')

 def test_durable_state_and_acceptance_publication_death(self):
  for boundary in ('status:staged','status:applying','status:applied-awaiting-verification'):
   for direction in ('resume','abort'):
    with self.subTest(boundary=boundary,direction=direction),fixture() as (root,maps):
     child(root,'resume',boundary,91);child(root,direction);verify(root,'new' if direction=='resume' else 'old')
  for direction,which in (('resume','new'),('abort','old')):
   for boundary in ('acceptance-written','status:verified-'+which,'admission-released'):
    with self.subTest(direction=direction,boundary=boundary),fixture() as (root,maps):
     child(root,direction);child(root,'accept',boundary,91);child(root,'accept')
     self.assertEqual(support.ready(root),which)
  for boundary in ('status:aborting','status:aborted-awaiting-verification'):
   with self.subTest(boundary=boundary),fixture() as (root,maps):
    child(root,'resume');child(root,'abort',boundary,91);child(root,'abort');verify(root,'old')
  for boundary in ('status:aborting-preparation','status:aborted-preparation-awaiting-verification'):
   with self.subTest(boundary=boundary),fixture() as (root,maps):
    child(root,'abort',boundary,91);child(root,'abort');verify(root,'old')

 def test_partial_copy_death_recovers_without_trusting_partial_payload(self):
  for operation in ('resume','abort'):
   with self.subTest(operation=operation),fixture() as (root,maps):
    child(root,'resume','partial-copy',91);child(root,operation)
    verify(root,'new' if operation=='resume' else 'old')
    child(root,'accept')

 def test_original_sources_not_needed_after_staging(self):
  with fixture() as (root,maps):
   child(root,'resume','status:staged',91)
   for sources in maps:
    shutil.rmtree(next(iter(sources.values())).parent)
   shutil.rmtree(root/'source');(root/'source').mkdir(mode=0o700)
   child(root,'resume');child(root,'abort');verify(root,'old')

 def test_validation_refusal_and_mutation_leave_admission_held(self):
  with fixture() as (root,maps):
   child(root,'resume')
   for proof in ({},dict(PROOF,native=False),dict(PROOF,native=1)):
    with self.subTest(proof=proof),self.assertRaises(ValueError):support.accept(root,lambda *args:proof)
   verify(root,'new')
   def mutate(current,*args):
    (current/'dispatcharr-jwt').write_text('changed');return PROOF
   with self.assertRaises(ValueError):support.accept(root,mutate)
   self.assertEqual(support.pub.read_json(root/'CONTROL.json')['admission'],'held')

 def test_validate_all_units_before_any_resume_or_abort_mutation(self):
  for operation in ('resume','abort'):
   with self.subTest(operation=operation),fixture() as (root,maps):
    child(root,'resume','status:staged',91)
    if operation=='abort':child(root,'resume')
    target=root/'transaction'/('incoming' if operation=='resume' else 'old')/support.UNITS[-1]
    target.write_text('tampered')
    before=support.pub.digest(root,True)
    with self.assertRaises(ValueError):getattr(support,operation)(root)
    self.assertEqual(support.pub.digest(root,True),before)

 def test_missing_source_during_preparation_and_changed_plan_refused(self):
  with fixture() as (root,maps):
   (root/'source'/'dispatcharr-jwt').unlink()
   before=support.pub.digest(root/'current',True)
   with self.assertRaises((ValueError,OSError)):support.resume(root)
   self.assertEqual(support.pub.digest(root/'current',True),before)
   tx=root/'transaction';plan=support.pub.read_json(tx/'PLAN.json')
   plan['archive_sha256']='b'*64;support.pub.write_json(tx/'PLAN.json',plan)
   with self.assertRaises(ValueError):support.abort(root)

 def test_symlink_unknown_entry_and_incomplete_setup_refused(self):
  for kind in ('symlink','extra','missing-plan'):
   with self.subTest(kind=kind),fixture() as (root,maps):
    if kind=='symlink':
     path=root/'current'/'dispatcharr-jwt';path.unlink();path.symlink_to(maps[0]['dispatcharr-jwt'])
    elif kind=='extra':(root/'unexpected').write_text('untrusted')
    else:(root/'transaction'/'PLAN.json').unlink()
    with self.assertRaises((ValueError,OSError)):support.resume(root)

 def test_shared_read_lease_blocks_mutation_and_detects_changed_content(self):
  with fixture() as (root,maps):
   child(root,'resume');child(root,'accept')
   with support.reader(root):
    result=subprocess.run([sys.executable,'-B','-c',CHILD,str(ENTRY),str(root),'resume',''],capture_output=True,timeout=30)
    self.assertNotEqual(result.returncode,0)
   with self.assertRaises(ValueError):
    with support.reader(root) as current:(current/'dispatcharr-jwt').write_text('changed')

class CompositionTests(unittest.TestCase):
 def test_representative_same_archive_trial_uses_actual_metadata_and_registry_consumers(self):
  entry=ROOT/'scripts/lib/sports-coordinated-recovery-acceptance.py'
  spec=importlib.util.spec_from_file_location('coordinated_composition_test',entry)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  native=module.registry.load('coordinated_unit_native','scripts/lib/sports-native-consumption.py')
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   parent=Path(tmp);parent.chmod(0o700);baseline=parent/'baseline';baseline.mkdir(mode=0o700)
   previous=baseline/'PRE_ARCHIVE';previous.mkdir(mode=0o700)
   for generation,directory in (('old',previous),('new',baseline)):
    for name in native.NATIVE:
     path=directory/name
     if name=='dispatcharr-db':path.mkdir(mode=0o700);path=path/'unit-payload'
     path.write_text(generation);path.chmod(0o600)
   metadata=parent/'metadata';metadata.mkdir(mode=0o700)
   module.registry.refresh.writer.archive.metadata.create(native,metadata,'new')
   original=parent/'registry';original.mkdir(mode=0o700)
   module.registry.populate({relative:original/relative for name,relative,requirement,kind in module.registry.SURFACES})
   retained=parent/'retained';retained.mkdir(mode=0o700)
   for name,relative,requirement,kind in module.registry.SURFACES:
    support.pub.copy(original/relative,retained/('registry-'+name),kind=='directory')
   for operation,boundary in (('resume','renamed:new:dispatcharr-db'),('abort','renamed:undo-new:registry-users')):
    with self.subTest(operation=operation):module.trial(native,baseline,metadata,retained,'a'*64,operation,boundary)

 def test_parent_cannot_initialize_without_completed_coordinated_archive_binding(self):
  from unittest.mock import patch
  entry=ROOT/'scripts/lib/sports-coordinated-recovery-acceptance.py'
  spec=importlib.util.spec_from_file_location('coordinated_guard_test',entry)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  rehearsal=module.Rehearsal()
  with patch.object(module.registry.Rehearsal,'initialize') as parent:
   with self.assertRaises(ValueError):rehearsal.initialize(None,None)
   parent.assert_not_called()

 def test_successful_parent_without_archive_callback_is_refused(self):
  from unittest.mock import patch,Mock
  entry=ROOT/'scripts/lib/sports-coordinated-recovery-acceptance.py'
  spec=importlib.util.spec_from_file_location('coordinated_missing_gate',entry)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  rehearsal=module.Rehearsal();native=Mock()
  original=module.registry.accept_archive
  with patch.object(module.registry.Rehearsal,'prepare_baseline',return_value=None):
   with self.assertRaises(ValueError):rehearsal.prepare_baseline(native,None,Path('/tmp/baseline'),None,None)
  self.assertIs(module.registry.accept_archive,original)
  self.assertIsNone(rehearsal.coordinated_archive_sha)

if __name__=='__main__':unittest.main()
