"""Run the real shell abort controller with private adapters and real journals."""
import contextlib
import fcntl
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


support = load('maintenance_rehearsal_test', 'scripts/lib/sports-maintenance-recovery.py')
previous = load('maintenance_journal_setup', 'tests/core/test_sports_consumption_interruption.py')


class ControllerTests(unittest.TestCase):
    def test_all_ten_failures_retain_private_maintenance_and_owner(self):
        with contextlib.redirect_stdout(io.StringIO()): support.failure_cases()

    def test_success_keeps_maintenance_after_checks_and_private_owner_release(self):
        with tempfile.TemporaryDirectory(prefix='atlas-maint-rehearsal.', dir='/tmp') as temporary:
            root = Path(temporary); calls = []
            def stop():
                with (root/'deployment-scheduler.lock').open('rb') as handle:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                calls.append('stop')
            actions = {name: (lambda name=name: calls.append(name))
                       for name in ('revert', 'validate', 'start', 'ready', 'runtime')}
            actions['stop'] = stop
            result = support.execute(root, actions)
            self.assertTrue(result['success'])
            self.assertTrue(result['maintenance_retained'])
            self.assertFalse(result['lock_retained'])
            self.assertNotIn('disable',result['events'])
            self.assertEqual(calls, ['stop', 'revert', 'validate', 'start', 'ready', 'runtime', 'runtime'])
            with (root/'deployment-scheduler.lock').open('rb') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_callback_exception_cannot_release_or_reopen(self):
        with tempfile.TemporaryDirectory(prefix='atlas-maint-rehearsal.', dir='/tmp') as temporary:
            def broken(): raise ValueError('suppressed fixture failure')
            actions = {name: lambda: None for name in ('stop', 'revert', 'validate', 'start', 'ready', 'runtime')}
            actions['start'] = broken
            result = support.execute(temporary, actions)
            self.assertFalse(result['success'])
            self.assertTrue(result['maintenance_retained'] and result['lock_retained'])
            self.assertEqual(result['events'][-1], 'start')

    def test_nonprivate_or_nonempty_runtime_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='atlas-maint-rehearsal.', dir='/tmp') as temporary:
            root = Path(temporary); (root/'keep').write_text('preserved')
            actions = {name: lambda: None for name in ('stop', 'revert', 'validate', 'start', 'ready', 'runtime')}
            with self.assertRaises(ValueError): support.execute(root, actions)
            self.assertEqual((root/'keep').read_text(), 'preserved')
            root.chmod(0o755)
            with self.assertRaises(ValueError): support.execute(root, actions)

    def test_orchestration_callback_requires_metadata_and_excludes_other_callback(self):
        with self.assertRaises(RuntimeError): previous.component.run(orchestrate_recovery=lambda *args: None)
        with self.assertRaises(RuntimeError): previous.component.run(orchestrate_recovery='bad')
        with self.assertRaises(RuntimeError):
            previous.component.run(orchestrate_recovery=lambda *args: None,
                                   metadata_hooks={}, recover_journal=lambda *args: None)


class JournalIntegrationTests(unittest.TestCase):
    setUp = previous.InterruptionTests.setUp

    def test_real_five_surface_recovery_precedes_acceptance_and_private_release(self):
        accepted = []
        def complete():
            self.assertEqual(previous.native.consumer.status(self.root/'consumption'), 'reverted')
            previous.interruption.metadata.check(previous.native, self.root/'current', 'old')
            previous.interruption.metadata.check(previous.native, self.root/'consumption/quarantine', 'consumed')
            accepted.append(True)
        support.recover(previous.native, self.root, complete)
        self.assertEqual(accepted, [True])

    def test_detachment_failure_prevents_recovery_and_acceptance(self):
        before = previous.native.pub.digest(self.root, True); accepted = []
        with patch.object(previous.native.fence, 'assert_detached', side_effect=ValueError('fixture active')):
            with self.assertRaises(ValueError): support.recover(previous.native, self.root, lambda: accepted.append(True))
        self.assertEqual(accepted, [])
        self.assertEqual(previous.native.pub.digest(self.root, True), before)


if __name__ == '__main__': unittest.main()
