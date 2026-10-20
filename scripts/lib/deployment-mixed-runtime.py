#!/usr/bin/env python3
"""Validate and preserve the bounded Sports mixed-runtime record contract."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
import tempfile


SUPPLEMENTS = (
    'service-sources.json', 'repair-tracked-source.json', 'recovery-chain.json',
    'sports-writer-source.tar.gz', 'repair-activation.json', 'original-lock-owner',
    'accepted-private-sustained.json',
)
MARKERS = {'runtime_provenance_schema': '1', 'requires_mixed_runtime_contract': '1',
           'ingress_source_mode': 'original-recipe-with-explicit-writer-source-override'}
SOURCE_CLAIM = 'verified-original-application-plus-linked-service-repairs'
CONFIGURATION = {'.env', 'config/atlas.conf', 'config/modules/modules.conf',
                 'modules/sports/.env', 'modules/notifications/.env'}


def need(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), 'Evidence must be a regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def digest(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), 'Evidence must be a regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    finally:
        os.close(fd)


def metadata(record):
    result = {}
    for line in read(record / 'metadata').decode().splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        need(key not in result, 'Duplicate metadata key')
        result[key] = value
    return result


EXTENSION_NAMES = (
    'ingress-runtime-extension.json', 'ingress-application-source.tar.gz',
    'ingress-application-tracked.json', 'ingress-api-build.Dockerfile',
    'ingress-portal-build.Dockerfile', 'maintenance-authority.service',
    'ingress-release-gate.json',
)


def extension_module():
    spec = importlib.util.spec_from_file_location(
        'atlas_ingress_provenance', Path(__file__).with_name('deployment-ingress-provenance.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mixed(record):
    values = metadata(record)
    return (any(k in values for k in MARKERS)
            or any((record / name).exists() or (record / name).is_symlink()
                   for name in SUPPLEMENTS[:3] + EXTENSION_NAMES))


def safe_name(name):
    p = PurePosixPath(name)
    need(name and not p.is_absolute() and str(p) == name
         and '..' not in p.parts and '\\' not in name and '\0' not in name,
         'Unsafe source member')


def verify_manifest(record):
    entries = {}
    for line in read(record / 'MANIFEST.sha256').decode().splitlines():
        need(re.fullmatch(r'[0-9a-f]{64}  [A-Za-z0-9][A-Za-z0-9._-]*', line),
             'Invalid evidence manifest entry')
        sha, name = line.split('  ', 1)
        need(name != 'MANIFEST.sha256' and name not in entries, 'Duplicate evidence manifest entry')
        need(digest(record / name) == sha, 'Mixed-runtime evidence checksum mismatch')
        entries[name] = sha
    actual = set()
    for p in record.iterdir():
        if p.name == 'MANIFEST.sha256':
            continue
        if p.is_dir() and not p.is_symlink():
            need(re.fullmatch(r'recovery-(core|ingress|sports)\.[A-Za-z0-9]+', p.name),
                 'Unexpected record subdirectory')
        else:
            actual.add(p.name)
    need(set(entries) == actual, 'Mixed-runtime manifest coverage differs')
    return entries


def archive_files(path, commit=None):
    files, seen = {}, set()
    with tarfile.open(path, 'r:gz') as archive:
        if commit is not None:
            need(archive.pax_headers.get('comment') == commit, 'Archive commit marker differs')
        for member in archive:
            name = member.name.rstrip('/')
            safe_name(name)
            need(name not in seen, 'Duplicate source member')
            seen.add(name)
            need(member.isfile() or member.isdir(), 'Unsupported source member')
            if member.isdir():
                continue
            sha1 = hashlib.sha1(b'blob ' + str(member.size).encode() + b'\0')
            sha256 = hashlib.sha256()
            dockerfile = bytearray() if name == 'modules/sports/Dockerfile.private-api' else None
            with archive.extractfile(member) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    sha1.update(chunk)
                    sha256.update(chunk)
                    if dockerfile is not None:
                        need(len(dockerfile) + len(chunk) <= 65536, 'Writer Dockerfile is too large')
                        dockerfile.extend(chunk)
            files[name] = {'oid': sha1.hexdigest(), 'sha256': sha256.hexdigest(),
                           'executable': bool(member.mode & 0o111)}
            if dockerfile is not None:
                files[name]['text'] = dockerfile.decode()
    return files


def expected_copies(files):
    result = {}
    for line in files['modules/sports/Dockerfile.private-api']['text'].splitlines():
        if not line.startswith('COPY '):
            continue
        fields = line.split()
        need(len(fields) == 3, 'Unsupported writer COPY syntax')
        _, source, target = fields
        safe_name(source)
        need(target.startswith('/srv/sports/'), 'Unexpected writer destination')
        paths = [p for p in files if p == source or p.startswith(source + '/')]
        need(paths, 'Missing writer COPY input')
        for p in paths:
            destination = target if p == source else target + p[len(source):]
            need(destination not in result, 'Overlapping writer COPY input')
            result[destination] = files[p]['sha256']
    need('/srv/sports/providers/thesportsdb.py' in result, 'Provider COPY input missing')
    return result


def check_record(record):
    values = metadata(record)
    extended = values.get('runtime_provenance_schema') == '2'
    if extended:
        ext = extension_module()
        result = _check_base_record(record, ext.MARKERS, ext.SOURCE_CLAIM)
        ext.check_record(__import__('types').SimpleNamespace(need=need, read=read, archive_files=archive_files, safe_name=safe_name),
                         record, verify_manifest(record), values)
        return result
    need(not any((record / name).exists() or (record / name).is_symlink() for name in EXTENSION_NAMES),
         'Schema-2 supplements cannot be interpreted as schema 1')
    return _check_base_record(record, MARKERS, SOURCE_CLAIM)


def _check_base_record(record, markers, source_claim):
    need(record.is_dir() and not record.is_symlink(), 'Invalid mixed-runtime record directory')
    entries = verify_manifest(record)
    need(set(SUPPLEMENTS) <= set(entries), 'Mixed-runtime supplements missing')
    m = metadata(record)
    need(all(m.get(k) == v for k, v in markers.items()), 'Mixed-runtime metadata markers differ')
    need(m.get('source_claim') == source_claim, 'Mixed-runtime source claim differs')
    ledger = json.loads(read(record / 'service-sources.json'))
    tracked = json.loads(read(record / 'repair-tracked-source.json'))
    activation = json.loads(read(record / 'repair-activation.json'))
    chain = json.loads(read(record / 'recovery-chain.json'))
    need(ledger['schema_version'] == 1 and chain['schema_version'] == 1, 'Unsupported provenance schema')
    need(set(activation['configuration_overlay']) == CONFIGURATION, 'Private overlay file set differs')
    need(ledger['component_commits_describe_base_recipes'] is True, 'Ambiguous component source meaning')
    for component in ('core', 'ingress', 'sports'):
        need(ledger[component]['recipe_commit'] == m[component + '_commit'], 'Component recipe source differs')
    for key in ('core_commit', 'ingress_commit', 'sports_commit', 'notifications_commit', 'scheduler_commit'):
        need(re.fullmatch('[0-9a-f]{40}', m[key]), 'Invalid component commit')
    need(m['source_commit'] == m['core_commit'] == m['scheduler_commit'], 'Scheduler/Core source differs')
    need(ledger['scheduler'] == {'source_commit': m['core_commit'],
         'publication_archive': 'core-source.tar.gz'}, 'Scheduler publication provenance differs')
    need(ledger['notifications']['source_commit'] == m['notifications_commit']
         and ledger['notifications']['source_mode'] == 'historical'
         and ledger['notifications']['source_checkout'] == '/opt/project-atlas',
         'Notifications source provenance differs')
    need(ledger['ingress']['default_application_source_commit'] == m['ingress_commit'],
         'Default Ingress application source differs')
    overrides = ledger['ingress']['overrides']
    need(set(overrides) == {'sports-writer'}, 'Unsupported Ingress source overrides')
    writer = overrides['sports-writer']
    need(writer['source_archive'] == 'sports-writer-source.tar.gz', 'Writer archive differs')
    need(writer['code_commit'] == tracked['commit'] == ledger['sports']['controller_source_commit']
         == m['sports_commit'] == activation['source_commit'], 'Repair source identities differ')
    need(entries['sports-source.tar.gz'] == entries['sports-writer-source.tar.gz']
         == activation['target_source_archive_sha256'], 'Repair archive identities differ')
    need(ledger['sports']['active_controller_source'] == activation['source_generation'],
         'Historical controller source location differs')
    # Historical protected hashes include the old current pointer and owned lock.
    # They describe the recovery chain and must not be reinterpreted as live pins.
    need(chain['original_failed_transaction'] == m['failed_deployment'], 'Failed transaction link differs')
    need(chain['original_lock_owner_sha256'] == entries['original-lock-owner'],
         'Original lock history differs')
    need('deployment_id=' + m['failed_deployment'] in read(record / 'original-lock-owner').decode().splitlines(),
         'Original lock owner identity differs')
    historical_acceptance = json.loads(read(record / 'accepted-private-sustained.json'))
    need(historical_acceptance.get('accepted') is True
         and historical_acceptance.get('source_commit') == tracked['commit'],
         'Historical private acceptance provenance differs')
    need(chain['previous_verified_baseline'] == m['previous_baseline']
         or m.get('baseline_kind') == 'rollback-reconciliation', 'Previous baseline link differs')
    # Native Git archives retain the commit marker as a global PAX comment.
    for component in ('core', 'ingress'):
        archive_files(record / (component + '-source.tar.gz'), m[component + '_commit'])
    archived = archive_files(record / 'sports-source.tar.gz', tracked['commit'])
    tracked_files = {}
    for row in tracked['files']:
        safe_name(row['path'])
        need(row['path'] not in tracked_files and row['mode'] in ('100644', '100755'),
             'Invalid tracked source manifest')
        tracked_files[row['path']] = row
    need(set(tracked_files) == set(archived), 'Tracked archive coverage differs')
    for path, row in tracked_files.items():
        need(archived[path]['oid'] == row['oid']
             and archived[path]['executable'] == (row['mode'] == '100755'), 'Tracked archive blob differs')
    need(writer['copied_file_sha256'] == expected_copies(archived), 'Writer COPY provenance differs')
    image_rows = {}
    for line in read(record / 'images.tsv').decode().splitlines():
        fields = line.split('|')
        need(len(fields) == 7 and all(fields) and fields[4] not in image_rows, 'Invalid image manifest')
        image_rows[fields[4]] = fields
    need(image_rows['/atlas-sports-writer'][6] == writer['image']
         and image_rows['/atlas-sports-controller'][6] == ledger['sports']['controller_image'],
         'Repair image provenance differs')
    return ledger, tracked_files, activation


def inspect(name):
    result = subprocess.run(['docker', 'inspect', name], capture_output=True, timeout=30)
    need(result.returncode == 0, 'Runtime inspection failed')
    rows = json.loads(result.stdout)
    need(len(rows) == 1, 'Ambiguous runtime inspection')
    return rows[0]


def check_live(record, excluded=''):
    ledger, files, activation = check_record(record)
    if metadata(record).get('runtime_provenance_schema') == '2':
        extension_module().check_live(__import__('types').SimpleNamespace(
            read=read, archive_files=archive_files, inspect=inspect), record)
    writer = ledger['ingress']['overrides']['sports-writer']
    row = inspect('atlas-sports-writer')
    need(row['Image'] == writer['image'] and row['State']['Running'], 'Writer runtime identity differs')
    expected = writer['copied_file_sha256']
    child = """import hashlib,json,pathlib,sys
