"""Copy-mediated admission of exactly owned native fixtures into the private21 epoch."""
import importlib.util
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path)
 result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
c=module('native_admission_consumption','scripts/lib/sports-coordinated-consumption.py')
require=c.require;pub=c.pub


def identity(identifier):
 require(isinstance(identifier,str) and re.fullmatch('[a-f0-9]{32}',identifier))


def controller_identity():
 return os.geteuid(),os.getegid()


def materialize(native,path,identifier,*,restored=False):
 root=c.core.scoped(path);require(controller_identity()==(0,0));identity(identifier)
 with c.core.consumer.file_lock(root/'journal.lock'):
  tx,directory,plan,control,state=c.load(root)
  require(state==('reverted' if restored else 'open') and control['admission']=='held')
  if restored:require(c.positions(root,tx,directory,c.seal_rows(directory,plan))==[2]*21)
  else:
   c.old_intact(tx,plan);require(not (directory/'NATIVE_INTENT.json').exists())
  sources={name:c.core.tree_hash(root/'current'/name,name) for name in c.NATIVE}
  expected={row['unit']:row['old_sha256' if restored else 'new_sha256'] for row in plan['units'] if row['unit'] in c.NATIVE}
  require(sources==expected)
  targets={role:native.volume_path(identifier,role) for role in native.fence.IMAGES}
  require(all(not any(path.iterdir()) for path in targets.values()))
  for role in native.fence.IMAGES:require(not native.fence.references(native.fence.names(identifier,role)[1]))
  if not restored:
   pub.write_json(directory/'NATIVE_INTENT.json',{'version':1,'scope':'private-copy-mediated-native-admission',
    'plan_sha256':pub.digest(tx/'PLAN.json'),'exposure_sha256':pub.digest(directory/'EXPOSURE.json'),
    'identifier':identifier,'source_hashes':sources,'live_restore_enabled':False})
  native.copy_tree(root/'current/dispatcharr-db',targets['dispatcharr']/'db',True,(0,0),(1000,1000))
  native.copy_tree(root/'current/dispatcharr-jwt',targets['dispatcharr']/'jwt',source_owner=(0,0))
  native.copy_tree(root/'current/teamarr-db',targets['teamarr']/'teamarr.db',source_owner=(0,0))
  require({name:c.core.tree_hash(root/'current'/name,name) for name in c.NATIVE}==sources)
  require({p.name for p in targets['teamarr'].iterdir()}=={'teamarr.db'})
  for role in native.fence.IMAGES:require(not native.fence.references(native.fence.names(identifier,role)[1]))


def bound(native,path,lifecycle_root,identifier):
 root=c.core.scoped(path);lifecycle_root=native.consumer.scoped(lifecycle_root)
 with c.core.consumer.file_lock(root/'journal.lock'):
  tx,directory,plan,control,state=c.load(root);require(state=='open')
  intent=pub.read_json(directory/'NATIVE_INTENT.json')
  require(intent=={'version':1,'scope':'private-copy-mediated-native-admission',
   'plan_sha256':pub.digest(tx/'PLAN.json'),'exposure_sha256':pub.digest(directory/'EXPOSURE.json'),
   'identifier':identifier,'source_hashes':{r['unit']:r['new_sha256'] for r in plan['units'] if r['unit'] in c.NATIVE},
   'live_restore_enabled':False})
  ledger=native.fence.load(lifecycle_root)
  require(ledger['stage']=='armed' and ledger['identifier']==identifier)
  for role,epoch in ledger['apps'].items():
   native.fence.volume(identifier,role)
   require(native.fence.inspect_app(identifier,role,epoch['id'],epoch)[1])
   require(native.fence.references(native.fence.names(identifier,role)[1])=={epoch['id']})
  require(not (directory/'NATIVE_BOUND.json').exists())
  pub.write_json(directory/'NATIVE_BOUND.json',{'version':1,'intent_sha256':pub.digest(directory/'NATIVE_INTENT.json'),
   'lifecycle_root':str(lifecycle_root),'identifier':identifier,'apps':ledger['apps'],'binding':ledger['binding']})


