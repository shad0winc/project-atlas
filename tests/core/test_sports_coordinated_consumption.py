"""Fresh-interpreter consumption recovery, simulated native barrier for unit cases."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
support=load('coordinated_consumption_test','scripts/lib/sports-coordinated-consumption.py')
previous=load('coordinated_consumption_fixture','tests/core/test_sports_coordinated_recovery.py')
PROOF={'native':True,'metadata':True,'registry':True}
CHILD=r'''
import importlib.util,os,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('fresh_consumption',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=Path(sys.argv[2]);m.checkpoint=lambda name:os._exit(91) if name==sys.argv[4] else None
if sys.argv[4]=='partial-copy':
 original=m.pub.copy
 def copy(source,target,directory=False):
  if target.name.endswith('.preparing'):
   if directory:target.mkdir(mode=0o700);target=target/'unfinished'
   target.write_bytes(b'partial');target.chmod(0o600);os._exit(91)
  return original(source,target,directory)
 m.pub.copy=copy
barrier=lambda:m.pub.digest(root/'consumption/NATIVE_DETACHED.json')
if sys.argv[3]=='accept':m.accept(root,lambda *args:{'native':True,'metadata':True,'registry':True},barrier)
else:getattr(m,sys.argv[3])(root,barrier)
'''


def child(root,operation,boundary='',expected=0):
 result=subprocess.run([sys.executable,'-B','-c',CHILD,str(ROOT/'scripts/lib/sports-coordinated-consumption.py'),
  str(root),operation,boundary],capture_output=True,timeout=30)
 if result.returncode!=expected:raise AssertionError((operation,boundary,result.returncode,result.stderr.decode()[-1800:]))


@contextmanager
def fixture(imported=True,begun=True):
 with previous.fixture() as (root,maps):
  support.core.resume(root);support.arm(root)
  sources={}
  with support.writer(root) as current:
   for name in support.core.UNITS:
    if name in support.NATIVE:
     source=maps[1][name];target=source/'payload' if source.is_dir() else source
     target.write_text('native-consumed:'+name);sources[name]=source
    else:
     path=current/name;target=path/'payload' if path.is_dir() else path
     target.write_text('consumed:'+name)
  support.pub.write_json(root/'consumption/NATIVE_DETACHED.json',{'scope':'unit-simulated-native-barrier'})
  barrier=lambda:support.pub.digest(root/'consumption/NATIVE_DETACHED.json')
  if begun:support.begin_import(root,sources,'c'*64,barrier)
  if imported:child(root,'finish_import')
  yield root,barrier,sources


def verify(root):
 tx,directory,plan,control,state=support.load(root)
 rows=support.seal_rows(directory,plan)
 if support.positions(root,tx,directory,rows)!=[2]*21:raise AssertionError('incomplete restore')
 return state,control


class ConsumptionTests(unittest.TestCase):
 def test_every_import_copy_move_sync_and_intent_boundary_recovers(self):
  boundaries=['status:import-preparing','status:importing','status:imported']
  for name in support.NATIVE:
   boundaries += ['copy:'+name,'renamed:import-prepare:'+name]
   for label in ('import-old:','import-new:'):
    boundaries += [point+label+name for point in ('before:','renamed:','source-synced:','moved:')]
  for boundary in boundaries:
   with self.subTest(boundary=boundary),fixture(False) as (root,barrier,sources):
    child(root,'finish_import',boundary,91);child(root,'finish_import');child(root,'finish_import')
    self.assertEqual(support.load(root)[-1],'imported')
    child(root,'recover');self.assertEqual(verify(root)[0],'reverted')

 def test_every_twenty_one_unit_undo_rename_and_sync_death_recovers(self):
  for name in support.core.UNITS:
   for label in ('quarantine:','restore:'):
    for point in ('before:','renamed:','source-synced:','moved:'):
     boundary=point+label+name
     with self.subTest(boundary=boundary),fixture() as (root,barrier,sources):
      child(root,'recover',boundary,91);child(root,'recover');child(root,'recover')
      self.assertEqual(verify(root)[0],'reverted')

 def test_sealing_recovery_and_acceptance_state_deaths(self):
  for boundary in ('status:sealing','seal-written','status:sealed','status:recovering','status:reverted'):
   with self.subTest(boundary=boundary),fixture() as (root,barrier,sources):
    child(root,'recover',boundary,91);child(root,'recover');self.assertEqual(verify(root)[0],'reverted')
  for boundary in ('acceptance-written','status:verified','admission-released'):
   with self.subTest(boundary=boundary),fixture() as (root,barrier,sources):
    child(root,'recover');child(root,'accept',boundary,91);child(root,'accept')
    self.assertEqual(verify(root)[0],'verified')
    with support.reader(root) as current:self.assertEqual(len(list(current.iterdir())),21)

 def test_import_plan_publication_and_partial_copy_death_resume(self):
  with fixture(False,begun=False) as (root,barrier,sources):
   def die(name):
    if name=='import-plan-written':raise RuntimeError('interrupted before state update')
   support.checkpoint=die
   try:
    with self.assertRaises(RuntimeError):support.begin_import(root,sources,'c'*64,barrier)
   finally:support.checkpoint=lambda name:None
   child(root,'recover');verify(root)
  with fixture(False) as (root,barrier,sources):
   child(root,'finish_import','partial-copy',91);child(root,'finish_import');child(root,'recover');verify(root)

 def test_preserved_native_import_evidence_tamper_holds_recovery(self):
  with fixture() as (root,barrier,sources):
   (root/'consumption/previous/teamarr-db').write_text('unexpected')
   before=support.pub.digest(root,True)
   with self.assertRaises(ValueError):support.recover(root,barrier)
   # A sealing fence may be recorded, but no active or rollback unit moves.
   self.assertTrue((root/'transaction/old/teamarr-db').exists())
   self.assertFalse(any((root/'consumption/quarantine').iterdir()))

 def test_existing_publication_apis_refuse_any_consumption_marker(self):
  with fixture() as (root,barrier,sources):
   for operation in (support.core.resume,support.core.abort,support.core.ready):
    with self.subTest(operation=operation.__name__),self.assertRaises(ValueError):operation(root)
   with self.assertRaises(ValueError):support.core.accept(root,lambda *args:PROOF)

 def test_writer_validation_reader_and_public_reader_hold_exclusion(self):
  with previous.fixture() as (root,maps):
   support.core.resume(root);support.arm(root)
   with support.writer(root):
    with self.assertRaises((ValueError,OSError)):support.recover(root,lambda:'a'*64)
  with fixture() as (root,barrier,sources):
   with self.assertRaises(ValueError):
    with support.reader(root):pass
   child(root,'recover')
   with support.validation_reader(root):
    with self.assertRaises((ValueError,OSError)):support.accept(root,lambda *args:PROOF,barrier)
   child(root,'accept')
   with support.reader(root):
    with self.assertRaises((ValueError,OSError)):support.recover(root,barrier)

 def test_barrier_failure_does_not_mutate_import_or_recovery(self):
  for imported in (False,True):
   with self.subTest(imported=imported),fixture(imported) as (root,barrier,sources):
    before=support.pub.digest(root,True)
    def reject():raise ValueError('native fixture still running or identity changed')
    with self.assertRaises(ValueError):support.recover(root,reject)
    self.assertEqual(support.pub.digest(root,True),before)
    with self.assertRaises(ValueError):support.recover(root,lambda:'d'*64)

 def test_all_units_checked_before_first_undo_move(self):
  with fixture() as (root,barrier,sources):
   support.checkpoint=lambda name:(_ for _ in ()).throw(RuntimeError()) if name=='seal-written' else None
   try:
    with self.assertRaises(RuntimeError):support.recover(root,barrier)
   finally:support.checkpoint=lambda name:None
   path=root/'current'/support.core.UNITS[-1];path.write_text('unexpected')
   before=support.pub.digest(root,True)
   with self.assertRaises(ValueError):support.recover(root,barrier)
   self.assertEqual(support.pub.digest(root,True),before)

 def test_original_native_sources_not_needed_after_importing_intent(self):
  with fixture(False) as (root,barrier,sources):
   child(root,'finish_import','status:importing',91)
   import shutil
   for source in sources.values():
    if source.is_dir():shutil.rmtree(source)
    else:source.unlink()
   child(root,'finish_import');child(root,'recover');verify(root)

 def test_bad_validator_and_mutating_validator_do_not_release(self):
  with fixture() as (root,barrier,sources):
   child(root,'recover')
   for proof in ({},dict(PROOF,native=1),dict(PROOF,registry=False)):
    with self.subTest(proof=proof),self.assertRaises(ValueError):support.accept(root,lambda *args:proof,barrier)
   def mutate(current,*args):
    (current/'dispatcharr-jwt').write_text('modified');return PROOF
   with self.assertRaises(ValueError):support.accept(root,mutate,barrier)
   self.assertEqual(support.pub.read_json(root/'CONTROL.json')['admission'],'held')

if __name__=='__main__':unittest.main()
