"""Private adapters for the held-completion shell restore-abort controller.

This module is a rehearsal adapter, never a production restore API.
"""
import importlib.util
import json
import os
from pathlib import Path
import signal
import select
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
ORDER = ('held', 'stop', 'revert', 'validate', 'start', 'ready',
         'runtime-held', 'retain', 'runtime-held-again', 'release')
CLIENT = """import os,sys,select
os.write(int(sys.argv[1]),(sys.argv[3]+'\\n').encode())
assert select.select([int(sys.argv[2])],[],[],900)[0]
assert os.read(int(sys.argv[2]),16)==b'OK\\n'
"""
SHELL = r'''
set -euo pipefail
source "$RESTORE_COMMAND"
rpc() { "$PYTHON" -B -c "$CLIENT" "$REQUEST_FD" "$RESPONSE_FD" "$1" 2>/dev/null; }
# All host/service boundaries are private fixture adapters. The abort controller,
# its held-failure branches and shared execution-exclusion functions are real.
atlas_restore_require_held_transaction() {
  [[ "$1" == restore-rehearsal ]] || return 1
  rpc held || return 1
  printf '%s\n' "$TRANSACTION"
}
atlas_restore_stop_writers() { rpc stop; }
atlas_backup_recovery_revert_applied_state() {
  [[ "$1" == "$TRANSACTION" ]] || return 1
  rpc revert
}
atlas_restore_validate_live_consumers() { rpc validate; }
atlas_restore_start_writers() { rpc start; }
atlas_restore_wait_for_writers() { rpc ready; }
runtime_checks=0
atlas_restore_verify_runtime_boundary() {
  [[ -f "$PRIVATE_ROOT/maintenance" ]] || return 1
  runtime_checks=$((runtime_checks+1))
  if [[ "$runtime_checks" == 1 ]]; then rpc runtime-held
  else rpc runtime-held-again; fi
}
atlas_maintenance_transaction_hold() {
  [[ "$1" == restore-rehearsal && "$2" =~ ^[0-9]+$ ]] || return 1
  rpc retain
}
atlas_maintenance_disable() { echo FORBIDDEN_REOPEN >&2; return 99; }
atlas_maintenance_enable() { : > "$PRIVATE_ROOT/maintenance"; }
atlas_deployment_release_lock() {
  [[ "$1" == restore-rehearsal ]] || return 1
  rpc release
}
# The real wrapper acquires exclusion once and owns it through every callback.
if atlas_restore_abort_live restore-rehearsal; then result=0; else result=$?; fi
exit "$result"
'''


def require(value):
    if not value:
        raise ValueError('Private maintenance recovery rehearsal held')


def execute(root, actions, *, fail_at=None):
    """Drive the real abort controller; return private evidence even on failure."""
    root = Path(root)
    require(root.parent == Path('/tmp') and root.name.startswith('atlas-maint-rehearsal.')
            and root.is_dir() and not root.is_symlink()
            and root.stat().st_uid == os.geteuid() and root.stat().st_mode & 0o777 == 0o700)
    require(set(actions) == {'stop', 'revert', 'validate', 'start', 'ready', 'runtime'})
    require(all(callable(value) for value in actions.values()))
    require(fail_at is None or fail_at in ORDER)
    require(not any(root.iterdir()))
    tx = root/'transaction'; tx.mkdir(mode=0o700)
    (tx/'status').write_text('applied-awaiting-verification\n')
    maintenance = root/'maintenance'; maintenance.touch(mode=0o600)
    lock = root/'owner'; lock.write_text('restore-rehearsal\n'); lock.chmod(0o600)
    events = []; failed = False; proc = None
    request_read, request_write = os.pipe()
    response_read, response_write = os.pipe()
    try:
        env = {'PATH': '/usr/bin:/bin', 'PYTHON': sys.executable, 'CLIENT': CLIENT,
               'REQUEST_FD': str(request_write), 'RESPONSE_FD': str(response_read),
               'PRIVATE_ROOT': str(root), 'TRANSACTION': str(tx),
               'RESTORE_COMMAND': str(ROOT/'scripts/commands/restore.sh'),
               'ATLAS_RUNTIME_CONFIG_DIR': str(root)}
        proc = subprocess.Popen(['bash', '-c', SHELL], env=env, cwd=root,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                pass_fds=(request_write, response_read), start_new_session=True)
        os.close(request_write); request_write = None
        os.close(response_read); response_read = None
        deadline = time.monotonic()+1200
        while proc.poll() is None:
            require(time.monotonic() < deadline)
            if not select.select([request_read], [], [], 0.2)[0]: continue
            request = os.read(request_read, 65)
            if not request:
                proc.wait(timeout=5); break
            try:
                op = request.decode('ascii').removesuffix('\n')
                require(not failed and len(events) < len(ORDER) and op == ORDER[len(events)])
                require(lock.read_text() == 'restore-rehearsal\n')
                require(maintenance.is_file())
                events.append(op)
                require(op != fail_at)
                if op in {'stop', 'revert', 'validate', 'start', 'ready'}:
                    actions[op]()
                elif op.startswith('runtime-'): actions['runtime']()
                if op == 'held': require((tx/'status').read_text().strip() == 'applied-awaiting-verification')
                elif op == 'revert': (tx/'status').write_text('reverted\n')
                elif op == 'retain': require(maintenance.is_file())
                elif op == 'release':
                    require((tx/'status').read_text().strip() == 'aborted')
                    lock.unlink()
                os.write(response_write, b'OK\n')
            except Exception:
                failed = True
                os.write(response_write, b'FAIL\n')
        code = proc.wait(timeout=5)
    finally:
        # Terminate only this created shell process group and its RPC client.
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=5)
        for descriptor in (request_read, request_write, response_read, response_write):
            if descriptor is not None: os.close(descriptor)
    result = {'events': events, 'success': code == 0 and not failed,
              'maintenance_retained': maintenance.exists(), 'lock_retained': lock.exists(),
              'status': (tx/'status').read_text().strip()}
    if result['success']:
        require(events == list(ORDER) and maintenance.is_file() and not lock.exists()
                and result['status'] == 'aborted')
    else:
        require(maintenance.is_file() and lock.is_file())
    return result


