"""Run a disposable PostgreSQL-only rehearsal, never a production restore."""
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
            == '8795962651877c25b70460d3863187efa0cafed3')
    helper = root / 'scripts/lib/sports-postgres-recovery-drill.py'
    require(helper.is_file() and not helper.is_symlink())
    raw = helper.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == 'eb15abfa0bf6332307cc193280162ffc30a8ec095ac2894efff5e367bebf0752')
    pointer = Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink())
    before = pointer.read_bytes()
    require(before.decode().strip() == DEPLOYMENT)
    observation = production_observation()
    require(observation.startswith(IMAGE + '|true|'))
    require(docker('image', 'inspect', '--format', '{{.Id}}', IMAGE) == IMAGE)
    identifier = uuid.uuid4().hex
    name = 'atlas-recovery-drill-' + identifier
    arguments = ['docker', 'run', '--rm', '-i', '--pull=never', '--name', name,
                 '--label', 'io.project-atlas.recovery-drill=' + identifier,
                 '--network=none', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777',
                 '--user=65534:65534', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                 '--memory=512m', '--cpus=1', '--pids-limit=128', '--restart=no', '--no-healthcheck',
                 '--env', 'ATLAS_SYNTHETIC_RECOVERY_DRILL=1', '--entrypoint', 'python3',
                 IMAGE, '-I', '-B', '-']
    try:
        result = subprocess.run(arguments, input=raw, capture_output=True, timeout=85)
        if result.returncode != 0:
            match = re.search(rb'SYNTHETIC_POSTGRES_RECOVERY_DRILL=FAIL category=([A-Za-z-]{1,80})', result.stderr)
            if match:
                print(match.group().decode(), file=sys.stderr)
            print('DRILL_CONTAINER_EXIT_CODE=' + str(result.returncode), file=sys.stderr)
        require(result.returncode == 0 and len(result.stdout) < 4096)
        receipt = json.loads(result.stdout)
        require(receipt == {'version': 1, 'scope': 'synthetic-isolated-postgres-only',
            'restore_data': 'pass', 'nonzero_exit_rejected': 'pass',
            'single_transaction_rollback': 'pass', 'corrupt_archive_rejected': 'pass',
            'postgres_stopped': 'pass', 'production_state_access': False})
    finally:
        # A timed-out Docker client can leave its one-shot container running.
        # Remove only a container carrying this invocation's random ownership label.
        check = subprocess.run(['docker', 'inspect', '--format',
            '{{index .Config.Labels "io.project-atlas.recovery-drill"}}', name],
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
    print('NATIVE_SYNTHETIC_RECOVERY_DRILL=PASS')
    print('STATE=synthetic-rehearsal-only-production-unchanged')


def main():
    try:
        run()
    except Exception:
        print('NATIVE_SYNTHETIC_RECOVERY_DRILL=FAIL; no production restore was requested.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
