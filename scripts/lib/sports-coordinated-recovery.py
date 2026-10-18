"""Durable private twenty-one-unit publish/resume/abort journal; no live-path API."""
from contextlib import contextmanager
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]

def load_module(name,relative):
 spec=importlib.util.spec_from_file_location(name,ROOT/relative)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

pub=load_module('coordinated_publication','scripts/lib/sports-recovery-publication.py')
consumer=load_module('coordinated_locks','scripts/lib/sports-recovery-consumption.py')
registry=load_module('coordinated_registry','scripts/lib/sports-registry-restore.py')
UNITS=pub.SURFACES+tuple('registry-'+row[0] for row in registry.SURFACES)
DIRECTORIES=pub.DIRECTORIES|{'registry-'+row[0] for row in registry.SURFACES if row[3]=='directory'}
STATES={'preparing','staged','applying','applied-awaiting-verification','aborting',
 'aborting-preparation','aborted-awaiting-verification','aborted-preparation-awaiting-verification',
 'verified-new','verified-old'}


def require(value):
 if not value:raise ValueError('Private coordinated recovery held')


def checkpoint(name):
 """No-op seam for real process death between durable transitions."""


def scoped(path):
 root=Path(path)
 require(root.parent==Path('/tmp') and re.fullmatch(r'project-atlas-coordinated-recovery\.[a-f0-9]{32}',root.name))
 pub.private(root,True)
 return root


@contextmanager
def locks(root,shared=False):
 root=scoped(root)
 with consumer.file_lock(root/'admission.lock',shared=shared),consumer.file_lock(root/'journal.lock'):
  yield root


def tree_hash(path,name):
 return pub.digest(path,name in DIRECTORIES)


def state_save(tx,state):
 require(state in STATES);pub.write_json(tx/'STATUS.json',{'state':state})
 checkpoint('status:'+state)


def initialize(root,old_sources,new_sources,archive_sha):
 root=scoped(root)
 require(not any(root.iterdir()) and set(old_sources)==set(new_sources)==set(UNITS)
  and isinstance(archive_sha,str) and re.fullmatch('[a-f0-9]{64}',archive_sha))
 # Fixture construction is offline: no existing application destination is moved.
 # A missing PLAN/CONTROL after interruption is refused, never reconstructed.
 for name in ('current','source','transaction'):(root/name).mkdir(mode=0o700)
 tx=root/'transaction'
 for name in ('incoming','old'):(tx/name).mkdir(mode=0o700)
 rows=[]
 for name in UNITS:
  old,new=Path(old_sources[name]),Path(new_sources[name])
  require(old==old.resolve() and new==new.resolve() and old.is_relative_to('/tmp') and new.is_relative_to('/tmp'))
  old_sha=tree_hash(old,name);new_sha=tree_hash(new,name)
  pub.copy(old,root/'current'/name,name in DIRECTORIES)
  pub.copy(new,root/'source'/name,name in DIRECTORIES)
  rows.append({'unit':name,'old_sha256':old_sha,'new_sha256':new_sha})
 for parent in (root/'current',root/'source',tx/'old',tx/'incoming',tx,root):pub.sync(parent)
 plan={'version':1,'scope':'private-coordinated-21','archive_sha256':archive_sha,
  'live_restore_enabled':False,'units':rows}
 pub.write_json(tx/'PLAN.json',plan)
 pub.write_json(root/'CONTROL.json',{'version':1,'plan_sha256':pub.digest(tx/'PLAN.json'),
  'archive_sha256':archive_sha,'admission':'held','live_restore_enabled':False})
 state_save(tx,'preparing')
 checkpoint('initialized')


