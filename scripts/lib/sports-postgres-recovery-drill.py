"""Synthetic PostgreSQL restore rehearsal; not a live-state recovery command.

Run only in the pinned, isolated image with a private temporary cluster. Nothing
here imports Django, reads application settings or uses existing database state.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

MAX_DUMP_BYTES = 16 * 1024 * 1024


class DrillFailure(RuntimeError):
    pass


def require(condition, category):
    if not condition:
        raise DrillFailure(category)


def command(arguments, *, env, timeout=20):
    # Never forward a native command's output/error to an operator-facing log.
    try:
        result = subprocess.run(arguments, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise DrillFailure('command-timeout') from None
    except OSError:
        raise DrillFailure('command-unavailable') from None
    require(result.returncode == 0, 'command-failed')
    require(len(result.stdout) <= 65536, 'command-output-budget')
    return result.stdout


def strict_restore(binary, dump, database, *, env):
    require(re.fullmatch(r'atlas_drill_[a-z_]+', database) is not None, 'drill-database-name')
    info = dump.lstat()
    require(dump.is_file() and not dump.is_symlink() and info.st_nlink == 1
            and 0 < info.st_size <= MAX_DUMP_BYTES, 'drill-dump-file')
    with dump.open('rb') as source:
        require(source.read(5) == b'PGDMP', 'drill-dump-header')
    command([str(binary), '--list', str(dump)], env=env)
    # Any nonzero exit is fatal. No stderr substring can turn failure into success.
    # Single-transaction is the tested rollback boundary for the synthetic target.
    command([str(binary), '--exit-on-error', '--single-transaction', '--no-owner',
             '--no-privileges', '--dbname', database, str(dump)], env=env)


def binaries():
    root = Path('/usr/lib/postgresql')
    versions = [p for p in root.iterdir() if p.is_dir() and p.name.isdigit()]
    require(bool(versions), 'postgres-binaries')
    folder = max(versions, key=lambda p: int(p.name)) / 'bin'
    result = {name: folder / name for name in ('initdb', 'pg_ctl', 'pg_isready', 'psql', 'pg_dump', 'pg_restore')}
    require(all(path.is_file() and os.access(path, os.X_OK) for path in result.values()), 'postgres-binaries')
    return result


def drill():
    require(os.geteuid() != 0, 'nonroot-required')
    require(os.environ.get('ATLAS_SYNTHETIC_RECOVERY_DRILL') == '1', 'isolated-drill-required')
    tools = binaries()
    # Explicit private libpq settings prevent inherited app/PG variables from
    # selecting any database, network endpoint, service file or credential.
    with tempfile.TemporaryDirectory(prefix='atlas-pg-drill-', dir='/tmp') as directory:
        root = Path(directory)
        socket = root / 'socket'; socket.mkdir(mode=0o700)
        cluster = root / 'cluster'
        env = {'PATH': str(tools['psql'].parent) + ':/usr/bin:/bin',
               'HOME': str(root), 'TMPDIR': str(root), 'LANG': 'C', 'LC_ALL': 'C',
               'PGHOST': str(socket), 'PGPORT': '5432', 'PGUSER': 'atlas_recovery',
               'PGDATABASE': 'postgres', 'PGCONNECT_TIMEOUT': '3'}
        command([str(tools['initdb']), '-D', str(cluster), '--username=atlas_recovery',
                 '--auth-local=trust', '--auth-host=reject', '--no-locale', '--encoding=UTF8'], env=env)
        # Only the synthetic cluster/socket are selected; TCP is disabled.
        options = f"-k {socket} -c listen_addresses='' -c unix_socket_permissions=0700 -c shared_buffers=16MB -c max_connections=10"
        started = False
        try:
            # Mark before launch so even a timed-out startup gets a stop attempt.
            started = True
            command([str(tools['pg_ctl']), '-D', str(cluster), '-l', str(root / 'postgres.log'),
                     '-w', '-t', '15', '-o', options, 'start'], env=env, timeout=20)
            def sql(database, query):
                return command([str(tools['psql']), '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
                                '-d', database, '-c', query], env=env).decode().strip()
            for database in ('atlas_drill_source', 'atlas_drill_restored', 'atlas_drill_conflict'):
                sql('postgres', 'CREATE DATABASE ' + database)
            sql('atlas_drill_source', "CREATE TABLE aa_first(id integer PRIMARY KEY, label text); INSERT INTO aa_first VALUES(1,'fixture'); CREATE TABLE zz_conflict(id integer); INSERT INTO zz_conflict VALUES(2)")
            dump = root / 'fixture.dump'
            command([str(tools['pg_dump']), '-Fc', '--no-owner', '--no-privileges',
                     '-d', 'atlas_drill_source', '-f', str(dump)], env=env)
            strict_restore(tools['pg_restore'], dump, 'atlas_drill_restored', env=env)
            require(sql('atlas_drill_restored', 'SELECT id,label FROM aa_first') == '1|fixture', 'restore-data')
            require(sql('atlas_drill_restored', 'SELECT id FROM zz_conflict') == '2', 'restore-second-table')
            sql('atlas_drill_conflict', 'CREATE TABLE zz_conflict(id integer); INSERT INTO zz_conflict VALUES(99)')
            try:
                strict_restore(tools['pg_restore'], dump, 'atlas_drill_conflict', env=env)
            except DrillFailure:
                pass
            else:
                raise DrillFailure('conflicting-restore-accepted')
            require(sql('atlas_drill_conflict', "SELECT to_regclass('public.aa_first') IS NULL") == 't', 'partial-restore-not-rolled-back')
            require(sql('atlas_drill_conflict', 'SELECT id FROM zz_conflict') == '99', 'existing-state-not-preserved')
            corrupt = root / 'corrupt.dump'
            corrupt.write_bytes(dump.read_bytes()[:12])
            try:
                strict_restore(tools['pg_restore'], corrupt, 'atlas_drill_conflict', env=env)
            except DrillFailure:
                pass
            else:
                raise DrillFailure('corrupt-restore-accepted')
            require(sql('atlas_drill_conflict', 'SELECT id FROM zz_conflict') == '99', 'corrupt-restore-mutated-target')
        finally:
            if started:
                # A failed stop is a failed drill, never a success receipt. The
                # outer one-shot container boundary also removes all processes.
                command([str(tools['pg_ctl']), '-D', str(cluster), '-m', 'fast', '-w',
                         '-t', '10', 'stop'], env=env, timeout=15)
        return {'version': 1, 'scope': 'synthetic-isolated-postgres-only',
                'restore_data': 'pass', 'nonzero_exit_rejected': 'pass',
                'single_transaction_rollback': 'pass', 'corrupt_archive_rejected': 'pass',
                'postgres_stopped': 'pass', 'production_state_access': False}


def main():
    try:
        print(json.dumps(drill(), sort_keys=True))
    except Exception as error:
        # No raw PostgreSQL output, filesystem state or connection data escapes.
        category = str(error) if isinstance(error, DrillFailure) else type(error).__name__
        if not re.fullmatch(r'[A-Za-z-]{1,80}', category):
            category = 'internal'
        print('SYNTHETIC_POSTGRES_RECOVERY_DRILL=FAIL category=' + category, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
