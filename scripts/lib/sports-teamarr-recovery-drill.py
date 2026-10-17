"""SQLite handling for a stopped, owned synthetic Teamarr fixture only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
import time

LIMIT = 512 * 1024**2
DATABASE = 'teamarr.db'
SNAPSHOT = 'atlas-teamarr-snapshot.db'
MEMBERS = (DATABASE, DATABASE + '-wal', DATABASE + '-shm')


class DrillError(ValueError):
    pass


def require(condition):
    if not condition: raise DrillError('fixture-contract')


def file_info(path):
    for parent in (path, *path.parents): require(not parent.is_symlink())
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid()
            and not info.st_mode & 0o022 and 0 <= info.st_size <= LIMIT)
    return info


def file_hash(path):
    before = file_info(path); size = 0; digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        opened = os.fstat(source.fileno())
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino))
        for raw in iter(lambda: source.read(1024 * 1024), b''):
            size += len(raw); require(size <= LIMIT); digest.update(raw)
        after = os.fstat(source.fileno())
    require(size == before.st_size and (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_size, after.st_mtime_ns, after.st_ctime_ns))
    return (digest.hexdigest(), before.st_mode & 0o777, before.st_uid, before.st_gid)


def copy_file(source, destination):
    before = file_hash(source)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as reader:
        out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(out, 'wb') as writer:
            size = 0
            for raw in iter(lambda: reader.read(1024 * 1024), b''):
                size += len(raw); require(size <= LIMIT); writer.write(raw)
            writer.flush(); os.fsync(writer.fileno())
    require(file_hash(source) == before and file_hash(destination)[0] == before[0])


def inventory(root):
    require(root.is_dir() and not root.is_symlink() and not root.stat().st_mode & 0o022)
    journal = root / (DATABASE + '-journal')
    require(not journal.exists() and not journal.is_symlink())
    result = {}
    for name in MEMBERS:
        path = root / name
        if path.exists() or path.is_symlink(): result[name] = file_hash(path)
    require(DATABASE in result)
    return result


def validate_database(path, marker, *, immutable=False):
    connection = sqlite3.connect(path.as_uri() + '?mode=' + ('ro&immutable=1' if immutable else 'rw'),
                                 uri=True, timeout=1)
    deadline = time.monotonic() + 10
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        require(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)])
        require(connection.execute('SELECT marker FROM atlas_teamarr_probe ORDER BY id').fetchall() == [(marker,)])
    finally:
        connection.close()


def capture(root, marker):
    before = inventory(root)
    snapshot = file_hash(root / SNAPSHOT)
    # A main-file-only immutable read would ignore committed WAL content.
    # Copy the whole stopped database set, then open ONLY that detached copy.
    with tempfile.TemporaryDirectory(prefix='atlas-teamarr-cold-') as temporary:
        target = Path(temporary)
        for name in before: copy_file(root / name, target / name)
        copy_file(root / SNAPSHOT, target / SNAPSHOT)
        require(inventory(root) == before and file_hash(root / SNAPSHOT) == snapshot)
        validate_database(target / DATABASE, marker)
        validate_database(target / SNAPSHOT, 'snapshot', immutable=True)
    require(inventory(root) == before and file_hash(root / SNAPSHOT) == snapshot)
    return {'cold_set_unchanged': True, 'cold_set_valid': True,
            'snapshot_valid': True, 'copied_wal': DATABASE + '-wal' in before,
            'database_mode': format(before[DATABASE][1], '04o')}


def sync(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def restore_fixture(root):
    # Fixed private test-volume destinations only; this is not the live engine.
    capture(root, 'after-dump')
    require(not any((root / (SNAPSHOT + suffix)).exists() or (root / (SNAPSHOT + suffix)).is_symlink()
                    for suffix in ('-wal', '-shm', '-journal')))
    require(not (root / (DATABASE + '-journal')).exists()
            and not (root / (DATABASE + '-journal')).is_symlink())
    rollback = root / 'atlas-drill-rollback'
    incoming = root / '.atlas-drill-incoming.db'
    require(not rollback.exists() and not rollback.is_symlink()
            and not incoming.exists() and not incoming.is_symlink())
    copy_file(root / SNAPSHOT, incoming)
    validate_database(incoming, 'snapshot', immutable=True)
    before = inventory(root)
    rollback.mkdir(mode=0o700)
    for name in before: os.rename(root / name, rollback / name)
    sync(rollback); sync(root)
    os.rename(incoming, root / DATABASE); sync(root)
    require(inventory(rollback) == before)
    validate_database(root / DATABASE, 'snapshot', immutable=True)
    require(file_info(root / DATABASE).st_mode & 0o777 == 0o600)
    return {'restored_snapshot': True, 'old_set_preserved': True, 'restored_mode': '0600'}


def run(mode):
    require(os.geteuid() == 0 and os.getegid() == 0
            and os.environ.get('ATLAS_TEAMARR_DRILL') == '1')
    root = Path('/source')
    if mode == 'capture': result = capture(root, 'after-dump')
    elif mode == 'capture-restored': result = capture(root, 'snapshot')
    elif mode == 'restore-fixture': result = restore_fixture(root)
    else: raise DrillError('fixture-mode')
    return {'version': 1, 'scope': 'synthetic-teamarr-only', 'mode': mode,
            'production_state_access': False, 'live_restore_enabled': False, **result}


def main(mode):
    try: print(json.dumps(run(mode), sort_keys=True)); return 0
    except Exception:
        print('TEAMARR_FIXTURE_HELPER=FAIL', file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main(sys.argv[1]))