def journal(root, *, consuming=False):
 require(consuming or not (root/'consumption').exists() and not (root/'consumption').is_symlink())
 require({p.name for p in root.iterdir()} <= ({'consumption'} if consuming else set())|{'current','source','transaction','CONTROL.json',
  '.CONTROL.json.writing','ACCEPTANCE.json','.ACCEPTANCE.json.writing','admission.lock','journal.lock'})
 tx=root/'transaction';pub.private(tx,True)
 require({p.name for p in tx.iterdir()} <= {'incoming','old','PLAN.json','STATUS.json','.STATUS.json.writing'})
 for parent in (root/'current',root/'source',tx/'old',tx/'incoming'):pub.private(parent,True)
 for parent in (root/'current',root/'source',tx/'old'):
  require({p.name for p in parent.iterdir()} <= set(UNITS))
 require({p.name for p in (tx/'incoming').iterdir()} <= set(UNITS)|{'.'+name+'.preparing' for name in UNITS})
 plan=pub.read_json(tx/'PLAN.json');control=pub.read_json(root/'CONTROL.json');status=pub.read_json(tx/'STATUS.json')
 require(isinstance(plan,dict) and set(plan)=={'version','scope','archive_sha256','live_restore_enabled','units'}
  and type(plan['version']) is int and plan['version']==1 and plan['scope']=='private-coordinated-21'
  and plan['live_restore_enabled'] is False and isinstance(plan['archive_sha256'],str) and re.fullmatch('[a-f0-9]{64}',plan['archive_sha256'])
  and isinstance(plan['units'],list) and len(plan['units'])==21)
 for name,row in zip(UNITS,plan['units']):
  require(isinstance(row,dict) and set(row)=={'unit','old_sha256','new_sha256'} and row['unit']==name
   and all(isinstance(row[key],str) and re.fullmatch('[a-f0-9]{64}',row[key]) for key in ('old_sha256','new_sha256')))
 require(isinstance(control,dict) and set(control)=={'version','plan_sha256','archive_sha256','admission','live_restore_enabled'}
  and type(control['version']) is int and control['version']==1
  and control['plan_sha256']==pub.digest(tx/'PLAN.json') and control['archive_sha256']==plan['archive_sha256']
  and control['admission'] in {'held','released'} and control['live_restore_enabled'] is False)
 require(isinstance(status,dict) and set(status)=={'state'} and status['state'] in STATES)
 require(all(parent.stat().st_dev==(root/'current').stat().st_dev for parent in (tx/'incoming',tx/'old',root/'source')))
 return tx,plan,control,status['state']


def positions(root,tx,plan):
 result=[]
 require(not any(p.name.startswith('.') for p in (tx/'incoming').iterdir()))
 for row in plan['units']:
  name=row['unit']
  def value(parent):
   path=parent/name
   return tree_hash(path,name) if path.exists() or path.is_symlink() else None
  observed=(value(root/'current'),value(tx/'old'),value(tx/'incoming'))
  choices=[(row['old_sha256'],None,row['new_sha256']),
   (None,row['old_sha256'],row['new_sha256']),
   (row['new_sha256'],row['old_sha256'],None)]
  require(observed in choices);result.append(choices.index(observed))
 return result


def preparing_positions(root,tx,plan):
 require(not any((tx/'old').iterdir()) and {p.name for p in (root/'current').iterdir()}==set(UNITS))
 for row in plan['units']:
  name=row['unit'];require(tree_hash(root/'current'/name,name)==row['old_sha256'])
  final=tx/'incoming'/name;partial=tx/'incoming'/('.'+name+'.preparing')
  if final.exists() or final.is_symlink():require(tree_hash(final,name)==row['new_sha256'])
  if partial.exists() or partial.is_symlink():
   require(not final.exists());tree_hash(partial,name)


def move(source,target,label):
 require(not target.exists() and not target.is_symlink())
 checkpoint('before:'+label)
 os.rename(source,target);checkpoint('renamed:'+label)
 pub.sync(source.parent);checkpoint('source-synced:'+label)
 pub.sync(target.parent);checkpoint('moved:'+label)


def prepare_locked(root,tx,plan):
 preparing_positions(root,tx,plan)
 # Verify every complete source before removing any abandoned partial copy.
 for row in plan['units']:require(tree_hash(root/'source'/row['unit'],row['unit'])==row['new_sha256'])
 for row in plan['units']:
  name=row['unit'];target=tx/'incoming'/name;partial=tx/'incoming'/('.'+name+'.preparing')
  if target.exists():continue
  if partial.exists():
   if name in DIRECTORIES:shutil.rmtree(partial)
   else:partial.unlink()
   pub.sync(partial.parent)
  pub.copy(root/'source'/name,partial,name in DIRECTORIES);pub.sync(partial.parent)
  checkpoint('copy:'+name)
  move(partial,target,'prepare:'+name)
 require(positions(root,tx,plan)==[0]*21)
 state_save(tx,'staged')


def resume(path):
 with locks(path) as root:
  tx,plan,control,state=journal(root)
  if state=='verified-new':return ready_locked(root,tx,plan,control,state)
  require(control['admission']=='held' and state in {'preparing','staged','applying','applied-awaiting-verification'})
  if state=='preparing':prepare_locked(root,tx,plan);state='staged'
  observed=positions(root,tx,plan)
  if state=='applied-awaiting-verification':require(observed==[2]*21);return
  if state=='staged':require(observed==[0]*21);state_save(tx,'applying')
  # The durable applying intent and frozen hashes permit reconstruction even if
  # death occurs after rename but before either directory fsync or a row log.
  for row,position in zip(plan['units'],observed):
   name=row['unit']
   if position==0:move(root/'current'/name,tx/'old'/name,'old:'+name)
   if position in (0,1):move(tx/'incoming'/name,root/'current'/name,'new:'+name)
  require(positions(root,tx,plan)==[2]*21)
  state_save(tx,'applied-awaiting-verification')


