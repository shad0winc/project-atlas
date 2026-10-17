"""Exercise actual private file publication, process death and repeatable undo."""
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


publication = load('sports_publication', ROOT / 'scripts/lib/sports-recovery-publication.py')
fixtures = load('publication_association_fixture', Path(__file__).with_name('test_sports_recovery_association.py'))


class RecoveryPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RecoveryAssociationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.association_root = self.fixture.associate()
        resolver = patch.object(publication, 'helper', return_value=fixtures.association)
        resolver.start(); self.addCleanup(resolver.stop)

    def sandbox(self):
        temp = tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name); (root / 'current').mkdir(mode=0o700)
        for name in publication.SURFACES:
            path = root / 'current' / name
            if name in publication.DIRECTORIES:
                path.mkdir(mode=0o700); path /= 'old-state'
            fixtures.fixture_module.write(path, ('old:' + name).encode())
        return root

    def hashes(self, root):
        return [publication.digest(root / 'current' / name, name in publication.DIRECTORIES)
                for name in publication.SURFACES]

    def stage(self):
        root = self.sandbox(); before = self.hashes(root)
        publication.stage(self.association_root, root)
        self.assertEqual(self.hashes(root), before)
        return root, before

    def status(self, root):
        return json.loads((root / 'transaction/STATUS.json').read_bytes())['state']

    def test_all_five_surfaces_publish_and_reverse_without_input_changes(self):
        original = self.fixture.snapshot()
        root, before = self.stage()
        plan = json.loads((root / 'transaction/PLAN.json').read_bytes())
        publication.apply(root)
        self.assertEqual(self.status(root), 'applied-awaiting-verification')
        self.assertEqual(self.hashes(root), [row['new_sha256'] for row in plan['surfaces']])
        self.assertFalse(plan['ready_for_live_apply'])
        publication.recover(root)
        self.assertEqual(self.status(root), 'reverted')
        self.assertEqual(self.hashes(root), before)
        publication.recover(root)
        self.assertEqual(self.fixture.snapshot(), original)

    def die_at(self, root, operation, boundary):
        # fork preserves the fixture's PG command stubs; no PostgreSQL or Docker
        # process is started. The publication child really exits without cleanup.
        def child():
            def stop(name):
                if name == boundary: os._exit(91)
            with patch.object(publication, 'checkpoint', side_effect=stop):
                operation(root)
            os._exit(92)
        process = multiprocessing.get_context('fork').Process(target=child)
        process.start(); process.join(10)
        if process.is_alive():
            process.kill(); process.join(5)
        self.assertEqual(process.exitcode, 91, boundary)

    def test_real_process_death_at_every_apply_move_recovers_exact_old_state(self):
        boundaries = ['applying', 'applied'] + [prefix + name
            for name in publication.SURFACES for prefix in ('old:', 'new:')]
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                root, before = self.stage()
                self.die_at(root, publication.apply, boundary)
                publication.recover(root)
                self.assertEqual(self.status(root), 'reverted')
                self.assertEqual(self.hashes(root), before)

    def test_real_process_death_during_every_undo_move_is_recoverable_again(self):
        boundaries = ['rolling-back'] + [prefix + name
            for name in publication.SURFACES for prefix in ('undo-new:', 'undo-old:')]
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                root, before = self.stage(); publication.apply(root)
                self.die_at(root, publication.recover, boundary)
                publication.recover(root)
                publication.recover(root)
                self.assertEqual(self.status(root), 'reverted')
                self.assertEqual(self.hashes(root), before)

    def test_ordinary_failure_automatically_reverts(self):
        root, before = self.stage()
        def fail(name):
            if name == 'old:teamarr-db': raise OSError('fixture publication failure')
        with patch.object(publication, 'checkpoint', side_effect=fail):
            with self.assertRaises(OSError): publication.apply(root)
        self.assertEqual(self.status(root), 'reverted')
        self.assertEqual(self.hashes(root), before)

    def test_fsync_error_after_a_rename_is_included_in_automatic_rollback(self):
        root, before = self.stage()
        real_sync = publication.sync
        failed = False
        def fail_once(path):
            nonlocal failed
            if Path(path) == root / 'current' and not failed:
                failed = True
                raise OSError('fixture fsync failure after rename')
            real_sync(path)
        with patch.object(publication, 'sync', side_effect=fail_once):
            with self.assertRaises(OSError): publication.apply(root)
        self.assertTrue(failed)
        self.assertEqual(self.status(root), 'reverted')
        self.assertEqual(self.hashes(root), before)

    def test_copy_failure_before_plan_publication_leaves_current_untouched(self):
        root = self.sandbox(); before = self.hashes(root)
        with patch.object(publication, 'copy_file', side_effect=OSError('fixture full disk')):
            with self.assertRaises(OSError): publication.stage(self.association_root, root)
        self.assertEqual(self.hashes(root), before)
        self.assertFalse((root / 'transaction/STATUS.json').exists())
        self.assertTrue((root / 'transaction').is_dir())
        with self.assertRaises(publication.PublicationError): publication.stage(self.association_root, root)

    def test_tampered_old_state_blocks_all_undo_mutations(self):
        root, _ = self.stage(); publication.apply(root)
        old = root / 'transaction/old/dispatcharr-jwt'; old.write_bytes(b'tampered')
        current = self.hashes(root)
        with self.assertRaises(publication.PublicationError): publication.recover(root)
        self.assertEqual(self.hashes(root), current)
        self.assertEqual(self.status(root), 'applied-awaiting-verification')

    def test_rollback_failure_is_held_and_can_be_retried(self):
        root, before = self.stage(); publication.apply(root)
        def fail(name):
            if name == 'undo-new:teamarr-db': raise OSError('fixture undo failure')
        with patch.object(publication, 'checkpoint', side_effect=fail):
            with self.assertRaises(OSError): publication.recover(root)
        self.assertEqual(self.status(root), 'rolling-back')
        publication.recover(root)
        self.assertEqual(self.hashes(root), before)

    def test_tampered_incoming_or_current_blocks_apply_without_mutation(self):
        for location in ('transaction/incoming', 'current'):
            with self.subTest(location=location):
                root, _ = self.stage()
                (root / location / 'dispatcharr-jwt').write_bytes(b'tampered')
                current = self.hashes(root)
                with self.assertRaises(publication.PublicationError): publication.apply(root)
                self.assertEqual(self.hashes(root), current)
                self.assertEqual(self.status(root), 'staged')

    def test_missing_association_does_not_prevent_rollback(self):
        root, before = self.stage(); publication.apply(root)
        document = self.association_root / 'ASSOCIATION.json'
        raw = document.read_bytes(); document.unlink()
        try:
            publication.recover(root)
            self.assertEqual(self.hashes(root), before)
        finally:
            fixtures.fixture_module.write(document, raw)

    def test_changed_association_blocks_apply_but_cannot_redirect_undo(self):
        root, before = self.stage()
        document = self.association_root / 'ASSOCIATION.json'
        raw = document.read_bytes()
        document.write_bytes(raw + b'\n')
        with self.assertRaises(publication.PublicationError): publication.apply(root)
        self.assertEqual(self.hashes(root), before)

    def test_paths_links_modes_hardlinks_and_existing_transaction_fail_closed(self):
        root, before = self.stage()
        with self.assertRaises(publication.PublicationError): publication.stage(self.association_root, root)
        self.assertEqual(self.hashes(root), before)
        with tempfile.TemporaryDirectory() as wrong:
            with self.assertRaises(publication.PublicationError): publication.apply(Path(wrong))
        target = root / 'transaction/incoming/dispatcharr-jwt'
        raw = target.read_bytes(); target.unlink()
        target.symlink_to(self.fixture.bundle_root / 'dispatcharr/jwt')
        with self.assertRaises(publication.PublicationError): publication.apply(root)
        target.unlink(); fixtures.fixture_module.write(target, raw)
        target.chmod(0o644)
        with self.assertRaises(publication.PublicationError): publication.apply(root)
        target.chmod(0o600)
        os.link(target, root / 'linked')
        with self.assertRaises(publication.PublicationError): publication.apply(root)

    def test_exclusion_lock_is_nonblocking_and_released_after_errors(self):
        root, _ = self.stage()
        with publication.locked(root):
            with self.assertRaises(BlockingIOError): publication.apply(root)
        publication.apply(root); publication.recover(root)

    def test_stale_partial_status_write_is_not_authoritative(self):
        root, before = self.stage(); publication.apply(root)
        fixtures.fixture_module.write(root / 'transaction/.STATUS.json.writing', b'{partial')
        publication.recover(root)
        self.assertEqual(self.hashes(root), before)
        self.assertFalse((root / 'transaction/.STATUS.json.writing').exists())

    def test_duplicate_or_unsafe_plan_is_rejected_before_mutation(self):
        root, before = self.stage()
        path = root / 'transaction/PLAN.json'; raw = path.read_bytes()
        for bad in (b'{"version":1,' + raw[1:],
                    raw.replace(b'"ready_for_live_apply": false', b'"ready_for_live_apply": true'),
                    raw.replace(b'"dispatcharr-db"', b'"../escape"')):
            path.write_bytes(bad)
            with self.assertRaises(publication.PublicationError): publication.apply(root)
            self.assertEqual(self.hashes(root), before)
        path.write_bytes(raw)




class ConsumptionMarkerGuardTests(unittest.TestCase):
    def test_generic_context_refuses_directory_or_link_consumer_marker(self):
        with tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.',dir='/tmp') as temporary:
            root=Path(temporary);(root/'current').mkdir(mode=0o700)
            marker=root/'consumption';marker.mkdir(mode=0o700)
            with self.assertRaises(publication.PublicationError):
                with publication.locked(root):self.fail('consumer marker accepted')
            marker.rmdir();marker.symlink_to(root/'missing')
            with self.assertRaises(publication.PublicationError):
                with publication.locked(root):self.fail('consumer marker link accepted')


if __name__ == '__main__': unittest.main()
