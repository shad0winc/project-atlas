"""Fixture-only broker factory/loopback provider inside the isolated writer runtime."""
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
LABEL = 'io.project-atlas.archive-broker-drill'
BOOTSTRAP = r'''
import json,os,sqlite3,sys,threading,urllib.request
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import private_api
from providers.espn_metadata import LEAGUE_UIDS
from providers.metadata_store import MetadataStore
from providers.metadata_broker import MetadataBroker,ESPNDayTransport,_NoRedirect
from providers import metadata_service
STAMP=datetime(2026,10,17,12,tzinfo=timezone.utc).timestamp()
state=Path(os.environ['SPORTS_SOURCE_LIFECYCLE_FILE']).parent
store=MetadataStore(Path(os.environ['ATLAS_SPORTS_METADATA_STATE_DIR'])/'metadata.sqlite')
class Provider(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  assert self.path=='/scoreboard?dates=20261017'
  # Separate connection: the reservation must be committed before HTTP fetch.
  with sqlite3.connect(store.path.as_uri()+'?mode=ro',uri=True) as connection:
   assert connection.execute('SELECT stamp FROM metadata_attempts').fetchall()==[(STAMP,)]
   assert connection.execute('SELECT until_stamp FROM metadata_holds WHERE key=?',('football/nfl:2026-10-17',)).fetchall()==[(STAMP+30,)]
  raw=(json.dumps({'route':'football/nfl','day':'2026-10-17','reservation_visible':True},sort_keys=True)+'\n').encode()
  fd=os.open(state/'provider-requests.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'ab') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
  payload=json.dumps({'events':[],'leagues':[{'uid':LEAGUE_UIDS['football/nfl']}],'fixture_generation':'broker-local'}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
provider=ThreadingHTTPServer(('127.0.0.1',0),Provider)
class LocalOpener:
 def open(self,request,timeout):
  assert request.full_url=='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261017'
  local=urllib.request.Request('http://127.0.0.1:'+str(provider.server_port)+'/scoreboard?dates=20261017',headers=dict(request.header_items()))
  return urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect()).open(local,timeout=min(timeout,2))
broker=MetadataBroker(store,transport=ESPNDayTransport(opener=LocalOpener(),clock=lambda:STAMP),clock=lambda:STAMP,hourly_budget=1)
# Explicit existing test seam: production request validation/serialization, broker,
# parser and SQLite admission are unchanged. The scheduler still loads disabled policy.
metadata_service.query_metadata.__kwdefaults__['broker_factory']=lambda:broker
thread=threading.Thread(target=provider.serve_forever,daemon=True);thread.start()
try:
 sys.argv=['private_api.py','--port',os.environ.get('ATLAS_FIXTURE_WRITER_PORT','8003')]
 result=private_api.main()
finally:
 provider.shutdown();provider.server_close();thread.join(3);assert not thread.is_alive()
raise SystemExit(result)
'''
CHECKS = r'''
import hashlib,json,os,sqlite3,sys,urllib.request,urllib.error
from datetime import date,datetime,timezone
from pathlib import Path
from providers.metadata_service import parse_snapshot
from providers.metadata_identity import SourceIdentity
from providers.metadata_refresh import load_refresh_policy
STAMP=datetime(2026,10,17,12,tzinfo=timezone.utc).timestamp()
first=sys.argv[1]=='first';assert sys.argv[1] in {'first','restart'}
directory=Path(os.environ['ATLAS_SPORTS_METADATA_STATE_DIR']);db=directory/'metadata.sqlite'
policy=Path(os.environ['ATLAS_SPORTS_METADATA_REFRESH_FILE']);state=Path(os.environ['SPORTS_SOURCE_LIFECYCLE_FILE']).parent
assert json.loads(policy.read_bytes())=={'version':1,'enabled':False} and load_refresh_policy() is None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(path,token=None):
 request=urllib.request.Request('http://127.0.0.1:'+os.environ.get('ATLAS_FIXTURE_WRITER_PORT','8003')+path)
 if token is not None:request.add_header('Authorization','Bearer '+token)
 try:response=opener.open(request,timeout=2)
 except urllib.error.HTTPError as error:response=error
 with response:
  raw=response.read(16385);assert len(raw)<=16384
  return response.status,json.loads(raw)
query='/internal/v1/metadata/day?route=football/nfl&day=2026-10-17'
assert get('/health')==(200,{'status':'ok'})
assert get(query)[0]==401 and get(query,'wrong-fixture-token')[0]==401
assert get('/internal/v1/metadata/refresh-status',os.environ['ATLAS_SPORTS_WRITER_TOKEN'])==(200,{'version':1,'state':'disabled','running':False})
assert get('/internal/v1/metadata/day?route=football/nfl&day=invalid',os.environ['ATLAS_SPORTS_WRITER_TOKEN'])[0]==400
if first:
 with sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True) as connection:
  assert connection.execute('SELECT stamp FROM metadata_attempts').fetchall()==[(123.0,)]
 assert not (state/'provider-requests.jsonl').exists()
responses=[]
for index in range(2):
 status,data=get(query,os.environ['ATLAS_SPORTS_WRITER_TOKEN']);assert status==200
 snapshot=parse_snapshot(data,kind='day',route='football/nfl',day=date(2026,10,17))
 assert snapshot.events==() and snapshot.observed_at==STAMP and snapshot.expires_at==STAMP+60
 assert snapshot.cache_hit is (not first or index==1) and not snapshot.stale
 responses.append(data)
status,error=get('/internal/v1/metadata/day?route=football/nfl&day=2026-10-18',os.environ['ATLAS_SPORTS_WRITER_TOKEN'])
assert status==503 and error=={'error':'Independent Sports metadata is unavailable.','retry_after_seconds':3600}
# The warm cache still works after the shared request budget is exhausted.
status,data=get(query,os.environ['ATLAS_SPORTS_WRITER_TOKEN']);assert status==200 and data==responses[1]
with sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True) as connection:
 assert connection.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 assert connection.execute('SELECT stamp FROM metadata_attempts').fetchall()==[(STAMP,)]
 assert connection.execute('SELECT key,until_stamp FROM metadata_holds ORDER BY key').fetchall()==[('espn:cooldown',153.0)]
 owner=SourceIdentity('thesportsdb','4391','910002')
 expected=[owner.values()+owner.values()+('f'*64,),SourceIdentity('espn','football/nfl','401999991').values()+owner.values()+('f'*64,)]
 assert sorted(connection.execute('SELECT * FROM metadata_aliases').fetchall())==sorted(expected)
 rows=connection.execute('SELECT route,day,payload,observed,expires FROM metadata_cache').fetchall()
 assert len(rows)==1 and rows[0][:2]==('football/nfl','2026-10-17') and rows[0][3:]==(STAMP,STAMP+60)
 assert json.loads(rows[0][2])['fixture_generation']=='broker-local'
assert {p.name for p in directory.iterdir()}=={'metadata.sqlite','metadata.sqlite.lock'}
records=[json.loads(line) for line in (state/'provider-requests.jsonl').read_text().splitlines()]
assert records==[{'route':'football/nfl','day':'2026-10-17','reservation_visible':True}]
print(json.dumps({'version':1,'paid_attempts':1,'provider_requests':1,'reservation_visible':True,
 'cache_reused':True,'budget_refused':True,'restart':not first,'refresh_enabled':False},sort_keys=True))
'''
IDENTITY = r'''
import os
from pathlib import Path
assert os.getresuid()==(1000,1000,1000) and os.getresgid()==(1000,1000,1000)
assert os.getgroups() in ([],[1000])
directory=Path('/metadata');policy=Path('/policy/refresh.json')
assert (directory.stat().st_uid,directory.stat().st_gid,directory.stat().st_mode&0o777)==(1000,1000,0o700)
for path in directory.iterdir():assert (path.stat().st_uid,path.stat().st_gid,path.stat().st_mode&0o777)==(1000,1000,0o600)
assert (policy.parent.stat().st_uid,policy.parent.stat().st_gid,policy.parent.stat().st_mode&0o777)==(0,1000,0o750)
assert (policy.stat().st_uid,policy.stat().st_gid,policy.stat().st_mode&0o777)==(0,1000,0o640)
'''
PROBE = IDENTITY+CHECKS
HEALTH = "import urllib.request; o=urllib.request.build_opener(urllib.request.ProxyHandler({})); assert o.open('http://127.0.0.1:8003/health',timeout=1).status==200"


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def require(value):
    if not value: raise ValueError('Isolated archive broker acceptance held')