def binding(native,root):
 tx,directory,plan,control,state=c.load(root)
 intent=pub.read_json(directory/'NATIVE_INTENT.json');bound=pub.read_json(directory/'NATIVE_BOUND.json')
 require(isinstance(intent,dict) and set(intent)=={'version','scope','plan_sha256','exposure_sha256','identifier','source_hashes','live_restore_enabled'}
  and type(intent['version']) is int and intent['version']==1 and intent['scope']=='private-copy-mediated-native-admission'
  and intent['plan_sha256']==pub.digest(tx/'PLAN.json') and intent['exposure_sha256']==pub.digest(directory/'EXPOSURE.json')
  and intent['live_restore_enabled'] is False)
 identity(intent['identifier'])
 expected={row['unit']:row['new_sha256'] for row in plan['units'] if row['unit'] in c.NATIVE}
 require(intent['source_hashes']==expected)
 require(isinstance(bound,dict) and set(bound)=={'version','intent_sha256','lifecycle_root','identifier','apps','binding'}
  and type(bound['version']) is int and bound['version']==1 and bound['intent_sha256']==pub.digest(directory/'NATIVE_INTENT.json')
  and bound['identifier']==intent['identifier'] and isinstance(bound['lifecycle_root'],str))
 lifecycle_root=native.consumer.scoped(Path(bound['lifecycle_root']))
 ledger=native.fence.load(lifecycle_root)
 require(ledger['identifier']==bound['identifier'] and ledger['apps']==bound['apps'] and ledger['binding']==bound['binding'])
 native.fence.assert_detached(ledger)
 return directory,lifecycle_root,ledger


def mark_detached(native,path):
 root=c.core.scoped(path)
 with c.core.consumer.file_lock(root/'journal.lock'):
  directory,lifecycle_root,ledger=binding(native,root)
  require(not (directory/'NATIVE_DETACHED.json').exists())
  pub.write_json(directory/'NATIVE_DETACHED.json',{'version':1,'bound_sha256':pub.digest(directory/'NATIVE_BOUND.json'),
   'ledger_sha256':pub.digest(lifecycle_root/'DOCKER_LIFECYCLE.json')})


def barrier(path):
 root=c.core.scoped(path)
 native=module('fresh_native_admission_barrier','scripts/lib/sports-native-consumption.py')
 directory,lifecycle_root,ledger=binding(native,root)
 require(pub.read_json(directory/'NATIVE_DETACHED.json')=={'version':1,
  'bound_sha256':pub.digest(directory/'NATIVE_BOUND.json'),'ledger_sha256':pub.digest(lifecycle_root/'DOCKER_LIFECYCLE.json')})
 return pub.digest(directory/'NATIVE_DETACHED.json')


def begin_capture(native,path,captured):
 root=c.core.scoped(path);captured=Path(captured);native.workspace(captured.parent)
 require(captured.name=='captured');proof=barrier(root)
 receipt=pub.read_json(captured/'CAPTURE.json')
 require(isinstance(receipt,dict) and set(receipt)=={'version','marker','copied_wal','ledger_sha256','surfaces'}
  and type(receipt['version']) is int and receipt['version']==1 and receipt['marker']=='native-consumer-committed'
  and type(receipt['copied_wal']) is bool and set(receipt['surfaces'])==set(c.NATIVE))
 detached=pub.read_json(root/'consumption/NATIVE_DETACHED.json')
 require(receipt['ledger_sha256']==detached['ledger_sha256'])
 for name in c.NATIVE:require(c.core.tree_hash(captured/name,name)==receipt['surfaces'][name])
 c.begin_import(root,{name:captured/name for name in c.NATIVE},pub.digest(captured/'CAPTURE.json'),lambda:barrier(root))
 require(barrier(root)==proof)
