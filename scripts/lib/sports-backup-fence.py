"""Fence four disposable writer proxies around stopped native baseline capture."""
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
LABEL = 'io.project-atlas.backup-fence-drill'
ROLES = ('api', 'sports-controller', 'notifications-worker', 'sports-writer')
IMAGE = 'sha256:ecec625df0a029cddecf72fcb86d0d2eb9c16ce14f9377b1ddc0954bba4e2ec7'
WRITER = r'''
import os,signal,sqlite3,time
os.umask(0o077)
running=True
def stop(*args):
 global running
 running=False
signal.signal(signal.SIGTERM,stop)
c=sqlite3.connect('/app/data/state.db',timeout=2)
c.execute('PRAGMA journal_mode=DELETE')
c.execute('CREATE TABLE IF NOT EXISTS counter(id INTEGER PRIMARY KEY CHECK(id=1),value INTEGER NOT NULL)')
c.execute('INSERT OR IGNORE INTO counter VALUES(1,0)');c.commit()
while running:
 c.execute('UPDATE counter SET value=value+1 WHERE id=1');c.commit();time.sleep(.05)
c.close()
'''
READ = "import sqlite3;c=sqlite3.connect('file:/app/data/state.db?mode=ro',uri=True,timeout=2);print(c.execute('SELECT value FROM counter WHERE id=1').fetchone()[0]);c.close()"
SHELL = r'''
set -euo pipefail
source "$RESTORE_COMMAND"
docker() { "$DOCKER" "$@"; }
atlas_restore_writer_containers() { printf '%s\n' "$WRITERS"; }
atlas_execution_exclusion_acquire capture_fd || exit 1
: > "$PRIVATE_ROOT/maintenance"
printf '%s\n' capture-rehearsal > "$PRIVATE_ROOT/owner"
atlas_restore_require_writers_running || exit 1
atlas_restore_stop_writers || exit 1
printf '%s\n' STOPPED
IFS= read -r -t 900 decision || exit 1
[[ "$decision" == resume ]] || exit 1
# This is the real post-backup four-writer recheck, before restart/release.
atlas_restore_require_writers_quiesced || exit 1
atlas_restore_start_writers || exit 1
atlas_restore_wait_for_writers || exit 1
printf '%s\n' RESUMED
IFS= read -r -t 60 decision || exit 1
[[ "$decision" == release ]] || exit 1
rm -- "$PRIVATE_ROOT/maintenance" "$PRIVATE_ROOT/owner"
atlas_execution_exclusion_release "$capture_fd" || exit 1
printf '%s\n' RELEASED
'''


def require(value):
    if not value: raise ValueError('Isolated backup fence held')


def counter_file(path):
    """Never accept image-populated files or SQLite sidecars as a cold counter set."""
    require(path.is_dir() and not path.is_symlink()
            and {entry.name for entry in path.iterdir()} == {'state.db'})
    result = path/'state.db'
    require(result.is_file() and not result.is_symlink() and result.stat().st_nlink == 1)
    return result


def controller(root, identifiers, capture, stopped, resumed, *, docker_executable=None):
    """Real shell stop/recheck/reverse-start/wait, with a private capture callback."""
    root = Path(root)
    require(root.parent == Path('/tmp') and root.name.startswith('atlas-backup-fence.')
            and root.is_dir() and not root.is_symlink()
            and root.stat().st_uid == os.geteuid() and root.stat().st_mode & 0o777 == 0o700
            and not any(root.iterdir()))
    require(len(identifiers) == 4 and len(set(identifiers)) == 4
            and all(re.fullmatch('[0-9a-f]{64}', item) for item in identifiers))
    executable = docker_executable or shutil.which('docker')
    require(executable and Path(executable).is_absolute())
    env = {'PATH': '/usr/bin:/bin', 'DOCKER': str(executable), 'PRIVATE_ROOT': str(root),
           'WRITERS': '\n'.join(identifiers), 'ATLAS_RUNTIME_CONFIG_DIR': str(root),
           'RESTORE_COMMAND': str(ROOT/'scripts/commands/restore.sh'),
           'ATLAS_RESTORE_WRITER_TIMEOUT_SECONDS': '15'}
    process = subprocess.Popen(['bash', '-c', SHELL], env=env, cwd=root,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0, start_new_session=True)
    def token(expected, timeout=180):
        require(select.select([process.stdout], [], [], timeout)[0])
        require(process.stdout.readline(65) == expected+b'\n')
    def private_held():
        require((root/'maintenance').is_file()
                and (root/'owner').read_text() == 'capture-rehearsal\n')
    try:
        token(b'STOPPED'); private_held()
        stopped(); capture(); stopped(); private_held()
        process.stdin.write(b'resume\n'); process.stdin.flush()
        token(b'RESUMED'); private_held(); resumed()
        process.stdin.write(b'release\n'); process.stdin.flush()
        token(b'RELEASED', 10)
        require(process.wait(timeout=10) == 0)
        require(not (root/'maintenance').exists() and not (root/'owner').exists())
    except BaseException:
        if process.poll() is None:
            try: process.stdin.write(b'hold\n'); process.stdin.flush()
            except OSError: pass
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
        # Held evidence is observed before fixture cleanup by the caller.
        require((root/'maintenance').is_file() and (root/'owner').is_file())
        raise
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
        process.stdin.close(); process.stdout.close()


