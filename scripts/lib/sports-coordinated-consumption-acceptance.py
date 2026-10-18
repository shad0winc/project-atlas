"""Actual native writes admitted from and recovered through the private21 journal."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import uuid

ROOT=Path(__file__).resolve().parents[2]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path)
 result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
admission=module('coordinated_application_admission','scripts/lib/sports-coordinated-native-admission.py')
c=admission.c;core=c.core;pub=c.pub
previous=module('coordinated_consumption_parent','scripts/lib/sports-coordinated-recovery-acceptance.py')
metadata=previous.registry.refresh.writer.archive.metadata
CHILD=r'''
import importlib.util,os,sys
from pathlib import Path
root=Path(sys.argv[2])
spec=importlib.util.spec_from_file_location('fresh_native_admission',Path(sys.argv[1])/'scripts/lib/sports-coordinated-native-admission.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.c.checkpoint=lambda name:os._exit(91) if name==sys.argv[4] else None
getattr(m.c,sys.argv[3])(root,lambda:m.barrier(root))
'''


def fresh(root,operation,boundary='',expected=0):
 result=subprocess.run([sys.executable,'-B','-c',CHILD,str(ROOT),str(root),operation,boundary],
  capture_output=True,timeout=240)
 core.require(result.returncode==expected and len(result.stdout)<16384 and len(result.stderr)<16384)


def registry_check(current):
 with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
  view=Path(temporary);view.chmod(0o700)
  for name,relative,required,kind in previous.registry.SURFACES:
   target=view/relative;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
   pub.copy(current/('registry-'+name),target,kind=='directory')
  previous.registry.manifest(view)
  core.require(all(row[0]=='PASS' for row in previous.registry.consumer(view)))


def registry_mutate(current):
 # Valid fixture writes, not requests to real registry HTTP APIs.
 for name,relative,required,kind in previous.registry.SURFACES:
  path=current/('registry-'+name)
  candidates=list(path.rglob('*.json')) if path.is_dir() else [path] if path.suffix=='.json' or relative.endswith('.json') else []
  for item in candidates:
   item.write_text(json.dumps(json.loads(item.read_text()),indent=2)+'\n')
   with item.open('rb') as stream:os.fsync(stream.fileno())
 event=current/'registry-runtime-events'
 with event.open('a') as stream:
  stream.write(json.dumps({'schema':2,'id':'evt-coordinated-consumed','timestamp':'2026-10-17T12:01:00Z',
   'event':'request.available','source':'private-coordinated-consumption','payload':{'synthetic':True}})+'\n')
  stream.flush();os.fsync(stream.fileno())
 cursor=current/'registry-runtime-subscribers/module-notifications.cursor'
 cursor.write_text('1\n')
 with cursor.open('rb') as stream:os.fsync(stream.fileno())
 pub.sync(cursor.parent);pub.sync(current);registry_check(current)


class Rehearsal(previous.Rehearsal):
 def __init__(self):
  super().__init__();self.root=None;self.baseline=None;self.native=None;self.legacy=None
  self.consumer_id=None;self.restored_id=None;self.write_lease=None;self.read_lease=None
  self.imported=False;self.reverted=False;self.accepted=False;self.original_load=None

 def prepare_baseline(self,native,sandbox,baseline,base,dispatch):
  result=super().prepare_baseline(native,sandbox,baseline,base,dispatch)
  self.baseline=Path(baseline);return result

 def initialize(self,native,sandbox):
  super().initialize(native,sandbox)
  core.require(self.root is None and self.baseline is not None)
  self.legacy=native.consumer.scoped(sandbox)
  self.root=Path('/tmp')/('project-atlas-coordinated-recovery.'+uuid.uuid4().hex)
  self.root.mkdir(mode=0o700)
  sources={name:self.baseline/name for name in c.NATIVE}
  for name in ('sports-metadata','sports-metadata-policy'):sources[name]=self.extracted/name
  retained=self.baseline.parent/'coordinated-registry'
  for name,relative,required,kind in previous.registry.SURFACES:sources['registry-'+name]=retained/('registry-'+name)
  # Both generations start at the same valid captured fixture baseline.
  core.initialize(self.root,sources,sources,self.archive_sha);core.resume(self.root)
  registry_check(self.root/'current');metadata.check(native,self.root/'current','new')
  c.arm(self.root)
  print('COORDINATED_NATIVE_ADMISSION_BASELINE=PASS units=21',flush=True)

 def mutate(self,native,sandbox):
  core.require(self.consumer_id is not None and self.write_lease is not None)
  metadata.mutate(native,sandbox)
  adapter=SimpleNamespace(pub=pub,consumer=SimpleNamespace(writer=c.writer))
  metadata.mutate(adapter,self.root)
  with c.writer(self.root) as current:registry_mutate(current)
  print('COORDINATED_METADATA_AND_REGISTRY_FIXTURE_WRITES=PASS',flush=True)

 def wrap_native(self,native):
  core.require(self.native is None);self.native=native
  original_materialize=native.materialize
  original_arm=native.fence.arm;original_detach=native.fence.detach;original_import=native.import_writes
  def materialize(source,identifier):
   core.require(self.root is not None and self.installed)
   source=Path(source)
   # The old caller's input must match the actual21 destination bytes.
   for name in c.NATIVE:core.require(pub.digest(source/name,name=='dispatcharr-db')==pub.digest(self.root/'current'/name,name=='dispatcharr-db'))
   if self.consumer_id is None:
    self.consumer_id=identifier;self.write_lease=c.writer(self.root);self.write_lease.__enter__()
    admission.materialize(native,self.root,identifier)
   else:
    core.require(self.reverted and self.restored_id is None)
    self.restored_id=identifier;self.read_lease=c.validation_reader(self.root);self.read_lease.__enter__()
    admission.materialize(native,self.root,identifier,restored=True)
  def arm(sandbox,identifier):
   original_arm(sandbox,identifier)
   if identifier==self.consumer_id:
    core.require(Path(sandbox)==self.legacy)
    admission.bound(native,self.root,sandbox,identifier)
    before=pub.digest(self.root/'current',True)
    fresh(self.root,'recover',expected=1)
    try:admission.barrier(self.root)
    except ValueError:pass
    else:raise ValueError('Running native fixtures accepted as detached')
    core.require(pub.digest(self.root/'current',True)==before)
    print('COORDINATED_RUNNING_NATIVE_RECOVERY_REFUSED=PASS',flush=True)
  def detach(sandbox):
   original_detach(sandbox)
   ledger=native.fence.load(native.consumer.scoped(sandbox))
   if ledger['identifier']==self.consumer_id:
    core.require(Path(sandbox)==self.legacy and self.write_lease is not None)
    admission.mark_detached(native,self.root)
    lease,self.write_lease=self.write_lease,None;lease.__exit__(None,None,None)
   elif self.restored_id is not None and ledger['identifier']==self.restored_id:
    core.require(self.read_lease is not None)
    lease,self.read_lease=self.read_lease,None;lease.__exit__(None,None,None)
  def import_writes(sandbox,captured):
   original_import(sandbox,captured)
   core.require(Path(sandbox)==self.legacy and self.write_lease is None and not self.imported)
   admission.begin_capture(native,self.root,captured)
   fresh(self.root,'finish_import','renamed:import-new:dispatcharr-db',91)
   fresh(self.root,'finish_import');fresh(self.root,'finish_import')
   self.imported=True
   print('COORDINATED_NATIVE_CAPTURE_IMPORT_RESUMED=PASS',flush=True)
  native.materialize=materialize;native.fence.arm=arm;native.fence.detach=detach;native.import_writes=import_writes
  self.restore_native=lambda:(setattr(native,'materialize',original_materialize),setattr(native.fence,'arm',original_arm),
   setattr(native.fence,'detach',original_detach),setattr(native,'import_writes',original_import))
  return native

 def attach(self,component):
  core.require(self.original_load is None)
  self.original_load=component.load
  def load(name,path):
   result=self.original_load(name,path)
   return self.wrap_native(result) if name=='native_drill_support' else result
  component.load=load

 def check_reverted(self,native,root):
  tx,directory,plan,control,state=c.load(root)
  core.require(state in {'reverted','verified'} and plan['archive_sha256']==self.archive_sha)
  rows=c.seal_rows(directory,plan);core.require(c.positions(root,tx,directory,rows)==[2]*21)
  registry_check(root/'current');registry_check(directory/'quarantine')
  metadata.check(native,root/'current','new');metadata.check(native,directory/'quarantine','consumed')
  for name in c.NATIVE:core.require(pub.digest(root/'current'/name,name=='dispatcharr-db')==pub.digest(self.baseline/name,name=='dispatcharr-db'))
  admission.barrier(root)

 def recover(self,native,sandbox,complete_restored):
  core.require(self.imported and not self.reverted and Path(sandbox)==self.legacy)
  before=pub.digest(self.root,True)
  for boundary in ('seal-written','renamed:quarantine:dispatcharr-db','source-synced:restore:registry-users'):
   copied=Path('/tmp')/('project-atlas-coordinated-recovery.'+uuid.uuid4().hex)
   try:
    pub.copy(self.root,copied,True)
    fresh(copied,'recover',boundary,91);fresh(copied,'recover');fresh(copied,'recover')
    self.check_reverted(native,copied)
    core.require(pub.read_json(copied/'CONTROL.json')['admission']=='held')
   finally:
    if copied.exists():shutil.rmtree(copied)
   core.require(pub.digest(self.root,True)==before)
   print('COORDINATED_POST_WRITE_RECOVERY_DEATH=PASS boundary='+boundary,flush=True)
  fresh(self.root,'recover');fresh(self.root,'recover');self.check_reverted(native,self.root)
  self.reverted=True
  def accepted_restored():
   complete_restored()
   core.require(self.read_lease is None and self.restored_id is not None)
   self.check_reverted(native,self.root)
   def validator(current,quarantine,digest):
    self.check_reverted(native,self.root)
    for name in pub.SURFACES:core.require(pub.digest(current/name,name in pub.DIRECTORIES)==pub.digest(self.legacy/'current'/name,name in pub.DIRECTORIES))
    core.require(current==self.root/'current' and quarantine==self.root/'consumption/quarantine' and digest==self.archive_sha)
    return {'registry':True,'native':self.restored_id is not None,'metadata':True}
   c.accept(self.root,validator,lambda:admission.barrier(self.root))
   with c.reader(self.root) as current:core.require(len(list(current.iterdir()))==21)
   self.accepted=True
   print('COORDINATED_RESTORED_NATIVE_BOOT_RESTART_AND_ADMISSION=PASS',flush=True)
  super().recover(native,sandbox,accepted_restored)
  core.require(self.accepted)
  print(json.dumps({'version':1,'scope':'private-coordinated-21-native-consumption',
   'archive_sha256':self.archive_sha,'units':21,'native_admission':'owned-volume-copies-from-coordinated-current',
   'native_post_write_capture_import':True,'native_restart_from_coordinated_rollback':True,
   'native_import_process_deaths':1,'post_write_recovery_process_deaths':3,'metadata_consumer_writes':True,
   'registry_writes':'valid synthetic fixture bytes and runtime event/cursor; no real registry HTTP writes',
   'direct_native_mounts_of_journal':False,'production_state_access':False,'live_restore_enabled':False,
   'power_loss_proven':False,'full_production_operational_restore':False},sort_keys=True),flush=True)

 def cleanup(self,component):
  try:
   for attribute in ('write_lease','read_lease'):
    lease=getattr(self,attribute)
    if lease is not None:
     setattr(self,attribute,None);lease.__exit__(None,None,None)
  finally:
   if self.original_load is not None:component.load=self.original_load
   if self.native is not None:self.restore_native()
   if self.root is not None and self.root.exists():
    core.scoped(self.root);shutil.rmtree(self.root)
