"""Start/stop a fresh pinned-image AIO fixture, then acquire a read-only cold copy."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

IMAGE = 'sha256:e5d4b045b51519be4142a7baf7da6750ad33f80dcb0a77b8832c2ce930c6fe12'
HEAD = 'a5ebc893e00a2ad837dafedc87213e4815af63a3'
DEPLOYMENT = 'update-20261015T211211Z-632971'
LABEL = 'io.project-atlas.cold-copy-drill'
EXPECTED = {'version': 1, 'scope': 'synthetic-aio-cold-copy',
    'cold_source_cleanly_stopped': True, 'cold_source_unchanged': True,
    'native_preparation_validated': True, 'backup_row_restored': True,
    'clone_stopped': True, 'production_state_access': False, 'live_restore_enabled': False}


def require(condition):
    if not condition: raise RuntimeError('Isolated cold-copy drill contract failed')


def invoke(*args, input=None, timeout=30, check=True):
    result = subprocess.run(list(args), input=input, capture_output=True, timeout=timeout)
    require(len(result.stdout) <= 1048576)
    if check: require(result.returncode == 0)
    return result


def docker(*args, **kwargs):
    return invoke('docker', *args, **kwargs).stdout.decode().strip()


def inspect(name):
    return json.loads(docker('inspect', name))[0]


def observation():
    rows = []
    for name in ('atlas-dispatcharr', 'atlas-teamarr', 'atlas-sports-writer'):
        item = inspect(name)
        require(item['State']['Running'])
        rows.append((name, item['Image'], item['State']['Pid'], item['State']['StartedAt'], item['Mounts']))
    require(rows[0][1] == IMAGE)
    return rows


def container_options(name, identifier):
    return ['--name', name, '--label', LABEL + '=' + identifier, '--pull=never',
            '--network=none', '--restart=no', '--no-healthcheck', '--log-driver=none',
            '--memory=2g', '--cpus=2', '--pids-limit=512', '--security-opt=no-new-privileges']


def app_arguments(name, volume, identifier):
    return ['docker', 'create', *container_options(name, identifier),
            '--cap-drop=ALL', '--cap-add=CHOWN', '--cap-add=DAC_OVERRIDE',
            '--cap-add=FOWNER', '--cap-add=SETUID', '--cap-add=SETGID', '--cap-add=NET_BIND_SERVICE',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777',
            '--mount', 'type=volume,source=' + volume + ',destination=/data,volume-nocopy',
            '--env', 'PUID=1000', '--env', 'PGID=1000', '--env', 'DISPATCHARR_ENV=aio',
            '--env', 'POSTGRES_USER=dispatch', '--env', 'POSTGRES_DB=atlas_cold_drill',
            '--env', 'POSTGRES_PASSWORD=atlas-isolated-drill-only',
            '--env', 'UWSGI_NICE_LEVEL=0', '--env', 'CELERY_NICE_LEVEL=0', IMAGE]


def helper_arguments(name, volume, identifier, bootstrap):
    return ['docker', 'create', '-i', *container_options(name, identifier),
            '--read-only', '--user=1000:1000', '--cap-drop=ALL',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m,mode=1777',
            '--mount', 'type=volume,source=' + volume + ',destination=/source,readonly,volume-nocopy',
            '--env', 'ATLAS_COLD_COPY_DRILL=1', '--entrypoint', 'python3',
            IMAGE, '-I', '-B', '-c', bootstrap]


def owned_container(name, identifier, volume, destination, readonly):
    item = inspect(name)
    require(item['Image'] == IMAGE and item['Config'].get('Labels', {}).get(LABEL) == identifier)
    require(item['HostConfig']['NetworkMode'] == 'none')
    mounts = [row for row in item['Mounts'] if row['Type'] != 'tmpfs']
    require(len(mounts) == 1)
    mount = mounts[0]
    require(mount['Type'] == 'volume' and mount['Name'] == volume
            and mount['Destination'] == destination and mount['RW'] is not readonly)
    require(not item['HostConfig'].get('Privileged') and not item['HostConfig'].get('PortBindings'))
    require(item['HostConfig'].get('ReadonlyRootfs') is readonly)
    return item


def cleanup(container_names, volume, identifier):
    for name in reversed(container_names):
        result = invoke('docker', 'inspect', name, check=False)
        if result.returncode == 0:
            item = json.loads(result.stdout)[0]
            require(item['Config'].get('Labels', {}).get(LABEL) == identifier)
            docker('rm', '--force', '--volumes', name, timeout=45)
        else: docker('info', '--format', '{{.ServerVersion}}')
    result = invoke('docker', 'volume', 'inspect', volume, check=False)
    if result.returncode == 0:
        item = json.loads(result.stdout)[0]
        require(item.get('Labels', {}).get(LABEL) == identifier and item['Driver'] == 'local'
                and not item.get('Options'))
        docker('volume', 'rm', volume, timeout=30)
    else: docker('info', '--format', '{{.ServerVersion}}')


READY = r'''
from pathlib import Path
import subprocess
names=set()
for p in Path('/proc').iterdir():
    if p.name.isdigit():
        try: names.add((p/'comm').read_text().strip())
        except OSError: pass
assert {'postgres','uwsgi','celery','daphne','redis-server'} <= names
result=subprocess.run(['/usr/lib/postgresql/17/bin/psql','-XAt','-h','/var/run/postgresql',
    '-U','dispatch','-d','atlas_cold_drill','-v','ON_ERROR_STOP=1',
    '-c','SELECT count(*) FROM django_migrations'],capture_output=True,timeout=5)
assert result.returncode==0 and int(result.stdout.strip())>0
print('ready')
'''

SNAPSHOT = r'''
from pathlib import Path
import hashlib,os,subprocess
pins={'/app/docker/entrypoint.sh':'2c96dd61a1999654e32ac7b60999d0b9af196cded50952e4650f8530df426ceb',
'/app/docker/init/02-postgres.sh':'736d0e97c1d4b913f1293024af500a4953a182b4ad99fe0edd00f0c108db5105',
'/app/docker/init/03-init-dispatcharr.sh':'e0b58d5f0ab2c217dcf7651bcf6b57b167684c0f9664ae5c43f78045199a2259',
'/app/docker/uwsgi.ini':'4d81958689da09970e0740e9ee426bec6db6ba7f54792a267ae4a9697d52f577'}
assert os.geteuid()==1000
for name,expected in pins.items(): assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected
base=['/usr/lib/postgresql/17/bin/psql','-XAt','-h','/var/run/postgresql','-U','dispatch',
      '-d','atlas_cold_drill','-v','ON_ERROR_STOP=1']
def sql(query):
    r=subprocess.run(base+['-c',query],capture_output=True,timeout=10); assert r.returncode==0
sql("CREATE TABLE atlas_cold_copy_probe(id integer PRIMARY KEY, marker text NOT NULL); INSERT INTO atlas_cold_copy_probe VALUES(1,'snapshot')")
r=subprocess.run(['/usr/lib/postgresql/17/bin/pg_dump','-h','/var/run/postgresql','-U','dispatch',
    '-d','atlas_cold_drill','--format=custom','--no-owner','--file=/data/atlas-cold-copy.dump'],
    capture_output=True,timeout=45)
assert r.returncode==0
Path('/data/atlas-cold-copy.dump').chmod(0o600)
assert 5<Path('/data/atlas-cold-copy.dump').stat().st_size<=512*1024**2
sql("UPDATE atlas_cold_copy_probe SET marker='after-dump'")
print('snapshot-captured')
'''


def run():
    root = Path(__file__).resolve().parents[2]
    require(invoke('git', '-C', str(root), 'rev-parse', 'HEAD').stdout.decode().strip() == HEAD)
    pointer = Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink())
    deployment = pointer.read_bytes(); require(deployment.decode().strip() == DEPLOYMENT)
    before = observation()
    image = json.loads(docker('image', 'inspect', IMAGE))[0]
    require(image['Id'] == IMAGE and image['Config']['Entrypoint'] == ['/app/docker/entrypoint.sh']
            and not image['Config'].get('Cmd') and not image['Config'].get('Volumes'))
    adapter = (root / 'scripts/lib/sports-postgres-prepare.py').read_bytes()
    helper = (root / 'scripts/lib/sports-cold-copy-drill.py').read_bytes()
    require(hashlib.sha256(adapter).hexdigest() == '34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc')
    require(hashlib.sha256(helper).hexdigest() == 'e575c8f4044aa0e46d021744b480f174db31cd779c07bc2e11aa96f82f4c6ad1')
    payload = json.dumps({'adapter': adapter.decode(), 'helper': helper.decode()}).encode()
    bootstrap = "import hashlib,json,sys,types\np=json.loads(sys.stdin.buffer.read(1048577))\nassert set(p)=={'adapter','helper'}\nassert hashlib.sha256(p['adapter'].encode()).hexdigest()=='34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc'\nassert hashlib.sha256(p['helper'].encode()).hexdigest()=='e575c8f4044aa0e46d021744b480f174db31cd779c07bc2e11aa96f82f4c6ad1'\nm=types.ModuleType('atlas_pg_prepare');sys.modules['atlas_pg_prepare']=m\nexec(compile(p['adapter'],'<adapter>','exec'),m.__dict__)\nexec(compile(p['helper'],'<helper>','exec'),{'__name__':'__main__'})\n"
    identifier = uuid.uuid4().hex
    app = 'atlas-cold-app-' + identifier; cold = 'atlas-cold-helper-' + identifier
    volume = 'atlas-cold-data-' + identifier
    phase = 'volume-create'
    try:
        docker('volume', 'create', '--driver', 'local', '--label', LABEL + '=' + identifier, volume)
        phase = 'app-create'
        invoke(*app_arguments(app, volume, identifier))
        owned_container(app, identifier, volume, '/data', False)
        docker('start', app)
        phase = 'app-readiness'
        deadline = time.monotonic() + 180; next_update = 0
        while time.monotonic() < deadline:
            item = owned_container(app, identifier, volume, '/data', False)
            require(item['State']['Running'])
            ready = invoke('docker', 'exec', '--user', '1000:1000', app, 'python3', '-B', '-c', READY,
                           timeout=12, check=False)
            if ready.returncode == 0 and ready.stdout.strip() == b'ready': break
            if time.monotonic() >= next_update:
                print('SYNTHETIC_AIO_STARTUP=pending', flush=True); next_update = time.monotonic() + 20
            time.sleep(2)
        else: raise RuntimeError('Startup deadline')
        print('SYNTHETIC_AIO_READY=PASS', flush=True)
        phase = 'synthetic-snapshot'
        require(docker('exec', '--user', '1000:1000', app, 'python3', '-B', '-c', SNAPSHOT,
                       timeout=65) == 'snapshot-captured')
        phase = 'synthetic-postgres-fast-stop'
        owned_container(app, identifier, volume, '/data', False)
        # Container exit alone is not evidence of a clean PostgreSQL shutdown.
        # Stop PG fast inside ONLY this owned synthetic AIO instance before the
        # entrypoint's bounded cleanup can fall back to an immediate PG stop.
        docker('exec', '--user', '1000:1000', app,
               '/usr/lib/postgresql/17/bin/pg_ctl', '-D', '/data/db',
               '-m', 'fast', '-w', '-t', '20', 'stop', timeout=30)
        print('SYNTHETIC_POSTGRES_FAST_STOP=PASS', flush=True)
        phase = 'synthetic-stop'
        owned_container(app, identifier, volume, '/data', False)
        docker('stop', '--time', '35', app, timeout=45)
        item = owned_container(app, identifier, volume, '/data', False)
        require(item['State']['Status'] == 'exited' and not item['State']['Running']
                and item['State']['Pid'] == 0 and not item['State']['OOMKilled']
                and item['State']['ExitCode'] in (0, 143))
        print('SYNTHETIC_AIO_STOPPED=PASS', flush=True)
        phase = 'cold-copy-preparation'
        print('SYNTHETIC_COLD_COPY_PREPARATION=running', flush=True)
        invoke(*helper_arguments(cold, volume, identifier, bootstrap))
        owned_container(cold, identifier, volume, '/source', True)
        result = invoke('docker', 'start', '--attach', '--interactive', cold,
                        input=payload, timeout=180, check=False)
        if result.returncode:
            match = re.search(rb'COLD_COPY_HELPER=FAIL category=([a-z-]{1,80})', result.stderr)
            if match: print(match.group().decode(), file=sys.stderr)
        require(result.returncode == 0 and json.loads(result.stdout) == EXPECTED)
        item = owned_container(cold, identifier, volume, '/source', True)
        require(item['State']['Status'] == 'exited' and item['State']['Pid'] == 0
                and not item['State']['Running'] and item['State']['ExitCode'] == 0
                and not item['State']['OOMKilled'])
    except Exception:
        print('COLD_COPY_DRILL=FAIL phase=' + phase, file=sys.stderr)
        raise
    finally:
        cleanup((app, cold), volume, identifier)
        require(pointer.read_bytes() == deployment and observation() == before)
    print(json.dumps(EXPECTED, sort_keys=True))
    print('SYNTHETIC_AIO_COLD_COPY_DRILL=PASS')
    print('STATE=synthetic-shutdown-cold-copy-only-production-unchanged')


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_AIO_COLD_COPY_DRILL=FAIL; production restore was not requested.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