def capture(native, baseline, capture_baseline):
    """Create only labelled counter proxies, never the four production services."""
    require(os.geteuid() == 0 and os.getegid() == 0)
    job = uuid.uuid4().hex; rows = []; captured = []; saved = []; before = []; source_hashes = []
    def docker(*args):
        result = subprocess.run(['docker', *args], capture_output=True, timeout=60)
        require(result.returncode == 0 and len(result.stdout) < 1_000_000)
        return result.stdout.decode().strip()
    def inspect(identifier): return json.loads(docker('inspect', identifier))[0]
    def attest(row, running=None):
        item = inspect(row['id'])
        require(item['Id'] == row['id'] and item['Name'] == '/'+row['name']
                and item['Image'] == IMAGE and item['Config']['Labels'].get(LABEL) == job
                and item['Config']['User'] == '0:0'
                and item['Config']['Entrypoint'] == ['python']
                and item['Config']['Cmd'] == ['-B', '-c', WRITER]
                and item['HostConfig']['NetworkMode'] == 'none'
                and item['HostConfig']['ReadonlyRootfs'] and not item['HostConfig']['Privileged']
                and item['HostConfig']['RestartPolicy']['Name'] == 'no'
                and not item['HostConfig']['PortBindings'])
        mounts = [mount for mount in item['Mounts'] if mount['Type'] != 'tmpfs']
        require(len(mounts) == 1 and mounts[0]['Type'] == 'volume'
                and mounts[0]['Name'] == row['volume'] and mounts[0]['Destination'] == '/app/data'
                and mounts[0]['RW'])
        requested = item['HostConfig']['Mounts']
        require(len(requested) == 1 and requested[0]['Type'] == 'volume'
                and requested[0]['Source'] == row['volume'] and requested[0]['Target'] == '/app/data'
                and not requested[0].get('ReadOnly', False)
                and requested[0].get('VolumeOptions', {}).get('NoCopy') is True)
        if running is not None: require(item['State']['Running'] is running)
        return item
    def source(row):
        volume = json.loads(docker('volume', 'inspect', row['volume']))[0]
        require(volume['Name'] == row['volume'] and volume['Driver'] == 'local'
                and volume['Labels'].get(LABEL) == job and not volume.get('Options'))
        base = Path(docker('info', '--format', '{{.DockerRootDir}}'))
        path = base/'volumes'/row['volume']/'_data'
        require(path.is_absolute() and path.resolve() == path and path.is_dir()
                and str(path) == volume['Mountpoint'])
        refs = docker('ps', '-aq', '--no-trunc', '--filter', 'volume='+row['volume']).splitlines()
        require(refs == [row['id']])
        return path
    def value(path):
        require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1)
        connection = sqlite3.connect('file:'+str(path)+'?mode=ro&immutable=1', uri=True)
        try:
            require(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)])
            result = connection.execute('SELECT value FROM counter WHERE id=1').fetchall()
            require(len(result) == 1 and type(result[0][0]) is int and result[0][0] > 0)
            return result[0][0]
        finally: connection.close()
    try:
        for role in ROLES:
            name = 'atlas-backup-fence-'+role+'-'+job; volume = name+'-data'
            row = {'name': name, 'volume': volume, 'id': None}; rows.append(row)
            docker('volume', 'create', '--driver', 'local', '--label', LABEL+'='+job, volume)
            identifier = docker('create', '--name', name, '--label', LABEL+'='+job,
                '--user', '0:0', '--network', 'none', '--restart', 'no', '--read-only', '--no-healthcheck',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--log-driver', 'none',
                '--memory', '128m', '--cpus', '0.25', '--pids-limit', '32',
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m',
                '--mount', 'type=volume,source='+volume+',target=/app/data,volume-nocopy',
                '--entrypoint', 'python', IMAGE, '-B', '-c', WRITER)
            require(re.fullmatch('[0-9a-f]{64}', identifier)); row['id'] = identifier
            docker('start', identifier)
            deadline = time.monotonic()+20
            while True:
                attest(row, True)
                try:
                    require(int(docker('exec', identifier, 'python', '-B', '-c', READ)) > 0); break
                except ValueError:
                    require(time.monotonic() < deadline); time.sleep(.1)
        print('FOUR_WRITER_PROXIES_RUNNING=PASS', flush=True)
        with tempfile.TemporaryDirectory(prefix='atlas-backup-fence.', dir='/tmp') as control, \
             tempfile.TemporaryDirectory(prefix='atlas-backup-counter-copy.', dir='/tmp') as copies:
            def stopped():
                values = []; hashes = []
                for row in rows:
                    state = attest(row, False)['State']
                    require(state['Status'] == 'exited' and state['ExitCode'] in (0, 143)
                            and not state['OOMKilled'] and state['Pid'] == 0)
                    path = source(row)
                    database = counter_file(path)
                    values.append(value(database)); hashes.append(native.pub.digest(database))
                if before: require(values == before and hashes == source_hashes)
                else: before.extend(values); source_hashes.extend(hashes)
            def checkpoint():
                for row in rows:
                    path = source(row)/'state.db'; target = Path(copies)/row['name']
                    native.copy_tree(path, target, False, (0, 0), (0, 0))
                    saved.append((target, native.pub.digest(target)))
                capture_baseline()
                captured.append(native.pub.digest(baseline, True))
                require([value(path) for path, _ in saved] == before)
                require([digest for _, digest in saved] == source_hashes)
                print('FOUR_WRITERS_QUIESCED_DURING_NATIVE_CAPTURE=PASS', flush=True)
            def resumed():
                for index, row in enumerate(rows):
                    attest(row, True); deadline = time.monotonic()+10
                    while int(docker('exec', row['id'], 'python', '-B', '-c', READ)) <= before[index]:
                        require(time.monotonic() < deadline); time.sleep(.1)
                require(all(native.pub.digest(path) == digest for path, digest in saved))
                require([value(path) for path, _ in saved] == before)
                require(captured == [native.pub.digest(baseline, True)])
                print('FOUR_WRITERS_RESUMED_CAPTURE_UNCHANGED=PASS', flush=True)
            controller(control, [row['id'] for row in rows], checkpoint, stopped, resumed)
        print(json.dumps({'version': 1, 'scope': 'four-disposable-counter-writer-native-capture',
            'real_shell_quiescence_helpers': True, 'counter_snapshots_unchanged': True,
            'native_capture_while_four_stopped': True, 'writers_resumed': True,
            'production_writer_services_tested': False, 'production_state_access': False,
            'live_restore_enabled': False}, sort_keys=True))
    finally:
        failures = []
        for row in reversed(rows):
            try:
                if row['id'] is not None:
                    attest(row)
                    if inspect(row['id'])['State']['Running']: docker('stop', '--time', '10', row['id'])
                    state = attest(row, False)['State']
                    require(state['ExitCode'] in (0, 143) and not state['OOMKilled'])
                    docker('rm', row['id'])
                volume = json.loads(docker('volume', 'inspect', row['volume']))[0]
                require(volume['Labels'].get(LABEL) == job and volume['Driver'] == 'local')
                require(not docker('ps', '-aq', '--filter', 'volume='+row['volume']))
                docker('volume', 'rm', row['volume'])
            except Exception: failures.append(row['name'])
        require(not failures)
