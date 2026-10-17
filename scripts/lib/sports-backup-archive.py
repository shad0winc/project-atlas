"""Run the real backup command against private registry, native and metadata fixtures."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT_FILES = ('docker-compose.yml', 'docker-compose.sports.yml', '.env.example',
                 'VERSION', 'CHARTER.md', 'ROADMAP.md', 'CHANGELOG.md')
PROJECT_DIRS = ('config', 'docs', 'modules', 'scripts')
BACKEND = (('dispatcharr-database', 'backend-recovery/dispatcharr/database.dump'),
           ('dispatcharr-jwt', 'backend-recovery/dispatcharr/jwt'),
           ('teamarr-database', 'backend-recovery/teamarr/teamarr.db'))
SHELL = r'''
set -euo pipefail
atlas_print_header() { :; }
source "$BACKUP_COMMAND"
# The backup command reloads its library. Install exactly one adapter after that
# reload: native artifacts already captured/prepared in the disposable fixture.
source() {
  builtin source "$@" || return 1
  if [[ "$1" == "$RECOVERY_LIBRARY" ]]; then
    atlas_sports_backend_recovery_capture() {
      cp -a -- "$NATIVE_PAYLOAD/backend-recovery" "$1/" || return 1
      atlas_sports_backend_recovery_validate_staged "$1"
    }
  fi
}
atlas_command_backup --notes 'Synthetic archive acceptance; restore-unverified'
'''


def require(value):
    if not value: raise ValueError('Isolated backup archive rehearsal held')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for raw in iter(lambda: stream.read(1024*1024), b''): result.update(raw)
    return result.hexdigest()


def shell(script, env, timeout=180):
    result = subprocess.run(['bash', '-c', 'set -euo pipefail\n'+script], env=env,
                            cwd=env['PRIVATE_ROOT'], capture_output=True, timeout=timeout)
    require(len(result.stdout) <= 1_000_000 and len(result.stderr) <= 1_000_000)
    return result


def copy_project(native, project_source, project):
    project_source = Path(project_source)
    fallback = {'.env.example': b'ATLAS_ARCHIVE_FIXTURE=1\n',
                'VERSION': b'1.0.0-rc.1\n',
                'CHANGELOG.md': b'# Synthetic archive fixture changelog\n'}
    for name in (*PROJECT_FILES, *PROJECT_DIRS):
        source = project_source/name; target = project/name
        if name == 'docker-compose.sports.yml' and not source.exists():
            source = project_source/'modules/sports/docker-compose.yml'
        if name in fallback and not source.exists():
            target.write_bytes(fallback[name]); target.chmod(0o600)
        elif name == 'config' and not source.exists():
            target.mkdir(mode=0o700)
            (target/'archive-fixture.json').write_text('{"synthetic":true}\n')
            (target/'archive-fixture.json').chmod(0o600)
        else:
            native.copy_tree(source, target, name in PROJECT_DIRS,
                             target_owner=(os.geteuid(), os.getegid()))
    note = project/'docs/ARCHIVE_FIXTURE_NOTE.md'
    require(not note.exists())
    note.write_text('Private archive fixture. Non-exported packaging inputs may use explicit synthetic scaffolding.\n')
    note.chmod(0o600)


def setup(native, root, native_files, *, project_source=ROOT):
    root = Path(root)
    require(root.parent == Path('/tmp') and root.name.startswith('atlas-backup-archive.')
            and root.is_dir() and not root.is_symlink() and root.stat().st_uid == os.geteuid()
            and stat.S_IMODE(root.stat().st_mode) == 0o700 and not any(root.iterdir()))
    require(set(native_files) == {relative for _, relative in BACKEND})
    project = root/'project'; project.mkdir(mode=0o700)
    copy_project(native, project_source, project)
    for args in (['git', 'init', '-q'], ['git', 'add', '.'],
                 ['git', '-c', 'user.name=Atlas Fixture', '-c', 'user.email=fixture@example.invalid',
                  'commit', '-qm', 'Private backup source fixture']):
        require(subprocess.run(args, cwd=project, capture_output=True, timeout=60).returncode == 0)
    config = root/'configs'; runtime = config/'atlas'
    runtime.mkdir(parents=True, mode=0o700)
    env = {**os.environ, 'PRIVATE_ROOT': str(root), 'ATLAS_PROJECT_DIR': str(project),
           'ATLAS_BACKUP_DIR': str(root/'backups'), 'ATLAS_CONFIG_ROOT': str(config),
           'ATLAS_RUNTIME_CONFIG_DIR': str(runtime), 'ATLAS_USERS_DIR': str(runtime/'users'),
           'ATLAS_IDENTITY_DIR': str(runtime/'identity'), 'ATLAS_REQUESTS_DIR': str(runtime/'requests'),
           'ATLAS_SCHEDULER_STATE_FILE': str(runtime/'scheduler/tasks.json'),
           'ATLAS_ARI_DIR': str(runtime/'ari'), 'SPORTS_CONFIG_DIR': str(config/'sportyfin'),
           'BACKUP_COMMAND': str(ROOT/'scripts/commands/backup.sh'),
           'RECOVERY_LIBRARY': str(ROOT/'scripts/lib/backup-recovery.sh'),
           'NATIVE_PAYLOAD': str(root/'payload')}
    rows = shell('source "$RECOVERY_LIBRARY"; atlas_backup_recovery_surface_rows', env)
    require(rows.returncode == 0)
    for line in rows.stdout.decode().splitlines():
        surface, source, archive, requirement, kind, group = line.split('\t')
        path = Path(source); require(path.is_relative_to(config))
        if requirement == 'optional': continue
        if kind == 'directory': path.mkdir(parents=True, mode=0o700); path = path/'fixture.json'
        else: path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(json.dumps({'synthetic_surface': surface, 'version': 1})+'\n'); path.chmod(0o600)
    payload = root/'payload'; payload.mkdir(mode=0o700)
    for _, relative in BACKEND:
        target = payload/relative; target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        native.copy_tree(Path(native_files[relative]), target,
                         target_owner=(os.geteuid(), os.getegid()))
    backend = payload/'backend-recovery'
    manifest = 'surface\tarchive_path\tstatus\n'+''.join(
        surface+'\t'+relative+'\tcaptured\n' for surface, relative in BACKEND)
    (backend/'MANIFEST.tsv').write_text(manifest)
    (backend/'SHA256SUMS').write_text(''.join(sha(payload/relative)+'  '+relative+'\n' for _, relative in BACKEND))
    for path in (backend/'MANIFEST.tsv', backend/'SHA256SUMS'): path.chmod(0o600)
    metadata = load('archive_metadata_fixture', 'scripts/lib/sports-metadata-consumption.py')
    fixture = load('archive_journal_fixture', 'scripts/diagnostics/sports-recovery-consumption-drill.py')
    with tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp') as journal:
        fixture.fixture(Path(journal)); metadata.initialize(native, Path(journal))
        private = runtime/'private'; private.mkdir(mode=0o700)
        for name in ('sports-metadata', 'sports-metadata-policy'):
            native.copy_tree(Path(journal)/'current'/name, private/name, True,
                             target_owner=(os.geteuid(), os.getegid()))
    # Match the real independent policy reader contract for metadata capture.
    policy = runtime/'private/sports-metadata-policy'; policy.chmod(0o750)
    (policy/'refresh.json').chmod(0o640)
    return env


def validate(archive, env):
    local = {**env, 'ARCHIVE': str(archive)}
    result = shell('source "$RECOVERY_LIBRARY"; atlas_backup_recovery_validate_archive "$ARCHIVE"; '
                   'atlas_backup_recovery_validate_safe_members "$ARCHIVE"', local)
    return result.returncode == 0


def publish(native, env):
    root = Path(env['PRIVATE_ROOT']); config = Path(env['ATLAS_CONFIG_ROOT']); payload = Path(env['NATIVE_PAYLOAD'])
    before = (native.shape(config, True), native.shape(payload, True))
    result = shell(SHELL, env)
    require(result.returncode == 0)
    directory = Path(env['ATLAS_BACKUP_DIR']); files = list(directory.iterdir())
    require(len(files) == 1 and files[0].name.startswith('atlas-') and files[0].name.endswith('.tar.gz'))
    archive = files[0]
    require(archive.is_file() and not archive.is_symlink() and stat.S_IMODE(archive.stat().st_mode) == 0o600)
    require(0 < archive.stat().st_size <= 1024**3 and validate(archive, env))
    require((native.shape(config, True), native.shape(payload, True)) == before)
    require(not list(Path(env['ATLAS_PROJECT_DIR']).glob('.atlas-backup-*.tmp')))
    return archive


def roundtrip(native, archive, env):
    root = Path(env['PRIVATE_ROOT']); metadata = load('archive_roundtrip_metadata', 'scripts/lib/sports-metadata-consumption.py')
    reader = root/'reader'; reader.mkdir(mode=0o700)
    for name in ('sports-metadata', 'sports-metadata-policy'): (reader/name).mkdir(mode=0o700)
    before = sha(archive)
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers(); names = [member.name.rstrip('/') for member in members]
        require(len(names) == len(set(names)))
        lookup = {member.name.rstrip('/'): member for member in members}
        def data(name, maximum):
            item = lookup[name]; require(item.isfile() and item.size <= maximum)
            with source.extractfile(item) as stream: raw = stream.read(maximum+1)
            require(len(raw) == item.size); return raw
        require(data('RECOVERY_FORMAT', 16).strip() == b'3')
        manifest = data('RECOVERY_MANIFEST.tsv', 16384).decode().splitlines()
        require(len(manifest) == 18)  # Header, configuration, sixteen registry surfaces.
        for _, relative in BACKEND:
            raw = data(relative, 512*1024**2)
            require(hashlib.sha256(raw).hexdigest() == sha(Path(env['NATIVE_PAYLOAD'])/relative))
        paths = {'metadata-recovery/database.sqlite': reader/'sports-metadata/metadata.sqlite',
                 'metadata-recovery/refresh-policy.json': reader/'sports-metadata-policy/refresh.json'}
        for name, destination in paths.items():
            descriptor = os.open(destination, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream: stream.write(data(name, 512*1024**2))
        (reader/'sports-metadata/metadata.sqlite.lock').touch(mode=0o600)
    metadata.check(native, reader, 'new')
    require(sha(archive) == before)
    return before


def prepare_baseline(native, sandbox, baseline, base, dispatch):
    strict = load('archive_strict_preparation', 'scripts/lib/sports-strict-consumption.py')
    strict.prepare_baseline(native, sandbox, baseline, base, dispatch)
    root = native.consumer.scoped(sandbox); baseline = Path(baseline)
    with native.consumer.file_lock(root/'docker-lifecycle.lock'):
        ledger = native.fence.load(root); native.fence.assert_detached(ledger)
        source = native.volume_path(ledger['identifier'], 'dispatcharr')/'atlas-cold-copy.dump'
        dump_before = native.shape(source, owner=(1000, 1000))
        receipt = native.pub.read_json(baseline/'STRICT_PREPARED.json')
        require(dump_before['.'][2] == receipt['native_receipt']['dump_sha256'])
        files = {BACKEND[0][1]: source, BACKEND[1][1]: baseline/'dispatcharr-jwt',
                 BACKEND[2][1]: baseline/'teamarr-db'}
        baseline_before = native.pub.digest(baseline, True)
        with tempfile.TemporaryDirectory(prefix='atlas-backup-archive.', dir='/tmp') as temporary:
            env = setup(native, temporary, files)
            archive = publish(native, env); digest = roundtrip(native, archive, env)
            require(native.pub.digest(baseline, True) == baseline_before)
            require(native.shape(source, owner=(1000, 1000)) == dump_before)
        native.fence.assert_detached(ledger)
        print('BACKUP_ARCHIVE_FORMAT3_VALIDATED_PUBLISHED_AND_ROUNDTRIP=PASS', flush=True)
        print(json.dumps({'version': 1, 'scope': 'private-complete-command-archive',
            'archive_sha256': digest, 'registry_surfaces': 16, 'archive_format': 3,
            'native_artifact_bytes_preserved': True, 'atlas_metadata_roundtrip': True,
            'real_backup_command': True, 'production_state_access': False,
            'live_restore_enabled': False}, sort_keys=True))
