"""Restore an archive into a NEW private copy of an already stopped PG cluster.

No live destinations, Docker operations, application settings or credentials are
accepted. The caller supplies isolated cold-copy inputs; publication is separate.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

MAX_CLUSTER_BYTES = 2 * 1024**3
MAX_FILES = 100000
MAX_DUMP_BYTES = 512 * 1024**2
MAX_OUTPUT_BYTES = 2 * 1024**2


class PrepareError(ValueError):
    pass


def require(condition, category):
    if not condition: raise PrepareError(category)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}', value) is not None, 'identifier')
    return value


def directory(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'path')
    for parent in (path, *path.parents): require(not parent.is_symlink(), 'path-link')
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o700, 'directory')
    return path


def command(arguments, *, env, timeout=30):
    try:
        with tempfile.TemporaryFile(dir=env['TMPDIR']) as output:
            result = subprocess.run(arguments, env=env, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
            require(result.returncode == 0, 'native-command-failed')
            require(output.tell() <= MAX_OUTPUT_BYTES, 'native-output-budget')
            output.seek(0); return output.read()
    except subprocess.TimeoutExpired:
        raise PrepareError('native-deadline') from None
    except OSError:
        raise PrepareError('native-unavailable') from None


def tools_for(cluster):
    descriptor = os.open(cluster / 'PG_VERSION', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        info = os.fstat(source.fileno())
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 4, 'postgres-version')
        raw = source.read(5)
    require(re.fullmatch(rb'[0-9]{1,2}\n?', raw) is not None, 'postgres-version')
    major = raw.decode().strip()
    tools = {name: Path('/usr/lib/postgresql') / major / 'bin' / name
             for name in ('pg_ctl', 'pg_controldata', 'psql', 'pg_restore')}
    require(all(p.is_file() and os.access(p, os.X_OK) for p in tools.values()), 'postgres-binaries')
    return major, tools


def cold_state(cluster, tools, env):
    require(not (cluster / 'postmaster.pid').exists() and not (cluster / 'postmaster.pid').is_symlink(), 'cluster-not-cold')
    output = command([str(tools['pg_controldata']), str(cluster)], env=env).decode()
    states = re.findall(r'^Database cluster state:\s*(.+)$', output, re.M)
    require(states == ['shut down'], 'cluster-not-cleanly-stopped')


def copy_cluster(source, target):
    total = 0; count = 0
    entries = []
    for path in source.rglob('*'):
        info = path.lstat(); count += 1
        require(count <= MAX_FILES and not stat.S_ISLNK(info.st_mode), 'cluster-entry-budget-or-link')
        require(info.st_uid == os.geteuid(), 'cluster-owner')
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
            require(info.st_nlink == 1 and total <= MAX_CLUSTER_BYTES, 'cluster-file-budget')
        else:
            require(stat.S_ISDIR(info.st_mode), 'cluster-entry-kind')
        entries.append((path.relative_to(source), info))
    target.mkdir(mode=0o700)
    for relative, before in sorted(entries, key=lambda item: (len(item[0].parts), str(item[0]))):
        destination = target / relative; original = source / relative
        if stat.S_ISDIR(before.st_mode):
            destination.mkdir(mode=0o700)
            continue
        descriptor = os.open(original, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as reader, destination.open('xb') as writer:
            current = os.fstat(reader.fileno())
            require((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_ctime_ns)
                    == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns), 'cold-source-changed')
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            after = os.fstat(reader.fileno())
            require((after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                    == (before.st_size, before.st_mtime_ns, before.st_ctime_ns), 'cold-source-changed')
            writer.flush(); os.fsync(writer.fileno())
        destination.chmod(0o600)


def cluster_digest(root):
    digest = hashlib.sha256(); total = 0; count = 0
    for path in sorted(root.rglob('*')):
        info = path.lstat(); count += 1
        require(count <= MAX_FILES and not stat.S_ISLNK(info.st_mode), 'cluster-entry-budget-or-link')
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative + b'\0')
        if stat.S_ISDIR(info.st_mode):
            digest.update(b'd\0'); continue
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'cluster-entry-kind')
        total += info.st_size; require(total <= MAX_CLUSTER_BYTES, 'cluster-file-budget')
        digest.update(b'f\0')
        with path.open('rb') as source:
            for raw in iter(lambda: source.read(1024 * 1024), b''): digest.update(raw)
        digest.update(b'\0')
    return digest.hexdigest()


def archive_plan(raw):
    require(isinstance(raw, bytes) and len(raw) <= MAX_OUTPUT_BYTES, 'archive-list-budget')
    text = raw.decode()
    schema_rows = re.findall(r'^\d+;\s+\d+\s+\d+\s+SCHEMA\s+-\s+(\S+)\s', text, re.M)
    require(all(name == 'public' for name in schema_rows) and len(schema_rows) <= 1, 'unsupported-archive-schema')
    # This adapter deliberately supports ordinary public-schema Django tables.
    # Quoted/nonstandard names and other schemas need a separate reviewed contract.
    tables = re.findall(r'^\d+;\s+\d+\s+\d+\s+TABLE\s+public\s+(\S+)\s', text, re.M)
    require(bool(tables) and len(tables) <= 10000 and len(set(tables)) == len(tables), 'archive-tables')
    for table in tables: identifier(table)
    other_tables = re.findall(r'^\d+;\s+\d+\s+\d+\s+TABLE\s+(?!DATA\s|ATTACH\s)(\S+)\s', text, re.M)
    require(all(schema == 'public' for schema in other_tables), 'unsupported-archive-schema')
    return bool(schema_rows), sorted(tables)


def archive_digest(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        before = os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.geteuid()
                and stat.S_IMODE(before.st_mode) == 0o600 and 5 < before.st_size <= MAX_DUMP_BYTES, 'dump-file')
        require(source.read(5) == b'PGDMP', 'dump-header'); source.seek(0)
        digest = hashlib.sha256(); size = 0
        for raw in iter(lambda: source.read(1024 * 1024), b''):
            size += len(raw); require(size <= MAX_DUMP_BYTES, 'dump-file'); digest.update(raw)
        after = os.fstat(source.fileno())
        require((size, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                == (before.st_size, before.st_size, before.st_mtime_ns, before.st_ctime_ns), 'dump-changed')
    return digest.hexdigest()


def prepare(workspace, *, database, admin_role, dump_sha256):
    require(os.geteuid() != 0, 'nonroot-required')
    database = identifier(database); admin_role = identifier(admin_role)
    workspace = directory(workspace)
    require(workspace.parent == Path('/tmp') and re.fullmatch(r'project-atlas-pg-prepare\.[A-Za-z0-9_-]+', workspace.name) is not None, 'workspace')
    source = directory(workspace / 'cold-cluster')
    target = workspace / 'restored-cluster'
    require(not target.exists() and not target.is_symlink() and not (workspace / 'PREPARED.json').exists() and not (workspace / 'PREPARED.json').is_symlink(), 'target-exists')
    dump = workspace / 'database.dump'
    require(isinstance(dump_sha256, str) and re.fullmatch('[a-f0-9]{64}', dump_sha256) is not None, 'dump-digest')
    require(archive_digest(dump) == dump_sha256, 'dump-digest')
    major, tools = tools_for(source)
    socket = workspace / 'socket'; socket.mkdir(mode=0o700)
    env = {'PATH': str(tools['psql'].parent) + ':/usr/bin:/bin', 'HOME': str(workspace),
           'TMPDIR': str(workspace), 'LANG': 'C', 'LC_ALL': 'C', 'PGHOST': str(socket),
           'PGPORT': '5432', 'PGUSER': admin_role, 'PGDATABASE': database,
           'PGCONNECT_TIMEOUT': '3', 'PGOPTIONS': '-c statement_timeout=10000 -c session_preload_libraries= -c local_preload_libraries='}
    cold_state(source, tools, env)
    toc = command([str(tools['pg_restore']), '--list', str(dump)], env=env)
    schema_in_dump, expected_tables = archive_plan(toc)
    schema_creates_public = False
    if schema_in_dump:
        rows = re.findall(r'^\d+;\s+\d+\s+\d+\s+SCHEMA\s+-\s+public\s+[^\n]+$', toc.decode(), re.M)
        require(len(rows) == 1, 'archive-schema-row')
        selection = workspace / 'schema.list'
        selection.write_text(rows[0] + '\n'); selection.chmod(0o600)
        schema_sql = command([str(tools['pg_restore']), '--schema-only', '--no-owner', '--no-privileges',
                              '--no-comments', '--use-list', str(selection), str(dump)], env=env)
        schema_creates_public = bool(re.search(rb'^\s*CREATE\s+SCHEMA\s+(?:public|"public")(?:\s|;)', schema_sql, re.M | re.I))
    source_fingerprint = cluster_digest(source)
    copy_cluster(source, target)
    cold_state(source, tools, env)
    # Trust applies only to a private Unix socket in the isolated clone helper.
    # TCP is disabled; the original cluster's auth/config files are not changed.
    hba = workspace / 'clone-hba.conf'; hba.write_text('local all all trust\n'); hba.chmod(0o600)
    # Never start the clone with source includes, preload hooks, replication or
    # archive commands. Retain its production config bytes for later publication.
    parked = {}
    for name in ('postgresql.auto.conf', 'postmaster.opts'):
        path = target / name
        if path.exists():
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536, 'cluster-startup-config')
            parked[name] = path.read_bytes()
    (target / 'postgresql.auto.conf').write_bytes(b'')
    (target / 'postgresql.auto.conf').chmod(0o600)
    config = workspace / 'clone-postgresql.conf'
    config.write_text('')
    config.chmod(0o600)
    options = (f"-k {socket} -c config_file={config} -c listen_addresses='' -c unix_socket_permissions=0700 "
               f"-c hba_file={hba} -c shared_buffers=16MB -c max_connections=10 "
               "-c archive_mode=off -c ssl=off -c shared_preload_libraries='' "
               "-c session_preload_libraries='' -c local_preload_libraries='' -c external_pid_file=''")
    attempted = False
    try:
        attempted = True
        command([str(tools['pg_ctl']), '-D', str(target), '-l', str(workspace / 'clone.log'),
                 '-w', '-t', '20', '-o', options, 'start'], env=env, timeout=30)
        def sql(query):
            return command([str(tools['psql']), '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
                            '-d', database, '-c', query], env=env).decode().strip()
        require(sql('SELECT rolsuper FROM pg_roles WHERE rolname=current_user') == 't', 'admin-role-required')
        require(sql("SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','pg_catalog','information_schema') AND nspname NOT LIKE 'pg_%'") == '0', 'unsupported-current-schema')
        role_query = "SELECT json_build_object('roles',(SELECT json_agg(t ORDER BY t.oid) FROM pg_authid t),'members',(SELECT json_agg(t ORDER BY t.roleid,t.member,t.grantor) FROM pg_auth_members t),'settings',(SELECT json_agg(t ORDER BY t.setdatabase,t.setrole) FROM pg_db_role_setting t))::text"
        role_fingerprint = hashlib.sha256(sql(role_query).encode()).hexdigest()
        properties_query = "SELECT row_to_json(t)::text FROM (SELECT datname,datdba,encoding,datcollate,datctype,dattablespace,datconnlimit,datallowconn,datacl FROM pg_database WHERE datname=current_database()) t"
        properties = sql(properties_query)
        # Only the newly copied cluster is touched. Dropping public here removes
        # stale objects absent from the archive. No upstream permissive helper runs.
        sql('DROP SCHEMA IF EXISTS public CASCADE')
        if not schema_creates_public: sql('CREATE SCHEMA public AUTHORIZATION "' + admin_role + '"')
        command([str(tools['pg_restore']), '--exit-on-error', '--single-transaction',
                 '--no-owner', '--dbname', database, str(dump)], env=env, timeout=120)
        actual = json.loads(sql("SELECT coalesce(json_agg(c.relname ORDER BY c.relname),'[]'::json)::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p')"))
        require(actual == expected_tables, 'restored-table-set')
        require(hashlib.sha256(sql(role_query).encode()).hexdigest() == role_fingerprint, 'global-roles-changed')
        require(sql(properties_query) == properties, 'database-properties-changed')
    finally:
        if attempted:
            command([str(tools['pg_ctl']), '-D', str(target), '-m', 'fast', '-w', '-t', '15', 'stop'], env=env, timeout=20)
    cold_state(target, tools, env)
    cold_state(source, tools, env)
    for name in ('postgresql.auto.conf', 'postmaster.opts'):
        path = target / name
        if name in parked:
            path.write_bytes(parked[name]); path.chmod(0o600)
        elif path.exists():
            path.unlink()
    require(cluster_digest(source) == source_fingerprint, 'cold-source-changed')
    receipt = {'version': 1, 'state': 'native-prepared-not-live-ready', 'postgres_major': major,
               'source_dump_sha256': dump_sha256, 'source_cold_cluster_sha256': source_fingerprint,
               'application_database': database, 'admin_role': admin_role, 'global_roles_preserved': True,
               'database_properties_preserved': True, 'table_set_verified': True,
               'cluster_stopped': True, 'ready_for_live_apply': False,
               'prepared_cluster_sha256': cluster_digest(target)}
    descriptor = os.open(workspace / 'PREPARED.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        json.dump(receipt, output, sort_keys=True); output.write('\n'); output.flush(); os.fsync(output.fileno())
    return receipt


def validate_prepared(workspace):
    workspace = directory(workspace)
    require(workspace.parent == Path('/tmp') and re.fullmatch(r'project-atlas-pg-prepare\.[A-Za-z0-9_-]+', workspace.name) is not None, 'workspace')
    path = workspace / 'PREPARED.json'
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        info = os.fstat(source.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 16384, 'receipt-file')
        raw = source.read(16385)
    require(len(raw) <= 16384, 'receipt-file')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'receipt-duplicate')
            result[key] = value
        return result
    receipt = json.loads(raw, object_pairs_hook=unique)
    require(isinstance(receipt, dict) and set(receipt) == {
        'version', 'state', 'postgres_major', 'source_dump_sha256',
        'source_cold_cluster_sha256', 'application_database', 'admin_role',
        'global_roles_preserved', 'database_properties_preserved', 'table_set_verified',
        'cluster_stopped', 'ready_for_live_apply', 'prepared_cluster_sha256'}, 'receipt-fields')
    require(type(receipt['version']) is int and receipt['version'] == 1
            and receipt['state'] == 'native-prepared-not-live-ready'
            and receipt['ready_for_live_apply'] is False, 'receipt-state')
    identifier(receipt['application_database']); identifier(receipt['admin_role'])
    for field in ('global_roles_preserved', 'database_properties_preserved', 'table_set_verified', 'cluster_stopped'):
        require(receipt[field] is True, 'receipt-state')
    for field in ('source_dump_sha256', 'source_cold_cluster_sha256', 'prepared_cluster_sha256'):
        require(isinstance(receipt[field], str) and re.fullmatch('[a-f0-9]{64}', receipt[field]) is not None, 'receipt-digest')
    require(archive_digest(workspace / 'database.dump') == receipt['source_dump_sha256'], 'receipt-dump-changed')
    source = directory(workspace / 'cold-cluster'); target = directory(workspace / 'restored-cluster')
    major, tools = tools_for(target)
    require(receipt['postgres_major'] == major, 'receipt-version')
    env = {'PATH': str(tools['pg_ctl'].parent) + ':/usr/bin:/bin', 'HOME': str(workspace),
           'TMPDIR': str(workspace), 'LANG': 'C', 'LC_ALL': 'C'}
    cold_state(source, tools, env); cold_state(target, tools, env)
    require(cluster_digest(source) == receipt['source_cold_cluster_sha256']
            and cluster_digest(target) == receipt['prepared_cluster_sha256'], 'receipt-cluster-changed')
    return receipt
