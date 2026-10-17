"""Actual four application processes on private data; no production service control."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]
LABEL = 'io.project-atlas.four-service-lifecycle-drill'
ROLES = ('api', 'sports-controller', 'notifications-worker', 'sports-writer')
IMAGES = {
    'api': 'sha256:1066e04d3c6828452ff90dc4f94b9156e46816cfba14cecccbe007c997376afa',
    'sports-controller': 'sha256:fb53d5a67038dd0aa48c1e0f66d8833174e7b51ce35fd12f656f4c695183d9ba',
    'notifications-worker': 'sha256:24bb16068637adf366875fae485e69d234623b708464c32ab3611d7b03ecffdc',
    'sports-writer': 'sha256:a352324695a2bff4b838313a8fd6f81445384f641ce7a1e9f016a8d00a55b0dd',
}
COMMANDS = {
    'api': ['uvicorn', 'atlas_api.main:app', '--host', '0.0.0.0', '--port', '8000'],
    'sports-controller': ['python3', '/opt/project-atlas/modules/sports/src/worker.py'],
    'notifications-worker': ['/opt/project-atlas/modules/notifications/scripts/worker.sh'],
    'sports-writer': ['python3', '/srv/sports/private_api.py'],
}
WORKDIRS = {'api': '/srv/apps/api', 'sports-controller': '/opt/project-atlas',
            'notifications-worker': '/opt/project-atlas', 'sports-writer': '/srv/sports'}
TOKEN = 'atlas-four-service-fixture-only'
CONFIG = 'ATLAS_MEDIA_ROOT=/media\nATLAS_DOWNLOADS_ROOT=/downloads\nATLAS_CLEANUP_EXECUTION_ENABLED=false\n'
SOURCE_GROUPS = ('atlas', 'apps/api/atlas_api', 'modules/sports/src', 'modules/notifications/src')
EVENT_ROOT = '/mnt/storage/configs/atlas/runtime'
NOTIFY_ROOT = '/mnt/storage/configs/atlas/notifications'
SPORTS_ROOT = '/mnt/storage/configs/sportyfin'


def require(value):
    if not value:
        raise ValueError('Isolated four-service lifecycle held')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_files():
    files = []
    for prefix in SOURCE_GROUPS:
        files.extend(p for p in (ROOT/prefix).rglob('*.py') if '__pycache__' not in p.parts)
    files.extend((ROOT/'scripts/lib').glob('*.sh'))
    files.append(ROOT/'modules/notifications/scripts/worker.sh')
    return sorted(files)


def tree(path):
    """Bounded stable file records, including modes and numeric owners."""
    rows = {}; total = 0
    for item in [path, *sorted(path.rglob('*'))] if path.is_dir() else [path]:
        require(not item.is_symlink())
        info = item.lstat(); directory = stat.S_ISDIR(info.st_mode)
        require(directory or stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        require(len(rows) < 10000)
        key = '.' if item == path else item.relative_to(path).as_posix()
        row = [stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid]
        if directory:
            rows[key] = ['directory', *row]; continue
        total += info.st_size; require(total <= 64*1024*1024)
        with os.fdopen(os.open(item, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
            opened = os.fstat(stream.fileno()); raw = stream.read(info.st_size+1)
            after = os.fstat(stream.fileno())
        require(len(raw) == info.st_size and (opened.st_ino, opened.st_dev, opened.st_size,
                opened.st_mtime_ns, opened.st_ctime_ns) == (info.st_ino, info.st_dev,
                info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                and (after.st_mtime_ns, after.st_ctime_ns) == (info.st_mtime_ns, info.st_ctime_ns))
        rows[key] = ['file', *row, hashlib.sha256(raw).hexdigest()]
    return rows


def stage(native, root):
    source = root/'source'; source.mkdir(mode=0o755)
    for path in source_files():
        relative = path.relative_to(ROOT)
        require(path.is_file() and not path.is_symlink())
        target = source/relative; target.parent.mkdir(parents=True, exist_ok=True)
        native.copy_tree(path, target, target_owner=(os.geteuid(), os.getegid()))
        target.chmod(0o755 if path.suffix == '.sh' or relative.as_posix() ==
            'modules/notifications/src/processor.py' else 0o644)
    for path in source.rglob('*'):
        if path.is_dir(): path.chmod(0o755)
    config = source/'config'; config.mkdir(mode=0o755)
    (config/'atlas.conf').write_text(CONFIG); (config/'atlas.conf').chmod(0o644)
    writer = load('four_service_writer', 'scripts/lib/sports-archive-writer.py')
    writer.stage_source(native, root/'writer-source')
    return source


def write(path, raw, uid=1000, gid=1000, mode=0o600):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as stream:
        stream.write(raw); stream.flush(); os.fchown(stream.fileno(), uid, gid); os.fsync(stream.fileno())


def event(number):
    return (json.dumps({'schema': 2, 'id': 'evt-four-service-'+str(number),
        'timestamp': '2026-10-17T12:00:00Z', 'source': 'isolated-lifecycle-fixture',
        'event': 'request.available', 'payload': {'fixture': number}}, separators=(',', ':'))+'\n').encode()


def prepare_data(root):
    data = root/'data'; data.mkdir(mode=0o700)
    for name, uid, gid in [('api', 999, 999), ('controller', 1000, 1000),
            ('notifications', 1000, 1000), ('writer', 1000, 1000)]:
        path = data/name; path.mkdir(mode=0o700); os.chown(path, uid, gid)
    write(data/'events.jsonl', event(1), 1000, 20000, 0o660)
    write(data/'module-notifications.cursor', b'0\n')
    write(data/'module-notifications.filter', b'*\n', 1000, 20000, 0o640)
    for name in ('state', 'config'):
        path = data/'controller'/name; path.mkdir(mode=0o700); os.chown(path, 1000, 1000)
    return data


def contract(role, root):
    require(role in ROLES)
    source = root/'source'; data = root/'data'
    mounts = []
    def mount(path, destination, writable=False):
        mounts.append((str(path), destination, writable))
    env = {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'}
    if role == 'api':
        mount(source/'atlas', '/srv/atlas')
        mount(source/'apps/api/atlas_api', '/srv/apps/api/atlas_api')
        mount(data/'api', '/fixture-api', True)
        mount(data/'events.jsonl', EVENT_ROOT+'/events.jsonl', True)
        env.update(ATLAS_JWT_SECRET='synthetic-four-service-jwt-secret-never-production',
            ATLAS_REQUESTS_DIR='/fixture-api/requests', PYTHONPATH='/srv:/srv/apps/api')
    elif role == 'sports-controller':
        mount(source, '/opt/project-atlas')
        mount(data/'controller', SPORTS_ROOT, True)
        mount(data/'events.jsonl', EVENT_ROOT+'/events.jsonl', True)
        env.update(PYTHONPATH='/opt/project-atlas:/opt/project-atlas/modules/sports/src',
            SPORTS_CONTROLLER_INTERVAL_SECONDS='1', SPORTS_THESPORTSDB_API_KEY='',
            SPORTS_STATE_DIR=SPORTS_ROOT+'/state', SPORTS_MAINTENANCE_ENABLED='false')
    elif role == 'notifications-worker':
        mount(source, '/opt/project-atlas')
        mount(data/'notifications', NOTIFY_ROOT, True)
        mount(data/'events.jsonl', EVENT_ROOT+'/events.jsonl')
        mount(data/'module-notifications.cursor', EVENT_ROOT+'/subscribers/module-notifications.cursor', True)
        mount(data/'module-notifications.filter', EVENT_ROOT+'/subscribers/module-notifications.filter')
        env.update(ATLAS_NOTIFICATIONS_INTERVAL='1', ATLAS_NOTIFICATIONS_WEBHOOK_URL='')
        for route in ('SYSTEM', 'MOVIES', 'TV', 'ANIME_MOVIES', 'ANIME_TV', 'SPORTS'):
            env['ATLAS_NOTIFICATIONS_DISCORD_'+route+'_WEBHOOK'] = ''
    else:
        mount(root/'writer-source', '/srv/sports')
        mount(data/'writer', '/state', True)
        env.update(ATLAS_SPORTS_WRITER_TOKEN=TOKEN)
        writer = load('four_service_writer_contract', 'scripts/lib/sports-archive-writer.py')
        for key, value in writer.REGISTRIES.items(): env[key] = '/state/'+value
    return mounts, env


def arguments(role, name, job, root):
    require(re.fullmatch('atlas-four-service-'+re.escape(role)+'-[0-9a-f]{32}', name))
    require(re.fullmatch('[0-9a-f]{32}', job) and name.endswith(job))
    require(root.parent == Path('/tmp') and root.name.startswith('atlas-four-service.'))
    mounts, env = contract(role, root)
    args = ['run', '-d', '--pull=never', '--name', name, '--label', LABEL+'='+job,
        '--user='+('999:999' if role == 'api' else '1000:1000'), '--network=none',
        '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
        '--restart=no', '--no-healthcheck', '--log-driver=none', '--memory=256m',
        '--cpus=.50', '--pids-limit=96', '--tmpfs=/tmp:rw,noexec,nosuid,size=16777216,mode=1777']
    for group in (['20000', '20001'] if role == 'api' else ['20000'] if role != 'sports-writer' else []):
        args += ['--group-add', group]
    for source, destination, writable in mounts:
        require(source.startswith(str(root)+'/') and ',' not in source)
        args += ['--mount', 'type=bind,src='+source+',dst='+destination+('' if writable else ',readonly')]
    for key, value in sorted(env.items()): args += ['--env', key+'='+value]
    return [*args, IMAGES[role]]


def inspect_owned(item, role, name, job, root, identifier):
    config = item['Config']; host = item['HostConfig']
    mounts, env = contract(role, root)
    groups = ['20000', '20001'] if role == 'api' else ['20000'] if role != 'sports-writer' else []
    actual_env = dict(part.split('=', 1) for part in config.get('Env', []) if '=' in part)
    require(item['Id'] == identifier and re.fullmatch('[0-9a-f]{64}', identifier)
        and item['Name'] == '/'+name and name == 'atlas-four-service-'+role+'-'+job
        and config.get('Labels', {}).get(LABEL) == job and item['Image'] == IMAGES[role]
        and config.get('Entrypoint') in (None, []) and config.get('Cmd') == COMMANDS[role]
        and config.get('User') == ('999:999' if role == 'api' else '1000:1000')
        and config.get('WorkingDir') == WORKDIRS[role] and not config.get('Volumes')
        and config.get('StopSignal') in (None, '')
        and all(actual_env.get(key) == value for key, value in env.items())
        and host.get('ReadonlyRootfs') is True and host.get('Privileged') is False
        and host.get('NetworkMode') == 'none' and host.get('PidMode') in ('', None)
        and host.get('IpcMode') == 'private' and not host.get('CapAdd')
        and host.get('CapDrop') == ['ALL'] and host.get('GroupAdd', []) in (groups, None if not groups else groups)
        and 'no-new-privileges:true' in host.get('SecurityOpt', [])
        and not host.get('PortBindings')
        and all(not value for value in (item.get('NetworkSettings', {}).get('Ports') or {}).values())
        and host.get('RestartPolicy', {}).get('Name') == 'no'
        and host.get('LogConfig', {}).get('Type') == 'none'
        and config.get('Healthcheck', {}).get('Test') == ['NONE']
        and host.get('Memory') == 256*1024*1024 and host.get('NanoCpus') == 500000000
        and host.get('PidsLimit') == 96 and host.get('Tmpfs') == {'/tmp': 'rw,noexec,nosuid,size=16777216,mode=1777'}
        and not host.get('Binds') and not host.get('Devices')
        and not host.get('VolumesFrom') and not host.get('Links'))
    actual = [(m.get('Source'), m['Destination'], m['RW']) for m in item['Mounts'] if m['Type'] == 'bind']
    require(len(actual) == len(mounts) and sorted(actual) == sorted(mounts)
        and len(item['Mounts']) == len(mounts)
        and all(m['Type'] == 'bind' and m.get('Propagation') == 'rprivate' for m in item['Mounts']))
    return item


IDENTITY = "import os; assert os.getresuid()==(UID,UID,UID) and os.getresgid()==(UID,UID,UID); assert sorted(os.getgroups())==GROUPS\n"
HTTP = "import urllib.request,json; o=urllib.request.build_opener(urllib.request.ProxyHandler({})); r=o.open('http://127.0.0.1:PORT/PATH',timeout=2); assert r.status==200; assert len(r.read(16385))<=16384\n"


def probe(role, count):
    uid = 999 if role == 'api' else 1000
    groups = [20000, 20001] if role == 'api' else [20000] if role != 'sports-writer' else []
    # Docker may include the primary group in the supplementary group list.
    identity = IDENTITY.replace('UID', str(uid)).replace('==GROUPS', ' in '+repr([groups, sorted([uid, *groups])]))
    if role in ('api', 'sports-writer'):
        port, path = (8000, 'api/v1/health') if role == 'api' else (8003, 'health')
        return identity+HTTP.replace('PORT', str(port)).replace('PATH', path)
    if role == 'sports-controller':
        return identity+"from pathlib import Path; import time; p=Path('"+SPORTS_ROOT+"/state/controller-heartbeat'); assert p.is_file() and time.time()-p.stat().st_mtime<10\n"
    return identity+"from pathlib import Path; import json,time; p=Path('"+NOTIFY_ROOT+"'); assert time.time()-(p/'worker-heartbeat').stat().st_mtime<10; assert Path('"+EVENT_ROOT+"/subscribers/module-notifications.cursor').read_text().strip()=='"+str(count)+"'; rows=[json.loads(line) for line in (p/'logs/notifications.log').read_text().splitlines()]; assert [row['event_id'] for row in rows]==['evt-four-service-'+str(n) for n in range(1,"+str(count+1)+")]\n"


def _capture(native, baseline, capture_baseline):
    """Replace only the capture fence with four actual application runtimes."""
    require(os.geteuid() == 0 and os.getegid() == 0)
    fence = load('four_service_real_shell', 'scripts/lib/sports-backup-fence.py')
    job = uuid.uuid4().hex; rows = []
    def docker(*args, check=True, timeout=60):
        result = subprocess.run(['docker', *args], capture_output=True, timeout=timeout)
        require(len(result.stdout) <= 1_000_000)
        if check: require(result.returncode == 0)
        return result
    def inspect(identifier): return json.loads(docker('inspect', identifier).stdout)[0]
    def observe():
        observations = []
        for role in ROLES:
            row = inspect('atlas-'+role)
            require(row['State']['Running'])
            observations.append([row['Id'], row['Image'], row['State']['Pid'], row['State']['StartedAt'],
                row['RestartCount'], sorted(row['Mounts'], key=lambda value: json.dumps(value, sort_keys=True)),
                row['Config'], row['HostConfig']])
        return observations
    before_production = observe()
    with tempfile.TemporaryDirectory(prefix='atlas-four-service.', dir='/tmp') as temporary:
        root = Path(temporary); root.chmod(0o700)
        stage(native, root); data = prepare_data(root)
        source_before = tree(root/'source'); writer_source_before = tree(root/'writer-source')
        before_heartbeat = None; copied = None; snapshot_shape = None
        def attest(row):
            return inspect_owned(inspect(row['id']), row['role'], row['name'], job, root, row['id'])
        def stopped():
            for row in rows:
                item = attest(row); state = item['State']
                require(not state['Running'] and state['Status'] == 'exited' and state['Pid'] == 0
                    and state['ExitCode'] == 0 and state['OOMKilled'] is False)
        def ready(count):
            for row in rows:
                deadline = time.monotonic()+25
                while True:
                    require(attest(row)['State']['Running'])
                    result = docker('exec', row['id'], 'python3', '-B', '-c', probe(row['role'], count), check=False, timeout=5)
                    if result.returncode == 0: break
                    require(time.monotonic() < deadline); time.sleep(.15)
        def held_capture():
            nonlocal before_heartbeat, copied, snapshot_shape
            stopped()
            before_heartbeat = (data/'controller/state/controller-heartbeat').stat().st_mtime_ns
            initial = tree(data)
            copied = root/'capture'; shutil.copytree(data, copied, copy_function=shutil.copy2)
            # Snapshot copies preserve bytes and modes; archive preparation is NOT
            # claimed here. Existing strict native capture runs under this fence.
            def content(shape): return {key: [value[0], value[1], *value[4:]] for key, value in shape.items()}
            require(content(tree(copied)) == content(initial) and tree(data) == initial)
            snapshot_shape = tree(copied)
            capture_baseline()
            require(tree(data) == initial and tree(copied) == snapshot_shape)
            with (data/'events.jsonl').open('ab') as stream:
                stream.write(event(2)); stream.flush(); os.fsync(stream.fileno())
            require((data/'module-notifications.cursor').read_text().strip() == '1')
            stopped()
            print('ACTUAL_FOUR_SERVICES_STOPPED_NATIVE_CAPTURE_AND_PRIVATE_SNAPSHOT=PASS', flush=True)
        def resumed():
            ready(2)
            deadline = time.monotonic()+5
            while (data/'controller/state/controller-heartbeat').stat().st_mtime_ns == before_heartbeat:
                require(time.monotonic() < deadline); time.sleep(.15)
            require(tree(copied) == snapshot_shape and tree(root/'source') == source_before
                and tree(root/'writer-source') == writer_source_before)
            print('ACTUAL_FOUR_SERVICES_RESTART_READINESS_AND_NOTIFICATION_CURSOR=PASS', flush=True)
        try:
            for role in ROLES:
                image = json.loads(docker('image', 'inspect', IMAGES[role]).stdout)[0]
                require(image['Id'] == IMAGES[role] and image['Config'].get('Entrypoint') in (None, [])
                    and image['Config'].get('Cmd') == COMMANDS[role] and not image['Config'].get('Volumes'))
                name = 'atlas-four-service-'+role+'-'+job
                args = arguments(role, name, job, root)
                # Create before start so the full owned ID is tracked before any
                # application code runs, even if readiness subsequently fails.
                args[0] = 'create'; args.remove('-d')
                identifier = docker(*args).stdout.decode().strip()
                require(re.fullmatch('[0-9a-f]{64}', identifier))
                row = {'id': identifier, 'name': name, 'role': role}; rows.append(row)
                attest(row); docker('start', identifier); attest(row)
            ready(1)
            print('ACTUAL_FOUR_APPLICATION_PROCESSES_READY=PASS', flush=True)
            with tempfile.TemporaryDirectory(prefix='atlas-backup-fence.', dir='/tmp') as control:
                fence.controller(Path(control), [row['id'] for row in rows], held_capture, stopped, resumed)
        finally:
            failures = []
            # Reconcile labelled creates too, including a daemon-created container
            # whose create reply was lost. Every removal still needs full proof.
            owned = docker('ps', '-a', '--filter', 'label='+LABEL+'='+job,
                '--format', '{{.ID}}').stdout.decode().splitlines()
            for identifier in owned:
                try:
                    item = inspect(identifier)
                    role = next(role for role in ROLES
                        if item['Name'] == '/atlas-four-service-'+role+'-'+job)
                    row = {'id': item['Id'], 'name': item['Name'][1:], 'role': role}
                    if all(previous['id'] != row['id'] for previous in rows): rows.append(row)
                except Exception:
                    failures.append('unproved-labelled-container')
            for row in reversed(rows):
                try:
                    item = attest(row)
                    if item['State']['Running']:
                        docker('stop', '--time', '35', row['id'], timeout=45)
                    item = attest(row)
                    clean = (not item['State']['Running'] and item['State']['ExitCode'] == 0
                        and not item['State']['OOMKilled'])
                    docker('rm', row['id'])
                    require(clean)
                except Exception:
                    failures.append('fixture-cleanup-refused')
            remaining = docker('ps', '-a', '--filter', 'label='+LABEL+'='+job, '--format', '{{.ID}}').stdout.strip()
            require(not remaining and not failures)
            require(observe() == before_production)
        require(tree(root/'source') == source_before and tree(root/'writer-source') == writer_source_before)
    print(json.dumps({'version': 1, 'scope': 'actual-four-application-private-capture-fence',
        'default_image_commands': True, 'reviewed_source_overlay': True,
        'api_uid': 999, 'worker_uid': 1000, 'normal_exit_zero': True,
        'native_capture_while_four_stopped': True, 'notifications_cursor_restart': True,
        'production_services_controlled': False, 'external_provider_access': False,
        'full_sixteen_surface_operational_restore': False, 'live_restore_enabled': False}, sort_keys=True), flush=True)


def capture(native, baseline, capture_baseline):
    try:
        return _capture(native, baseline, capture_baseline)
    except Exception as error:
        frames = []
        for frame in traceback.extract_tb(error.__traceback__):
            path = Path(frame.filename)
            if path.is_relative_to(ROOT):
                frames.append({'file': path.relative_to(ROOT).as_posix(),
                    'function': frame.name, 'line': frame.lineno})
        kind = type(error).__name__
        if kind not in {'ValueError', 'RuntimeError', 'PermissionError', 'FileNotFoundError',
                'TimeoutExpired', 'CalledProcessError', 'OSError', 'AssertionError'}:
            kind = 'Exception'
        print('ACTUAL_FOUR_SERVICE_FAILURE=' + json.dumps({
            'exception_type': kind, 'frames': frames[-10:]}, sort_keys=True), flush=True)
        raise
