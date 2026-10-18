"""Same-archive private journal acceptance composed with the accepted native rehearsal."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import importlib.util

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('coordinated_acceptance_core',ROOT/'scripts/lib/sports-coordinated-recovery.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
registry=core.registry
CHILD=r'''
import importlib.util,os,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('fresh_journal',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.checkpoint=lambda label:os._exit(91) if label==sys.argv[4] else None
getattr(m,sys.argv[3])(Path(sys.argv[2]))
'''


def fresh(root,operation,boundary='',expected=0):
 result=subprocess.run([sys.executable,'-B','-c',CHILD,str(ROOT/'scripts/lib/sports-coordinated-recovery.py'),
  str(root),operation,boundary],capture_output=True,timeout=180)
 core.require(result.returncode==expected and len(result.stdout)<16384 and len(result.stderr)<16384)


def retain_registry(native,archive,env,destination):
 """Use the real validated safe archive stager before its owning fixture disappears."""
 source=registry.private_archive_environment(env)
 native.workspace(destination.parent)
 core.require(destination.name=='coordinated-registry')
 core.require(not destination.exists() and not destination.is_symlink())
 with tempfile.TemporaryDirectory(prefix='atlas-registry-restore.',dir='/tmp') as temporary:
  parent=Path(temporary);parent.chmod(0o700)
  stage_env=registry.environment(parent)
  result=registry.shell('source "$RECOVERY_LIBRARY"; atlas_backup_recovery_stage_archive "$ARCHIVE" "$STAGE_PARENT"',
   dict(stage_env,ARCHIVE=str(archive),STAGE_PARENT=str(parent)),180)
  core.require(result.returncode==0)
  stage=Path(result.stdout.decode().strip())
  core.require(stage.parent==parent and stage.name.startswith('project-atlas-restore.'))
  core.require(all(row[0]=='PASS' for row in registry.consumer(stage)))
  destination.mkdir(mode=0o700)
  for name,relative,requirement,kind in registry.SURFACES:
   core.pub.copy(stage/relative,destination/('registry-'+name),kind=='directory')
 core.pub.sync(destination)
 return registry.load('coordinated_archive_hash','scripts/lib/sports-backup-archive.py').sha(archive)


def validation(native,current,which,archive_sha,expected_archive,native_hashes):
 core.require(archive_sha==expected_archive)
 # Consumers read a private verification view copied from the actual journal destinations.
 with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
  view=Path(temporary);view.chmod(0o700)
  for name,relative,requirement,kind in registry.SURFACES:
   target=view/relative;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
   core.pub.copy(current/('registry-'+name),target,kind=='directory')
  registry.manifest(view)
  core.require(all(row[0]=='PASS' for row in registry.consumer(view)))
 registry.refresh.writer.archive.metadata.check(native,current,which)
 core.require({name:core.tree_hash(current/name,name) for name in native.NATIVE}==native_hashes[which])
 return {'registry':True,'metadata':True,'native':True}


def trial(native,baseline,extracted,retained,archive_sha,operation,boundary):
 with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
  parent=Path(temporary);parent.chmod(0o700)
  oldmeta=parent/'old-metadata';oldmeta.mkdir(mode=0o700)
  registry.refresh.writer.archive.metadata.create(native,oldmeta,'old')
  oldreg=parent/'old-registry';oldreg.mkdir(mode=0o700)
  registry.populate({relative:oldreg/relative for name,relative,requirement,kind in registry.SURFACES},old=True)
  old={name:baseline/'PRE_ARCHIVE'/name for name in native.NATIVE}
  new={name:baseline/name for name in native.NATIVE}
  for name in ('sports-metadata','sports-metadata-policy'):
   old[name]=oldmeta/name;new[name]=extracted/name
  for name,relative,requirement,kind in registry.SURFACES:
   old['registry-'+name]=oldreg/relative;new['registry-'+name]=retained/('registry-'+name)
  hashes={generation:{name:core.tree_hash(sources[name],name) for name in native.NATIVE}
   for generation,sources in (('old',old),('new',new))}
  root=Path('/tmp')/('project-atlas-coordinated-recovery.'+uuid.uuid4().hex)
  root.mkdir(mode=0o700)
  try:
   core.initialize(root,old,new,archive_sha)
   if operation=='abort':fresh(root,'resume')
   fresh(root,operation,boundary,91);fresh(root,operation);fresh(root,operation)
   core.require(core.pub.read_json(root/'CONTROL.json')['admission']=='held')
   try:core.ready(root)
   except ValueError:pass
   else:raise ValueError('Unverified journal admitted')
   expected='new' if operation=='resume' else 'old'
   validator=lambda current,which,digest:validation(native,current,which,digest,archive_sha,hashes)
   core.require(core.accept(root,validator)==expected and core.ready(root)==expected)
   with core.reader(root) as current:core.require(len(list(current.iterdir()))==21)
   print('COORDINATED_SAME_ARCHIVE_RECOVERY=PASS direction='+operation+' boundary='+boundary,flush=True)
  finally:shutil.rmtree(root)


class Rehearsal(registry.Rehearsal):
 def __init__(self):
  super().__init__();self.coordinated_archive_sha=None

 def prepare_baseline(self,native,sandbox,baseline,base,dispatch):
  native.workspace(Path(baseline).parent)
  retained=Path(baseline).parent/'coordinated-registry'
  original=registry.accept_archive
  completed=[]
  def accept(n,archive,env):
   original(n,archive,env)
   core.require(not completed)
   completed.append(retain_registry(n,archive,env,retained))
  registry.accept_archive=accept
  try:result=super().prepare_baseline(native,sandbox,baseline,base,dispatch)
  finally:registry.accept_archive=original
  core.require(len(completed)==1 and completed[0]==self.archive_sha==self.registry_archive_sha)
  proof=core.pub.read_json(Path(baseline)/'ARCHIVE_RESTORED.json')
  core.require(proof['archive_sha256']==self.archive_sha)
  registry.refresh.writer.archive.validate(native,self.extracted,self.archive_sha)
  before={name:core.pub.digest(path,True) for name,path in (
   ('baseline',Path(baseline)),('metadata',self.extracted),('registry',retained))}
  for operation,boundary in (
   ('resume','copy:sports-metadata'),
   ('resume','renamed:new:dispatcharr-db'),
   ('resume','source-synced:new:registry-users'),
   ('abort','renamed:undo-new:registry-sports-scheduler'),
   ('abort','source-synced:undo-old:sports-metadata')):
   trial(native,Path(baseline),self.extracted,retained,self.archive_sha,operation,boundary)
  core.require(before=={name:core.pub.digest(path,True) for name,path in (
   ('baseline',Path(baseline)),('metadata',self.extracted),('registry',retained))})
  self.coordinated_archive_sha=self.archive_sha
  print(json.dumps({'version':1,'scope':'private-coordinated-21-same-archive',
   'archive_sha256':self.archive_sha,'units':21,'representative_process_deaths':5,
   'native_evidence':'prepared-baseline-hashes; parent rehearsal boots matching baseline separately',
   'production_state_access':False,'live_restore_enabled':False,'power_loss_proven':False},sort_keys=True),flush=True)
  return result

 def initialize(self,*args,**kwargs):
  core.require(self.coordinated_archive_sha is not None and self.coordinated_archive_sha==self.archive_sha)
  return super().initialize(*args,**kwargs)
