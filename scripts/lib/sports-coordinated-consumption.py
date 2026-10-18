"""Private21 consumption import/seal/quarantine journal; production restore stays blocked."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('coordinated_consumption_core',ROOT/'scripts/lib/sports-coordinated-recovery.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
pub=core.pub
NATIVE=('dispatcharr-db','dispatcharr-jwt','teamarr-db')
STATES={'open','import-preparing','importing','imported','sealing','sealed','recovering','reverted','verified'}
DOCUMENTS={'EXPOSURE.json','STATUS.json','IMPORT.json','SEAL.json','ACCEPTANCE.json',
 'NATIVE_INTENT.json','NATIVE_BOUND.json','NATIVE_DETACHED.json'}
require=core.require


def checkpoint(name):
 """Fresh-process death seam; never a production callback."""


def save(directory,state):
 require(state in STATES);pub.write_json(directory/'STATUS.json',{'state':state});checkpoint('status:'+state)


def load(root):
 tx,plan,control,original=core.journal(root,consuming=True)
 require(original=='applied-awaiting-verification')
 directory=root/'consumption';pub.private(directory,True)
 require({p.name for p in directory.iterdir()} <= DOCUMENTS|{'.'+n+'.writing' for n in DOCUMENTS}|{'incoming','previous','quarantine'})
 for name in ('incoming','previous','quarantine'):
  parent=directory/name;pub.private(parent,True)
  require(parent.stat().st_dev==(root/'current').stat().st_dev)
  allowed=set(core.UNITS) if name=='quarantine' else set(NATIVE)
  if name=='incoming':allowed|={'.'+n+'.preparing' for n in NATIVE}
  require({p.name for p in parent.iterdir()}<=allowed)
 exposure=pub.read_json(directory/'EXPOSURE.json');status=pub.read_json(directory/'STATUS.json')
 require(exposure=={'version':1,'scope':'private-coordinated-21-consumption','plan_sha256':pub.digest(tx/'PLAN.json'),
  'publication_status_sha256':pub.digest(tx/'STATUS.json'),'archive_sha256':plan['archive_sha256'],
  'units':plan['units'],'live_restore_enabled':False})
 require(isinstance(status,dict) and set(status)=={'state'} and isinstance(status['state'],str) and status['state'] in STATES)
 require(control['admission']=='held' or status['state']=='verified')
 return tx,directory,plan,control,status['state']


def old_intact(tx,plan):
 require(not any((tx/'incoming').iterdir()))
 require({p.name for p in (tx/'old').iterdir()}==set(core.UNITS))
 for row in plan['units']:require(core.tree_hash(tx/'old'/row['unit'],row['unit'])==row['old_sha256'])


def arm(path):
 with core.locks(path) as root:
  tx,plan,control,state=core.journal(root)
  require(control['admission']=='held' and state=='applied-awaiting-verification'
   and core.positions(root,tx,plan)==[2]*21 and not (root/'ACCEPTANCE.json').exists())
  directory=root/'consumption';directory.mkdir(mode=0o700)
  for name in ('incoming','previous','quarantine'):(directory/name).mkdir(mode=0o700)
  pub.write_json(directory/'EXPOSURE.json',{'version':1,'scope':'private-coordinated-21-consumption',
   'plan_sha256':pub.digest(tx/'PLAN.json'),'publication_status_sha256':pub.digest(tx/'STATUS.json'),
   'archive_sha256':plan['archive_sha256'],'units':plan['units'],'live_restore_enabled':False})
  save(directory,'open');pub.sync(directory);pub.sync(root)
  checkpoint('armed')


@contextmanager
def writer(path):
 root=core.scoped(path)
 with core.consumer.file_lock(root/'admission.lock',shared=True):
  with core.consumer.file_lock(root/'journal.lock'):
   tx,directory,plan,control,state=load(root)
   require(state=='open' and control['admission']=='held'
    and not (directory/'NATIVE_DETACHED.json').exists() and not (directory/'IMPORT.json').exists())
   old_intact(tx,plan)
   require(not any((directory/'quarantine').iterdir()) and {p.name for p in (root/'current').iterdir()}==set(core.UNITS))
   for name in core.UNITS:core.tree_hash(root/'current'/name,name)
  yield root/'current'


def detached(directory,barrier):
 require(callable(barrier));expected=pub.digest(directory/'NATIVE_DETACHED.json')
 require(barrier()==expected)
 return expected


def import_plan(directory,plan):
 value=pub.read_json(directory/'IMPORT.json')
 require(isinstance(value,dict) and set(value)=={'version','exposure_sha256','detached_sha256','capture_sha256','units'}
  and type(value['version']) is int and value['version']==1
  and value['exposure_sha256']==pub.digest(directory/'EXPOSURE.json')
  and value['detached_sha256']==pub.digest(directory/'NATIVE_DETACHED.json')
  and isinstance(value['capture_sha256'],str) and re.fullmatch('[a-f0-9]{64}',value['capture_sha256'])
  and isinstance(value['units'],list) and len(value['units'])==3)
 for name,row in zip(NATIVE,value['units']):
  original=next(r for r in plan['units'] if r['unit']==name)
  require(isinstance(row,dict) and set(row)=={'unit','previous_sha256','consumed_sha256','source'}
   and row['unit']==name and row['previous_sha256']==original['new_sha256']
   and isinstance(row['consumed_sha256'],str) and re.fullmatch('[a-f0-9]{64}',row['consumed_sha256'])
   and isinstance(row['source'],str))
  source=Path(row['source']);require(source==source.resolve() and source.is_relative_to('/tmp'))
 return value


def import_positions(root,directory,rows):
 require(not any(p.name.startswith('.') for p in (directory/'incoming').iterdir()))
 result=[]
 for row in rows:
  name=row['unit']
  def value(parent):
   path=parent/name
   return core.tree_hash(path,name) if path.exists() or path.is_symlink() else None
  observed=(value(root/'current'),value(directory/'previous'),value(directory/'incoming'))
  choices=[(row['previous_sha256'],None,row['consumed_sha256']),
   (None,row['previous_sha256'],row['consumed_sha256']),
   (row['consumed_sha256'],row['previous_sha256'],None)]
  require(observed in choices);result.append(choices.index(observed))
 return result


def move(source,target,label):
 require(not target.exists() and not target.is_symlink());checkpoint('before:'+label)
 source.rename(target);checkpoint('renamed:'+label)
 pub.sync(source.parent);checkpoint('source-synced:'+label)
 pub.sync(target.parent);checkpoint('moved:'+label)


def begin_import(path,sources,capture_sha,barrier):
 with core.locks(path) as root:
  tx,directory,plan,control,state=load(root)
  require(state=='open' and set(sources)==set(NATIVE) and not (directory/'IMPORT.json').exists())
  proof=detached(directory,barrier);old_intact(tx,plan)
  require(isinstance(capture_sha,str) and re.fullmatch('[a-f0-9]{64}',capture_sha))
  rows=[]
  for name in NATIVE:
   original=next(row for row in plan['units'] if row['unit']==name)
   require(core.tree_hash(root/'current'/name,name)==original['new_sha256'])
   source=Path(sources[name]);require(source==source.resolve() and source.is_relative_to('/tmp'))
   rows.append({'unit':name,'previous_sha256':original['new_sha256'],
    'consumed_sha256':core.tree_hash(source,name),'source':str(source)})
  pub.write_json(directory/'IMPORT.json',{'version':1,'exposure_sha256':pub.digest(directory/'EXPOSURE.json'),
   'detached_sha256':proof,'capture_sha256':capture_sha,'units':rows})
  checkpoint('import-plan-written');save(directory,'import-preparing')


def finish_import_locked(root,tx,directory,plan,state,barrier):
 detached(directory,barrier);old_intact(tx,plan)
 require(state in {'open','import-preparing','importing','imported'})
 value=import_plan(directory,plan);rows=value['units']
 if state in {'open','import-preparing'}:
  require(not any((directory/'previous').iterdir()))
  # Validate every original destination, complete incoming and source before cleanup.
  for row in rows:
   name=row['unit'];require(core.tree_hash(root/'current'/name,name)==row['previous_sha256'])
   require(core.tree_hash(Path(row['source']),name)==row['consumed_sha256'])
   final=directory/'incoming'/name;partial=directory/'incoming'/('.'+name+'.preparing')
   if final.exists() or final.is_symlink():require(core.tree_hash(final,name)==row['consumed_sha256'])
   if partial.exists() or partial.is_symlink():require(not final.exists());core.tree_hash(partial,name)
  save(directory,'import-preparing')
  for row in rows:
   name=row['unit'];target=directory/'incoming'/name;partial=directory/'incoming'/('.'+name+'.preparing')
   if target.exists():continue
   if partial.exists():
    if name in core.DIRECTORIES:shutil.rmtree(partial)
    else:partial.unlink()
    pub.sync(partial.parent)
   pub.copy(Path(row['source']),partial,name in core.DIRECTORIES);pub.sync(partial.parent)
   checkpoint('copy:'+name);move(partial,target,'import-prepare:'+name)
  require(import_positions(root,directory,rows)==[0]*3);save(directory,'importing');state='importing'
 observed=import_positions(root,directory,rows)
 if state=='imported':require(observed==[2]*3);return
 for row,position in zip(rows,observed):
  name=row['unit']
  if position==0:move(root/'current'/name,directory/'previous'/name,'import-old:'+name)
  if position in (0,1):move(directory/'incoming'/name,root/'current'/name,'import-new:'+name)
 require(import_positions(root,directory,rows)==[2]*3)
 detached(directory,barrier);save(directory,'imported')


def finish_import(path,barrier):
 with core.locks(path) as root:
  tx,directory,plan,control,state=load(root)
  finish_import_locked(root,tx,directory,plan,state,barrier)


def seal_rows(directory,plan):
 imported=import_plan(directory,plan)
 require(not any((directory/'incoming').iterdir()) and {p.name for p in (directory/'previous').iterdir()}==set(NATIVE))
 for row in imported['units']:require(core.tree_hash(directory/'previous'/row['unit'],row['unit'])==row['previous_sha256'])
 seal=pub.read_json(directory/'SEAL.json')
 require(isinstance(seal,dict) and set(seal)=={'version','exposure_sha256','import_sha256','units'}
  and type(seal['version']) is int and seal['version']==1
  and seal['exposure_sha256']==pub.digest(directory/'EXPOSURE.json')
  and seal['import_sha256']==pub.digest(directory/'IMPORT.json')
  and isinstance(seal['units'],list) and len(seal['units'])==21)
 for original,row in zip(plan['units'],seal['units']):
  require(isinstance(row,dict) and set(row)=={'unit','old_sha256','consumed_sha256'}
   and row['unit']==original['unit'] and row['old_sha256']==original['old_sha256']
   and isinstance(row['consumed_sha256'],str) and re.fullmatch('[a-f0-9]{64}',row['consumed_sha256']))
 return seal['units']


def seal_locked(root,tx,directory,plan,state,barrier):
 require(state in {'imported','sealing','sealed'});detached(directory,barrier);old_intact(tx,plan)
 require(import_positions(root,directory,import_plan(directory,plan)['units'])==[2]*3)
 require(not any((directory/'quarantine').iterdir()) and {p.name for p in (root/'current').iterdir()}==set(core.UNITS))
 if state=='imported':save(directory,'sealing')
 if not (directory/'SEAL.json').exists():
  rows=[{'unit':row['unit'],'old_sha256':row['old_sha256'],
   'consumed_sha256':core.tree_hash(root/'current'/row['unit'],row['unit'])} for row in plan['units']]
  for row in rows:require(core.tree_hash(root/'current'/row['unit'],row['unit'])==row['consumed_sha256'])
  pub.write_json(directory/'SEAL.json',{'version':1,'exposure_sha256':pub.digest(directory/'EXPOSURE.json'),
   'import_sha256':pub.digest(directory/'IMPORT.json'),'units':rows});checkpoint('seal-written')
 rows=seal_rows(directory,plan)
 for row in rows:require(core.tree_hash(root/'current'/row['unit'],row['unit'])==row['consumed_sha256'])
 detached(directory,barrier);save(directory,'sealed');return rows


def positions(root,tx,directory,rows):
 require(not any((tx/'incoming').iterdir()))
 result=[]
 for row in rows:
  name=row['unit']
  def value(parent):
   path=parent/name
   return core.tree_hash(path,name) if path.exists() or path.is_symlink() else None
  observed=(value(root/'current'),value(tx/'old'),value(directory/'quarantine'))
  choices=[(row['consumed_sha256'],row['old_sha256'],None),
   (None,row['old_sha256'],row['consumed_sha256']),
   (row['old_sha256'],None,row['consumed_sha256'])]
  require(observed in choices);result.append(choices.index(observed))
 return result


def recover(path,barrier):
 with core.locks(path) as root:
  tx,directory,plan,control,state=load(root);detached(directory,barrier)
  if state in {'open','import-preparing','importing'}:
   finish_import_locked(root,tx,directory,plan,state,barrier);state='imported'
  if state in {'imported','sealing','sealed'}:rows=seal_locked(root,tx,directory,plan,state,barrier)
  else:rows=seal_rows(directory,plan)
  observed=positions(root,tx,directory,rows)
  if state in {'reverted','verified'}:
   require(observed==[2]*21)
   if state=='verified':ready_locked(root,tx,directory,plan,control,state)
   return
  save(directory,'recovering')
  for row,position in reversed(list(zip(rows,observed))):
   name=row['unit']
   if position==0:move(root/'current'/name,directory/'quarantine'/name,'quarantine:'+name)
   if position in (0,1):move(tx/'old'/name,root/'current'/name,'restore:'+name)
  require(positions(root,tx,directory,rows)==[2]*21)
  detached(directory,barrier);save(directory,'reverted')


def acceptance(root,tx,directory,plan,rows):
 return {'version':1,'scope':'private-coordinated-21-post-consumption-acceptance',
  'plan_sha256':pub.digest(tx/'PLAN.json'),'exposure_sha256':pub.digest(directory/'EXPOSURE.json'),
  'seal_sha256':pub.digest(directory/'SEAL.json'),'detached_sha256':pub.digest(directory/'NATIVE_DETACHED.json'),
  'archive_sha256':plan['archive_sha256'],'restored':{r['unit']:r['old_sha256'] for r in rows},
  'quarantined':{r['unit']:r['consumed_sha256'] for r in rows},'live_restore_enabled':False}


def ready_locked(root,tx,directory,plan,control,state):
 require(state=='verified' and control['admission']=='released')
 rows=seal_rows(directory,plan);require(positions(root,tx,directory,rows)==[2]*21)
 require(pub.read_json(directory/'ACCEPTANCE.json')==acceptance(root,tx,directory,plan,rows))
 return root/'current'


def accept(path,validator,barrier):
 require(callable(validator))
 with core.locks(path) as root:
  tx,directory,plan,control,state=load(root);detached(directory,barrier)
  if control['admission']=='released':return ready_locked(root,tx,directory,plan,control,state)
  require(state in {'reverted','verified'})
  rows=seal_rows(directory,plan);require(positions(root,tx,directory,rows)==[2]*21)
  proof=validator(root/'current',directory/'quarantine',plan['archive_sha256'])
  require(isinstance(proof,dict) and set(proof)=={'registry','native','metadata'} and all(v is True for v in proof.values()))
  require(positions(root,tx,directory,rows)==[2]*21);detached(directory,barrier)
  receipt=acceptance(root,tx,directory,plan,rows)
  if (directory/'ACCEPTANCE.json').exists():require(pub.read_json(directory/'ACCEPTANCE.json')==receipt)
  else:pub.write_json(directory/'ACCEPTANCE.json',receipt)
  checkpoint('acceptance-written');save(directory,'verified')
  pub.write_json(root/'CONTROL.json',dict(control,admission='released'));checkpoint('admission-released')
  return ready_locked(root,tx,directory,plan,dict(control,admission='released'),'verified')


@contextmanager
def reader(path):
 root=core.scoped(path)
 with core.consumer.file_lock(root/'admission.lock',shared=True):
  with core.consumer.file_lock(root/'journal.lock'):
   tx,directory,plan,control,state=load(root);current=ready_locked(root,tx,directory,plan,control,state)
  yield current
  ready_locked(root,tx,directory,plan,control,state)


@contextmanager
def validation_reader(path):
 """Private maintenance validation lease, before public fixture admission."""
 root=core.scoped(path)
 with core.consumer.file_lock(root/'admission.lock',shared=True):
  with core.consumer.file_lock(root/'journal.lock'):
   tx,directory,plan,control,state=load(root)
   require(state=='reverted' and control['admission']=='held')
   rows=seal_rows(directory,plan);require(positions(root,tx,directory,rows)==[2]*21)
  yield root/'current'
  require(positions(root,tx,directory,rows)==[2]*21)
