"""Import detached native fixture writes into the cooperative recovery journal.

Root-only CT fixture controller. No live destinations or production volume names.
Teamarr sidecars are captured together and folded into a detached SQLite backup.
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

_spec = importlib.util.spec_from_file_location('native_consumption_fence',
    Path(__file__).with_name('sports-recovery-lifecycle.py'))
fence = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fence)
consumer = fence.consumption
pub = consumer.publication
NATIVE = ('dispatcharr-db', 'dispatcharr-jwt', 'teamarr-db')
MAX_BYTES = 2 * 1024**3
MAX_ENTRIES = 100000
MARKERS = {'after-dump', 'native-consumer-committed'}


def require(value):
    if not value: raise ValueError('Isolated native consumption contract held')


def workspace(path):
    path = Path(path)
    require(path.parent == Path('/tmp') and re.fullmatch('project-atlas-native-consumption\\.[a-f0-9]{32}', path.name))
    pub.private(path, True)
    require(os.geteuid() == 0 and os.getegid() == 0)
    return path


def parents_safe(path):
    for parent in (path, *path.parents): require(not parent.is_symlink())


def shape(path, directory=False, owner=None):
    parents_safe(path)
    entries = [path, *sorted(path.rglob('*'))] if directory else [path]
    require(len(entries) <= MAX_ENTRIES); rows = {}; total = 0
    for item in entries:
        parents_safe(item); info = item.lstat(); is_dir = stat.S_ISDIR(info.st_mode)
        require(is_dir or stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        require(not stat.S_IMODE(info.st_mode) & 0o022)
        if owner is not None: require((info.st_uid, info.st_gid) == owner)
        name = '.' if item == path else item.relative_to(path).as_posix()
        if is_dir: rows[name] = ['directory']; continue
        total += info.st_size; require(total <= MAX_BYTES)
        digest = hashlib.sha256(); count = 0
        fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            require((opened.st_ino, opened.st_dev, opened.st_size) == (info.st_ino, info.st_dev, info.st_size))
            for raw in iter(lambda: stream.read(1024*1024), b''):
                count += len(raw); require(count <= info.st_size); digest.update(raw)
            after = os.fstat(stream.fileno())
        require(count == info.st_size and (after.st_mtime_ns, after.st_ctime_ns) == (info.st_mtime_ns, info.st_ctime_ns))
        rows[name] = ['file', count, digest.hexdigest()]
    return rows


def copy_tree(source, target, directory=False, source_owner=None, target_owner=(0, 0)):
    before = shape(source, directory, source_owner)
    require(not target.exists() and not target.is_symlink()); parents_safe(target.parent)
    if directory:
        target.mkdir(mode=0o700)
        for path in sorted(source.rglob('*'), key=lambda p: (len(p.parts), str(p))):
            out = target/path.relative_to(source)
            if path.is_dir(): out.mkdir(mode=0o700)
            else: copy_tree(path, out, source_owner=source_owner, target_owner=target_owner)
        for path in [*sorted(target.rglob('*'), key=lambda p: -len(p.parts)), target]:
            if path.is_dir():
                path.chmod(0o700); os.chown(path, *target_owner); pub.sync(path)
    else:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as writer, source.open('rb') as reader:
            shutil.copyfileobj(reader, writer, 1024*1024); writer.flush(); os.fsync(writer.fileno())
            os.fchown(writer.fileno(), *target_owner); os.fsync(writer.fileno())
    pub.sync(target.parent)
    require(shape(source, directory, source_owner) == before and shape(target, directory, target_owner) == before)


def volume_path(identifier, role, detached=True):
    data = fence.volume(identifier, role)
    info = json.loads(fence.command('info', '--format', '{{json .}}'))
    require(not any('userns' in value for value in info.get('SecurityOptions', [])))
    docker_root = Path(info['DockerRootDir'])
    require(docker_root.is_absolute() and '..' not in docker_root.parts)
    item = json.loads(fence.command('volume', 'inspect', data))[0]
    path = Path(item['Mountpoint'])
    require(path == docker_root/'volumes'/data/'_data')
    parents_safe(path); require(path.is_dir())
    if detached: require(not fence.references(data))
    return path


def cold_set(source):
    require(not (source/'teamarr.db-journal').exists() and not (source/'teamarr.db-journal').is_symlink())
    names = ['teamarr.db']
    for suffix in ('-wal', '-shm'):
        path = source/('teamarr.db'+suffix)
        if path.exists() or path.is_symlink(): names.append(path.name)
    require('teamarr.db-shm' not in names or 'teamarr.db-wal' in names)
    return {name: shape(source/name, owner=(0, 0)) for name in names}


def sqlite_snapshot(source, target, marker):
    require(marker in MARKERS)
    before = cold_set(source)
    require(all((source/name).stat().st_size <= 512*1024**2 for name in before))
    with tempfile.TemporaryDirectory(prefix='sqlite-cold.', dir=target.parent) as temporary:
        copied = Path(temporary)
        for name in before: copy_tree(source/name, copied/name, source_owner=(0, 0))
        connection = sqlite3.connect(copied/'teamarr.db', timeout=2)
        output = sqlite3.connect(target, timeout=2)
        deadline = time.monotonic()+30
        def progress(*unused):
            require(time.monotonic() < deadline)
            return 0
        connection.set_progress_handler(progress, 10000)
        try:
            require(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)])
            require(connection.execute('SELECT marker FROM atlas_teamarr_probe ORDER BY id').fetchall() == [(marker,)])
            connection.backup(output, pages=256, progress=progress, sleep=0.01)
            require(output.execute('PRAGMA journal_mode=DELETE').fetchone() == ('delete',))
        finally: output.close(); connection.close()
    require(not any(target.with_name(target.name+suffix).exists() for suffix in ('-wal', '-shm', '-journal')))
    target.chmod(0o600)
    with target.open('rb') as stream: os.fsync(stream.fileno())
    # Validate a detached snapshot, never the original stopped main file alone.
    with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1', uri=True) as connection:
        require(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)])
        require(connection.execute('SELECT marker FROM atlas_teamarr_probe ORDER BY id').fetchall() == [(marker,)])
    require(cold_set(source) == before); pub.sync(target.parent)
    return 'teamarr.db-wal' in before


def capture(sandbox, destination, marker):
    root = consumer.scoped(sandbox); destination = Path(destination)
    workspace(destination.parent); require(destination.name in {'baseline', 'captured'})
    with consumer.file_lock(root/'docker-lifecycle.lock'):
        ledger = fence.load(root); fence.assert_detached(ledger)
        require(not destination.exists() and not destination.is_symlink()); destination.mkdir(mode=0o700)
        dispatch = volume_path(ledger['identifier'], 'dispatcharr')
        team = volume_path(ledger['identifier'], 'teamarr')
        shape(dispatch/'db', True, (1000, 1000))
        require((dispatch/'db/PG_VERSION').stat().st_size <= 16
            and (dispatch/'db/PG_VERSION').read_text().strip() == '17')
        require(not (dispatch/'db/postmaster.pid').exists() and not (dispatch/'db/postmaster.pid').is_symlink())
        jwt = dispatch/'jwt'; shape(jwt, owner=(0, 0)); require(stat.S_IMODE(jwt.stat().st_mode) == 0o600 and 0 < jwt.stat().st_size <= 16384)
        copy_tree(dispatch/'db', destination/'dispatcharr-db', True, (1000, 1000))
        copy_tree(jwt, destination/'dispatcharr-jwt', source_owner=(0, 0))
        wal = sqlite_snapshot(team, destination/'teamarr-db', marker)
        fence.assert_detached(ledger)
        pub.write_json(destination/'CAPTURE.json', {'version': 1, 'marker': marker, 'copied_wal': wal,
            'ledger_sha256': consumer.document_sha(root/'DOCKER_LIFECYCLE.json'),
            'surfaces': {name: pub.digest(destination/name, name == 'dispatcharr-db') for name in NATIVE}})
        pub.sync(destination); pub.sync(destination.parent)


def materialize(source, identifier):
    source = Path(source); pub.private(source, True)
    require(source.name in {'baseline', 'current'} and (
        source.parent.parent == Path('/tmp') or source.parent == Path('/tmp')))
    if source.name == 'baseline': workspace(source.parent)
    else: consumer.scoped(source.parent)
    # Validate all inputs and both empty, unreferenced targets before copying.
    for name in NATIVE: pub.digest(source/name, name == 'dispatcharr-db')
    targets = {role: volume_path(identifier, role) for role in fence.IMAGES}
    require(all(not any(path.iterdir()) for path in targets.values()))
    copy_tree(source/'dispatcharr-db', targets['dispatcharr']/'db', True, (0, 0), (1000, 1000))
    copy_tree(source/'dispatcharr-jwt', targets['dispatcharr']/'jwt', source_owner=(0, 0))
    copy_tree(source/'teamarr-db', targets['teamarr']/'teamarr.db', source_owner=(0, 0))
    require({p.name for p in targets['teamarr'].iterdir()} == {'teamarr.db'})
    for role in fence.IMAGES: require(not fence.references(fence.names(identifier, role)[1]))


def install_baseline(journal, baseline):
    root = consumer.scoped(journal); baseline = Path(baseline); workspace(baseline.parent)
    require(baseline.name == 'baseline')
    # Diagnostic fixture PLAN has not been exposed to any writer yet.
    require(not (root/'consumption').exists() and not (root/'consumption').is_symlink())
    transaction, plan, state = pub.load(root)
    require(state == 'applied-awaiting-verification')
    for parent in (root/'current', transaction/'old'):
        for name in NATIVE:
            target = parent/name
            if target.is_dir(): shutil.rmtree(target)
            else: target.unlink()
            copy_tree(baseline/name, target, name == 'dispatcharr-db', (0, 0))
    for row in plan['surfaces']:
        name = row['surface']; directory = name in pub.DIRECTORIES
        row['old_sha256'] = pub.digest(transaction/'old'/name, directory)
        row['new_sha256'] = pub.digest(root/'current'/name, directory)
    pub.write_json(transaction/'PLAN.json', plan)
    pub.sync(root/'current'); pub.sync(transaction/'old'); pub.sync(root)


def import_writes(journal, captured):
    root = consumer.scoped(journal); captured = Path(captured); workspace(captured.parent)
    require(captured.name == 'captured')
    with consumer.file_lock(root/'docker-lifecycle.lock'):
        ledger = fence.load(root); fence.assert_detached(ledger)
        receipt = pub.read_json(captured/'CAPTURE.json')
        require(receipt['version'] == 1 and receipt['marker'] == 'native-consumer-committed'
            and receipt['ledger_sha256'] == consumer.document_sha(root/'DOCKER_LIFECYCLE.json')
            and set(receipt['surfaces']) == set(NATIVE))
        for name in NATIVE: require(pub.digest(captured/name, name == 'dispatcharr-db') == receipt['surfaces'][name])
        directory = root/'NATIVE_IMPORT'; require(not directory.exists() and not directory.is_symlink())
        with consumer.writer(root) as current:
            directory.mkdir(mode=0o700); (directory/'previous').mkdir(mode=0o700)
            pub.write_json(directory/'RECEIPT.json', receipt)
            pub.write_json(directory/'STATUS.json', {'state': 'importing'}); pub.sync(root)
            # A partial import is deliberately held, never guessed or recovered
            # automatically. Complete evidence is required before native undo.
            for name in NATIVE:
                pub.move(current/name, directory/'previous'/name)
                copy_tree(captured/name, current/name, name == 'dispatcharr-db', (0, 0))
            fence.assert_detached(ledger)
            pub.write_json(directory/'STATUS.json', {'state': 'imported'})


def recover(journal):
    root = consumer.scoped(journal)
    with consumer.file_lock(root/'docker-lifecycle.lock'):
        ledger = fence.load(root); fence.assert_detached(ledger)
        directory = root/'NATIVE_IMPORT'; pub.private(directory, True)
        require({p.name for p in directory.iterdir()} == {'RECEIPT.json', 'STATUS.json', 'previous'})
        require(pub.read_json(directory/'STATUS.json') == {'state': 'imported'})
        receipt = pub.read_json(directory/'RECEIPT.json')
        require(receipt['ledger_sha256'] == consumer.document_sha(root/'DOCKER_LIFECYCLE.json'))
        state = consumer.load(root)[3]
        # Seal under the cooperative EX fence first. Once sealed, new writers
        # are refused; validate native receipt hashes before the first undo.
        if state in {'open', 'sealing', 'sealed'}: consumer.seal(root)
        sealed = consumer.sealed_rows(root/'consumption', consumer.load(root)[2])
        require(all(row['consumed_sha256'] == receipt['surfaces'][row['surface']] for row in sealed if row['surface'] in NATIVE))
        consumer.recover(root); fence.assert_detached(ledger)
