"""Native disposable app detachment gates a separate filesystem recovery fixture."""
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
HEAD = 'b2d8a40df5caf83e5057717bb8482b917d3d1afc'
DEPLOYMENT = 'update-20261015T211211Z-632971'
PINS = {'scripts/lib/sports-recovery-lifecycle.py': 'e5fa5c7baff858d064457c83d9e3f2102bc371337471865b10596ad1cf36a84c', 'scripts/diagnostics/sports-cold-copy-drill.py': '1d714b2d4be23d3234045836b1c31e1d92826fbcc03fa08411d184e7f7191ecb', 'scripts/diagnostics/sports-teamarr-recovery-drill.py': '68b4920da2fe6a2bca558de15879d941a65e591d3979ac9ee59e3c5ccd925e9e', 'scripts/diagnostics/sports-recovery-consumption-drill.py': 'abe7252feceab92ac730e1494952e4a0681a42e8390524dd5e6bc704efeb5a5c', 'scripts/lib/sports-recovery-consumption.py': 'df7cc1d8897783db8073de033758f3012918a626f782df26263382b738600abd', 'scripts/lib/sports-recovery-publication.py': 'b0266e90b83ca297070aa98c563ae3fc98f674b46aa14f41357cc682b61d38c8'}


def require(value):
    if not value: raise RuntimeError('Isolated Docker lifecycle drill held')


def load(name, relative):
    path = ROOT/relative
    require(path.is_file() and not path.is_symlink()
        and hashlib.sha256(path.read_bytes()).hexdigest() == PINS[relative])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def child_detach(fence, root):
    def die(name):
        if name == 'removed:dispatcharr': os._exit(86)
    fence.checkpoint = die
    fence.detach(root)
    os._exit(0)