writer = load('archive_broker_writer', 'scripts/lib/sports-archive-writer.py')


def arguments(name, identifier, root):
    require(name == 'atlas-archive-broker-'+identifier)
    args = writer.arguments('atlas-archive-writer-'+identifier, identifier, root)
    args[args.index('--name')+1] = name
    args[args.index('--label')+1] = LABEL+'='+identifier
    return args[:-1]+['--entrypoint', 'python3', writer.IMAGE, '-B', '-c', BOOTSTRAP]


def inspect_owned(base, name, identifier, root, container_id=None):
    row=base.inspect(name);host=row['HostConfig'];config=row['Config']
    require(re.fullmatch('[a-f0-9]{32}',identifier) and name=='atlas-archive-broker-'+identifier)
    require(re.fullmatch('[a-f0-9]{64}',row['Id']) and (container_id is None or row['Id']==container_id))
    require(row['Name']=='/'+name and row['Image']==writer.IMAGE and config.get('Labels',{}).get(LABEL)==identifier)
    require(config.get('User')=='1000:1000' and config.get('Entrypoint')==['python3']
        and config.get('Cmd')==['-B','-c',BOOTSTRAP] and config.get('WorkingDir')=='/srv/sports' and not config.get('Volumes'))
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


def receipt(data, restart):
    require(data=={'version':1,'paid_attempts':1,'provider_requests':1,'reservation_visible':True,
        'cache_reused':True,'budget_refused':True,'restart':restart,'refresh_enabled':False})


