"""Normal pinned AIO startup and persistence after strict synthetic PG restore."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
import uuid

HEAD = 'bfa7c8a0bdb732b5ba01993955784c899fffc904'
LABEL = 'io.project-atlas.dispatcharr-recovery-drill'
ADAPTER_SHA = '34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc'
HELPER_SHA = '042791e83a2c15a58f9da660876430dfe54926fc701bcf1b70d744335692b27a'


def require(condition):
    if not condition: raise RuntimeError('Synthetic Dispatcharr drill contract failed')


def utilities(root):
    path = root / 'scripts/diagnostics/sports-cold-copy-drill.py'
    require(path.is_file() and not path.is_symlink())
    require(hashlib.sha256(path.read_bytes()).hexdigest() == '1d714b2d4be23d3234045836b1c31e1d92826fbcc03fa08411d184e7f7191ecb')
    spec = importlib.util.spec_from_file_location('dispatcharr_drill_utilities', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.LABEL = LABEL
    return module


INIT = "import os\nfrom pathlib import Path\np=Path('/target');assert p.is_dir() and not p.is_symlink() and not any(p.iterdir())\np.chmod(0o700);os.chown(p,1000,1000)\nprint('volume-initialized')\n"


def helper_arguments(base, name, source, target, identifier, bootstrap, mode, digest=None):
    require(mode in {'prepare', 'verify'})
    require((mode == 'prepare' and digest is None) or
            (mode == 'verify' and isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest) is not None))
    return ['docker', 'create', '-i', *base.container_options(name, identifier),
        '--read-only', '--user=1000:1000', '--cap-drop=ALL',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m,mode=1777',
        '--mount', 'type=volume,source=' + source + ',destination=/source,readonly,volume-nocopy',
        '--mount', 'type=volume,source=' + target + ',destination=/target,'
            + ('readonly,' if mode == 'verify' else '') + 'volume-nocopy',
        '--env', 'ATLAS_DISPATCHARR_DRILL=1', '--entrypoint', 'python3', base.IMAGE,
        '-I', '-B', '-c', bootstrap, mode, *([digest] if digest else [])]


def initialize_arguments(base, name, target, identifier):
    return ['docker', 'create', *base.container_options(name, identifier), '--read-only',
        '--user=0:0', '--cap-drop=ALL', '--cap-add=CHOWN', '--mount',
        'type=volume,source=' + target + ',destination=/target,volume-nocopy',
        '--entrypoint', 'python3', base.IMAGE, '-I', '-B', '-c', INIT]


def inspect_helper(base, name, source, target, identifier, mode):
    require(mode in {'initialize', 'prepare', 'verify'})
    item = base.inspect(name); config = item['Config']; host = item['HostConfig']
    require(item['Image'] == base.IMAGE and config.get('Labels', {}).get(LABEL) == identifier
            and config['User'] == ('0:0' if mode == 'initialize' else '1000:1000')
            and config['Entrypoint'] == ['python3'] and host['ReadonlyRootfs'] is True
            and host['NetworkMode'] == 'none' and not host.get('Privileged') and not host.get('PortBindings'))
    mounts = [m for m in item['Mounts'] if m['Type'] != 'tmpfs']
    expected = {'/target': (target, mode != 'verify')}
    if mode != 'initialize': expected['/source'] = (source, False)
    require(len(mounts) == len(expected))
    require({m['Destination'] for m in mounts} == set(expected))
    for m in mounts:
        require(m['Type'] == 'volume' and (m['Name'], m['RW']) == expected[m['Destination']])
    return item


def exited(item):
    state = item['State']
    require(state['Status'] == 'exited' and not state['Running'] and state['Pid'] == 0
            and not state['OOMKilled'] and state['ExitCode'] == 0)


HTTP_READY = r'''
import http.client
c=http.client.HTTPConnection('127.0.0.1',9191,timeout=3)
c.request('GET','/');r=c.getresponse();raw=r.read(65537)
assert r.status==200 and 0<len(raw)<=65536
assert 'text/html' in r.getheader('Content-Type','').lower()
c.close();print('http-ready')
'''


def wait_ready(base, app, volume, identifier):
    deadline = time.monotonic() + 180; next_update = 0
    while time.monotonic() < deadline:
        require(base.owned_container(app, identifier, volume, '/data', False)['State']['Running'])
        result = base.invoke('docker', 'exec', '--user', '1000:1000', app, 'python3', '-B', '-c',
                             base.READY, timeout=12, check=False)
        if result.returncode == 0 and result.stdout.strip() == b'ready':
            http = base.invoke('docker', 'exec', app, 'python3', '-B', '-c', HTTP_READY, timeout=8, check=False)
            if http.returncode == 0 and http.stdout.strip() == b'http-ready': return
        if time.monotonic() >= next_update:
            print('SYNTHETIC_DISPATCHARR_STARTUP=pending', flush=True); next_update = time.monotonic() + 20
        time.sleep(2)
    raise RuntimeError('Dispatcharr readiness deadline')


def stop(base, app, volume, identifier):
    base.owned_container(app, identifier, volume, '/data', False)
    base.docker('exec', '--user', '1000:1000', app, '/usr/lib/postgresql/17/bin/pg_ctl',
                '-D', '/data/db', '-m', 'fast', '-w', '-t', '20', 'stop', timeout=30)
    base.docker('stop', '--time', '35', app, timeout=45)
    state = base.owned_container(app, identifier, volume, '/data', False)['State']
    require(state['Status'] == 'exited' and not state['Running'] and state['Pid'] == 0
            and not state['OOMKilled'] and state['ExitCode'] in (0, 143))


def marker_code(marker, change=False):
    require(marker in {'snapshot', 'persisted-after-restore'})
    query = "SELECT marker FROM atlas_cold_copy_probe ORDER BY id"
    if change: query = "UPDATE atlas_cold_copy_probe SET marker='persisted-after-restore'; " + query
    return "import subprocess\nb=['/usr/lib/postgresql/17/bin/psql','-XAt','-h','/var/run/postgresql','-U','dispatch','-d','atlas_cold_drill','-v','ON_ERROR_STOP=1']\nr=subprocess.run(b+['-c'," + repr(query) + "],capture_output=True,timeout=10)\nassert r.returncode==0 and r.stdout.splitlines()[-1:]==[" + repr(marker.encode()) + "]\nr=subprocess.run(b+['-c',\"SELECT to_regclass('public.atlas_post_dump_stale') IS NULL\"],capture_output=True,timeout=10)\nassert r.returncode==0 and r.stdout.strip()==b't'\nprint('marker-valid')\n"


def payload(root):
    parts = {}
    for name, relative, digest in (('adapter', 'scripts/lib/sports-postgres-prepare.py', ADAPTER_SHA),
                                   ('helper', 'scripts/lib/sports-dispatcharr-recovery-drill.py', HELPER_SHA)):
        path = root / relative; require(path.is_file() and not path.is_symlink())
        raw = path.read_bytes(); require(hashlib.sha256(raw).hexdigest() == digest)
        parts[name] = raw.decode()
    bootstrap = ("import hashlib,json,sys,types\nr=sys.stdin.buffer.read(1048577)\nassert len(r)<=1048576\np=json.loads(r)\nassert set(p)=={'adapter','helper'}\n"
        + "assert hashlib.sha256(p['adapter'].encode()).hexdigest()==" + repr(ADAPTER_SHA) + "\n"
        + "assert hashlib.sha256(p['helper'].encode()).hexdigest()==" + repr(HELPER_SHA) + "\n"
        + "m=types.ModuleType('atlas_pg_prepare');sys.modules['atlas_pg_prepare']=m\nexec(compile(p['adapter'],'<adapter>','exec'),m.__dict__)\nexec(compile(p['helper'],'<fixture>','exec'),{'__name__':'__main__'})\n")
    return json.dumps(parts).encode(), bootstrap


def validate_receipt(receipt, mode, previous=None):
    common = {'version': 1, 'scope': 'synthetic-dispatcharr-only', 'mode': mode,
              'cold_source_unchanged': True, 'restored_cluster_stopped': True,
              'production_state_access': False, 'live_restore_enabled': False}
    require(set(receipt) == set(common) | {'source_sha256', 'dump_sha256'})
    require(all(type(receipt[k]) is type(v) and receipt[k] == v for k, v in common.items()))
    for key in ('source_sha256', 'dump_sha256'):
        require(isinstance(receipt[key], str) and re.fullmatch('[a-f0-9]{64}', receipt[key]) is not None)
        if previous is not None: require(receipt[key] == previous[key])


def observation(base):
    # Docker mount arrays are unordered. Preserve every field and duplicate;
    # canonicalize list order only, so actual mount changes still fail closed.
    return [(name, image, pid, started, sorted(mounts,
             key=lambda mount: json.dumps(mount, sort_keys=True)))
            for name, image, pid, started, mounts in base.observation()]


def run():
    root = Path(__file__).resolve().parents[2]; base = utilities(root)
    require(base.invoke('git', '-C', str(root), 'rev-parse', 'HEAD').stdout.decode().strip() == HEAD)
    pointer = Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink())
    deployment = pointer.read_bytes(); require(deployment.decode().strip() == base.DEPLOYMENT)
    before = observation(base)
    image = json.loads(base.docker('image', 'inspect', base.IMAGE))[0]
    require(image['Id'] == base.IMAGE and image['Config']['Entrypoint'] == ['/app/docker/entrypoint.sh']
            and not image['Config'].get('Cmd') and not image['Config'].get('Volumes'))
    data, bootstrap = payload(root)
    identifier = uuid.uuid4().hex
    source = 'atlas-dispatch-drill-source-' + identifier
    target = 'atlas-dispatch-drill-target-' + identifier
    original = 'atlas-dispatch-drill-original-' + identifier
    restored = 'atlas-dispatch-drill-restored-' + identifier
    containers = []; phase = 'create-volumes'
    def helper_run(mode, previous=None):
        # Both applications must be stopped before either data volume is read.
        for app, volume in ((original, source), (restored, target)):
            if app in containers:
                s = base.owned_container(app, identifier, volume, '/data', False)['State']
                require(s['Status'] == 'exited' and not s['Running'] and s['Pid'] == 0
                        and not s['OOMKilled'] and s['ExitCode'] in (0, 143))
        name = 'atlas-dispatch-drill-' + mode + '-' + identifier; containers.append(name)
        base.invoke(*helper_arguments(base, name, source, target, identifier, bootstrap, mode,
                                     previous['source_sha256'] if previous else None))
        inspect_helper(base, name, source, target, identifier, mode)
        result = base.invoke('docker', 'start', '--attach', '--interactive', name, input=data, timeout=180, check=False)
        if result.returncode:
            match = re.search(rb'DISPATCHARR_FIXTURE_HELPER=FAIL category=([a-z-]{1,80})', result.stderr)
            if match: print(match.group().decode(), file=sys.stderr)
        require(result.returncode == 0 and len(result.stdout) <= 4096)
        receipt = json.loads(result.stdout); validate_receipt(receipt, mode, previous)
        exited(inspect_helper(base, name, source, target, identifier, mode))
        return receipt
    try:
        for volume in (source, target):
            base.docker('volume', 'create', '--driver', 'local', '--label', LABEL + '=' + identifier, volume)
        phase = 'initial-application'; containers.append(original)
        base.invoke(*base.app_arguments(original, source, identifier))
        base.owned_container(original, identifier, source, '/data', False)
        base.docker('start', original); wait_ready(base, original, source, identifier)
        require(base.docker('exec', '--user', '1000:1000', original, 'python3', '-B', '-c', base.SNAPSHOT, timeout=65) == 'snapshot-captured')
        stale = "import subprocess\nr=subprocess.run(['/usr/lib/postgresql/17/bin/psql','-XAt','-h','/var/run/postgresql','-U','dispatch','-d','atlas_cold_drill','-v','ON_ERROR_STOP=1','-c','CREATE TABLE atlas_post_dump_stale(id integer)'],capture_output=True,timeout=10)\nassert r.returncode==0\nprint('stale-created')\n"
        require(base.docker('exec', '--user', '1000:1000', original, 'python3', '-B', '-c', stale) == 'stale-created')
        stop(base, original, source, identifier)
        phase = 'initialize-empty-target'
        initializer = 'atlas-dispatch-drill-initialize-' + identifier; containers.append(initializer)
        base.invoke(*initialize_arguments(base, initializer, target, identifier))
        inspect_helper(base, initializer, source, target, identifier, 'initialize')
        require(base.docker('start', '--attach', initializer) == 'volume-initialized')
        exited(inspect_helper(base, initializer, source, target, identifier, 'initialize'))
        phase = 'strict-native-preparation'; first = helper_run('prepare')
        print('SYNTHETIC_DISPATCHARR_PREPARED=PASS', flush=True)
        phase = 'restored-application-start'; containers.append(restored)
        base.invoke(*base.app_arguments(restored, target, identifier))
        base.owned_container(restored, identifier, target, '/data', False)
        base.docker('start', restored); wait_ready(base, restored, target, identifier)
        require(base.docker('exec', '--user', '1000:1000', restored, 'python3', '-B', '-c', marker_code('snapshot')) == 'marker-valid')
        print('SYNTHETIC_DISPATCHARR_RESTORED_START=PASS', flush=True)
        require(base.docker('exec', '--user', '1000:1000', restored, 'python3', '-B', '-c', marker_code('persisted-after-restore', True)) == 'marker-valid')
        stop(base, restored, target, identifier)
        phase = 'restored-persistence-restart'
        base.docker('start', restored); wait_ready(base, restored, target, identifier)
        require(base.docker('exec', '--user', '1000:1000', restored, 'python3', '-B', '-c', marker_code('persisted-after-restore')) == 'marker-valid')
        stop(base, restored, target, identifier)
        print('SYNTHETIC_DISPATCHARR_PERSISTENCE_RESTART=PASS', flush=True)
        phase = 'final-cold-verification'; helper_run('verify', first)
        print('SYNTHETIC_DISPATCHARR_COLD_VERIFICATION=PASS', flush=True)
    except Exception:
        print('DISPATCHARR_RECOVERY_DRILL=FAIL phase=' + phase, file=sys.stderr); raise
    finally:
        try:
            try: base.cleanup(containers, source, identifier)
            finally: base.cleanup((), target, identifier)
        finally: require(pointer.read_bytes() == deployment and observation(base) == before)
    print(json.dumps({'version': 1, 'scope': 'synthetic-dispatcharr-recovery',
        'strict_native_preparation': True, 'restored_application_start': True,
        'restored_persistence_restart': True, 'stale_object_absent': True,
        'cold_source_unchanged': True, 'restored_cluster_stopped': True,
        'production_state_access': False, 'live_restore_enabled': False}, sort_keys=True))
    print('SYNTHETIC_DISPATCHARR_RECOVERY_DRILL=PASS')
    print('STATE=synthetic-Dispatcharr-restart-only-production-unchanged')


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_DISPATCHARR_RECOVERY_DRILL=FAIL; no production restore requested.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
