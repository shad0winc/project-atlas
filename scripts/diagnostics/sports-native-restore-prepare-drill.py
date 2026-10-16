"""Rehearse the native restore adapter in a disposable, isolated container."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import uuid

IMAGE = 'sha256:e5d4b045b51519be4142a7baf7da6750ad33f80dcb0a77b8832c2ce930c6fe12'
DEPLOYMENT = 'update-20261015T211211Z-632971'


def require(condition):
    if not condition:
        raise RuntimeError('Synthetic recovery drill contract failed')


def docker(*arguments, timeout=15):
    result = subprocess.run(['docker', *arguments], capture_output=True, timeout=timeout)
    require(result.returncode == 0 and len(result.stdout) < 65536)
    return result.stdout.decode().strip()


def production_observation():
    return docker('inspect', '--format', '{{.Image}}|{{.State.Running}}|{{.State.StartedAt}}', 'atlas-dispatcharr')


def run():
    root = Path(__file__).resolve().parents[2]
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            == 'be41d82819441c8be7457ebcd351d40221120208')
    helper = root / 'scripts/lib/sports-postgres-prepare.py'
    require(helper.is_file() and not helper.is_symlink())
    adapter_raw = helper.read_bytes()
    require(hashlib.sha256(adapter_raw).hexdigest() == '34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc')
    drill_file = root / 'scripts/lib/sports-postgres-prepare-drill.py'
    require(drill_file.is_file() and not drill_file.is_symlink())
    drill_raw = drill_file.read_bytes()
    require(hashlib.sha256(drill_raw).hexdigest() == '9809d9073e3e0ffdf547acc75c7c435226322afae4e8a22e7980286bbf4f719c')
    raw = json.dumps({'adapter': adapter_raw.decode(), 'drill': drill_raw.decode()}).encode()
    bootstrap = "import hashlib,json,sys,types\nraw=sys.stdin.buffer.read(1048577)\nassert len(raw)<=1048576\npayload=json.loads(raw)\nassert set(payload)=={'adapter','drill'}\nassert hashlib.sha256(payload['adapter'].encode()).hexdigest()=='34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc'\nassert hashlib.sha256(payload['drill'].encode()).hexdigest()=='9809d9073e3e0ffdf547acc75c7c435226322afae4e8a22e7980286bbf4f719c'\nmodule=types.ModuleType('atlas_pg_prepare')\nmodule.__file__='<native-adapter>'\nsys.modules['atlas_pg_prepare']=module\nexec(compile(payload['adapter'],'<native-adapter>','exec'),module.__dict__)\nexec(compile(payload['drill'],'<native-drill>','exec'),{'__name__':'__main__'})\n"
    pointer = Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink())
    before = pointer.read_bytes()
    require(before.decode().strip() == DEPLOYMENT)
    observation = production_observation()
    require(observation.startswith(IMAGE + '|true|'))
    require(docker('image', 'inspect', '--format', '{{.Id}}', IMAGE) == IMAGE)
    identifier = uuid.uuid4().hex
    name = 'atlas-native-prepare-drill-' + identifier
    arguments = ['docker', 'run', '--rm', '-i', '--pull=never', '--name', name,
                 '--label', 'io.project-atlas.native-prepare-drill=' + identifier,
                 '--network=none', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777',
                 '--user=65534:65534', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                 '--memory=512m', '--cpus=1', '--pids-limit=128', '--restart=no', '--no-healthcheck',
                 '--env', 'ATLAS_NATIVE_PREPARE_DRILL=1', '--entrypoint', 'python3',
                 IMAGE, '-I', '-B', '-c', bootstrap]
    try:
        result = subprocess.run(arguments, input=raw, capture_output=True, timeout=180)
        if result.returncode != 0:
            match = re.search(rb'NATIVE_PREPARE_DRILL=FAIL category=([A-Za-z-]{1,80})', result.stderr)
            if match:
                print(match.group().decode(), file=sys.stderr)
            print('DRILL_CONTAINER_EXIT_CODE=' + str(result.returncode), file=sys.stderr)
        require(result.returncode == 0 and len(result.stdout) < 4096)
        receipt = json.loads(result.stdout)
        require(receipt == {'version': 1, 'scope': 'synthetic-native-restore-preparation',
            'restore_data': 'pass', 'stale_objects_removed': 'pass', 'grants_restored': 'pass',
            'global_roles_preserved': 'pass', 'cold_source_unchanged': 'pass',
            'startup_hooks_isolated': 'pass', 'startup_config_preserved': 'pass',
            'corrupt_archive_rejected': 'pass', 'clusters_stopped': 'pass',
            'production_state_access': False, 'live_restore_enabled': False})
    finally:
        # A timed-out Docker client can leave its one-shot container running.
        # Remove only a container carrying this invocation's random ownership label.
        check = subprocess.run(['docker', 'inspect', '--format',
            '{{index .Config.Labels "io.project-atlas.native-prepare-drill"}}', name],
            capture_output=True, timeout=10)
        if check.returncode == 0:
            require(check.stdout.decode().strip() == identifier)
            docker('rm', '--force', name)
        else:
            # Distinguish normal --rm absence from an unreachable Docker daemon.
            docker('info', '--format', '{{.ServerVersion}}')
    require(pointer.read_bytes() == before)
    require(production_observation() == observation)
    print(json.dumps(receipt, sort_keys=True))
    print('NATIVE_RESTORE_PREPARATION_DRILL=PASS')
    print('STATE=synthetic-rehearsal-only-production-unchanged')


def main():
    try:
        run()
    except Exception:
        print('NATIVE_RESTORE_PREPARATION_DRILL=FAIL; no production restore was requested.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