def recover(native, sandbox, complete_restored):
    """Recover a detached five-surface journal under private maintenance control."""
    root = native.consumer.scoped(sandbox)
    pub = native.pub
    rows = pub.read_json(root/'transaction/PLAN.json')['surfaces']
    consumed = {name: pub.digest(root/'current'/name, name in pub.DIRECTORIES)
                for name in pub.SURFACES}
    spec = importlib.util
    module_spec = spec.spec_from_file_location('maintenance_metadata', ROOT/'scripts/lib/sports-metadata-consumption.py')
    metadata = spec.module_from_spec(module_spec); module_spec.loader.exec_module(metadata)
    accepted = []

    def detached():
        native.fence.assert_detached(native.fence.load(root))

    def revert():
        native.recover(root); native.recover(root)

    def validate():
        detached()
        require(native.consumer.status(root/'consumption') == 'reverted')
        for row in rows:
            name = row['surface']; directory = name in pub.DIRECTORIES
            require(pub.digest(root/'current'/name, directory) == row['old_sha256'])
            require(pub.digest(root/'consumption/quarantine'/name, directory) == consumed[name])
        metadata.check(native, root/'current', 'old')
        metadata.check(native, root/'consumption/quarantine', 'consumed')

    def start():
        complete_restored()  # Actual restored app start, persistence restart, UID1000 readers.
        accepted.append(True)

    def ready():
        require(accepted == [True]); validate()

    with tempfile.TemporaryDirectory(prefix='atlas-maint-rehearsal.', dir='/tmp') as temporary:
        result = execute(temporary, {'stop': detached, 'revert': revert, 'validate': validate,
                                    'start': start, 'ready': ready, 'runtime': ready})
        require(result['success'])
    print('MAINTENANCE_ABORT_NATIVE_ACCEPTANCE_AND_RELEASE=PASS', flush=True)
    print(json.dumps({'version': 1, 'scope': 'private-maintenance-abort-native-recovery',
                      'shell_abort_controller': True, 'shared_execution_exclusion': True,
                      'native_acceptance_before_private_release': True,
                      'production_state_access': False, 'live_restore_enabled': False}, sort_keys=True))


def failure_cases():
    """Failure injection uses no native apps; prove actual shell held branches."""
    for boundary in ORDER:
        calls = []
        actions = {name: (lambda name=name: calls.append(name))
                   for name in ('stop', 'revert', 'validate', 'start', 'ready', 'runtime')}
        with tempfile.TemporaryDirectory(prefix='atlas-maint-rehearsal.', dir='/tmp') as temporary:
            result = execute(temporary, actions, fail_at=boundary)
            require(not result['success'] and result['maintenance_retained'] and result['lock_retained'])
            require(result['events'] == list(ORDER[:ORDER.index(boundary)+1]))
            if ORDER.index(boundary) <= ORDER.index('validate'): require('start' not in calls)
        print('MAINTENANCE_ABORT_HELD_FAILURE=PASS boundary='+boundary, flush=True)
