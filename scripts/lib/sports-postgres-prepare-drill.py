"""Exercise the actual native adapter on two disposable, non-root PG clusters."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import atlas_pg_prepare as adapter


def drill():
    adapter.require(os.geteuid() != 0 and os.environ.get('ATLAS_NATIVE_PREPARE_DRILL') == '1', 'isolated-drill-required')
    with tempfile.TemporaryDirectory(prefix='project-atlas-pg-prepare.', dir='/tmp') as directory:
        root = Path(directory)
        folders = [p for p in Path('/usr/lib/postgresql').iterdir() if p.is_dir() and p.name.isdigit()]
        adapter.require(bool(folders), 'postgres-binaries')
        binary = max(folders, key=lambda p: int(p.name)) / 'bin'
        cold = root / 'cold-cluster'
        socket = root / 'source-socket'; socket.mkdir(mode=0o700)
        env = {'PATH': str(binary) + ':/usr/bin:/bin', 'HOME': str(root), 'TMPDIR': str(root),
               'LANG': 'C', 'LC_ALL': 'C', 'PGHOST': str(socket), 'PGPORT': '5432',
               'PGUSER': 'atlas_admin', 'PGDATABASE': 'postgres', 'PGCONNECT_TIMEOUT': '3'}
        adapter.command([str(binary / 'initdb'), '-D', str(cold), '--username=atlas_admin',
                         '--auth-local=trust', '--auth-host=reject', '--no-locale', '--encoding=UTF8'], env=env)
        started = False
        try:
            started = True
            adapter.command([str(binary / 'pg_ctl'), '-D', str(cold), '-l', str(root / 'source.log'),
                '-w', '-t', '15', '-o', f"-k {socket} -c listen_addresses='' -c shared_buffers=16MB -c max_connections=10", 'start'], env=env)
            def sql(database, query):
                return adapter.command([str(binary / 'psql'), '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-d', database, '-c', query], env=env).decode().strip()
            sql('postgres', 'CREATE DATABASE atlas_app')
            sql('postgres', "CREATE ROLE atlas_consumer LOGIN PASSWORD 'synthetic-drill-only'; ALTER ROLE atlas_consumer SET statement_timeout='20s'")
            sql('atlas_app', "CREATE TABLE aa_first(id integer PRIMARY KEY, label text); INSERT INTO aa_first VALUES(1,'snapshot'); CREATE TABLE zz_tail(id integer); INSERT INTO zz_tail VALUES(2); GRANT SELECT ON aa_first TO atlas_consumer")
            dump = root / 'database.dump'
            adapter.command([str(binary / 'pg_dump'), '-Fc', '--no-owner', '-d', 'atlas_app', '-f', str(dump)], env=env)
            dump.chmod(0o600)
            sql('atlas_app', "CREATE TABLE stale_after_backup(id integer); INSERT INTO stale_after_backup VALUES(99); UPDATE aa_first SET label='old-state'; INSERT INTO aa_first VALUES(3,'old-extra')")
        finally:
            if started:
                adapter.command([str(binary / 'pg_ctl'), '-D', str(cold), '-m', 'fast', '-w', '-t', '10', 'stop'], env=env)
        # A clone must not execute copied startup hooks. This deliberately invalid
        # preload is never started in the source and is preserved byte-for-byte.
        auto = cold / 'postgresql.auto.conf'
        original_auto = auto.read_bytes() + b"\nshared_preload_libraries = 'atlas_fixture_missing_library'\n"
        auto.write_bytes(original_auto)
        source_digest = adapter.cluster_digest(cold)
        digest = hashlib.sha256(dump.read_bytes()).hexdigest()
        receipt = adapter.prepare(root, database='atlas_app', admin_role='atlas_admin', dump_sha256=digest)
        adapter.require(adapter.cluster_digest(cold) == source_digest, 'source-cluster-mutated')
        adapter.require(adapter.validate_prepared(root) == receipt, 'prepared-revalidation')
        restored = root / 'restored-cluster'
        adapter.require((restored / 'postgresql.auto.conf').read_bytes() == original_auto, 'startup-config-not-preserved')
        adapter.require(receipt['prepared_cluster_sha256'] == adapter.cluster_digest(restored), 'cluster-receipt')
        second_env = {**env, 'PGHOST': str(root / 'socket'), 'PGDATABASE': 'atlas_app'}
        options = (f"-k {root / 'socket'} -c config_file={root / 'clone-postgresql.conf'} "
                   f"-c hba_file={root / 'clone-hba.conf'} -c listen_addresses='' "
                   "-c shared_preload_libraries='' -c shared_buffers=16MB -c max_connections=10")
        attempted = False
        try:
            attempted = True
            adapter.command([str(binary / 'pg_ctl'), '-D', str(restored), '-l', str(root / 'verify.log'),
                             '-w', '-t', '15', '-o', options, 'start'], env=second_env)
            def verify(query):
                return adapter.command([str(binary / 'psql'), '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
                    '-d', 'atlas_app', '-c', query], env=second_env).decode().strip()
            adapter.require(verify('SELECT id,label FROM aa_first ORDER BY id') == '1|snapshot', 'restored-fixture')
            adapter.require(verify('SELECT id FROM zz_tail') == '2', 'restored-second-fixture')
            adapter.require(verify("SELECT to_regclass('public.stale_after_backup') IS NULL") == 't', 'stale-table-survived')
            adapter.require(verify("SELECT has_table_privilege('atlas_consumer','aa_first','SELECT')") == 't', 'grant-not-restored')
        finally:
            if attempted:
                adapter.command([str(binary / 'pg_ctl'), '-D', str(restored), '-m', 'fast', '-w', '-t', '10', 'stop'], env=second_env)
        # Failure must not produce a success receipt or mutate the cold source.
        # The namespace is a fresh sibling workspace, never a live path.
        with tempfile.TemporaryDirectory(prefix='project-atlas-pg-prepare.', dir='/tmp') as failure_directory:
            failure = Path(failure_directory)
            shutil.copytree(cold, failure / 'cold-cluster')
            (failure / 'database.dump').write_bytes(dump.read_bytes()[:12]); (failure / 'database.dump').chmod(0o600)
            before = adapter.cluster_digest(failure / 'cold-cluster')
            try:
                adapter.prepare(failure, database='atlas_app', admin_role='atlas_admin',
                    dump_sha256=hashlib.sha256((failure / 'database.dump').read_bytes()).hexdigest())
            except adapter.PrepareError:
                pass
            else:
                raise adapter.PrepareError('corrupt-archive-accepted')
            adapter.require(not (failure / 'PREPARED.json').exists(), 'failed-prepare-receipt')
            adapter.require(adapter.cluster_digest(failure / 'cold-cluster') == before, 'failed-prepare-mutated-source')
        return {'version': 1, 'scope': 'synthetic-native-restore-preparation',
                'restore_data': 'pass', 'stale_objects_removed': 'pass', 'grants_restored': 'pass',
                'global_roles_preserved': 'pass', 'cold_source_unchanged': 'pass',
                'startup_hooks_isolated': 'pass', 'startup_config_preserved': 'pass',
                'corrupt_archive_rejected': 'pass', 'clusters_stopped': 'pass',
                'production_state_access': False, 'live_restore_enabled': False}


def main():
    try:
        print(json.dumps(drill(), sort_keys=True))
    except Exception as error:
        category = str(error) if isinstance(error, adapter.PrepareError) else type(error).__name__
        if not adapter.re.fullmatch('[A-Za-z-]{1,80}', category): category = 'internal'
        print('NATIVE_PREPARE_DRILL=FAIL category=' + category, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
