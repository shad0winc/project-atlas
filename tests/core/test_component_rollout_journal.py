"""Real held exclusion and crash recovery; all actions affect private fixtures."""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

from atlas.deployment_component_rollout import ComponentRollout, SURFACES, digest
from atlas.deployment_publication_journal import encoded, read_file
from atlas.maintenance_control import MaintenanceControlError


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class FixtureAdapter:
    """File-backed actions survive SIGKILL independently of journal receipts."""
    def __init__(self, root, plan):
        self.root, self.plan = root, plan
        self.state = root / 'fixture-state.json'
        self.log = root / 'fixture-actions.jsonl'
        self.verification = True
        self.write({entry['name']: entry['before'] for entry in plan['surfaces']})
        self.log.write_bytes(b'')

    def write(self, value):
        temp = self.state.with_suffix('.tmp')
        with temp.open('wb') as stream:
            stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        os.replace(temp, self.state)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def observe(self, name):
        return json.loads(self.state.read_bytes())[name]

    def action(self, name, mode):
        value = json.loads(self.state.read_bytes())
        entry = next(item for item in self.plan['surfaces'] if item['name'] == name)
        target = entry['after'] if mode == 'apply' else entry['before']['fingerprint']
        value[name] = {'fingerprint': target, 'identity': 'absent' if target == 'absent' else sha(os.urandom(16))}
        self.write(value)
        with self.log.open('ab') as stream:
            stream.write(encoded({'mode': mode, 'surface': name}));stream.flush();os.fsync(stream.fileno())

    def apply(self, name): self.action(name, 'apply')
    def rollback(self, name): self.action(name, 'rollback')

    def verify(self, mode):
        value = json.loads(self.state.read_bytes())
        expected = {entry['name']: entry['after'] if mode == 'apply' else entry['before']['fingerprint'] for entry in self.plan['surfaces']}
        return self.verification and all(value[name]['fingerprint'] == target for name, target in expected.items())

    def actions(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]


class ComponentRolloutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('maintenance', 'deployments', 'deployments/update.lock', 'deployments/records',
                     'deployments/records/original-failed', 'deployments/records/original-baseline', 'assets'):
            (self.root / name).mkdir(mode=0o700)
        self.owner = self.root / 'deployments/update.lock/owner'
        self.owner.write_bytes(b'deployment_id=original-failed\npid=123\n')
        self.current = self.root / 'deployments/current'
        self.current.write_bytes(b'original-baseline\n')
        self.flag = self.root / 'maintenance/enabled'
        self.flag.write_bytes(b'held\n')
        for record, status in (('original-failed', 'failed'), ('original-baseline', 'verified')):
            (self.root / 'deployments/records' / record / 'metadata').write_text('deployment_id=' + record + '\n')
            (self.root / 'deployments/records' / record / 'status').write_text(status + '\n')
        self.lock = self.root / 'deployment-scheduler.lock'
        self.lock.touch(mode=0o600)
        self.stream = self.lock.open('r+')
        self.addCleanup(self.stream.close)
        fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        artifacts = {}
        for name in ('source-archive', 'target-recipe', 'rollback-recipe', 'authority-unit'):
            path = self.root / 'assets' / name
            path.write_bytes(('fixture-' + name).encode())
            artifacts[name] = {'path': str(path), 'sha256': sha(path.read_bytes())}
        self.plan = {'schema_version': 1, 'rollout_id': 'rollout-private', 'original_owner': 'original-failed',
                     'expected_current': 'original-baseline',
                     'generation': str(self.root / 'deployments/repairs/fixture/source'),
                     'artifacts': artifacts,
                     'protected': {str(file): sha(file.read_bytes()) for file in (self.root / 'deployments/records').rglob('*') if file.is_file()},
                     'surfaces': [{'name': name, 'before': {'fingerprint': 'absent', 'identity': 'absent'} if index < 3 else
                                  {'fingerprint': sha((name + '-old').encode()), 'identity': sha((name + '-old-container').encode())},
                                  'after': sha((name + '-new').encode())} for index, name in enumerate(SURFACES)]}
        self.adapter = FixtureAdapter(self.root, self.plan)
        self.engine = ComponentRollout(self.root, 'original-failed', self.stream.fileno(), adapter=self.adapter)
        self.owner_bytes = self.owner.read_bytes()
        self.owner_inode, self.directory_inode = self.owner.stat().st_ino, self.owner.parent.stat().st_ino
        self.boundary = {path: (path.read_bytes(), path.stat().st_ino) for path in (self.current, self.flag, self.owner)}
        self.addCleanup(self.assert_boundary)

    def assert_boundary(self):
        for path, (raw, inode) in self.boundary.items():
            self.assertEqual((path.read_bytes(), path.stat().st_ino), (raw, inode))
        self.assertEqual(self.owner.parent.stat().st_ino, self.directory_inode)
        with self.lock.open('r') as stream:
            with self.assertRaises(BlockingIOError): fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)

    def prepare(self): return self.engine.prepare('rollout-private', self.plan)

    def test_prepare_binds_plan_without_actions_or_publication(self):
        folder = self.prepare()
        self.assertEqual(self.prepare(), folder)
        result = self.engine.inspect_rollout('rollout-private')
        self.assertFalse(result['verified_held'])
        self.assertEqual(self.adapter.actions(), [])
        self.assertFalse((self.root / 'maintenance/publication-pending').exists())
        self.assertFalse((self.root / 'deployments/repairs/fixture/source').exists())

    def test_apply_and_rollback_are_held_and_use_exact_order(self):
        self.prepare()
        result = self.engine.run('rollout-private')
        self.assertTrue(result['verified_held'])
        self.assertFalse(result['owner_release_permitted'])
        self.assertFalse(result['publication_permitted'])
        self.assertFalse(result['public_reopen_permitted'])
        self.assertEqual([entry['surface'] for entry in self.adapter.actions()], list(SURFACES))
        result = self.engine.run('rollout-private', rollback=True)
        self.assertEqual(result['mode'], 'rollback')
        self.assertTrue(result['verified_held'])
        self.assertEqual([entry['surface'] for entry in self.adapter.actions()[6:]], list(reversed(SURFACES)))
        count = len(self.adapter.actions())
        self.engine.run('rollout-private', rollback=True)
        self.assertEqual(len(self.adapter.actions()), count)
        with self.assertRaises(MaintenanceControlError): self.engine.run('rollout-private')

    def test_false_final_verifier_never_produces_verified_receipt(self):
        self.prepare()
        self.adapter.verification = False
        with self.assertRaisesRegex(MaintenanceControlError, 'final_verification_failed'):
            self.engine.run('rollout-private')
        self.assertFalse(self.engine.inspect_rollout('rollout-private')['verified_held'])
        self.adapter.verification = True
        self.assertTrue(self.engine.run('rollout-private')['verified_held'])
        self.assertEqual(len(self.adapter.actions()), 6)

    def test_unlocked_shared_unrelated_or_wrong_inode_exclusion_refuses(self):
        for mode in (None, fcntl.LOCK_SH):
            fcntl.flock(self.stream, fcntl.LOCK_UN)
            if mode is not None: fcntl.flock(self.stream, mode)
            try:
                with self.assertRaises(MaintenanceControlError): self.prepare()
            finally:
                fcntl.flock(self.stream, fcntl.LOCK_UN);fcntl.flock(self.stream, fcntl.LOCK_EX)
        for path in (self.lock, self.root / 'other-lock'):
            path.touch(exist_ok=True)
            with path.open('r+') as other:
                if path != self.lock: fcntl.flock(other, fcntl.LOCK_EX)
                engine = ComponentRollout(self.root, 'original-failed', other.fileno(), adapter=self.adapter)
                with self.assertRaises(MaintenanceControlError): engine.prepare('rollout-private', self.plan)

    def test_owner_current_and_maintenance_drift_refuse_without_action(self):
        self.prepare()
        for path, raw in ((self.owner, self.owner_bytes + b'changed=yes\n'), (self.current, b'other-baseline\n'), (self.flag, b'')):
            old = path.read_bytes()
            if path == self.flag: path.unlink()
            else: path.write_bytes(raw)
            try:
                with self.assertRaises(MaintenanceControlError): self.engine.run('rollout-private')
                self.assertEqual(self.adapter.actions(), [])
            finally:
                path.write_bytes(old)
                if path == self.flag: self.boundary[path] = (old, path.stat().st_ino)

    def test_unexpected_owner_entry_is_retained_and_refused(self):
        self.prepare()
        extra = self.owner.parent / 'retain'
        extra.write_bytes(b'retain')
        try:
            with self.assertRaises(MaintenanceControlError): self.engine.run('rollout-private')
            self.assertEqual(extra.read_bytes(), b'retain')
        finally: extra.unlink()

    def test_artifact_or_protected_record_change_refuses(self):
        self.prepare()
        for path in (Path(self.plan['artifacts']['rollback-recipe']['path']), Path(next(iter(self.plan['protected'])))):
            old = path.read_bytes();path.write_bytes(b'changed')
            try:
                with self.assertRaises(MaintenanceControlError): self.engine.run('rollout-private')
                self.assertEqual(self.adapter.actions(), [])
            finally: path.write_bytes(old)

    def test_changed_plan_or_surface_order_refuses(self):
        self.prepare()
        changed = copy.deepcopy(self.plan)
        changed['surfaces'].reverse()
        with self.assertRaises(MaintenanceControlError): self.engine.prepare('rollout-private', changed)
        changed = copy.deepcopy(self.plan)
        changed['surfaces'][0]['after'] = '0' * 64
        with self.assertRaises(MaintenanceControlError): self.engine.prepare('rollout-private', changed)

    def test_partial_or_foreign_journal_is_not_replaced(self):
        parent = self.root / 'deployments/rollout-journals';parent.mkdir()
        folder = parent / 'rollout-private';folder.mkdir()
        (folder / 'plan.json').write_bytes(b'{partial')
        with self.assertRaises((MaintenanceControlError, ValueError, OSError)):
            self.prepare()
        self.assertEqual((folder / 'plan.json').read_bytes(), b'{partial')

    def test_tampered_or_missing_event_chain_refuses(self):
        folder = self.prepare();self.engine.run('rollout-private')
        first = folder / 'event-000001.json';raw = first.read_bytes();first.write_bytes(b'{}')
        with self.assertRaises(MaintenanceControlError): self.engine.inspect_rollout('rollout-private')
        first.write_bytes(raw)
        first.rename(folder / 'event-999999.json')
        with self.assertRaises(MaintenanceControlError): self.engine.run('rollout-private')

    def test_visible_intent_after_fsync_uncertainty_is_reflushed_before_resume(self):
        from atlas import deployment_component_rollout as rollout
        folder = self.prepare()
        original = rollout.create_once
        def uncertain(path, raw):
            original(path, raw)
            if path.name == 'event-000001.json': raise OSError('fixture durability uncertainty')
        with patch.object(rollout, 'create_once', side_effect=uncertain), self.assertRaises((OSError, MaintenanceControlError)):
            self.engine.run('rollout-private')
        self.assertEqual(self.adapter.actions(), [])
        with patch.object(self.engine, '_flush_journal', side_effect=OSError('fixture repeat flush failed')), self.assertRaises((OSError, MaintenanceControlError)):
            self.engine.run('rollout-private')
        self.assertEqual(self.adapter.actions(), [])
        self.assertTrue(self.engine.run('rollout-private')['verified_held'])
        self.assertEqual(len(self.adapter.actions()), 6)

    def test_partial_intent_is_retained_without_action(self):
        folder = self.prepare()
        file = folder / 'event-000001.json'
        file.write_bytes(b'{partial-intent')
        with self.assertRaises((ValueError, MaintenanceControlError)):
            self.engine.run('rollout-private')
        self.assertEqual(file.read_bytes(), b'{partial-intent')
        self.assertEqual(self.adapter.actions(), [])

    def test_target_lookalike_with_new_process_identity_refuses(self):
        self.prepare();self.engine.run('rollout-private')
        value = json.loads(self.adapter.state.read_bytes());value['api']['identity'] = '0' * 64;self.adapter.write(value)
        with self.assertRaisesRegex(MaintenanceControlError, 'runtime_drift'):
            self.engine.run('rollout-private')

    def crash(self, stage, rollback=False):
        pid = os.fork()
        if pid == 0:
            self.engine.checkpoint = lambda phase: os.kill(os.getpid(), signal.SIGKILL) if phase == stage else None
            try: self.engine.run('rollout-private', rollback=rollback)
            finally: os._exit(97)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFSIGNALED(status), (stage, status))
        self.assert_boundary()

    def test_kill_before_action_resumes_without_duplicate_actions(self):
        self.prepare();self.crash('apply:api:before-action')
        self.assertEqual(self.engine.inspect_rollout('rollout-private')['pending_outcome'], 'not-applied')
        self.assertTrue(self.engine.run('rollout-private')['verified_held'])
        self.assertEqual([row['surface'] for row in self.adapter.actions()], list(SURFACES))

    def test_kill_after_action_adopts_exact_observation_without_repeating(self):
        self.prepare();self.crash('apply:api:after-action')
        self.assertEqual(self.engine.inspect_rollout('rollout-private')['pending_outcome'], 'applied')
        self.assertTrue(self.engine.run('rollout-private')['verified_held'])
        self.assertEqual([row['surface'] for row in self.adapter.actions()], list(SURFACES))

    def test_unknown_inflight_result_never_retries_or_blindly_rolls_back(self):
        self.prepare();self.crash('apply:api:after-action')
        value = json.loads(self.adapter.state.read_bytes())
        value['api'] = {'fingerprint': '0' * 64, 'identity': '1' * 64};self.adapter.write(value)
        self.assertEqual(self.engine.inspect_rollout('rollout-private')['pending_outcome'], 'unknown')
        count = len(self.adapter.actions())
        for rollback in (False, True):
            with self.assertRaisesRegex(MaintenanceControlError, 'uncertain_action'):
                self.engine.run('rollout-private', rollback=rollback)
        self.assertEqual(len(self.adapter.actions()), count)

    def test_partial_apply_can_roll_back_without_running_remaining_actions(self):
        self.prepare();self.crash('apply:api:before-action')
        result = self.engine.run('rollout-private', rollback=True)
        self.assertTrue(result['verified_held'])
        rows = self.adapter.actions()
        self.assertEqual([(row['mode'], row['surface']) for row in rows],
                         [('apply', name) for name in SURFACES[:3]] + [('rollback', name) for name in reversed(SURFACES[:3])])

    def test_kill_after_rollback_action_resumes_without_repeating(self):
        self.prepare();self.engine.run('rollout-private');self.crash('rollback:caddy:after-action', rollback=True)
        self.assertEqual(self.engine.inspect_rollout('rollout-private')['pending_outcome'], 'applied')
        self.assertTrue(self.engine.run('rollout-private', rollback=True)['verified_held'])
        self.assertEqual(len(self.adapter.actions()), 12)

    def test_process_death_at_every_forward_and_reverse_durable_boundary(self):
        # Fresh contexts per phase keep original fixture owner and process identity pinned.
        phases = [f'apply:{name}:{point}' for name in SURFACES for point in ('intent:durable', 'after-action', 'complete:durable')]
        phases += [f'rollback:{name}:{point}' for name in reversed(SURFACES) for point in ('intent:durable', 'after-action', 'complete:durable')]
        for phase in phases:
            with self.subTest(phase=phase):
                child = ComponentRolloutTests('test_prepare_binds_plan_without_actions_or_publication')
                child.setUp()
                try:
                    child.prepare()
                    reverse = phase.startswith('rollback')
                    if reverse: child.engine.run('rollout-private')
                    child.crash(phase, rollback=reverse)
                    self.assertTrue(child.engine.run('rollout-private', rollback=reverse)['verified_held'])
                    self.assertEqual(len(child.adapter.actions()), 12 if reverse else 6)
                finally: child.doCleanups()


if __name__ == '__main__':
    unittest.main()