def accept(native, parent):
    base=load('archive_broker_docker','scripts/diagnostics/sports-cold-copy-drill.py')
    metadata=writer.load('archive_broker_metadata','scripts/lib/sports-metadata-consumption.py')
    parent=Path(parent);metadata.check(native,parent,'new')
    before={name:native.pub.digest(parent/name,True) for name in ('sports-metadata','sports-metadata-policy')}
    image=json.loads(base.docker('image','inspect',writer.IMAGE))[0]
    require(image['Id']==writer.IMAGE and not image['Config'].get('Volumes') and not image['Config'].get('Entrypoint'))
    identifier=uuid.uuid4().hex;name='atlas-archive-broker-'+identifier;created=None
    with tempfile.TemporaryDirectory(prefix='project-atlas-writer-runtime.',dir='/tmp') as temporary:
        root=Path(temporary);root.chmod(0o700)
        writer.stage_source(native,root/'source')
        (root/'state').mkdir(mode=0o700);os.chown(root/'state',1000,1000)
        native.copy_tree(parent/'sports-metadata',root/'sports-metadata',True,(0,0),(1000,1000))
        native.copy_tree(parent/'sports-metadata-policy',root/'sports-metadata-policy',True,(0,0),(0,1000))
        (root/'sports-metadata-policy').chmod(0o750);(root/'sports-metadata-policy/refresh.json').chmod(0o640)
        preserved={key:native.shape(root/key,True) for key in ('source','sports-metadata-policy')}
        original_metadata=native.shape(root/'sports-metadata',True)
        def owned():return inspect_owned(base,name,identifier,root,created)
        def ready():
            deadline=time.monotonic()+30
            while True:
                require(owned()['State']['Running'])
                result=base.invoke('docker','exec',created,'python3','-B','-c',HEALTH,timeout=3,check=False)
                if result.returncode==0:break
                require(time.monotonic()<deadline);time.sleep(.1)
        phase='create'
        print('SPORTS_WRITER_CONTROLLED_BROKER_STARTUP=pending',flush=True)
        try:
            created=base.docker(*arguments(name,identifier,root)[1:]);require(re.fullmatch('[a-f0-9]{64}',created))
            require(owned()['State']['Status']=='created')
            first_state=None
            for attempt in range(2):
                phase='start' if attempt==0 else 'restart'
                base.docker('start',created);ready()
                phase='broker-requests' if attempt==0 else 'persisted-cache-and-budget'
                result=base.invoke('docker','exec',created,'python3','-B','-c',PROBE,'first' if attempt==0 else 'restart',timeout=15)
                require(len(result.stdout)<=4096);receipt(json.loads(result.stdout),attempt==1)
                phase='normal-stop';base.docker('stop','--time','10',created,timeout=20);writer.stopped(owned())
                current=(native.shape(root/'state',True,(1000,1000)),native.shape(root/'sports-metadata',True,(1000,1000)))
                if first_state is None:first_state=current
                else:require(current==first_state)
            require(native.shape(root/'sports-metadata',True)!=original_metadata)
            require(all(native.shape(root/key,True)==value for key,value in preserved.items()))
        except Exception:
            print('SPORTS_WRITER_CONTROLLED_BROKER=FAIL phase='+phase,flush=True);raise
        finally:
            found=base.invoke('docker','inspect',name,check=False)
            if found.returncode==0:
                row=owned()
                if row['State']['Running']:base.docker('stop','--time','10',row['Id'],timeout=20)
                base.docker('rm',row['Id'])
            else:base.docker('info','--format','{{.ServerVersion}}')
            require(not base.docker('ps','-a','--filter','label='+LABEL+'='+identifier,'--format','{{.ID}}'))
        require(all(native.pub.digest(parent/key,True)==value for key,value in before.items()))
    print('SPORTS_WRITER_CONTROLLED_BROKER_RESERVATION_CACHE_BUDGET_RESTART=PASS',flush=True)
    print(json.dumps({'version':1,'scope':'synthetic-writer-loopback-broker-accounting','upstream_requests':1,
        'paid_attempts':1,'reservation_visible_before_fetch':True,'cache_and_budget_persisted':True,
        'scheduler_enabled':False,'external_provider_access':False,'bounded_worker_transport_tested':False,
        'production_state_access':False,'live_restore_enabled':False},sort_keys=True))


class Rehearsal(writer.Rehearsal):
    def verify(self,native,sandbox):
        super().verify(native,sandbox)
        root=native.consumer.scoped(sandbox);accept(native,root/'current')
