"""Start the real writer application in an isolated installed-image runtime."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'sha256:a352324695a2bff4b838313a8fd6f81445384f641ce7a1e9f016a8d00a55b0dd'
LABEL = 'io.project-atlas.archive-writer-drill'
TOKEN = 'atlas-isolated-writer-drill-only'
# Exact source packaging declared by the actual writer Dockerfile. Mount it RO
# over the installed image's code; no image build, pull or production bind mount.
FILES = ('private_api.py', 'atlas_live_policy_claim.py', 'shared_admission.py', 'games_state.py', 'dispatcharr_admin.py',
         'dispatcharr_channel_bindings.py', 'live_tv_bindings.py', 'live_sources.py',
         'subscriptions.py', 'source_lifecycle.py')
REGISTRIES = {'SPORTS_LIVE_SOURCE_CATALOG_PATH': 'live-sources.json',
    'SPORTS_DISPATCHARR_CHANNEL_BINDINGS_FILE': 'dispatcharr-channel-bindings.json',
    'SPORTS_LIVE_TV_BINDINGS_FILE': 'live-tv-bindings.json',
    'SPORTS_SOURCE_LIFECYCLE_FILE': 'source-lifecycle.json'}
PROBE = r'''
import hashlib,json,os,sqlite3,urllib.request,urllib.error
from pathlib import Path
from providers.metadata_refresh import load_refresh_policy
assert os.getresuid()==(1000,1000,1000) and os.getresgid()==(1000,1000,1000)
assert os.getgroups() in ([],[1000])
root=Path('/metadata'); db=root/'metadata.sqlite'; policy=Path('/policy/refresh.json')
assert (root.stat().st_uid,root.stat().st_gid,root.stat().st_mode&0o777)==(1000,1000,0o700)
for path in root.iterdir():
 assert (path.stat().st_uid,path.stat().st_gid,path.stat().st_mode&0o777)==(1000,1000,0o600)
assert {p.name for p in root.iterdir()}=={'metadata.sqlite','metadata.sqlite.lock'}
assert (policy.parent.stat().st_uid,policy.parent.stat().st_gid,policy.parent.stat().st_mode&0o777)==(0,1000,0o750)
assert (policy.stat().st_uid,policy.stat().st_gid,policy.stat().st_mode&0o777)==(0,1000,0o640)
assert json.loads(policy.read_bytes())=={'version':1,'enabled':False}
assert load_refresh_policy() is None
with sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True) as connection:
 assert connection.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 assert connection.execute('SELECT stamp FROM metadata_attempts ORDER BY stamp').fetchall()==[(123.0,)]
 assert connection.execute('SELECT count(*) FROM metadata_aliases').fetchone()==(2,)
 assert connection.execute('SELECT key,until_stamp FROM metadata_holds').fetchall()==[('espn:cooldown',153.0)]
 rows=connection.execute('SELECT route,day,payload,observed,expires FROM metadata_cache').fetchall()
 assert len(rows)==1 and rows[0][:2]==('football/nfl','2026-10-17') and rows[0][3:]==(123.0,183.0)
 assert json.loads(rows[0][2])['fixture_generation']=='new'
def get(path,token=None):
 request=urllib.request.Request('http://127.0.0.1:8003'+path)
 if token is not None:request.add_header('Authorization','Bearer '+token)
 try:
  response=urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=2)
 except urllib.error.HTTPError as error:response=error
 with response:
  data=response.read(16385);assert len(data)<=16384
  return response.status,json.loads(data)
assert get('/health')==(200,{'status':'ok'})
assert get('/internal/v1/metadata/refresh-status')[0]==401
assert get('/internal/v1/metadata/refresh-status','wrong-fixture-token')[0]==401
assert get('/internal/v1/metadata/refresh-status',os.environ['ATLAS_SPORTS_WRITER_TOKEN'])==(200,{'version':1,'state':'disabled','running':False})
# Disabled policy must refuse HTTP broker access; no external request is enabled.
status,data=get('/internal/v1/metadata/day?route=football/nfl&day=2026-10-17',os.environ['ATLAS_SPORTS_WRITER_TOKEN'])
assert status==503 and data.get('error')=='Independent Sports metadata is unavailable.'
print(json.dumps({'uid':1000,'gid':1000,'database_sha256':hashlib.sha256(db.read_bytes()).hexdigest(),
 'policy_sha256':hashlib.sha256(policy.read_bytes()).hexdigest(),'refresh_disabled':True,'http_authenticated':True},sort_keys=True))
'''


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def require(value):
    if not value: raise ValueError('Isolated archive writer acceptance held')


def source_inputs():
    return {**{name: ROOT/'modules/sports/src'/name for name in FILES},
            'sports_shared_admission_config.py': ROOT/'atlas/sports_shared_admission_config.py',
            'providers': ROOT/'modules/sports/src/providers',
            'metadata-refresh.disabled.json': ROOT/'modules/sports/config/metadata-refresh.disabled.json'}


def stage_source(native, target):
    # Verify the reviewed Dockerfile still declares exactly this COPY set.
    dockerfile = (ROOT/'modules/sports/Dockerfile.private-api').read_text()
    copies = [line.split()[1:] for line in dockerfile.splitlines() if line.startswith('COPY ')]
    expected = [[str(path.relative_to(ROOT)), '/srv/sports/'+name] for name, path in source_inputs().items()]
    require(sorted(copies) == sorted(expected))
    target.mkdir(mode=0o755)
    for name, source in source_inputs().items():
        out = target/name
        native.copy_tree(source, out, source.is_dir(), target_owner=(os.geteuid(), os.getegid()))
        for path in [out, *out.rglob('*')] if out.is_dir() else [out]:
            path.chmod(0o755 if path.is_dir() else 0o644)
    native.pub.sync(target)


def arguments(name, identifier, root):
    require(re.fullmatch('[a-f0-9]{32}', identifier) and name == 'atlas-archive-writer-'+identifier)
    root = Path(root)
    require(root.parent == Path('/tmp') and root.name.startswith('project-atlas-writer-runtime.'))
    args = ['docker', 'create', '--name', name, '--label', LABEL+'='+identifier,
        '--pull=never', '--network=none', '--restart=no', '--no-healthcheck', '--log-driver=none',
        '--read-only', '--user=1000:1000', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
        '--memory=128m', '--cpus=0.5', '--pids-limit=64',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=16m,mode=1777']
    for source, destination, readonly in (('source', '/srv/sports', True), ('state', '/state', False),
            ('sports-metadata', '/metadata', False), ('sports-metadata-policy', '/policy', True)):
        args += ['--mount', 'type=bind,source='+str(root/source)+',destination='+destination+(',readonly' if readonly else '')]
    environment = {'ATLAS_SPORTS_WRITER_TOKEN': TOKEN, 'ATLAS_SPORTS_METADATA_STATE_DIR': '/metadata',
                   'ATLAS_SPORTS_METADATA_REFRESH_FILE': '/policy/refresh.json',
                   **{key: '/state/'+value for key, value in REGISTRIES.items()}}
    for key, value in environment.items(): args += ['--env', key+'='+value]
    # Preserve the installed image's actual entrypoint and command.
    return args+[IMAGE]


def inspect_owned(base, name, identifier, root, container_id=None):
    row = base.inspect(name); host = row['HostConfig']; config = row['Config']
    require(re.fullmatch('[a-f0-9]{64}', row['Id']) and (container_id is None or row['Id'] == container_id))
    require(row['Name'] == '/'+name and row['Image'] == IMAGE and config.get('Labels', {}).get(LABEL) == identifier)
    require(config.get('User') == '1000:1000' and not config.get('Entrypoint')
            and config.get('Cmd') == ['python3', '/srv/sports/private_api.py']
            and config.get('WorkingDir') == '/srv/sports' and not config.get('Volumes'))
    require(host.get('ReadonlyRootfs') and host.get('NetworkMode') == 'none'
        and not host.get('Privileged') and not host.get('PortBindings') and not host.get('PublishAllPorts')
        and not host.get('GroupAdd') and not host.get('CapAdd') and host.get('CapDrop') == ['ALL']
        and host.get('SecurityOpt') == ['no-new-privileges:true'] and not host.get('UsernsMode')
        and host.get('RestartPolicy', {}).get('Name') == 'no'
        and set(host.get('Tmpfs') or {}) == {'/tmp'} and host.get('IpcMode') == 'private'
        and host.get('LogConfig', {}).get('Type') == 'none'
        and host.get('Memory') == 128*1024**2 and host.get('PidsLimit') == 64)
    mounts = [item for item in row['Mounts'] if item['Type'] != 'tmpfs']
    require(len(mounts) == 4)
    expected = {'/srv/sports': ('source', False), '/state': ('state', True),
                '/metadata': ('sports-metadata', True), '/policy': ('sports-metadata-policy', False)}
    require({item['Destination'] for item in mounts} == set(expected))
    for item in mounts:
        source, writable = expected[item['Destination']]
        require(item['Type'] == 'bind' and item['Source'] == str(Path(root)/source) and item['RW'] is writable)
    return row


def stopped(row):
    state = row['State']
    require(state['Status'] == 'exited' and not state['Running'] and state['Pid'] == 0
            and state['ExitCode'] == 0 and not state['OOMKilled'])


def accept(native, parent):
    base = load('archive_writer_docker', 'scripts/diagnostics/sports-cold-copy-drill.py')
    metadata = load('archive_writer_metadata_contract', 'scripts/lib/sports-metadata-consumption.py')
    parent = Path(parent); metadata.check(native, parent, 'new')
    before = {name: native.pub.digest(parent/name, True) for name in ('sports-metadata', 'sports-metadata-policy')}
    image = json.loads(base.docker('image', 'inspect', IMAGE))[0]
    require(image['Id'] == IMAGE and not image['Config'].get('Volumes') and not image['Config'].get('Entrypoint')
            and image['Config'].get('Cmd') == ['python3', '/srv/sports/private_api.py'])
    identifier = uuid.uuid4().hex; name = 'atlas-archive-writer-'+identifier; created = None
    with tempfile.TemporaryDirectory(prefix='project-atlas-writer-runtime.', dir='/tmp') as temporary:
        root = Path(temporary); root.chmod(0o700)
        stage_source(native, root/'source')
        (root/'state').mkdir(mode=0o700); os.chown(root/'state', 1000, 1000)
        native.copy_tree(parent/'sports-metadata', root/'sports-metadata', True, (0, 0), (1000, 1000))
        native.copy_tree(parent/'sports-metadata-policy', root/'sports-metadata-policy', True, (0, 0), (0, 1000))
        (root/'sports-metadata-policy').chmod(0o750); (root/'sports-metadata-policy/refresh.json').chmod(0o640)
        preserved = {name: native.shape(root/name, True) for name in ('source', 'sports-metadata', 'sports-metadata-policy')}
        def owned(): return inspect_owned(base, name, identifier, root, created)
        def probe():
            result = base.invoke('docker', 'exec', created, 'python3', '-B', '-c', PROBE, timeout=10, check=False)
            if result.returncode != 0: return False
            require(len(result.stdout) <= 4096); data = json.loads(result.stdout)
            require(data == {'uid': 1000, 'gid': 1000,
                'database_sha256': hashlib.sha256((root/'sports-metadata/metadata.sqlite').read_bytes()).hexdigest(),
                'policy_sha256': hashlib.sha256((root/'sports-metadata-policy/refresh.json').read_bytes()).hexdigest(),
                'refresh_disabled': True, 'http_authenticated': True})
            return True
        def ready():
            deadline = time.monotonic()+30
            while True:
                require(owned()['State']['Running'])
                if probe(): break
                require(time.monotonic() < deadline); time.sleep(0.1)
        phase = 'create'
        print('SPORTS_WRITER_ARCHIVE_STARTUP=pending', flush=True)
        try:
            result = base.invoke(*arguments(name, identifier, root))
            created = result.stdout.decode().strip(); require(re.fullmatch('[a-f0-9]{64}', created))
            require(owned()['State']['Status'] == 'created')
            phase = 'start-and-probe'
            base.docker('start', created); ready()
            registry_before = native.shape(root/'state', True, (1000, 1000))
            require(all((root/'state'/name).is_file() for name in REGISTRIES.values()))
            phase = 'normal-stop'
            base.docker('stop', '--time', '10', created, timeout=20); stopped(owned())
            phase = 'restart-and-probe'
            base.docker('start', created); ready()
            require(native.shape(root/'state', True, (1000, 1000)) == registry_before)
            base.docker('stop', '--time', '10', created, timeout=20); stopped(owned())
            require(all(native.shape(root/key, True) == value for key, value in preserved.items()))
        except Exception:
            print('SPORTS_WRITER_ARCHIVE_ACCEPTANCE=FAIL phase='+phase, flush=True)
            raise
        finally:
            # A created object is removed only after its full ID, image, label,
            # settings and fixture mount sources are revalidated. Never prune.
            found = base.invoke('docker', 'inspect', name, check=False)
            if found.returncode == 0:
                row = owned()
                if row['State']['Running']: base.docker('stop', '--time', '10', row['Id'], timeout=20)
                base.docker('rm', row['Id'])
            else:
                base.docker('info', '--format', '{{.ServerVersion}}')
            require(not base.docker('ps', '-a', '--filter', 'label='+LABEL+'='+identifier, '--format', '{{.ID}}'))
        require(all(native.pub.digest(parent/key, True) == value for key, value in before.items()))
    print('SPORTS_WRITER_ARCHIVE_METADATA_START_RESTART_AND_AUTH=PASS', flush=True)
    print(json.dumps({'version': 1, 'scope': 'isolated-installed-writer-runtime-reviewed-source',
        'uid': 1000, 'restored_metadata_mounted': True, 'policy_mount_readonly': True,
        'rootfs_readonly': True, 'network': 'none', 'published_ports': False,
        'refresh_enabled': False, 'authenticated_http': True, 'normal_restart': True,
        'production_state_access': False, 'live_restore_enabled': False}, sort_keys=True))


archive = load('archive_writer_five_surface', 'scripts/lib/sports-archive-metadata.py')


class Rehearsal(archive.Rehearsal):
    def verify(self, native, sandbox):
        super().verify(native, sandbox)
        root = native.consumer.scoped(sandbox)
        accept(native, root/'current')