def run():
    for relative, digest in PINS.items():
        path = ROOT/relative
        require(path.is_file() and not path.is_symlink()
            and hashlib.sha256(path.read_bytes()).hexdigest() == digest)
    fence = load('native_lifecycle_fence', 'scripts/lib/sports-recovery-lifecycle.py')
    cold = load('lifecycle_cold', 'scripts/diagnostics/sports-cold-copy-drill.py')
    team = load('lifecycle_team', 'scripts/diagnostics/sports-teamarr-recovery-drill.py')
    fixture = load('lifecycle_journal_fixture', 'scripts/diagnostics/sports-recovery-consumption-drill.py')
    # Also pin the journal and publication implementations loaded transitively.
    for relative in ('scripts/lib/sports-recovery-consumption.py', 'scripts/lib/sports-recovery-publication.py'):
        require(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == PINS[relative])
    def git(*args): return cold.invoke('git', '-C', str(ROOT), *args).stdout.decode().strip()
    def canonical(*args): return cold.invoke('git', '-C', '/opt/project-atlas', *args).stdout.decode().strip()
    require(git('rev-parse', 'HEAD') == HEAD and canonical('rev-parse', 'HEAD') == HEAD
        and canonical('branch', '--show-current') == 'main' and not canonical('status', '--porcelain=v1'))
    pointer = Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink())
    deployment = pointer.read_bytes(); require(deployment.decode().strip() == DEPLOYMENT)
    def observe():
        rows = []
        for name in ('atlas-dispatcharr', 'atlas-teamarr', 'atlas-sports-writer'):
            item = cold.inspect(name); require(item['State']['Running'])
            mounts = sorted(item['Mounts'], key=lambda row: json.dumps(row, sort_keys=True))
            rows.append((name, item['Image'], item['State']['Pid'], item['State']['StartedAt'], mounts))
        return rows
    before = observe()
    cold.LABEL = fence.LABEL
    team_base = team.utilities(ROOT); team_base.LABEL = fence.LABEL
    identifier = uuid.uuid4().hex; created = []; child = None; phase = 'create-fixtures'
    # Helpers share utility functions but keep separate image identities.
    utilities = {'dispatcharr': cold, 'teamarr': team_base}
    with tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp') as temporary:
        root = Path(temporary); original = fixture.fixture(root)
        fence.consumption.arm(root); fixture.mutate(root)
        try:
            for role in fence.IMAGES:
                base = utilities[role]; app, data = fence.names(identifier, role)
                created.append((base, app, data))
                base.docker('volume', 'create', '--driver', 'local', '--label', fence.LABEL+'='+identifier, data)
                if role == 'dispatcharr':
                    args = cold.app_arguments(app, data, identifier)
                    args.insert(-1, '--user=0:0')
                else: args = team.app_arguments(base, app, data, identifier)
                base.invoke(*args); base.docker('start', app)
                if role == 'dispatcharr':
                    deadline = time.monotonic()+180; next_update = 0
                    while time.monotonic() < deadline:
                        require(base.owned_container(app, identifier, data, '/data', False)['State']['Running'])
                        result = base.invoke('docker', 'exec', app, 'python3', '-B', '-c', cold.READY, check=False, timeout=8)
                        if result.returncode == 0 and result.stdout.strip() == b'ready': break
                        if time.monotonic() >= next_update:
                            print('LIFECYCLE_DISPATCHARR_STARTUP=pending', flush=True); next_update=time.monotonic()+20
                        time.sleep(2)
                    else: raise RuntimeError('Dispatcharr readiness deadline')
                    require(base.docker('exec', '--user', '1000:1000', app, 'python3', '-B', '-c', cold.SNAPSHOT, timeout=60) == 'snapshot-captured')
                else:
                    team.wait_ready(base, app, identifier, data)
                    require(base.docker('exec', app, 'python3', '-B', '-c', team.SEED, timeout=30) == 'snapshot-captured')
            phase = 'arm-and-deny-running-recovery'; fence.arm(root, identifier)
            before_current = [fence.pub.digest(root/'current'/name, name in fence.pub.DIRECTORIES) for name in fence.pub.SURFACES]
            try: fence.recover(root)
            except fence.LifecycleError: pass
            else: raise RuntimeError('Recovery accepted live app objects')
            require(before_current == [fence.pub.digest(root/'current'/name, name in fence.pub.DIRECTORIES) for name in fence.pub.SURFACES])
            print('LIFECYCLE_RUNNING_RECOVERY_REFUSED=PASS', flush=True)
            phase = 'stop-detach-process-death'
            child = multiprocessing.get_context('fork').Process(target=child_detach, args=(fence, root))
            child.start(); deadline = time.monotonic()+150; next_update = 0
            while child.is_alive() and time.monotonic() < deadline:
                child.join(2)
                if time.monotonic() >= next_update:
                    print('LIFECYCLE_STOP_AND_DETACH=pending', flush=True); next_update=time.monotonic()+20
            if child.is_alive(): child.kill(); child.join(5); raise RuntimeError('Detachment deadline')
            require(child.exitcode == 86)
            require(fence.load(root)['stage'] == 'detaching')
            fence.detach(root); fence.detach(root)
            print('LIFECYCLE_PROCESS_DEATH_RESUME=PASS boundary=removed:dispatcharr', flush=True)
            phase = 'gated-filesystem-recovery'
            fence.recover(root); fence.recover(root); fixture.verify(root, original)
            print('LIFECYCLE_GATED_JOURNAL_RECOVERY=PASS', flush=True)
        except Exception:
            print('LIFECYCLE_DRILL=FAIL phase='+phase, file=sys.stderr); raise
        finally:
            if child is not None and child.is_alive(): child.kill(); child.join(5)
            # Exact ownership labels only; cleanup is never the recovery barrier.
            try:
                for base, app, data in reversed(created): base.cleanup([app], data, identifier)
            finally:
                require(pointer.read_bytes() == deployment and observe() == before
                    and canonical('rev-parse', 'HEAD') == HEAD and not canonical('status', '--porcelain=v1'))
    print(json.dumps({'version': 1, 'scope': 'disposable-native-apps-separate-filesystem-journal',
        'postgres_fast_stop': True, 'owned_app_objects_removed': True, 'retained_volumes_unreferenced': True,
        'process_death_resume': True, 'gated_journal_recovery': True,
        'native_data_journal_integration': False, 'production_state_access': False,
        'live_restore_enabled': False}, sort_keys=True))
    print('SYNTHETIC_DOCKER_LIFECYCLE_DRILL=PASS')
    print('STATE=isolated-Docker-fence-only-production-unchanged-not-deployed')


def main():
    try: run(); return 0
    except Exception:
        print('SYNTHETIC_DOCKER_LIFECYCLE_DRILL=FAIL; no production restore requested.', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
