"""Schema-2 Ingress source and read-only live provenance verification."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath
import re
import tarfile

SUPPLEMENTS = (
    'ingress-runtime-extension.json', 'ingress-application-source.tar.gz',
    'ingress-application-tracked.json', 'ingress-api-build.Dockerfile',
    'ingress-portal-build.Dockerfile', 'maintenance-authority.service',
    'ingress-release-gate.json',
)
MARKERS = {
    'runtime_provenance_schema': '2', 'requires_mixed_runtime_contract': '2',
    'ingress_source_mode': 'base-recipe-with-explicit-maintenance-extension',
}
SOURCE_CLAIM = 'verified-base-recipes-plus-linked-service-and-maintenance-repairs'


def tree_oid(files):
    """Reconstruct a Git tree from regular archive blobs and executable bits."""
    root = {}
    for name, row in files.items():
        node = root
        parts = name.split('/')
        for part in parts[:-1]:
            if part in node and not isinstance(node[part], dict):
                raise ValueError('Source path collides with a file')
            node = node.setdefault(part, {})
        if parts[-1] in node:
            raise ValueError('Source file collides with a directory')
        node[parts[-1]] = (row['oid'], row['executable'])

    def encode(node):
        raw = bytearray()
        for name in sorted(node, key=lambda n: n.encode() + (b'/' if isinstance(node[n], dict) else b'')):
            row = node[name]
            mode, oid = ('40000', encode(row)) if isinstance(row, dict) else (
                '100755' if row[1] else '100644', row[0])
            raw.extend(mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(oid))
        return hashlib.sha1(b'tree ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    return encode(root)


def check_record(m, record, entries, values):
    need = m.need
    need(set(SUPPLEMENTS) <= set(entries), 'Ingress extension supplements missing')
    ext = json.loads(m.read(record / SUPPLEMENTS[0]))
    need(set(ext) == {'schema_version', 'source_archive_commit', 'released_commit', 'source_tree',
                     'base_ledger_sha256', 'images', 'caddy', 'authority'}, 'Ingress extension fields differ')
    need(ext['schema_version'] == 1, 'Unsupported Ingress extension schema')
    for key in ('source_archive_commit', 'released_commit', 'source_tree'):
        need(isinstance(ext[key], str) and re.fullmatch('[0-9a-f]{40}', ext[key]), 'Invalid Ingress source identity')
    need(ext['base_ledger_sha256'] == entries['service-sources.json'], 'Base service ledger link differs')
    need(values.get('ingress_extension_commit') == ext['released_commit']
         and values.get('ingress_extension_tree') == ext['source_tree'], 'Ingress extension metadata differs')
    archived = m.archive_files(record / 'ingress-application-source.tar.gz', ext['source_archive_commit'])
    tracked = json.loads(m.read(record / 'ingress-application-tracked.json'))
    need(set(tracked) == {'commit', 'tree', 'files'} and tracked['commit'] == ext['source_archive_commit']
         and tracked['tree'] == ext['source_tree'], 'Ingress tracked source identity differs')
    rows = {}
    for row in tracked['files']:
        need(set(row) == {'path', 'mode', 'oid'}, 'Ingress tracked row fields differ')
        m.safe_name(row['path'])
        need(row['path'] not in rows and row['mode'] in ('100644', '100755'), 'Invalid Ingress tracked row')
        rows[row['path']] = row
    need(set(rows) == set(archived), 'Ingress archive coverage differs')
    for name, row in rows.items():
        need(row['oid'] == archived[name]['oid'] and (row['mode'] == '100755') == archived[name]['executable'],
             'Ingress tracked archive blob differs')
    need(tree_oid(archived) == ext['source_tree'], 'Ingress archive Git tree differs')
    # Read only the small recipe/unit inputs; every blob was already streamed above.
    inputs = {}
    with tarfile.open(record / 'ingress-application-source.tar.gz', 'r:gz') as archive:
        for name in ('apps/api/Dockerfile', 'apps/portal/Dockerfile', 'systemd/atlas-maintenance-control.service'):
            member = archive.getmember(name)
            need(member.isfile() and member.size <= 65536, 'Invalid Ingress recipe input')
            with archive.extractfile(member) as stream:
                inputs[name] = stream.read().decode()
    image_ids = {}
    for line in m.read(record / 'images.tsv').decode().splitlines():
        fields = line.split('|')
        need(len(fields) == 7 and fields[4] not in image_ids, 'Invalid extended image manifest')
        image_ids[fields[4]] = fields[6]
    need(set(ext['images']) == {'api', 'portal'}, 'Ingress image roles differ')
    for role, item in ext['images'].items():
        need(set(item) == {'image_id', 'base_images'}, 'Ingress image evidence fields differ')
        need(re.fullmatch(r'sha256:[0-9a-f]{64}', item['image_id'])
             and image_ids.get('/atlas-' + role) == item['image_id'], 'Ingress image manifest differs')
        text = inputs['apps/' + role + '/Dockerfile']
        bases = item['base_images']
        need(isinstance(bases, dict) and bases, 'Pinned build bases missing')
        changed = 0
        used = set()
        output = []
        for line in text.splitlines(keepends=True):
            match = re.match(r'^(FROM\s+)(\S+)(.*?)(\r?\n)?$', line, re.I)
            if match:
                old = match[2]
                need(old in bases and re.fullmatch(r'[a-z0-9./_-]+@sha256:[0-9a-f]{64}', bases[old]),
                     'Unpinned or unknown build base')
                line = match[1] + bases[old] + match[3] + (match[4] or '')
                used.add(old)
                changed += 1
            output.append(line)
        need(changed > 0 and used == set(bases), 'Build base map coverage differs')
        need(m.read(record / ('ingress-' + role + '-build.Dockerfile')) == ''.join(output).encode(),
             'Build recipe changes exceed pinned FROM references')
    caddy = ext['caddy']
    need(set(caddy) == {'image_id', 'immutable_source', 'binds'}, 'Caddy evidence fields differ')
    source = caddy['immutable_source']
    need(isinstance(source, str) and re.fullmatch(
        r'/mnt/storage/configs/atlas/deployments/repairs/[A-Za-z0-9][A-Za-z0-9._-]*/source', source)
        and str(PurePosixPath(source)) == source, 'Invalid immutable Ingress source location')
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', caddy['image_id'])
         and image_ids.get('/atlas-caddy') == caddy['image_id'], 'Caddy image manifest differs')
    need(caddy['binds'] == {'/etc/caddy': {'subdirectory': 'infra/caddy', 'rw': False},
                             '/srv': {'subdirectory': 'infra/caddy/site', 'rw': False}}, 'Caddy bind provenance differs')
    need(any(name.startswith('infra/caddy/') for name in archived), 'Caddy source missing')
    authority = ext['authority']
    need(authority == {'unit_path': '/etc/systemd/system/atlas-maintenance-control.service',
                       'socket': '/run/atlas-maintenance-control/control.sock',
                       'socket_uid': 0, 'socket_gid': 20000, 'socket_mode': '0660',
                       'parent_mode': '0750', 'allowed_peer_uid': 999}, 'Host authority boundary differs')
    unit = inputs['systemd/atlas-maintenance-control.service']
    need(unit.count('/opt/project-atlas-v1-main') == 2 and unit.count('/usr/bin/python3 -B -m') == 1,
         'Host authority source unit structure differs')
    unit = unit.replace('/opt/project-atlas-v1-main', source).replace('/usr/bin/python3 -B -m', '/usr/bin/python3 -P -B -m')
    need(m.read(record / 'maintenance-authority.service') == unit.encode(), 'Pinned host authority unit differs')
    gate = json.loads(m.read(record / 'ingress-release-gate.json'))
    need(set(gate) == {'schema_version', 'event', 'head_sha', 'source_tree', 'workflow_path',
                      'run_id', 'run_attempt', 'conclusion', 'jobs'}, 'Ingress release evidence fields differ')
    need(gate['schema_version'] == 1 and gate['event'] == 'push' and gate['head_sha'] == ext['released_commit']
         and gate['source_tree'] == ext['source_tree'] and gate['workflow_path'] == '.github/workflows/release-gate.yml'
         and type(gate['run_id']) is int and gate['run_id'] > 0
         and type(gate['run_attempt']) is int and gate['run_attempt'] > 0
         and gate['conclusion'] == 'success', 'Ingress release evidence identity differs')
    need(gate['jobs'] == {name: 'success' for name in ('Release Contracts', 'API', 'Portal', 'Core Python', 'Sports', 'release-gate')},
         'Ingress release jobs differ')
    return ext


def need(value, message):
    if not value:
        raise ValueError(message)


def query(args, *, data=None, timeout=30):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    need(result.returncode == 0, 'Ingress read-only runtime query failed')
    return result.stdout


def open_directory(path):
    """Open an absolute directory without following any path-component symlink."""
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'Unsafe immutable source path')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = following
        return fd
    except BaseException:
        os.close(fd)
        raise


def verify_source(source, archived, *, owner_uid=0, owner_gid=0):
    """Stream all files through directory FDs; production requires root ownership."""
    # owner arguments allow non-root filesystem fixtures; the live entry uses defaults.
    try:
        root_fd = open_directory(source)
    except OSError as exc:
        raise ValueError('Immutable Ingress source unavailable') from exc
    observed = set()

    def walk(fd, prefix=''):
        initial = os.fstat(fd)
        need(stat.S_ISDIR(initial.st_mode) and (initial.st_uid, initial.st_gid) == (owner_uid, owner_gid)
             and stat.S_IMODE(initial.st_mode) == 0o555, 'Immutable source directory metadata differs')
        for name in os.listdir(fd):
            relative = prefix + name
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(before.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'Source directory changed during open')
                    walk(child, relative + '/')
                finally:
                    os.close(child)
            else:
                need(relative in archived and stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                     'Unexpected immutable source file or link')
                row = archived[relative]
                expected_mode = 0o555 if row['executable'] else 0o444
                need((before.st_uid, before.st_gid) == (owner_uid, owner_gid)
                     and stat.S_IMODE(before.st_mode) == expected_mode, 'Immutable source file metadata differs')
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode, st.st_uid, st.st_gid, st.st_nlink)
                    need(identity(opened) == identity(before), 'Source file changed during open')
                    with os.fdopen(child, 'rb', closefd=False) as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    need(digest == row['sha256'] and identity(os.fstat(child)) == identity(opened)
                         and identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == identity(opened),
                         'Immutable source bytes or identity changed')
                finally:
                    os.close(child)
                observed.add(relative)
        final = os.fstat(fd)
        need((initial.st_dev, initial.st_ino, initial.st_mtime_ns, initial.st_ctime_ns) ==
             (final.st_dev, final.st_ino, final.st_mtime_ns, final.st_ctime_ns), 'Source directory changed during verification')

    try:
        walk(root_fd)
        need(observed == set(archived), 'Immutable source file coverage differs')
        current_fd = open_directory(source)
        try:
            first, current = os.fstat(root_fd), os.fstat(current_fd)
            need((first.st_dev, first.st_ino) == (current.st_dev, current.st_ino), 'Immutable source root was replaced')
        finally:
            os.close(current_fd)
        parent_fd = open_directory(Path(source).parent)
        try:
            parent = os.fstat(parent_fd)
            need(parent.st_uid == owner_uid and not parent.st_mode & 0o022, 'Immutable source parent is writable by other users')
        finally:
            os.close(parent_fd)
    finally:
        os.close(root_fd)


def state_identity(row):
    state = row['State']
    need(state.get('Running') is True and not any(state.get(key) for key in ('Paused', 'Restarting', 'Dead', 'OOMKilled'))
         and state.get('Health', {}).get('Status') == 'healthy', 'Ingress component is not healthy and running')
    need(type(state.get('Pid')) is int and state['Pid'] > 0, 'Ingress component process identity missing')
    return {key: row[key] for key in ('Id', 'Image', 'Name', 'Config', 'HostConfig', 'Mounts', 'RestartCount')} | {
        'State': {key: state[key] for key in ('Pid', 'StartedAt')}}


def mounts(row):
    result = {}
    for item in row['Mounts']:
        need(item['Destination'] not in result, 'Duplicate Ingress mount target')
        result[item['Destination']] = item
    return result


def overlaps(left, right):
    left, right = PurePosixPath(left), PurePosixPath(right)
    return left == right or left in right.parents or right in left.parents


def check_mount_boundaries(role, row, ext):
    mounted = mounts(row)
    if role == 'portal':
        need(not mounted, 'Portal image must not have source or host mounts')
    if role == 'api':
        read_only = ('users', 'identity/invitations', 'identity/custom_roles', 'runtime/ari',
                     'runtime/services', 'runtime/dashboard', 'runtime/downloads')
        writable = ('identity/password-recovery', 'identity/favorites', 'identity/dislikes',
                    'runtime/requests', 'runtime/sports', 'runtime/events.jsonl')
        allowed = {'/mnt/storage/configs/atlas/' + name: False for name in read_only}
        allowed.update({'/mnt/storage/configs/atlas/' + name: True for name in writable})
        allowed['/run/atlas-maintenance-control'] = False
        for destination, item in mounted.items():
            need(destination in allowed and item.get('Type') == 'bind'
                 and item.get('Source') == destination and item.get('RW') is allowed[destination],
                 'API mount is outside the bounded application state contract')
    source = ext['caddy']['immutable_source']
    if role == 'caddy':
        allowed = {'/etc/caddy': (source + '/infra/caddy', False), '/srv': (source + '/infra/caddy/site', False),
                   '/etc/atlas-maintenance': ('/mnt/storage/configs/atlas/maintenance', False),
                   '/data': ('/mnt/storage/configs/atlas/caddy/data', True),
                   '/config': ('/mnt/storage/configs/atlas/caddy/config', True),
                   '/var/log/caddy': ('/mnt/storage/configs/atlas/caddy/logs', True)}
        for destination, item in mounted.items():
            if destination in ('/tmp', '/run'):
                need(item.get('Type') == 'tmpfs', 'Caddy temporary mount differs')
                continue
            need(destination in allowed and item.get('Type') == 'bind'
                 and (item.get('Source'), item.get('RW')) == allowed[destination],
                 'Caddy mount is outside the bounded ingress contract')
        for destination, relative in (('/etc/caddy', 'infra/caddy'), ('/srv', 'infra/caddy/site')):
            item = mounted.get(destination, {})
            need(item.get('Type') == 'bind' and item.get('RW') is False
                 and item.get('Source') == source + '/' + relative, 'Caddy immutable source bind differs')
        state = mounted.get('/etc/atlas-maintenance', {})
        need(state.get('Type') == 'bind' and state.get('RW') is False
             and state.get('Source') == '/mnt/storage/configs/atlas/maintenance', 'Caddy maintenance-state bind differs')
        need(row['HostConfig'].get('ReadonlyRootfs') is True, 'Caddy root filesystem must remain read-only')
        # Nested mounts could hide verified source files even when the two top-level binds match.
        for destination in mounted:
            if destination not in ('/etc/caddy', '/srv'):
                need(not any(overlaps(destination, root) for root in ('/etc/caddy', '/srv')), 'Caddy source has an overlapping mount')
    else:
        code_roots = ('/srv', '/usr/local', '/usr', '/bin', '/lib', '/lib64', '/etc/passwd', '/etc/group', '/etc/ld.so.preload') if role == 'api' else (
            '/app', '/usr/local', '/usr', '/bin', '/lib', '/lib64', '/etc/passwd', '/etc/group', '/etc/ld.so.preload')
        for destination, item in mounted.items():
            need(not any(overlaps(destination, root) for root in code_roots), 'Application image source is hidden by a mount')
            host_source = item.get('Source', '')
            need(not any(overlaps(host_source, root) for root in (
                '/var/run/docker.sock', '/run/docker.sock', '/mnt/storage/configs/atlas/deployments',
                '/mnt/storage/configs/atlas/deployment-scheduler.lock', '/mnt/storage/configs/atlas/maintenance')),
                'Application has a host control/recovery mount')
        if role == 'api':
            item = mounted.get('/run/atlas-maintenance-control', {})
            need(item.get('Type') == 'bind' and item.get('RW') is False
                 and item.get('Source') == '/run/atlas-maintenance-control', 'API authority mount must be read-only')
            need(not any(destination != '/run/atlas-maintenance-control' and overlaps(destination, '/run/atlas-maintenance-control')
                         for destination in mounted), 'API authority mount is shadowed')
        else:
            need(not any(overlaps(destination, '/run/atlas-maintenance-control') for destination in mounted),
                 'Portal must not have host authority access')


def image_checks(m, role, row, ext, record):
    image_id = ext['images'][role]['image_id'] if role in ext['images'] else ext['caddy']['image_id']
    need(row['Image'] == image_id and row['Name'] == '/atlas-' + role, 'Ingress component image/name differs')
    host = row['HostConfig']
    need(host.get('Privileged') is False and 'no-new-privileges:true' in (host.get('SecurityOpt') or [])
         and not host.get('PidMode') == 'host' and not host.get('IpcMode') == 'host', 'Ingress execution boundary differs')
    if role in ext['images']:
        values = json.loads(query(['docker', 'image', 'inspect', image_id]))
        need(len(values) == 1 and values[0]['Id'] == image_id, 'Application image identity unavailable')
        image = values[0]
        config = image['Config']
        expected_user = 'atlas' if role == 'api' else 'nextjs'
        need(config.get('User') == row['Config'].get('User') == expected_user, 'Application default process user differs')
        for key in ('Cmd', 'Entrypoint', 'WorkingDir'):
            need(row['Config'].get(key) == config.get(key), 'Application default startup is overridden')
        labels = config.get('Labels') or {}
        expected = {'org.opencontainers.image.revision': ext['released_commit'],
                    'io.project-atlas.archive-source-commit': ext['source_archive_commit'],
                    'io.project-atlas.source-tree': ext['source_tree'],
                    'io.project-atlas.build-recipe-sha256': hashlib.sha256(m.read(record / ('ingress-' + role + '-build.Dockerfile'))).hexdigest()}
        need(all(labels.get(key) == value for key, value in expected.items()), 'Application image source labels differ')
        env = {}
        for line in row['Config'].get('Env') or []:
            key, separator, value = line.partition('=')
            need(separator and key not in env, 'Duplicate application environment key')
            env[key] = value
        need(not any(key in env for key in ('PYTHONHOME', 'PYTHONSTARTUP', 'LD_PRELOAD', 'NODE_OPTIONS', 'NODE_PATH')),
             'Application executable environment is overridden')
        if role == 'api':
            need(env.get('PYTHONPATH') == '/srv:/srv/apps/api'
                 and env.get('ATLAS_MAINTENANCE_CONTROL_SOCKET') == ext['authority']['socket'], 'API source/socket environment differs')
    else:
        values = json.loads(query(['docker', 'image', 'inspect', image_id]))
        need(len(values) == 1 and values[0]['Id'] == image_id, 'Caddy image identity unavailable')
        for key in ('Cmd', 'Entrypoint', 'WorkingDir', 'User'):
            need(row['Config'].get(key) == values[0]['Config'].get(key), 'Caddy default startup is overridden')
    check_mount_boundaries(role, row, ext)


def service_properties():
    keys = ('LoadState', 'ActiveState', 'SubState', 'FragmentPath', 'DropInPaths', 'NeedDaemonReload',
            'MainPID', 'NRestarts', 'ExecMainStartTimestampMonotonic', 'WorkingDirectory', 'User', 'Group')
    raw = query(['systemctl', 'show', 'atlas-maintenance-control.service', *['--property=' + key for key in keys]])
    result = {}
    for line in raw.decode().splitlines():
        key, separator, value = line.partition('=')
        need(separator and key in keys and key not in result, 'Invalid host authority service properties')
        result[key] = value
    need(set(result) == set(keys), 'Incomplete host authority service properties')
    return result


def authority_properties(properties, source, authority):
    expected = {'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'running',
                'FragmentPath': authority['unit_path'], 'DropInPaths': '', 'NeedDaemonReload': 'no',
                'WorkingDirectory': source, 'User': 'root', 'Group': '20000'}
    need(all(properties.get(key) == value for key, value in expected.items()), 'Host authority service contract differs')
    need(properties['MainPID'].isdigit() and int(properties['MainPID']) > 0
         and properties['ExecMainStartTimestampMonotonic'].isdigit()
         and int(properties['ExecMainStartTimestampMonotonic']) > 0
         and properties['NRestarts'].isdigit(), 'Host authority process identity unavailable')


def socket_metadata(info, parent):
    need(stat.S_ISSOCK(info.st_mode) and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (0, 20000, 0o660),
         'Host authority socket metadata differs')
    need(stat.S_ISDIR(parent.st_mode) and (parent.st_uid, parent.st_gid, stat.S_IMODE(parent.st_mode)) == (0, 20000, 0o750),
         'Host authority socket parent metadata differs')


def socket_listener(raw, path, descriptor_links):
    rows = [line.split() for line in raw.decode().splitlines()[1:]]
    matching = [row for row in rows if len(row) == 8 and row[7] == path]
    need(len(matching) == 1 and matching[0][3:6] == ['00010000', '0001', '01']
         and 'socket:[' + matching[0][6] + ']' in descriptor_links, 'Host authority does not own the listening socket')


def process_status(raw):
    fields = {}
    for line in raw.decode().splitlines():
        key, separator, value = line.partition(':')
        if separator:
            fields[key] = value.strip()
    need(fields.get('Uid', '').split() == ['0'] * 4 and fields.get('Gid', '').split() == ['20000'] * 4
         and fields.get('NoNewPrivs') == '1' and fields.get('CapEff') == fields.get('CapBnd') == '0000000000000000',
         'Host authority process credentials differ')


def verify_authority(m, record, ext):
    authority = ext['authority']
    source = ext['caddy']['immutable_source']
    path = Path(authority['unit_path'])
    parent_fd = open_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        try:
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == info.st_gid == 0
                 and stat.S_IMODE(info.st_mode) == 0o644, 'Installed host authority unit metadata differs')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(65537)
            need(raw == m.read(record / 'maintenance-authority.service'), 'Installed host authority unit bytes differ')
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    properties = service_properties()
    authority_properties(properties, source, authority)
    proc = Path('/proc') / properties['MainPID']
    before = m.read(proc / 'stat')
    process_status(m.read(proc / 'status'))
    command = m.read(proc / 'cmdline').split(b'\0')
    expected = ['/usr/bin/python3', '-P', '-B', '-m', 'atlas.maintenance_control_server',
                '--runtime-root', '/mnt/storage/configs/atlas', '--socket', authority['socket'],
                '--allowed-uid', '999', '--socket-gid', '20000']
    need(command == [part.encode() for part in expected] + [b''], 'Host authority command/source differs')
    need(os.readlink(proc / 'cwd') == source and os.readlink(proc / 'exe') == str(Path('/usr/bin/python3').resolve(strict=True)),
         'Host authority executable/working directory differs')
    environment = dict(part.split(b'=', 1) for part in m.read(proc / 'environ').split(b'\0') if part)
    need(environment.get(b'PYTHONPATH') == source.encode() and environment.get(b'PYTHONDONTWRITEBYTECODE') == b'1'
         and not any(key in environment for key in (b'PYTHONHOME', b'PYTHONSTARTUP', b'LD_PRELOAD')),
         'Host authority Python environment differs')
    socket_path = Path(authority['socket'])
    socket_fd = open_directory(socket_path.parent)
    try:
        info, parent = os.stat(socket_path.name, dir_fd=socket_fd, follow_symlinks=False), os.fstat(socket_fd)
        socket_metadata(info, parent)
        links = [os.readlink(file) for file in (proc / 'fd').iterdir()]
        socket_listener(m.read(Path('/proc/net/unix')), str(socket_path), links)
        after = os.stat(socket_path.name, dir_fd=socket_fd, follow_symlinks=False)
        need((info.st_dev, info.st_ino, info.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_ctime_ns),
             'Host authority socket changed during verification')
    finally:
        os.close(socket_fd)
    # Only field 22 is stable across process accounting changes. A fresh process must not be accepted mid-check.
    ticks = lambda raw: raw.rsplit(b')', 1)[1].split()[19]
    need(ticks(before) == ticks(m.read(proc / 'stat')) and properties == service_properties(),
         'Host authority process or service changed during verification')
    return properties


API_FILES_PROBE = r'''import hashlib,json,os,pathlib,stat,sys
expected=json.load(sys.stdin)
assert os.getuid()==999 and os.getgid()==999 and 20000 in os.getgroups()
for name,digest in expected.items():
 fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  info=os.fstat(fd)
  assert stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022
  with os.fdopen(fd,'rb',closefd=False) as stream: actual=hashlib.file_digest(stream,'sha256').hexdigest()
  assert actual==digest
 finally: os.close(fd)
actual=set()
for root in ('/srv/atlas','/srv/apps/api/atlas_api'):
 for path in pathlib.Path(root).rglob('*'):
  assert not path.is_symlink()
  if path.is_file():actual.add(str(path))
assert actual=={name for name in expected if name!='/srv/apps/api/pyproject.toml'}
'''
PORTAL_IDENTITY_PROBE = r'''const fs=require('node:fs');
const row=fs.readFileSync('/etc/passwd','utf8').split('\n').find(line=>line.startsWith('nextjs:')).split(':');
if(process.getuid()!==1001 || process.getuid()!==Number(row[2]) || process.getgid()!==Number(row[3]))process.exit(1);
'''


def check_live(m, record):
    ext = json.loads(m.read(record / 'ingress-runtime-extension.json'))
    archived = m.archive_files(record / 'ingress-application-source.tar.gz', ext['source_archive_commit'])
    verify_source(ext['caddy']['immutable_source'], archived)
    authority_before = verify_authority(m, record, ext)
    first = {}
    for role in ('api', 'portal', 'caddy'):
        row = m.inspect('atlas-' + role)
        first[role] = state_identity(row)
        image_checks(m, role, row, ext, record)
    copied = {}
    for name, row in archived.items():
        if name.startswith('atlas/'):
            copied['/srv/' + name] = row['sha256']
        elif name.startswith('apps/api/atlas_api/') or name == 'apps/api/pyproject.toml':
            copied['/srv/' + name] = row['sha256']
    need(copied and '/srv/apps/api/atlas_api/services/maintenance_access.py' in copied,
         'API packaged authority client provenance missing')
    query(['docker', 'exec', '-i', 'atlas-api', 'python3', '-I', '-B', '-c', API_FILES_PROBE],
          data=json.dumps(copied).encode(), timeout=90)
    query(['docker', 'exec', 'atlas-portal', 'node', '-e', PORTAL_IDENTITY_PROBE])
    need(verify_authority(m, record, ext) == authority_before, 'Host authority changed during Ingress verification')
    for role in first:
        need(state_identity(m.inspect('atlas-' + role)) == first[role], 'Ingress runtime changed during verification')
