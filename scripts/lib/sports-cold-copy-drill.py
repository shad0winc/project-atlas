"""Acquire and restore only the stopped synthetic Dispatcharr drill volume."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


def checked_cold(adapter, cluster, tools, env, stage):
    try:
        adapter.cold_state(cluster, tools, env)
    except adapter.PrepareError as error:
        raise adapter.PrepareError(stage + '-' + str(error)) from None


def run(adapter):
    adapter.require(os.geteuid() == 1000 and os.getegid() == 1000, 'drill-identity')
    adapter.require(os.environ.get('ATLAS_COLD_COPY_DRILL') == '1', 'drill-scope')
    source = adapter.directory(Path('/source/db'))
    dump = Path('/source/atlas-cold-copy.dump')
    with tempfile.TemporaryDirectory(prefix='project-atlas-pg-prepare.', dir='/tmp') as temporary:
        workspace = Path(temporary)
        major, tools = adapter.tools_for(source)
        adapter.require(major == '17', 'drill-postgres-version')
        env = {'PATH': str(tools['psql'].parent) + ':/usr/bin:/bin', 'HOME': temporary,
               'TMPDIR': temporary, 'LANG': 'C', 'LC_ALL': 'C', 'PGUSER': 'dispatch',
               'PGDATABASE': 'atlas_cold_drill', 'PGCONNECT_TIMEOUT': '3'}
        # pg_controldata must already say clean shutdown. Neither repair nor
        # startup of the read-only volume is permitted to make that check pass.
        checked_cold(adapter, source, tools, env, 'initial-source')
        before = adapter.cluster_digest(source)
        dump_hash = adapter.archive_digest(dump)
        adapter.copy_cluster(source, workspace / 'cold-cluster')
        adapter.require(adapter.cluster_digest(source) == before, 'drill-source-changed')
        with dump.open('rb') as reader, (workspace / 'database.dump').open('xb') as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
            writer.flush(); os.fsync(writer.fileno())
        (workspace / 'database.dump').chmod(0o600)
        adapter.require(adapter.archive_digest(workspace / 'database.dump') == dump_hash
                        and adapter.archive_digest(dump) == dump_hash, 'drill-dump-changed')
        try:
            adapter.prepare(workspace, database='atlas_cold_drill', admin_role='dispatch', dump_sha256=dump_hash)
        except adapter.PrepareError as error:
            raise adapter.PrepareError('native-prepare-' + str(error)) from None
        adapter.validate_prepared(workspace)
        target = workspace / 'restored-cluster'
        socket = workspace / 'verify-socket'; socket.mkdir(mode=0o700)
        env['PGHOST'] = str(socket)
        env['PGOPTIONS'] = '-c statement_timeout=10000 -c session_preload_libraries= -c local_preload_libraries='
        options = (f"-k {socket} -c config_file={workspace / 'clone-postgresql.conf'} "
                   f"-c hba_file={workspace / 'clone-hba.conf'} -c listen_addresses='' "
                   "-c unix_socket_permissions=0700 -c shared_buffers=16MB -c max_connections=10 "
                   "-c archive_mode=off -c ssl=off -c shared_preload_libraries='' "
                   "-c session_preload_libraries='' -c local_preload_libraries='' -c external_pid_file=''")
        try:
            adapter.command([str(tools['pg_ctl']), '-D', str(target), '-l', str(workspace / 'verify.log'),
                             '-w', '-t', '20', '-o', options, 'start'], env=env, timeout=30)
            rows = adapter.command([str(tools['psql']), '-XAt', '-v', 'ON_ERROR_STOP=1',
                '-c', 'SELECT marker FROM atlas_cold_copy_probe ORDER BY id'], env=env)
            adapter.require(rows.strip() == b'snapshot', 'drill-backup-row')
        finally:
            adapter.command([str(tools['pg_ctl']), '-D', str(target), '-m', 'fast', '-w',
                             '-t', '15', 'stop'], env=env, timeout=20)
        checked_cold(adapter, target, tools, env, 'final-clone')
        checked_cold(adapter, source, tools, env, 'final-source')
        adapter.require(adapter.cluster_digest(source) == before
                        and adapter.archive_digest(dump) == dump_hash, 'drill-source-changed')
    return {'version': 1, 'scope': 'synthetic-aio-cold-copy',
            'cold_source_cleanly_stopped': True, 'cold_source_unchanged': True,
            'native_preparation_validated': True, 'backup_row_restored': True,
            'clone_stopped': True, 'production_state_access': False, 'live_restore_enabled': False}


def main(adapter):
    try:
        print(json.dumps(run(adapter), sort_keys=True))
        return 0
    except Exception as error:
        category = str(error) if isinstance(error, adapter.PrepareError) else 'helper-failed'
        # Native error categories are fixed ASCII strings; never forward tool
        # stderr, SQL, logs or arbitrary exception text.
        import re
        if re.fullmatch('[a-z-]{1,80}', category) is None: category = 'helper-failed'
        print('COLD_COPY_HELPER=FAIL category=' + category, file=sys.stderr)
        return 1


if __name__ == '__main__':
    import atlas_pg_prepare
    raise SystemExit(main(atlas_pg_prepare))
