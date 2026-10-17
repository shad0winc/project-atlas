"""Fixture-enabled refresh worker and real bounded fetch child during writer SIGTERM."""
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
LABEL='io.project-atlas.archive-refresh-drill'
DEADLINE=8
POLICY={'version':1,'enabled':True,'routes':['football/nfl'],'hourly_budget':96,
    'current_ttl':60,'past_ttl':900,'future_ttl':900,'directory_ttl':3600,'tick_seconds':1,
    'generation':'isolated-refresh-shutdown'}
CHILD = r'''
import os,urllib.request
from providers import metadata_broker as module
Original=module.ESPNDayTransport
class LocalOpener:
 def open(self,request,timeout):
  assert request.full_url=='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261017'
  url=os.environ['ATLAS_FIXTURE_PROVIDER_URL'];assert url.startswith('http://127.0.0.1:') and url.endswith('/scoreboard?dates=20261017')
  headers=dict(request.header_items());headers['X-Atlas-Fixture-Pid']=str(os.getpid());headers['X-Atlas-Fixture-Parent']=str(os.getppid())
  local=urllib.request.Request(url,headers=headers)
  assert timeout==8
  # Keep the local socket open beyond the parent deadline; only the real
  # subprocess timeout may end the deliberately stalled fixture fetch.
  return urllib.request.build_opener(urllib.request.ProxyHandler({}),module._NoRedirect()).open(local,timeout=30)
module.ESPNDayTransport=lambda:Original(opener=LocalOpener())
module._fetch_worker()
'''
BOOTSTRAP_PREFIX = r'''
import hashlib,json,os,sqlite3,subprocess,sys,threading,time
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import private_api
from providers.espn_metadata import LEAGUE_UIDS
from providers.metadata_store import MetadataStore
from providers.metadata_broker import MetadataBroker,BoundedESPNTransport
from providers.metadata_refresh import MetadataRefreshWorker,parse_refresh_policy,load_refresh_policy
STAMP=datetime(2026,10,17,12,tzinfo=timezone.utc).timestamp()
case=os.environ['ATLAS_FIXTURE_REFRESH_CASE'];assert case in {'complete','deadline'}
assert load_refresh_policy() is None
state=Path(os.environ['SPORTS_SOURCE_LIFECYCLE_FILE']).parent
store=MetadataStore(Path(os.environ['ATLAS_SPORTS_METADATA_STATE_DIR'])/'metadata.sqlite')
worker=None;child_pid=None;calls=[];release=threading.Event();handler_done=threading.Event()
def document(name,data):
 temporary=state/('.'+name+'.writing')
 fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as stream:json.dump(data,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
 assert not (state/name).exists();os.rename(temporary,state/name)
 descriptor=os.open(state,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(descriptor)
 finally:os.close(descriptor)
class Provider(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  global child_pid
  try:
   assert self.path=='/scoreboard?dates=20261017' and child_pid is None
   child_pid=int(self.headers['X-Atlas-Fixture-Pid']);assert child_pid>1 and int(self.headers['X-Atlas-Fixture-Parent'])==os.getpid()
   with sqlite3.connect(store.path.as_uri()+'?mode=ro',uri=True) as connection:
    assert connection.execute('SELECT stamp FROM metadata_attempts').fetchall()==[(STAMP,)]
    assert connection.execute('SELECT until_stamp FROM metadata_holds WHERE key=?',('football/nfl:2026-10-17',)).fetchall()==[(STAMP+30,)]
   document('FETCH.json',{'child_pid':child_pid,'reservation_visible':True})
   assert worker is not None and worker.stop_event.wait(12)
   document('STOP_OBSERVED.json',{'stop_requested':True})
   if case=='deadline':assert release.wait(12)
   payload=json.dumps({'events':[],'leagues':[{'uid':LEAGUE_UIDS['football/nfl']}],'fixture_generation':'refresh-local'}).encode()
   try:
    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
   except (BrokenPipeError,ConnectionResetError):pass
  finally:handler_done.set()
provider=ThreadingHTTPServer(('127.0.0.1',0),Provider)
thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
def runner(arguments,**kwargs):
 assert arguments==[sys.executable,'-B','-c','from providers.metadata_broker import _fetch_worker; _fetch_worker()']
 assert kwargs['timeout']==8 and kwargs['capture_output'] is True
 assert json.loads(kwargs['input'])=={'route':'football/nfl','day':'2026-10-17'}
 assert worker is not None and not worker.stop_event.is_set() and not calls
 calls.append(True)
 env=dict(kwargs['env']);env['ATLAS_FIXTURE_PROVIDER_URL']='http://127.0.0.1:'+str(provider.server_port)+'/scoreboard?dates=20261017'
 return subprocess.run([sys.executable,'-B','-c',CHILD],**{**kwargs,'env':env})
policy=parse_refresh_policy(POLICY)
broker=MetadataBroker(store,transport=BoundedESPNTransport(deadline_seconds=8,runner=runner),clock=lambda:STAMP,**dict(policy.broker_settings))
def factory():
 global worker
 worker=MetadataRefreshWorker(lambda:policy,lambda selected:broker,clock=lambda:STAMP)
 return worker.start()
original_serve=private_api._serve_with_metadata
private_api._serve_with_metadata=lambda server:original_serve(server,refresh_factory=factory)
try:
 sys.argv=['private_api.py','--port',os.environ.get('ATLAS_FIXTURE_WRITER_PORT','8003')]
 code=private_api.main()
 assert code==0 and worker is not None and worker.stop_event.is_set() and not worker.thread.is_alive()
 status=worker.status();assert status['state']=='stopped' and status['running'] is False
 assert child_pid is not None and calls==[True]
 try:os.kill(child_pid,0)
 except ProcessLookupError:pass
 else:raise AssertionError('owned fetch child still exists')
 try:os.waitpid(child_pid,os.WNOHANG)
 except ChildProcessError:pass
 else:raise AssertionError('owned fetch child was not reaped by subprocess.run')
 before=hashlib.sha256(store.path.read_bytes()).hexdigest()
 assert worker.tick()==30 and calls==[True] and hashlib.sha256(store.path.read_bytes()).hexdigest()==before
 release.set();assert handler_done.wait(3)
 assert json.loads((state/'STOP_OBSERVED.json').read_text())=={'stop_requested':True}
 with sqlite3.connect(store.path.as_uri()+'?mode=ro&immutable=1',uri=True) as connection:
  assert connection.execute('SELECT stamp FROM metadata_attempts').fetchall()==[(STAMP,)]
  assert connection.execute('SELECT count(*) FROM metadata_aliases').fetchone()==(2,)
  rows=connection.execute('SELECT payload,observed,expires FROM metadata_cache').fetchall();assert len(rows)==1
  holds=connection.execute('SELECT key,until_stamp FROM metadata_holds ORDER BY key').fetchall()
  if case=='complete':
   assert status['last_provider_success_at']==STAMP and status['last_failure_category'] is None
   assert json.loads(rows[0][0])['fixture_generation']=='refresh-local' and rows[0][1:]==(STAMP,STAMP+60)
   assert holds==[('espn:cooldown',153.0)]
  else:
   assert status['last_provider_success_at'] is None and status['last_failure_category']=='deadline' and status['last_failure_at']==STAMP
   assert json.loads(rows[0][0])['fixture_generation']=='new' and rows[0][1:]==(123.0,183.0)
   assert holds==[('espn:cooldown',153.0),('football/nfl:2026-10-17',STAMP+15)]
 proof={'version':1,'case':case,'worker_stopped':True,'child_reaped':True,
   'paid_attempts':1,'fetch_children':1,'post_stop_tick_blocked':True,'reservation_visible':True,
   'failure_category':status['last_failure_category'],'production_state_access':False,'live_restore_enabled':False}
finally:
 release.set();provider.shutdown();provider.server_close();thread.join(3);assert not thread.is_alive()
document('SHUTDOWN.json',proof)
raise SystemExit(code)
'''
BOOTSTRAP='CHILD='+repr(CHILD)+'\nPOLICY='+repr(POLICY)+'\n'+BOOTSTRAP_PREFIX
PREFLIGHT = r'''
import json,os,sqlite3,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from providers.metadata_refresh import parse_refresh_policy,load_refresh_policy
assert load_refresh_policy() is None
state=Path(os.environ['SPORTS_SOURCE_LIFECYCLE_FILE']).parent
started=json.loads((state/'FETCH.json').read_text());assert started['reservation_visible'] is True and started['child_pid']>1
assert not (state/'STOP_OBSERVED.json').exists() and not (state/'SHUTDOWN.json').exists()
assert os.kill(started['child_pid'],0) is None
port=os.environ.get('ATLAS_FIXTURE_WRITER_PORT','8003')
request=urllib.request.Request('http://127.0.0.1:'+port+'/internal/v1/metadata/refresh-status')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:opener.open(request,timeout=2)
except urllib.error.HTTPError as error:assert error.code==401;error.close()
else:raise AssertionError('refresh status did not require auth')
request.add_header('Authorization','Bearer '+os.environ['ATLAS_SPORTS_WRITER_TOKEN'])
with opener.open(request,timeout=2) as response:
 assert response.status==200;status=json.loads(response.read(16384))
assert status['running'] is True and status['policy_fingerprint']==parse_refresh_policy(POLICY).fingerprint
stamp=datetime(2026,10,17,12,tzinfo=timezone.utc).timestamp();assert status['last_tick_at']==stamp
with sqlite3.connect((Path(os.environ['ATLAS_SPORTS_METADATA_STATE_DIR'])/'metadata.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True) as connection:
 assert connection.execute('SELECT stamp FROM metadata_attempts').fetchall()==[(stamp,)]
 assert connection.execute('SELECT until_stamp FROM metadata_holds WHERE key=?',('football/nfl:2026-10-17',)).fetchall()==[(stamp+30,)]
print('refresh-inflight-and-reservation-valid')
'''


