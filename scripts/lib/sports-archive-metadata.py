"""Bind disposable five-surface recovery to one validated archive; never live restore."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SURFACES = ('sports-metadata', 'sports-metadata-policy')
MEMBERS = {'sports-metadata/metadata.sqlite': 'metadata-recovery/database.sqlite',
           'sports-metadata-policy/refresh.json': 'metadata-recovery/refresh-policy.json'}
MAX_MEMBER = 512*1024**2


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def require(value):
    if not value: raise ValueError('Isolated archive metadata recovery held')


metadata = load('archive_metadata_contracts', 'scripts/lib/sports-metadata-consumption.py')


def extract(native, archive, env, destination):
    archive, destination = Path(archive), Path(destination)
    native.workspace(destination.parent)
    require(destination.name == 'archive-metadata' and not destination.exists() and not destination.is_symlink())
    support = load('archive_metadata_validation', 'scripts/lib/sports-backup-archive.py')
    require(archive.parent == Path(env['ATLAS_BACKUP_DIR']) and support.validate(archive, env))
    before = support.sha(archive)
    destination.mkdir(mode=0o700)
    for name in SURFACES: (destination/name).mkdir(mode=0o700)
    hashes = {}
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers(); names = [row.name.rstrip('/') for row in members]
        require(len(names) == len(set(names)))
        lookup = {row.name.rstrip('/'): row for row in members}
        for name, archived in MEMBERS.items():
            row = lookup[archived]
            require(row.isfile() and row.mode == 0o600 and 0 < row.size <= MAX_MEMBER)
            descriptor = os.open(destination/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            digest = hashlib.sha256(); size = 0
            with os.fdopen(descriptor, 'wb') as out, source.extractfile(row) as stream:
                for raw in iter(lambda: stream.read(1024*1024), b''):
                    size += len(raw); require(size <= row.size); digest.update(raw); out.write(raw)
                require(size == row.size); out.flush(); os.fsync(out.fileno())
            hashes[name] = digest.hexdigest()
    # The lock is a fresh, empty process coordination file, never archived WAL/SHM.
    lock = destination/'sports-metadata/metadata.sqlite.lock'
    descriptor = os.open(lock, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    for name in SURFACES: native.pub.sync(destination/name)
    metadata.check(native, destination, 'new')
    require(support.sha(archive) == before)
    receipt = {'version': 1, 'scope': 'synthetic-extracted-archive-metadata',
        'archive_sha256': before, 'members': hashes,
        'surfaces': {name: native.pub.digest(destination/name, True) for name in SURFACES},
        'production_state_access': False, 'live_restore_enabled': False}
    native.pub.write_json(destination/'METADATA_EXTRACTED.json', receipt)
    native.pub.sync(destination)
    return receipt


def validate(native, extracted, archive_sha):
    extracted = Path(extracted)
    native.pub.private(extracted, True)
    require({path.name for path in extracted.iterdir()} == set(SURFACES)|{'METADATA_EXTRACTED.json'})
    receipt = native.pub.read_json(extracted/'METADATA_EXTRACTED.json')
    require(set(receipt) == {'version', 'scope', 'archive_sha256', 'members', 'surfaces',
                            'production_state_access', 'live_restore_enabled'})
    require(type(receipt['version']) is int and receipt['version'] == 1
        and receipt['scope'] == 'synthetic-extracted-archive-metadata'
        and receipt['archive_sha256'] == archive_sha
        and receipt['production_state_access'] is False and receipt['live_restore_enabled'] is False
        and set(receipt['members']) == set(MEMBERS) and set(receipt['surfaces']) == set(SURFACES))
    for name in SURFACES: require(native.pub.digest(extracted/name, True) == receipt['surfaces'][name])
    for name in MEMBERS: require(hashlib.sha256((extracted/name).read_bytes()).hexdigest() == receipt['members'][name])
    metadata.check(native, extracted, 'new')
    return receipt


class Rehearsal:
    """One invocation owns one extraction; hooks cannot fall back to fresh old metadata."""
    def __init__(self):
        self.extracted = None
        self.archive_sha = None
        self.installed = False

    def prepare_baseline(self, native, sandbox, baseline, base, dispatch):
        require(self.extracted is None and self.archive_sha is None)
        restore = load('archive_metadata_native_restore', 'scripts/lib/sports-archive-restore.py')
        original_load = restore.load
        def scoped_load(name, relative):
            module = original_load(name, relative)
            if name == 'archive_restore_command':
                original = module.roundtrip
                def readback(native_module, archive, env):
                    require(native_module is native and self.extracted is None)
                    digest = original(native_module, archive, env)
                    target = Path(baseline).parent/'archive-metadata'
                    receipt = extract(native, archive, env, target)
                    require(receipt['archive_sha256'] == digest)
                    self.extracted, self.archive_sha = target, digest
                    return digest
                module.roundtrip = readback
            return module
        restore.load = scoped_load
        restore.prepare_baseline(native, sandbox, baseline, base, dispatch)
        require(self.extracted is not None)
        proof = native.pub.read_json(Path(baseline)/'ARCHIVE_RESTORED.json')
        require(proof['archive_sha256'] == self.archive_sha)
        validate(native, self.extracted, self.archive_sha)
        print('SAME_ARCHIVE_NATIVE_AND_METADATA_BINDING=PASS', flush=True)

    def initialize(self, native, sandbox):
        require(self.extracted is not None and not self.installed)
        receipt = validate(native, self.extracted, self.archive_sha)
        root = native.consumer.scoped(sandbox)
        with native.pub.locked(root):
            transaction, plan, state = native.pub.load(root)
            require(state == 'applied-awaiting-verification' and not (root/'consumption').exists())
            require(not (root/'ARCHIVE_METADATA.json').exists())
            for parent in (transaction/'old', root/'current'):
                for name in SURFACES: native.pub.digest(parent/name, True)
            # Both initial generations use the archive bytes. Only the active
            # generation is later changed through real metadata consumer commits.
            for parent in (transaction/'old', root/'current'):
                for name in SURFACES:
                    shutil.rmtree(parent/name)
                    native.pub.copy(self.extracted/name, parent/name, True)
                metadata.check(native, parent, 'new')
                native.pub.sync(parent)
            for row in plan['surfaces']:
                if row['surface'] in SURFACES:
                    row['old_sha256'] = row['new_sha256'] = receipt['surfaces'][row['surface']]
            native.pub.write_json(root/'ARCHIVE_METADATA.json', receipt)
            native.pub.write_json(transaction/'PLAN.json', plan)
        self.installed = True
        print('ARCHIVE_METADATA_INSTALLED_AS_ROLLBACK_BASELINE=PASS', flush=True)

    def verify(self, native, sandbox):
        require(self.installed)
        receipt = validate(native, self.extracted, self.archive_sha)
        root = native.consumer.scoped(sandbox)
        require(native.consumer.status(root/'consumption') == 'reverted')
        require(native.pub.read_json(root/'ARCHIVE_METADATA.json') == receipt)
        for name in SURFACES:
            require(native.pub.digest(root/'current'/name, True) == receipt['surfaces'][name])
        metadata.check(native, root/'current', 'new')
        metadata.check(native, root/'consumption/quarantine', 'consumed')
        metadata.reader_probe(native, root/'current', 'new')
        metadata.reader_probe(native, root/'consumption/quarantine', 'consumed')
        print('ARCHIVED_METADATA_ALIASES_BUDGET_POLICY_AND_UID1000_READER=PASS', flush=True)

    def recover(self, native, sandbox, complete_restored):
        # Reuse the real maintenance shell controller and its held branches.
        # Validation uses the archive generation instead of the older toy baseline.
        require(self.installed)
        maintenance = load('archive_metadata_maintenance', 'scripts/lib/sports-maintenance-recovery.py')
        root = native.consumer.scoped(sandbox); pub = native.pub
        rows = pub.read_json(root/'transaction/PLAN.json')['surfaces']
        consumed = {name: pub.digest(root/'current'/name, name in pub.DIRECTORIES) for name in pub.SURFACES}
        accepted = []
        def detached(): native.fence.assert_detached(native.fence.load(root))
        def revert(): native.recover(root); native.recover(root)
        def checked():
            detached()
            require(native.consumer.status(root/'consumption') == 'reverted')
            for row in rows:
                name = row['surface']; directory = name in pub.DIRECTORIES
                require(pub.digest(root/'current'/name, directory) == row['old_sha256'])
                require(pub.digest(root/'consumption/quarantine'/name, directory) == consumed[name])
            receipt = validate(native, self.extracted, self.archive_sha)
            require(pub.read_json(root/'ARCHIVE_METADATA.json') == receipt)
            for name in SURFACES: require(pub.digest(root/'current'/name, True) == receipt['surfaces'][name])
            metadata.check(native, root/'current', 'new')
            metadata.check(native, root/'consumption/quarantine', 'consumed')
        def start(): complete_restored(); accepted.append(True)
        def ready(): require(accepted == [True]); checked()
        with tempfile.TemporaryDirectory(prefix='atlas-maint-rehearsal.', dir='/tmp') as temporary:
            result = maintenance.execute(temporary, {'stop': detached, 'revert': revert, 'validate': checked,
                'start': start, 'ready': ready, 'runtime': ready})
            require(result['success'])
        print('ARCHIVE_METADATA_MAINTENANCE_ACCEPTANCE_AND_RELEASE=PASS', flush=True)
