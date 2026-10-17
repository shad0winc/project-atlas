"""Pinned-image Teamarr synthetic shutdown, WAL-copy and restored restart drill."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import uuid

IMAGE = 'sha256:ecec625df0a029cddecf72fcb86d0d2eb9c16ce14f9377b1ddc0954bba4e2ec7'
HEAD = '39133f6dcacd343c4dde20c6cfc7cad372dd985b'
DEPLOYMENT = 'update-20261015T211211Z-632971'
LABEL = 'io.project-atlas.teamarr-recovery-drill'


def require(condition):
    if not condition: raise RuntimeError('Synthetic Teamarr drill contract failed')


def utilities(root):
    path = root / 'scripts/diagnostics/sports-cold-copy-drill.py'
    require(path.is_file() and not path.is_symlink())
    require(hashlib.sha256(path.read_bytes()).hexdigest() == '1d714b2d4be23d3234045836b1c31e1d92826fbcc03fa08411d184e7f7191ecb')
    spec = importlib.util.spec_from_file_location('teamarr_drill_utilities', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.IMAGE = IMAGE; module.LABEL = LABEL
    return module


def app_arguments(base, name, volume, identifier):
    return ['docker', 'create', *base.container_options(name, identifier), '--user=0:0',
        '--cap-drop=ALL', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m,mode=1777',
        '--mount', 'type=volume,source=' + volume + ',destination=/app/data,volume-nocopy',
        '--env', 'SKIP_CACHE_REFRESH=1', '--env', 'SCHEDULER=off', '--env', 'DRY_RUN=true',
        '--env', 'PORT=9195', '--env', 'PYTHONDONTWRITEBYTECODE=1', IMAGE]


def helper_arguments(base, name, volume, identifier, bootstrap, mode):
    require(mode in {'capture', 'capture-restored', 'restore-fixture'})
    readonly = mode != 'restore-fixture'
    return ['docker', 'create', '-i', *base.container_options(name, identifier),
        '--read-only', '--user=0:0', '--cap-drop=ALL',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777',
        '--mount', 'type=volume,source=' + volume + ',destination=/source,'
            + ('readonly,' if readonly else '') + 'volume-nocopy',
        '--env', 'ATLAS_TEAMARR_DRILL=1', '--entrypoint', 'python3',
        IMAGE, '-I', '-B', '-c', bootstrap, mode]


READY = r'''
import http.client,json
c=http.client.HTTPConnection('127.0.0.1',9195,timeout=3)
c.request('GET','/health');r=c.getresponse();raw=r.read(65537)
assert r.status==200 and len(raw)<=65536
p=json.loads(raw)
assert p['status']=='healthy' and p['runtime']=={'scheduler_enabled':False,'dry_run':True}
c.close();print('ready')
'''

SEED = r'''
from pathlib import Path
import hashlib,sqlite3,time
pins={'/app/app.py':'b98d67e115868c163545774ddd53ab1aa5681cdf64495d00f8edbf34b3e6e17e',
'/app/teamarr/api/app.py':'1a796278a94840f0e82e7f5086f378cbdff51e7ae17a860c82914fe93a79c9d5',
'/app/teamarr/config/runtime.py':'cf54a812930c79f05af96df6399084094bdd6745f4ad231862773dcb28db9493',
'/app/teamarr/api/routes/health.py':'5a90ba2fa8115cfca9e07a0a6acc600660ca398d306a6392174c6529b536923f'}
for name,digest in pins.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
db=Path('/app/data/teamarr.db');assert db.is_file() and not db.is_symlink()
conn=sqlite3.connect(db,timeout=2)
target=sqlite3.connect('/app/data/atlas-teamarr-snapshot.db',timeout=2)
deadline=time.monotonic()+10
def progress(*unused):
    if time.monotonic()>deadline:raise RuntimeError('snapshot deadline')
try:
    conn.execute('CREATE TABLE atlas_teamarr_probe(id INTEGER PRIMARY KEY,marker TEXT NOT NULL)')
    conn.execute("INSERT INTO atlas_teamarr_probe VALUES(1,'snapshot')");conn.commit()
    conn.backup(target,pages=256,progress=progress,sleep=0.01)
    target.close();target=None
    Path('/app/data/atlas-teamarr-snapshot.db').chmod(0o600)
    conn.execute("UPDATE atlas_teamarr_probe SET marker='after-dump'");conn.commit()
finally:
    if target is not None:target.close()
    conn.close()
print('snapshot-captured')
'''


def marker_code(marker):
    require(marker in {'snapshot', 'after-dump'})
    return "import sqlite3\nc=sqlite3.connect('file:/app/data/teamarr.db?mode=ro',uri=True,timeout=1)\ntry:\n assert c.execute('SELECT marker FROM atlas_teamarr_probe ORDER BY id').fetchall()==[(" + repr(marker) + ",)]\nfinally:c.close()\nprint('marker-valid')\n"


def wait_ready(base, app, identifier, volume):
    deadline = time.monotonic() + 120; next_update = 0
    while time.monotonic() < deadline:
        require(base.owned_container(app, identifier, volume, '/app/data', False)['State']['Running'])
        result = base.invoke('docker', 'exec', app, 'python3', '-B', '-c', READY, timeout=8, check=False)
        if result.returncode == 0 and result.stdout.strip() == b'ready': return
        if time.monotonic() >= next_update:
            print('SYNTHETIC_TEAMARR_STARTUP=pending', flush=True); next_update = time.monotonic() + 20
        time.sleep(2)
    raise RuntimeError('Teamarr readiness deadline')


def stop(base, app, identifier, volume):
    base.owned_container(app, identifier, volume, '/app/data', False)
    base.docker('stop', '--time', '35', app, timeout=45)
    state = base.owned_container(app, identifier, volume, '/app/data', False)['State']
    require(state['Status'] == 'exited' and not state['Running'] and state['Pid'] == 0
            and state['ExitCode'] in (0, 143) and not state['OOMKilled'])


def inspect_helper(base, name, identifier, volume, mode):
    item = base.inspect(name)
    require(item['Image'] == IMAGE and item['Config'].get('Labels', {}).get(LABEL) == identifier
            and item['Config']['User'] == '0:0' and item['HostConfig']['ReadonlyRootfs'] is True
            and item['HostConfig']['NetworkMode'] == 'none'
            and not item['HostConfig'].get('Privileged') and not item['HostConfig'].get('PortBindings'))
    mounts = [m for m in item['Mounts'] if m['Type'] != 'tmpfs']
    require(len(mounts) == 1 and mounts[0]['Type'] == 'volume' and mounts[0]['Name'] == volume
            and mounts[0]['Destination'] == '/source' and mounts[0]['RW'] is (mode == 'restore-fixture'))
    return item


def run():
    root = Path(__file__).resolve().parents[2]; base = utilities(root)
    require(base.invoke('git', '-C', str(root), 'rev-parse', 'HEAD').stdout.decode().strip() == HEAD)
    pointer = Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink())
    deployment = pointer.read_bytes(); require(deployment.decode().strip() == DEPLOYMENT)
    def observe():
        rows = []
        for name in ('atlas-dispatcharr', 'atlas-teamarr', 'atlas-sports-writer'):
            item = base.inspect(name); require(item['State']['Running'])
            if name == 'atlas-teamarr': require(item['Image'] == IMAGE)
            rows.append((name, item['Image'], item['State']['Pid'], item['State']['StartedAt'], item['Mounts']))
        return rows
    before = observe()
    image = json.loads(base.docker('image', 'inspect', IMAGE))[0]
    config = image['Config']
    require(image['Id'] == IMAGE and not config.get('Entrypoint') and config.get('Cmd') == ['python', 'app.py']
            and config.get('WorkingDir') == '/app' and not config.get('Volumes'))
    helper = (root / 'scripts/lib/sports-teamarr-recovery-drill.py').read_bytes()
    require(hashlib.sha256(helper).hexdigest() == 'dcda557e3bb34a832458a19bf1fea1e409568cabbd02dd9c2adbd4668772660d')
    bootstrap = "import hashlib,sys\nr=sys.stdin.buffer.read(1048577)\nassert len(r)<=1048576\nassert hashlib.sha256(r).hexdigest()=='dcda557e3bb34a832458a19bf1fea1e409568cabbd02dd9c2adbd4668772660d'\nexec(compile(r,'<teamarr-fixture>','exec'),{'__name__':'__main__'})\n"
    identifier = uuid.uuid4().hex
    app = 'atlas-teamarr-drill-app-' + identifier
    volume = 'atlas-teamarr-drill-data-' + identifier
    containers = [app]; phase = 'create-fixture'; results = []
    def helper_run(mode):
        stopped = base.owned_container(app, identifier, volume, '/app/data', False)['State']
        require(stopped['Status'] == 'exited' and not stopped['Running'] and stopped['Pid'] == 0
                and stopped['ExitCode'] in (0, 143) and not stopped['OOMKilled'])
        name = 'atlas-teamarr-drill-' + mode + '-' + identifier
        containers.append(name)
        # The base utility couples RO source mounts with RO roots. The write
        # helper still has a RO root, so inspect that separately below.
        base.invoke(*helper_arguments(base, name, volume, identifier, bootstrap, mode))
        inspect_helper(base, name, identifier, volume, mode)
        result = base.invoke('docker', 'start', '--attach', '--interactive', name, input=helper, timeout=60, check=False)
        if result.returncode: print('TEAMARR_FIXTURE_HELPER=FAIL mode=' + mode, file=sys.stderr)
        require(result.returncode == 0 and len(result.stdout) <= 4096)
        receipt = json.loads(result.stdout)
        common = {'version': 1, 'scope': 'synthetic-teamarr-only', 'mode': mode,
                  'production_state_access': False, 'live_restore_enabled': False}
        if mode == 'restore-fixture':
            require(receipt == {**common, 'restored_snapshot': True, 'old_set_preserved': True, 'restored_mode': '0600'})
        else:
            require(set(receipt) == set(common) | {'cold_set_unchanged', 'cold_set_valid', 'snapshot_valid', 'copied_wal', 'database_mode'})
            require(all(receipt[key] == value for key, value in common.items()))
            require(all(receipt[key] is True for key in ('cold_set_unchanged', 'cold_set_valid', 'snapshot_valid'))
                    and type(receipt['copied_wal']) is bool)
            require(receipt['database_mode'] in {'0600', '0644'})
            if mode == 'capture-restored': require(receipt['database_mode'] == '0600')
        state = inspect_helper(base, name, identifier, volume, mode)['State']
        require(not state['Running'] and state['Status'] == 'exited' and state['ExitCode'] == 0 and not state['OOMKilled'])
        results.append(receipt)
    try:
        base.docker('volume', 'create', '--driver', 'local', '--label', LABEL + '=' + identifier, volume)
        base.invoke(*app_arguments(base, app, volume, identifier))
        base.owned_container(app, identifier, volume, '/app/data', False)
        base.docker('start', app); wait_ready(base, app, identifier, volume)
        require(base.docker('exec', app, 'python3', '-B', '-c', SEED, timeout=30) == 'snapshot-captured')
        phase = 'stop-and-cold-copy'; stop(base, app, identifier, volume); helper_run('capture')
        print('TEAMARR_STOPPED_COLD_COPY=PASS', flush=True)
        phase = 'persistence-restart'
        base.docker('start', app); wait_ready(base, app, identifier, volume)
        require(base.docker('exec', app, 'python3', '-B', '-c', marker_code('after-dump')) == 'marker-valid')
        stop(base, app, identifier, volume)
        phase = 'restore-stopped-fixture'; helper_run('restore-fixture')
        phase = 'restored-application-restart'
        base.docker('start', app); wait_ready(base, app, identifier, volume)
        require(base.docker('exec', app, 'python3', '-B', '-c', marker_code('snapshot')) == 'marker-valid')
        stop(base, app, identifier, volume); helper_run('capture-restored')
    except Exception:
        print('TEAMARR_RECOVERY_DRILL=FAIL phase=' + phase, file=sys.stderr); raise
    finally:
        base.cleanup(containers, volume, identifier)
        require(pointer.read_bytes() == deployment and observe() == before)
    print(json.dumps({'version': 1, 'scope': 'synthetic-teamarr-recovery', 'stopped_cold_copy': True,
        'persistence_restart': True, 'restored_application_restart': True, 'restored_mode': '0600',
        'production_state_access': False, 'live_restore_enabled': False, 'checks': results}, sort_keys=True))
    print('SYNTHETIC_TEAMARR_RECOVERY_DRILL=PASS')
    print('STATE=synthetic-Teamarr-rehearsal-only-production-unchanged')


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_TEAMARR_RECOVERY_DRILL=FAIL; no production restore requested.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
