"""Prepare only synthetic PG state into a separate, disposable AIO volume."""
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


def run(adapter, mode, expected=None):
    adapter.require(os.geteuid() == 1000 and os.getegid() == 1000, 'drill-identity')
    adapter.require(os.environ.get('ATLAS_DISPATCHARR_DRILL') == '1', 'drill-scope')
    adapter.require(mode in {'prepare', 'verify'}, 'drill-mode')
    adapter.require((mode == 'prepare' and expected is None) or
                    (mode == 'verify' and isinstance(expected, str) and
                     re.fullmatch('[a-f0-9]{64}', expected) is not None), 'drill-digest')
    source = adapter.directory(Path('/source/db'))
    major, tools = adapter.tools_for(source)
    adapter.require(major == '17', 'drill-version')
    env = {'PATH': str(tools['pg_ctl'].parent) + ':/usr/bin:/bin', 'HOME': '/tmp',
           'TMPDIR': '/tmp', 'LANG': 'C', 'LC_ALL': 'C'}
    adapter.cold_state(source, tools, env)
    before = adapter.cluster_digest(source)
    dump = Path('/source/atlas-cold-copy.dump')
    dump_hash = adapter.archive_digest(dump)
    if mode == 'prepare':
        target = adapter.directory(Path('/target'))
        adapter.require(not any(target.iterdir()), 'drill-target-not-empty')
        with tempfile.TemporaryDirectory(prefix='project-atlas-pg-prepare.', dir='/tmp') as temporary:
            workspace = Path(temporary)
            adapter.copy_cluster(source, workspace / 'cold-cluster')
            with dump.open('rb') as reader, (workspace / 'database.dump').open('xb') as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
                writer.flush(); os.fsync(writer.fileno())
            (workspace / 'database.dump').chmod(0o600)
            adapter.require(adapter.archive_digest(workspace / 'database.dump') == dump_hash, 'drill-dump-changed')
            adapter.prepare(workspace, database='atlas_cold_drill', admin_role='dispatch', dump_sha256=dump_hash)
            receipt = adapter.validate_prepared(workspace)
            adapter.copy_cluster(workspace / 'restored-cluster', target / 'db')
            adapter.require(adapter.cluster_digest(target / 'db') == receipt['prepared_cluster_sha256'], 'drill-copy-changed')
            adapter.cold_state(target / 'db', tools, env)
            fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try: os.fsync(fd)
            finally: os.close(fd)
    else:
        adapter.require(before == expected, 'drill-source-changed')
        adapter.cold_state(adapter.directory(Path('/target/db')), tools, env)
    adapter.cold_state(source, tools, env)
    adapter.require(adapter.cluster_digest(source) == before
                    and adapter.archive_digest(dump) == dump_hash, 'drill-source-changed')
    return {'version': 1, 'scope': 'synthetic-dispatcharr-only', 'mode': mode,
            'source_sha256': before, 'dump_sha256': dump_hash,
            'cold_source_unchanged': True, 'restored_cluster_stopped': True,
            'production_state_access': False, 'live_restore_enabled': False}


def main(adapter):
    try:
        adapter.require(len(sys.argv) in (2, 3), 'drill-arguments')
        print(json.dumps(run(adapter, sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None), sort_keys=True))
        return 0
    except Exception as error:
        category = str(error) if isinstance(error, adapter.PrepareError) else 'helper-failed'
        if re.fullmatch('[a-z-]{1,80}', category) is None: category = 'helper-failed'
        print('DISPATCHARR_FIXTURE_HELPER=FAIL category=' + category, file=sys.stderr)
        return 1


if __name__ == '__main__':
    import atlas_pg_prepare
    raise SystemExit(main(atlas_pg_prepare))
