"""Rehearse durable five-surface publication under private /tmp paths only.

No live path mapping, ownership conversion, service control or finalization API.
The preserved old state remains available until a separate acceptance design.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

SURFACES = ('dispatcharr-db', 'dispatcharr-jwt', 'teamarr-db',
            'sports-metadata', 'sports-metadata-policy')
DIRECTORIES = {'dispatcharr-db', 'sports-metadata', 'sports-metadata-policy'}
MAX_BYTES = 2 * 1024**3
MAX_ENTRIES = 100000


class PublicationError(ValueError):
    pass


def require(condition):
    if not condition:
        raise PublicationError('Invalid isolated Sports publication transaction')


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'),
                                                Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private(path, directory=False):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts)
    for parent in (path, *path.parents): require(not parent.is_symlink())
    info = path.lstat()
    require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o600))
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    return info


def sync(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def digest(path, directory=False):
    private(path, directory)
    entries = [path, *sorted(path.rglob('*'))] if directory else [path]
    require(len(entries) <= MAX_ENTRIES)
    result = hashlib.sha256(); total = 0
    for entry in entries:
        info = entry.lstat()
        is_dir = stat.S_ISDIR(info.st_mode)
        private(entry, is_dir)
        relative = '.' if entry == path else entry.relative_to(path).as_posix()
        result.update(relative.encode() + (b'\0d\0' if is_dir else b'\0f\0'))
        if is_dir: continue
        total += info.st_size; require(total <= MAX_BYTES)
        descriptor = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as source:
            before = os.fstat(source.fileno())
            require((before.st_ino, before.st_dev, before.st_size) == (info.st_ino, info.st_dev, info.st_size))
            size = 0
            for raw in iter(lambda: source.read(1024 * 1024), b''):
                size += len(raw); require(size <= info.st_size); result.update(raw)
            after = os.fstat(source.fileno())
            require(size == info.st_size and (after.st_mtime_ns, after.st_ctime_ns) == (info.st_mtime_ns, info.st_ctime_ns))
        result.update(b'\0')
    return result.hexdigest()


def copy(source, target, directory=False):
    before = digest(source, directory)
    if directory:
        target.mkdir(mode=0o700)
        entries = sorted(source.rglob('*'), key=lambda p: (len(p.parts), str(p)))
        for entry in entries:
            destination = target / entry.relative_to(source)
            if entry.is_dir(): destination.mkdir(mode=0o700)
            else: copy_file(entry, destination)
        for entry in sorted(target.rglob('*'), key=lambda p: -len(p.parts)):
            if entry.is_dir(): sync(entry)
        sync(target)
    else:
        copy_file(source, target)
    require(digest(source, directory) == before and digest(target, directory) == before)
    return before


def copy_file(source, target):
    private(source)
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(source_fd, 'rb') as reader:
        private(source)
        require(stat.S_ISREG(os.fstat(reader.fileno()).st_mode))
        target_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(target_fd, 'wb') as writer:
            size = 0
            for raw in iter(lambda: reader.read(1024 * 1024), b''):
                size += len(raw); require(size <= MAX_BYTES); writer.write(raw)
            writer.flush(); os.fsync(writer.fileno())


def write_json(path, value):
    temporary = path.with_name('.' + path.name + '.writing')
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    # A previous process can die while writing the scratch document. It is not
    # authoritative and may be removed only after checking its private type.
    if temporary.exists() or temporary.is_symlink():
        private(temporary); temporary.unlink()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as target:
        target.write(raw); target.flush(); os.fsync(target.fileno())
    os.replace(temporary, path); sync(path.parent)


def read_json(path):
    info = private(path); require(info.st_size <= 16384)
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value); value[key] = item
        return value
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


@contextmanager
def locked(root):
    root = Path(root)
    require(root.parent == Path('/tmp') and re.fullmatch(
        r'project-atlas-sports-publication\.[A-Za-z0-9_-]+', root.name) is not None)
    private(root, True)
    descriptor = os.open(root / 'publication.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        private(root / 'publication.lock')
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Consumer exposure transfers recovery authority to the consumption journal.
        require(not (root / 'consumption').exists() and not (root / 'consumption').is_symlink())
        private(root / 'current', True)
        # A crash can leave a surface in old/ while current/ lacks that entry.
        # The journal's position validator decides whether that absence is valid.
        require({p.name for p in (root / 'current').iterdir()} <= set(SURFACES))
        yield root
    finally:
        os.close(descriptor)


def checkpoint(name):
    """No-op seam for real process-exit tests at durable mutation boundaries."""


def stage(association_root, sandbox):
    association_root = Path(association_root)
    with locked(sandbox) as root:
        association = helper('sports-recovery-association')
        receipt = association.validate_association(association_root)
        association_hash = digest(association_root / 'ASSOCIATION.json')
        bundle = Path(receipt['bundle_root']); postgres = Path(receipt['postgres_root'])
        sources = (postgres / 'restored-cluster', bundle / 'dispatcharr/jwt',
                   bundle / 'teamarr/teamarr.db', bundle / 'sports-metadata',
                   bundle / 'sports-metadata-policy')
        transaction = root / 'transaction'
        require(not transaction.exists() and not transaction.is_symlink())
        transaction.mkdir(mode=0o700)
        for name in ('incoming', 'old'): (transaction / name).mkdir(mode=0o700)
        rows = []
        for name, source in zip(SURFACES, sources):
            is_dir = name in DIRECTORIES
            old_hash = digest(root / 'current' / name, is_dir)
            new_hash = copy(source, transaction / 'incoming' / name, is_dir)
            rows.append({'surface': name, 'old_sha256': old_hash, 'new_sha256': new_hash})
        require(association.validate_association(association_root) == receipt
                and digest(association_root / 'ASSOCIATION.json') == association_hash)
        sync(transaction / 'incoming'); sync(transaction / 'old')
        write_json(transaction / 'PLAN.json', {'version': 1, 'scope': 'isolated-only',
            'ready_for_live_apply': False, 'association_root': str(association_root),
            'association_sha256': association_hash, 'surfaces': rows})
        write_json(transaction / 'STATUS.json', {'state': 'staged'})
        sync(transaction); sync(root)
        return transaction


def load(root):
    transaction = root / 'transaction'; private(transaction, True)
    require({p.name for p in transaction.iterdir()} <= {
        'incoming', 'old', 'PLAN.json', 'STATUS.json', '.STATUS.json.writing'})
    for name in ('incoming', 'old'):
        private(transaction / name, True)
        require({p.name for p in (transaction / name).iterdir()} <= set(SURFACES))
        require((transaction / name).stat().st_dev == (root / 'current').stat().st_dev)
    plan = read_json(transaction / 'PLAN.json')
    require(isinstance(plan, dict) and set(plan) == {'version', 'scope', 'ready_for_live_apply',
        'association_root', 'association_sha256', 'surfaces'})
    require(type(plan['version']) is int and plan['version'] == 1
            and plan['scope'] == 'isolated-only' and plan['ready_for_live_apply'] is False)
    require(isinstance(plan['association_root'], str)
            and re.fullmatch('[a-f0-9]{64}', plan['association_sha256']) is not None)
    require(isinstance(plan['surfaces'], list) and len(plan['surfaces']) == len(SURFACES))
    for name, row in zip(SURFACES, plan['surfaces']):
        require(isinstance(row, dict) and set(row) == {'surface', 'old_sha256', 'new_sha256'}
                and row['surface'] == name)
        for field in ('old_sha256', 'new_sha256'):
            require(isinstance(row[field], str) and re.fullmatch('[a-f0-9]{64}', row[field]) is not None)
    status = read_json(transaction / 'STATUS.json')
    require(isinstance(status, dict) and set(status) == {'state'} and status['state'] in {
        'staged', 'applying', 'applied-awaiting-verification', 'rolling-back', 'reverted'})
    return transaction, plan, status['state']


def positions(root, transaction, rows):
    states = []
    for row in rows:
        name = row['surface']; is_dir = name in DIRECTORIES
        def value(path):
            if path.exists() or path.is_symlink(): return digest(path, is_dir)
            return None
        observed = (value(root / 'current' / name), value(transaction / 'old' / name),
                    value(transaction / 'incoming' / name))
        old, new = row['old_sha256'], row['new_sha256']
        options = [(old, None, new), (None, old, new), (new, old, None)]
        require(observed in options)
        states.append(options.index(observed))
    return states


def move(source, target):
    require(not target.exists() and not target.is_symlink())
    os.rename(source, target)
    sync(source.parent); sync(target.parent)


def apply(sandbox):
    with locked(sandbox) as root:
        transaction, plan, state = load(root)
        require(state == 'staged' and positions(root, transaction, plan['surfaces']) == [0] * 5)
        association_root = Path(plan['association_root'])
        helper('sports-recovery-association').validate_association(association_root)
        require(digest(association_root / 'ASSOCIATION.json') == plan['association_sha256'])
        write_json(transaction / 'STATUS.json', {'state': 'applying'})
        checkpoint('applying')
        try:
            for row in plan['surfaces']:
                name = row['surface']
                move(root / 'current' / name, transaction / 'old' / name)
                checkpoint('old:' + name)
                move(transaction / 'incoming' / name, root / 'current' / name)
                checkpoint('new:' + name)
            require(positions(root, transaction, plan['surfaces']) == [2] * 5)
            write_json(transaction / 'STATUS.json', {'state': 'applied-awaiting-verification'})
            checkpoint('applied')
        except Exception:
            rollback(root, transaction, plan)
            raise


def rollback(root, transaction, plan):
    states = positions(root, transaction, plan['surfaces'])
    write_json(transaction / 'STATUS.json', {'state': 'rolling-back'})
    checkpoint('rolling-back')
    for row, position in reversed(list(zip(plan['surfaces'], states))):
        name = row['surface']
        if position == 2:
            move(root / 'current' / name, transaction / 'incoming' / name)
            checkpoint('undo-new:' + name)
        if position in (1, 2):
            move(transaction / 'old' / name, root / 'current' / name)
            checkpoint('undo-old:' + name)
    require(positions(root, transaction, plan['surfaces']) == [0] * 5)
    write_json(transaction / 'STATUS.json', {'state': 'reverted'})


def recover(sandbox):
    with locked(sandbox) as root:
        transaction, plan, state = load(root)
        # No source association is required to undo. Recovery relies only on the
        # private durable plan and exact hashes of preserved old/incoming state.
        require(state in {'applying', 'applied-awaiting-verification', 'rolling-back', 'reverted'})
        if state == 'reverted':
            require(positions(root, transaction, plan['surfaces']) == [0] * 5)
        else:
            rollback(root, transaction, plan)