def abort(path):
 with locks(path) as root:
  tx,plan,control,state=journal(root)
  if state=='verified-old':return ready_locked(root,tx,plan,control,state)
  require(control['admission']=='held' and state!='verified-new')
  if state in {'preparing','aborting-preparation','aborted-preparation-awaiting-verification'}:
   preparing_positions(root,tx,plan)
   if state!='aborted-preparation-awaiting-verification':
    state_save(tx,'aborting-preparation');state_save(tx,'aborted-preparation-awaiting-verification')
   return
  observed=positions(root,tx,plan)
  if state=='aborted-awaiting-verification':require(observed==[0]*21);return
  require(state in {'staged','applying','applied-awaiting-verification','aborting'})
  state_save(tx,'aborting')
  for row,position in reversed(list(zip(plan['units'],observed))):
   name=row['unit']
   if position==2:move(root/'current'/name,tx/'incoming'/name,'undo-new:'+name)
   if position in (1,2):move(tx/'old'/name,root/'current'/name,'undo-old:'+name)
  require(positions(root,tx,plan)==[0]*21)
  state_save(tx,'aborted-awaiting-verification')


def current_hashes(root,plan,which):
 expected={row['unit']:row[which+'_sha256'] for row in plan['units']}
 require({p.name for p in (root/'current').iterdir()}==set(UNITS))
 actual={name:tree_hash(root/'current'/name,name) for name in UNITS}
 require(actual==expected);return actual


def receipt(root,tx,plan,which,hashes):
 return {'version':1,'scope':'private-coordinated-21-acceptance','plan_sha256':pub.digest(tx/'PLAN.json'),
  'archive_sha256':plan['archive_sha256'],'generation':which,'units':hashes,
  'production_state_access':False,'live_restore_enabled':False}


def ready_locked(root,tx,plan,control,state):
 require(state in {'verified-new','verified-old'} and control['admission']=='released')
 which=state.removeprefix('verified-');hashes=current_hashes(root,plan,which)
 require(pub.read_json(root/'ACCEPTANCE.json')==receipt(root,tx,plan,which,hashes))
 return which


def accept(path,validator):
 require(callable(validator))
 with locks(path) as root:
  tx,plan,control,state=journal(root)
  if control['admission']=='released':return ready_locked(root,tx,plan,control,state)
  require(state in {'applied-awaiting-verification','aborted-awaiting-verification',
   'aborted-preparation-awaiting-verification','verified-new','verified-old'})
  which='new' if state in {'applied-awaiting-verification','verified-new'} else 'old'
  if state=='aborted-preparation-awaiting-verification':preparing_positions(root,tx,plan)
  elif state.startswith('verified-'):pass
  else:require(positions(root,tx,plan)==([2]*21 if which=='new' else [0]*21))
  hashes=current_hashes(root,plan,which)
  proof=validator(root/'current',which,plan['archive_sha256'])
  require(isinstance(proof,dict) and set(proof)=={'registry','native','metadata'}
   and all(value is True for value in proof.values()))
  require(current_hashes(root,plan,which)==hashes)
  accepted=receipt(root,tx,plan,which,hashes)
  if (root/'ACCEPTANCE.json').exists():require(pub.read_json(root/'ACCEPTANCE.json')==accepted)
  else:pub.write_json(root/'ACCEPTANCE.json',accepted)
  checkpoint('acceptance-written')
  state_save(tx,'verified-'+which)
  pub.write_json(root/'CONTROL.json',dict(control,admission='released'))
  checkpoint('admission-released')
  return ready_locked(root,tx,plan,dict(control,admission='released'),'verified-'+which)


def ready(path):
 with locks(path) as root:
  tx,plan,control,state=journal(root)
  return ready_locked(root,tx,plan,control,state)


@contextmanager
def reader(path):
 # Cooperative read-only fixture lease; this is not Docker mount admission.
 root=scoped(path)
 with consumer.file_lock(root/'admission.lock',shared=True):
  with consumer.file_lock(root/'journal.lock'):
   tx,plan,control,state=journal(root);ready_locked(root,tx,plan,control,state)
   before=current_hashes(root,plan,state.removeprefix('verified-'))
  yield root/'current'
  require(current_hashes(root,plan,state.removeprefix('verified-'))==before)
