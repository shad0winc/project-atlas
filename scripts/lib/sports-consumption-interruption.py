"""SIGKILL recovery cases on private copies of the complete native/metadata journal."""
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import signal
import tempfile

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('interruption_metadata', ROOT/'scripts/lib/sports-metadata-consumption.py')
metadata = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(metadata)


def require(value):
    if not value: raise ValueError('Combined recovery interruption rehearsal held')


def boundaries(native):
    return ('sealing', 'seal-written', 'sealed', 'rolling-back',
        *('quarantine:'+name for name in native.pub.SURFACES),
        *('restore:'+name for name in native.pub.SURFACES), 'reverted')


def child_recover(native, root, boundary):
    def die(name):
        if name == boundary: os.kill(os.getpid(), signal.SIGKILL)
    native.consumer.checkpoint = die
    try: native.recover(root)
    except BaseException: os._exit(2)
    os._exit(0)


def verify(native, root, old_rows, consumed):
    require(native.consumer.status(root/'consumption') == 'reverted')
    require(not any((root/'transaction/old').iterdir()) and not any((root/'transaction/incoming').iterdir()))
    for row in old_rows:
        name = row['surface']; directory = name in native.pub.DIRECTORIES
        require(native.pub.digest(root/'current'/name, directory) == row['old_sha256'])
        require(native.pub.digest(root/'consumption/quarantine'/name, directory) == consumed[name])
    metadata.check(native, root/'current', 'old')
    metadata.check(native, root/'consumption/quarantine', 'consumed')


def recover(native, sandbox):
    root = native.consumer.scoped(sandbox); pub = native.pub; consumer = native.consumer
    require(not (root/'INTERRUPTION.json').exists() and not (root/'INTERRUPTION.json').is_symlink())
    completed = []; owner = (os.geteuid(), os.getegid())
    with consumer.file_lock(root/'docker-lifecycle.lock'), consumer.file_lock(root/'consumer.lock'), consumer.journal(root):
        ledger = native.fence.load(root); native.fence.assert_detached(ledger)
        require(consumer.load(root)[3] == 'open'
            and pub.read_json(root/'NATIVE_IMPORT/STATUS.json') == {'state': 'imported'}
            and not (root/'consumption/SEAL.json').exists())
        old_rows = pub.read_json(root/'transaction/PLAN.json')['surfaces']
        consumed = {name: pub.digest(root/'current'/name, name in pub.DIRECTORIES) for name in pub.SURFACES}
        metadata.check(native, root/'current', 'consumed')
        before = pub.digest(root, True)
        for boundary in boundaries(native):
            print('COMBINED_RECOVERY_SIGKILL=pending boundary='+boundary, flush=True)
            with tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp') as temporary:
                copied = Path(temporary)
                for path in sorted(root.iterdir()):
                    native.copy_tree(path, copied/path.name, path.is_dir(), owner, owner)
                require(pub.digest(copied, True) == before and pub.digest(root, True) == before)
                child = multiprocessing.get_context('fork').Process(target=child_recover, args=(native, copied, boundary))
                child.start()
                try:
                    child.join(60)
                    if child.is_alive(): child.kill(); child.join(5); raise RuntimeError('Recovery worker deadline')
                    require(child.exitcode == -signal.SIGKILL)
                    native.recover(copied); native.recover(copied)
                    verify(native, copied, old_rows, consumed)
                finally:
                    if child.is_alive(): child.kill(); child.join(5)
                completed.append(boundary)
            require(pub.digest(root, True) == before)
            print('COMBINED_RECOVERY_SIGKILL=PASS boundary='+boundary, flush=True)
        native.fence.assert_detached(ledger)
        pub.write_json(root/'INTERRUPTION.json', {'version': 1, 'scope': 'isolated-combined-journal-sigkill',
            'source_journal_sha256': before, 'boundaries': completed,
            'production_state_access': False, 'live_restore_enabled': False})
    # Recover the original journal only after all independent copy cases pass.
    # The caller then runs numeric reader acceptance and both restored starts.
    native.recover(root); native.recover(root)
    verify(native, root, old_rows, consumed)
    print(json.dumps({'version': 1, 'scope': 'isolated-combined-journal-sigkill',
        'process_death_boundaries': len(completed), 'source_preserved_through_cases': True,
        'old_surfaces_restored': True, 'consumed_surfaces_quarantined': True,
        'production_state_access': False, 'live_restore_enabled': False}, sort_keys=True))