expected=json.load(sys.stdin)
for name,digest in expected.items():
 p=pathlib.Path(name)
 assert p.is_file() and not p.is_symlink()
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
actual={str(p) for p in pathlib.Path('/srv/sports').rglob('*.py')}
assert actual=={p for p in expected if p.endswith('.py')}
"""
    result = subprocess.run(['docker', 'exec', '-i', 'atlas-sports-writer', 'python3', '-B', '-c', child],
                            input=json.dumps(expected).encode(), capture_output=True, timeout=60)
    need(result.returncode == 0, 'Writer copied-file provenance differs')
    if excluded == 'sports':
        return
    row = inspect('atlas-sports-controller')
    need(row['Image'] == ledger['sports']['controller_image'] and row['State']['Running'],
         'Controller runtime identity differs')
    mounts = [m for m in row['Mounts'] if m['Destination'] == '/opt/project-atlas']
    need(len(mounts) == 1 and mounts[0]['Type'] == 'bind' and mounts[0]['RW'] is False,
         'Controller executable source must be one read-only bind')
    source = Path(mounts[0]['Source'])
    need(source.is_absolute() and source.is_dir() and not source.is_symlink(), 'Invalid controller source')
    for name, expected_row in files.items():
        path = source / name
        raw = read(path)
        need(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == expected_row['oid'],
             'Controller tracked source blob differs')
        need(bool(path.stat().st_mode & 0o111) == (expected_row['mode'] == '100755'),
             'Controller executable bit differs')
    need({p.relative_to(source).as_posix() for p in source.rglob('*.py')}
         == {name for name in files if name.endswith('.py')}, 'Unexpected controller Python source')
    for name, expected_row in activation['configuration_overlay'].items():
        safe_name(name)
        path = source / name
        st = path.stat()
        need({'sha256': digest(path), 'uid': st.st_uid, 'gid': st.st_gid,
              'mode': oct(stat.S_IMODE(st.st_mode))} == expected_row, 'Controller configuration overlay differs')


def atomic_write(path, raw):
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temp).unlink(missing_ok=True)


def seal(record):
    lines = []
    for p in sorted(record.iterdir()):
        if p.name == 'MANIFEST.sha256':
            continue
        if p.is_dir() and not p.is_symlink():
            need(re.fullmatch(r'recovery-(core|ingress|sports)\.[A-Za-z0-9]+', p.name),
                 'Unexpected record subdirectory')
            continue
        need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', p.name), 'Invalid evidence filename')
        lines.append(digest(p) + '  ' + p.name)
    atomic_write(record / 'MANIFEST.sha256', ('\n'.join(lines) + '\n').encode())


def inherit(source, destination, recovery_transaction=None):
    if not mixed(source):
        return
    check_record(source)
    need(metadata(source).get('runtime_provenance_schema') != '2',
         'Schema-2 inheritance requires the pending recovery coordinator')
    need(destination.is_dir() and not destination.is_symlink(), 'Invalid inheritance destination')
    for name in SUPPLEMENTS:
        need(not (destination / name).exists() and not (destination / name).is_symlink(),
             'Destination already contains mixed-runtime evidence')
        atomic_write(destination / name, read(source / name))
    reference = source if recovery_transaction is None else recovery_transaction
    for name in ('backup_file', 'pre-images.tsv', 'rollback-images.tsv'):
        if (reference / name).is_file():
            atomic_write(destination / name, read(reference / name))
    values = metadata(destination)
    values.update(MARKERS)
    values['source_claim'] = SOURCE_CLAIM
    values['scheduler_commit'] = metadata(source)['scheduler_commit']
    # Keep the actual original failed transaction as the repair-chain identity.
    values['reconciliation_transaction'] = values.get('failed_deployment', '')
    values['failed_deployment'] = metadata(source)['failed_deployment']
    atomic_write(destination / 'metadata', ''.join(k + '=' + v + '\n' for k, v in values.items()).encode())
    seal(destination)


def prepare_restore(record, destination):
    ledger, _, activation = check_record(record)
    need(metadata(record).get('runtime_provenance_schema') != '2',
         'Schema-2 restore requires the pending recovery coordinator')
    need(destination.is_absolute() and destination.is_dir() and not destination.is_symlink(),
         'Invalid private restore destination')
    # Only the native records/<transaction>/recovery-sports.* namespace is writable here.
    records = record.parent.resolve()
    resolved = destination.resolve()
    need(resolved.parent.parent == records and resolved.name.startswith('recovery-sports.'),
         'Restore destination is outside native recovery namespace')
    source = Path(ledger['sports']['active_controller_source'])
    prepared = []
    for name, expected in activation['configuration_overlay'].items():
        safe_name(name)
        original, target = source / name, destination / name
        st = original.stat()
        need({'sha256': digest(original), 'uid': st.st_uid, 'gid': st.st_gid,
              'mode': oct(stat.S_IMODE(st.st_mode))} == expected, 'Preserved private overlay differs')
        need(not target.is_symlink(), 'Restore configuration target is a symlink')
        prepared.append((target, read(original), expected))
    for target, raw, expected in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, raw)
        os.chown(target, expected['uid'], expected['gid'])
        os.chmod(target, int(expected['mode'], 8))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('record', 'live', 'inherit', 'seal', 'prepare-restore'))
    parser.add_argument('record', type=Path)
    parser.add_argument('argument', nargs='?', default='')
    parser.add_argument('--recovery-transaction', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'record':
            check_record(args.record)
        elif args.action == 'live':
            need(args.argument in ('', 'sports'), 'Unsupported runtime exclusion')
            check_live(args.record, args.argument)
        elif args.action == 'inherit':
            inherit(args.record, Path(args.argument), args.recovery_transaction)
        elif args.action == 'seal':
            seal(args.record)
        else:
            prepare_restore(args.record, Path(args.argument))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError) as exc:
        detail = str(exc) if type(exc) is ValueError else 'private details withheld'
        print('ERROR: mixed-runtime provenance contract failed: ' + detail, file=__import__('sys').stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
