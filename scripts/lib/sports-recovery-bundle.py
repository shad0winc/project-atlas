"""Prepare the Sports portion of a format-3 staged recovery, never apply live state.

Only a fresh isolated workspace is written. Ownership fields are a numeric plan;
all prepared artifacts remain private and owned by the preparing operator until
future reviewed publication assigns the intended consumer ownership.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import time

MAX_DATABASE = 512 * 1024 * 1024
NATIVE = (
    ('dispatcharr-database', 'backend-recovery/dispatcharr/database.dump', MAX_DATABASE),
    ('dispatcharr-jwt', 'backend-recovery/dispatcharr/jwt', 16384),
    ('teamarr-database', 'backend-recovery/teamarr/teamarr.db', MAX_DATABASE),
)


class BundleError(ValueError):
    pass


def require(condition):
    if not condition:
        raise BundleError('Invalid Sports recovery bundle')


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts)
    for part in (path, *path.parents):
        require(not part.is_symlink())
    return path


def directory(path):
    info = safe_path(path).lstat()
    require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700
            and info.st_uid == os.geteuid())


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def checked_file(path, limit):
    safe_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_uid == os.geteuid() and 0 <= info.st_size <= limit)
    except BaseException:
        os.close(descriptor)
        raise
    return os.fdopen(descriptor, 'rb'), info


def bytes_checked(path, limit):
    stream, info = checked_file(path, limit)
    with stream:
        raw = stream.read(limit + 1)
    require(len(raw) == info.st_size and len(raw) <= limit)
    return raw


def copy_checked(source, destination, expected, limit):
    require(re.fullmatch('[a-f0-9]{64}', expected) is not None)
    stream, before = checked_file(source, limit)
    descriptor = None
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        digest = hashlib.sha256()
        size = 0
        with os.fdopen(descriptor, 'wb') as target:
            descriptor = None
            for raw in iter(lambda: stream.read(1024 * 1024), b''):
                size += len(raw)
                require(size <= limit)
                digest.update(raw); target.write(raw)
            target.flush(); os.fsync(target.fileno())
        after = os.fstat(stream.fileno())
        require(size == before.st_size and digest.hexdigest() == expected)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns))
    finally:
        stream.close()
        if descriptor is not None: os.close(descriptor)


def sqlite_valid(path):
    # The prepared copy is detached; immutable read-only validation cannot create
    # a journal/WAL or repair the original staged archive.
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True, timeout=1)
    deadline = time.monotonic() + 10
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        require(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)])
    finally:
        connection.close()


def ownership_plan(identities):
    require(isinstance(identities, dict) and set(identities) == {'dispatcharr', 'dispatcharr_jwt', 'teamarr', 'writer'})
    for identity in identities.values():
        require(isinstance(identity, (list, tuple)) and len(identity) == 2
                and all(type(value) is int and 0 <= value < 2**31 for value in identity))
    return {name: list(identity) for name, identity in identities.items()}


def native_contract(root):
    backend = root / 'backend-recovery'
    directory(backend)
    rows = bytes_checked(backend / 'MANIFEST.tsv', 8192).decode().splitlines()
    require(len(rows) == 4 and rows[0] == 'surface\tarchive_path\tstatus')
    statuses = []
    for raw, (surface, relative, _) in zip(rows[1:], NATIVE):
        fields = raw.split('\t')
        require(len(fields) == 3 and fields[:2] == [surface, relative]
                and fields[2] in {'captured', 'absent'})
        statuses.append(fields[2])
    require(len(set(statuses)) == 1)
    checksum_raw = bytes_checked(backend / 'SHA256SUMS', 8192)
    expected = {}
    for line in checksum_raw.decode().splitlines():
        fields = line.split('  ', 1)
        require(len(fields) == 2 and re.fullmatch('[a-f0-9]{64}', fields[0]) is not None
                and fields[1] in {row[1] for row in NATIVE} and fields[1] not in expected)
        expected[fields[1]] = fields[0]
    captured = statuses[0] == 'captured'
    require(set(expected) == ({row[1] for row in NATIVE} if captured else set()))
    paths = {p.relative_to(backend).as_posix() for p in backend.rglob('*')}
    required = {'MANIFEST.tsv', 'SHA256SUMS'}
    if captured:
        required |= {'dispatcharr', 'dispatcharr/database.dump', 'dispatcharr/jwt', 'teamarr', 'teamarr/teamarr.db'}
        directory(backend / 'dispatcharr'); directory(backend / 'teamarr')
    require(paths == required)
    for part in backend.rglob('*'): require(not part.is_symlink())
    return captured, expected


def write_private(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as target:
        target.write(raw); target.flush(); os.fsync(target.fileno())


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def prepare(root, identities, *, scratch_parent=Path('/tmp')):
    root = safe_path(root); scratch_parent = safe_path(scratch_parent)
    directory(root)
    # Input must be an existing canonical isolated staging root. There is no live
    # destination parameter and no ability to publish into production paths.
    require(root.parent == Path('/tmp') and root.name.startswith('project-atlas-restore.'))
    require(scratch_parent == Path('/tmp'))
    identities = ownership_plan(identities)
    require(bytes_checked(root / 'RECOVERY_FORMAT', 16) == b'3\n')
    captured, native_hashes = native_contract(root)
    metadata = root / 'metadata-recovery'
    directory(metadata)
    manifest_raw = bytes_checked(metadata / 'MANIFEST.json', 4096)
    manifest = json.loads(manifest_raw, object_pairs_hook=unique)
    # A database-only v1 snapshot cannot prove which refresh policy to restore.
    # Legacy inspection remains supported; unified pair preparation refuses it.
    require(set(manifest) == {'version', 'database_schema', 'database_sha256', 'policy_sha256'}
            and type(manifest['version']) is int and manifest['version'] == 2
            and type(manifest['database_schema']) is int and manifest['database_schema'] == 1)
    require({p.name for p in metadata.iterdir()} == {'MANIFEST.json', 'database.sqlite', 'refresh-policy.json'})
    workspace = Path(tempfile.mkdtemp(prefix='project-atlas-sports-prepare.', dir=scratch_parent))
    work = workspace / '.preparing'; work.mkdir(mode=0o700)
    try:
        records = []
        if captured:
            for name in ('dispatcharr', 'teamarr'): (work / name).mkdir(mode=0o700)
            for surface, relative, limit in NATIVE:
                role = {'dispatcharr-database': 'dispatcharr',
                        'dispatcharr-jwt': 'dispatcharr_jwt', 'teamarr-database': 'teamarr'}[surface]
                output = relative.removeprefix('backend-recovery/')
                copy_checked(root / relative, work / output, native_hashes[relative], limit)
                records.append({'surface': surface, 'path': output, 'sha256': native_hashes[relative],
                                'publish_owner': identities[role], 'publish_mode': '0600',
                                'state': 'native-restore-required' if surface == 'dispatcharr-database' else 'prepared-copy'})
            with (work / 'dispatcharr/database.dump').open('rb') as source:
                require(source.read(5) == b'PGDMP')
            require((work / 'dispatcharr/jwt').stat().st_size > 0)
            sqlite_valid(work / 'teamarr/teamarr.db')
        (work / 'sports-metadata').mkdir(mode=0o700)
        (work / 'sports-metadata-policy').mkdir(mode=0o700)
        copy_checked(metadata / 'database.sqlite', work / 'sports-metadata/metadata.sqlite', manifest['database_sha256'], MAX_DATABASE)
        write_private(work / 'sports-metadata/metadata.sqlite.lock', b'')
        copy_checked(metadata / 'refresh-policy.json', work / 'sports-metadata-policy/refresh.json', manifest['policy_sha256'], 16384)
        helper('metadata-recovery').validate_database(work / 'sports-metadata/metadata.sqlite', immutable=True)
        helper('sports-metadata-policy').validate_bytes(bytes_checked(work / 'sports-metadata-policy/refresh.json', 16384))
        for surface, relative, digest, owner, mode in (
            ('metadata-database', 'sports-metadata/metadata.sqlite', manifest['database_sha256'], identities['writer'], '0600'),
            ('metadata-lock', 'sports-metadata/metadata.sqlite.lock', hashlib.sha256(b'').hexdigest(), identities['writer'], '0600'),
            ('metadata-policy', 'sports-metadata-policy/refresh.json', manifest['policy_sha256'], [0, identities['writer'][1]], '0640'),
        ):
            records.append({'surface': surface, 'path': relative, 'sha256': digest,
                            'publish_owner': owner, 'publish_mode': mode, 'state': 'prepared-copy'})
        result = {'version': 2, 'native_backend': 'captured' if captured else 'absent-unresolved',
                  'ready_for_live_apply': False, 'ownership_plan': identities,
                  'publish_directories': {'sports-metadata': {'owner': identities['writer'], 'mode': '0700'},
                                         'sports-metadata-policy': {'owner': [0, identities['writer'][1]], 'mode': '0750'}},
                  'source_native_contract_sha256': hashlib.sha256(json.dumps(
                      {'captured': captured, 'hashes': native_hashes}, sort_keys=True).encode()).hexdigest(),
                  'source_metadata_manifest_sha256': hashlib.sha256(manifest_raw).hexdigest(),
                  'files': records}
        write_private(work / 'BUNDLE.json', (json.dumps(result, sort_keys=True) + '\n').encode())
        # Detect changed source contracts before publishing any prepared bundle.
        require(bytes_checked(metadata / 'MANIFEST.json', 4096) == manifest_raw)
        require(native_contract(root) == (captured, native_hashes))
        for child in work.iterdir():
            if child.is_dir(): sync_directory(child)
        sync_directory(work)
        destination = workspace / 'bundle'
        os.rename(work, destination); sync_directory(workspace)
        validate_bundle(destination)
        return destination
    except BaseException:
        # Only this invocation's new, private workspace is removed. Never the
        # staged archive or any existing/live recovery state.
        shutil.rmtree(workspace)
        raise


def file_digest(path, limit):
    stream, before = checked_file(path, limit)
    digest = hashlib.sha256(); size = 0
    with stream:
        for raw in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(raw); require(size <= limit); digest.update(raw)
        after = os.fstat(stream.fileno())
    require(size == before.st_size and (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns))
    return digest.hexdigest()


def validate_bundle(root):
    root = safe_path(root)
    require(root.name == 'bundle' and root.parent.parent == Path('/tmp')
            and root.parent.name.startswith('project-atlas-sports-prepare.'))
    directory(root.parent); directory(root)
    manifest = json.loads(bytes_checked(root / 'BUNDLE.json', 16384), object_pairs_hook=unique)
    require(isinstance(manifest, dict) and set(manifest) == {
        'version', 'native_backend', 'ready_for_live_apply', 'ownership_plan',
        'publish_directories', 'source_native_contract_sha256',
        'source_metadata_manifest_sha256', 'files'})
    require(type(manifest['version']) is int and manifest['version'] == 2
            and manifest['ready_for_live_apply'] is False
            and manifest['native_backend'] in {'captured', 'absent-unresolved'})
    identities = ownership_plan(manifest['ownership_plan'])
    require(manifest['publish_directories'] == {
        'sports-metadata': {'owner': identities['writer'], 'mode': '0700'},
        'sports-metadata-policy': {'owner': [0, identities['writer'][1]], 'mode': '0750'}})
    for key in ('source_native_contract_sha256', 'source_metadata_manifest_sha256'):
        require(isinstance(manifest[key], str) and re.fullmatch('[a-f0-9]{64}', manifest[key]) is not None)
    empty_hash = hashlib.sha256(b'').hexdigest()
    expected = {
        'metadata-database': ('sports-metadata/metadata.sqlite', identities['writer'], '0600', MAX_DATABASE, 'prepared-copy'),
        'metadata-lock': ('sports-metadata/metadata.sqlite.lock', identities['writer'], '0600', 0, 'prepared-copy'),
        'metadata-policy': ('sports-metadata-policy/refresh.json', [0, identities['writer'][1]], '0640', 16384, 'prepared-copy'),
    }
    directories = {'sports-metadata', 'sports-metadata-policy'}
    if manifest['native_backend'] == 'captured':
        directories |= {'dispatcharr', 'teamarr'}
        for surface, relative, limit in NATIVE:
            role = {'dispatcharr-database': 'dispatcharr',
                        'dispatcharr-jwt': 'dispatcharr_jwt', 'teamarr-database': 'teamarr'}[surface]
            expected[surface] = (relative.removeprefix('backend-recovery/'), identities[role], '0600', limit,
                                 'native-restore-required' if surface == 'dispatcharr-database' else 'prepared-copy')
    require(isinstance(manifest['files'], list) and len(manifest['files']) == len(expected))
    seen = set()
    for row in manifest['files']:
        require(isinstance(row, dict) and set(row) == {'surface', 'path', 'sha256', 'publish_owner', 'publish_mode', 'state'})
        surface = row['surface']
        require(isinstance(surface, str) and surface in expected and surface not in seen)
        seen.add(surface)
        relative, owner, mode, limit, state = expected[surface]
        require((row['path'], row['publish_owner'], row['publish_mode'], row['state']) == (relative, owner, mode, state))
        require(isinstance(row['sha256'], str) and re.fullmatch('[a-f0-9]{64}', row['sha256']) is not None)
        require(file_digest(root / relative, limit) == row['sha256'])
        if surface == 'metadata-lock': require(row['sha256'] == empty_hash)
    require({p.relative_to(root).as_posix() for p in root.rglob('*')}
            == {'BUNDLE.json', *directories, *(row[0] for row in expected.values())})
    for name in directories: directory(root / name)
    helper('metadata-recovery').validate_database(root / 'sports-metadata/metadata.sqlite', immutable=True)
    helper('sports-metadata-policy').validate_bytes(bytes_checked(root / 'sports-metadata-policy/refresh.json', 16384))
    if manifest['native_backend'] == 'captured':
        with (root / 'dispatcharr/database.dump').open('rb') as source: require(source.read(5) == b'PGDMP')
        require((root / 'dispatcharr/jwt').stat().st_size > 0)
        sqlite_valid(root / 'teamarr/teamarr.db')
    return manifest