def load(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def require(value):
    if not value:raise ValueError('Isolated archive refresh shutdown held')


broker=load('archive_refresh_broker','scripts/lib/sports-archive-broker.py')
writer=broker.writer


def arguments(name,identifier,root,case):
    require(case in {'complete','deadline'} and name=='atlas-archive-refresh-'+identifier)
    args=broker.arguments('atlas-archive-broker-'+identifier,identifier,root)
    args[args.index('--name')+1]=name;args[args.index('--label')+1]=LABEL+'='+identifier
    args[-1]=BOOTSTRAP
    index=args.index(writer.IMAGE)
    return args[:index]+['--env','ATLAS_FIXTURE_REFRESH_CASE='+case]+args[index:]


def inspect_owned(base,name,identifier,root,case,container_id=None):
    row=base.inspect(name);host=row['HostConfig'];config=row['Config']
    require(re.fullmatch('[a-f0-9]{32}',identifier) and name=='atlas-archive-refresh-'+identifier)
    require(re.fullmatch('[a-f0-9]{64}',row['Id']) and (container_id is None or row['Id']==container_id))
    require(row['Name']=='/'+name and row['Image']==writer.IMAGE and config.get('Labels',{}).get(LABEL)==identifier)
    require(config.get('User')=='1000:1000' and config.get('Entrypoint')==['python3']
        and config.get('Cmd')==['-B','-c',BOOTSTRAP] and config.get('WorkingDir')=='/srv/sports' and not config.get('Volumes'))
    env=dict(item.split('=',1) for item in config['Env'])
    require(env.get('ATLAS_FIXTURE_REFRESH_CASE')==case and env.get('ATLAS_SPORTS_METADATA_STATE_DIR')=='/metadata'
        and env.get('ATLAS_SPORTS_METADATA_REFRESH_FILE')=='/policy/refresh.json'
        and env.get('ATLAS_SPORTS_WRITER_TOKEN')==writer.TOKEN)
    require(host.get('ReadonlyRootfs') and host.get('NetworkMode')=='none' and not host.get('Privileged')
        and not host.get('PortBindings') and not host.get('PublishAllPorts') and not host.get('GroupAdd')
        and not host.get('CapAdd') and host.get('CapDrop')==['ALL']
        and host.get('SecurityOpt')==['no-new-privileges:true'] and not host.get('UsernsMode')
        and host.get('RestartPolicy',{}).get('Name')=='no' and set(host.get('Tmpfs') or {})=={'/tmp'}
        and host.get('IpcMode')=='private' and host.get('LogConfig',{}).get('Type')=='none'
        and host.get('Memory')==128*1024**2 and host.get('PidsLimit')==64)
    mounts=[item for item in row['Mounts'] if item['Type']!='tmpfs']
    expected={'/srv/sports':('source',False),'/state':('state',True),'/metadata':('sports-metadata',True),'/policy':('sports-metadata-policy',False)}
    require(len(mounts)==4 and {item['Destination'] for item in mounts}==set(expected))
    for item in mounts:
        source,rw=expected[item['Destination']]
        require(item['Type']=='bind' and item['Source']==str(Path(root)/source) and item['RW'] is rw)
    return row


def validate_receipt(data,case):
    require(case in {'complete','deadline'})
    require(data=={'version':1,'case':case,'worker_stopped':True,'child_reaped':True,'paid_attempts':1,
        'fetch_children':1,'post_stop_tick_blocked':True,'reservation_visible':True,
        'failure_category':'deadline' if case=='deadline' else None,
        'production_state_access':False,'live_restore_enabled':False})


def accept(native,parent):
    base=load('archive_refresh_docker','scripts/diagnostics/sports-cold-copy-drill.py')
    metadata=writer.archive.metadata;parent=Path(parent);metadata.check(native,parent,'new')
    before={key:native.pub.digest(parent/key,True) for key in ('sports-metadata','sports-metadata-policy')}
    image=json.loads(base.docker('image','inspect',writer.IMAGE))[0]
    require(image['Id']==writer.IMAGE and not image['Config'].get('Volumes') and not image['Config'].get('Entrypoint'))
    for case in ('complete','deadline'):
        identifier=uuid.uuid4().hex;name='atlas-archive-refresh-'+identifier;created=None
        with tempfile.TemporaryDirectory(prefix='project-atlas-writer-runtime.',dir='/tmp') as temporary:
            root=Path(temporary);root.chmod(0o700);writer.stage_source(native,root/'source')
            (root/'state').mkdir(mode=0o700);os.chown(root/'state',1000,1000)
            native.copy_tree(parent/'sports-metadata',root/'sports-metadata',True,(0,0),(1000,1000))
            native.copy_tree(parent/'sports-metadata-policy',root/'sports-metadata-policy',True,(0,0),(0,1000))
            (root/'sports-metadata-policy').chmod(0o750);(root/'sports-metadata-policy/refresh.json').chmod(0o640)
            preserved={key:native.shape(root/key,True) for key in ('source','sports-metadata-policy')}
            def owned():return inspect_owned(base,name,identifier,root,case,created)
            phase='create';print('SPORTS_REFRESH_SHUTDOWN=pending case='+case,flush=True)
            try:
                created=base.docker(*arguments(name,identifier,root,case)[1:]);require(re.fullmatch('[a-f0-9]{64}',created))
                require(owned()['State']['Status']=='created');base.docker('start',created)
                phase='inflight-fetch';deadline=time.monotonic()+15
                while not (root/'state/FETCH.json').exists():
                    require(owned()['State']['Running'] and time.monotonic()<deadline);time.sleep(.02)
                while True:
                    health=base.invoke('docker','exec',created,'python3','-B','-c',broker.HEALTH,timeout=3,check=False)
                    if health.returncode==0:break
                    require(owned()['State']['Running'] and time.monotonic()<deadline);time.sleep(.02)
                # Do not retry a mutating fetch: this probe only reads status/state.
                phase='inflight-proof'
                probe=broker.IDENTITY+'\nPOLICY='+repr(POLICY)+'\n'+PREFLIGHT
                result=base.invoke('docker','exec',created,'python3','-B','-c',probe,timeout=4)
                require(result.stdout.strip()==b'refresh-inflight-and-reservation-valid')
                phase='sigterm-and-join';start=time.monotonic()
                base.docker('stop','--time','20',created,timeout=25)
                require(time.monotonic()-start<15);writer.stopped(owned())
                proof=root/'state/SHUTDOWN.json'
                native.shape(proof,owner=(1000,1000))
                require(proof.stat().st_mode & 0o777==0o600 and proof.stat().st_size<=4096)
                validate_receipt(json.loads(proof.read_bytes()),case)
                require(all(native.shape(root/key,True)==value for key,value in preserved.items()))
            except Exception:
                print('SPORTS_REFRESH_SHUTDOWN=FAIL case='+case+' phase='+phase,flush=True);raise
            finally:
                found=base.invoke('docker','inspect',name,check=False)
                if found.returncode==0:
                    row=owned()
                    if row['State']['Running']:base.docker('stop','--time','20',row['Id'],timeout=25)
                    base.docker('rm',row['Id'])
                else:base.docker('info','--format','{{.ServerVersion}}')
                require(not base.docker('ps','-a','--filter','label='+LABEL+'='+identifier,'--format','{{.ID}}'))
        print('SPORTS_REFRESH_SIGTERM_CHILD_REAP_AND_ADMISSION_STOP=PASS case='+case,flush=True)
    require(all(native.pub.digest(parent/key,True)==value for key,value in before.items()))
    print(json.dumps({'version':1,'scope':'synthetic-refresh-worker-bounded-child-shutdown','cases':2,
        'normal_exit':True,'owned_child_reaped_before_writer_exit':True,'post_stop_admission_blocked':True,
        'bounded_worker_transport_tested':True,'external_provider_access':False,'production_refresh_enabled':False,
        'production_state_access':False,'live_restore_enabled':False},sort_keys=True))


class Rehearsal(broker.Rehearsal):
    def verify(self,native,sandbox):
        super().verify(native,sandbox)
        root=native.consumer.scoped(sandbox);accept(native,root/'current')
