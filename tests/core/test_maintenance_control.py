"""Offline authority/IPC and abrupt-process-death checks; no production paths."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from atlas.maintenance_control import MaintenanceAuthority, MaintenanceControlError
from atlas.maintenance_control_server import MaintenanceClient, MaintenanceServer


class MaintenanceControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        (self.root / 'maintenance').mkdir()
        (self.root / 'deployments').mkdir()
        (self.root / 'deployment-scheduler.lock').touch(mode=0o600)
        self.authority = MaintenanceAuthority(self.root)

    def enable(self):
        return self.authority.change(True, actor='admin-id', source='web')

    def test_enable_disable_is_audited_and_status_is_exact(self):
        self.assertFalse(self.authority.status()['enabled'])
        self.assertTrue(self.enable()['enabled'])
        self.assertEqual((self.authority.flag.stat().st_mode & 0o777), 0o644)
        self.assertFalse(self.authority.change(False, actor='admin-id', source='web')['enabled'])
        rows = [json.loads(x) for x in self.authority.audit.read_text().splitlines()]
        self.assertEqual([x['event'] for x in rows], ['security.maintenance.requested',
            'security.maintenance.completed'] * 2)
        self.assertEqual([x['operation'] for x in rows], ['enable','enable','disable','disable'])
        self.assertEqual(len({x['request_id'] for x in rows}), 2)
        self.assertEqual(self.authority.audit.stat().st_mode & 0o777, 0o600)

    def test_private_service_umask_preserves_flag_and_audit_modes(self):
        previous = os.umask(0o077)
        try:
            self.enable()
        finally:
            os.umask(previous)
        self.assertEqual(self.authority.flag.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.authority.audit.stat().st_mode & 0o777, 0o600)

    def test_recovery_hold_refuses_disable_without_touching_owner(self):
        self.enable()
        self.authority.recovery_lock.mkdir()
        owner = self.authority.recovery_lock / 'owner'
        owner.write_bytes(b'original recovery owner\n')
        before = owner.stat()
        with self.assertRaisesRegex(MaintenanceControlError, '^recovery_held$'):
            self.authority.change(False, actor='admin-id', source='web')
        self.assertTrue(self.authority.status()['enabled'])
        self.assertEqual(owner.read_bytes(), b'original recovery owner\n')
        self.assertEqual(owner.stat().st_ino, before.st_ino)
        self.assertFalse(self.authority.pending.exists())

    def test_empty_recovery_directory_is_still_a_hold(self):
        self.authority.recovery_lock.mkdir()
        with self.assertRaisesRegex(MaintenanceControlError, '^recovery_held$'):
            self.authority.change(False, actor='admin-id', source='web')

    def test_unreadable_state_is_fail_closed(self):
        with patch.object(Path, 'lstat', side_effect=PermissionError('private')):
            state = self.authority.status()
        self.assertTrue(state['enabled'])
        self.assertTrue(state['recovery_held'])
        self.assertTrue(state['state_uncertain'])

    def test_missing_exclusion_lock_is_not_silently_created(self):
        self.authority.lock.unlink()
        with self.assertRaisesRegex(MaintenanceControlError, '^exclusion_unavailable$'):
            self.enable()
        self.assertFalse(self.authority.lock.exists())

    def test_exclusion_busy_refuses_mutation(self):
        with self.authority.lock.open('r+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(MaintenanceControlError, '^operation_busy$'):
                self.enable()
        self.assertFalse(self.authority.pending.exists())

    def test_symlink_state_and_shared_lock_fail_closed(self):
        foreign = self.root / 'foreign'
        foreign.write_bytes(b'untouched')
        self.authority.flag.symlink_to(foreign)
        self.assertTrue(self.authority.status()['state_uncertain'])
        with self.assertRaisesRegex(MaintenanceControlError, '^state_unavailable$'):
            self.enable()
        self.authority.flag.unlink()
        self.authority.lock.unlink()
        self.authority.lock.symlink_to(foreign)
        with self.assertRaisesRegex(MaintenanceControlError, '^exclusion_unavailable$'):
            self.enable()
        self.assertEqual(foreign.read_bytes(), b'untouched')

    def test_symlink_recovery_lock_cannot_look_unheld(self):
        self.authority.recovery_lock.symlink_to(self.root / 'missing', target_is_directory=True)
        self.assertTrue(self.authority.status()['state_uncertain'])
        with self.assertRaisesRegex(MaintenanceControlError, '^state_unavailable$'):
            self.authority.change(False, actor='admin-id', source='web')

    def test_audit_failure_retains_hold_and_blocks_retry(self):
        with patch.object(self.authority, '_append_audit', side_effect=OSError('private secret')):
            with self.assertRaisesRegex(MaintenanceControlError, '^transition_incomplete$'):
                self.enable()
        self.assertTrue(self.authority.status()['enabled'])
        self.assertTrue(self.authority.pending.exists())
        with self.assertRaisesRegex(MaintenanceControlError, '^transition_requires_host_repair$'):
            self.authority.change(False, actor='admin-id', source='web')
        self.assertTrue(self.authority.recover_hold(actor='host-root')['enabled'])
        self.assertFalse(self.authority.pending.exists())

    def test_completion_audit_failure_restores_flag(self):
        self.enable()
        original = self.authority._append_audit
        def append(operation, actor, source, request_id, phase):
            if operation == 'disable' and phase == 'completed':
                raise OSError('disk full')
            return original(operation, actor, source, request_id, phase)
        with patch.object(self.authority, '_append_audit', side_effect=append):
            with self.assertRaisesRegex(MaintenanceControlError, '^transition_incomplete$'):
                self.authority.change(False, actor='admin-id', source='web')
        self.assertTrue(self.authority.flag.exists())
        self.assertTrue(self.authority.pending.exists())

    def test_lock_acquired_during_transition_is_detected_before_disable(self):
        self.enable()
        def checkpoint(phase):
            if phase == 'intent_durable':
                self.authority.recovery_lock.mkdir()
        self.authority.checkpoint = checkpoint
        with self.assertRaisesRegex(MaintenanceControlError, '^transition_incomplete$'):
            self.authority.change(False, actor='admin-id', source='web')
        self.assertTrue(self.authority.status()['enabled'])

    def test_abrupt_exit_at_each_durable_phase_keeps_effective_maintenance(self):
        # os._exit bypasses Python cleanup, modeling a dead control process.
        for phase in ('pending_durable','intent_durable','flag_durable','completion_durable'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                (root / 'maintenance').mkdir()
                (root / 'deployments').mkdir()
                (root / 'deployment-scheduler.lock').touch(mode=0o600)
                (root / 'maintenance/enabled').touch(mode=0o644)
                code = '''import os,sys
from pathlib import Path
from atlas.maintenance_control import MaintenanceAuthority
phase=sys.argv[2]
def checkpoint(value):
 if value==phase: os._exit(73)
MaintenanceAuthority(Path(sys.argv[1]),checkpoint=checkpoint).change(False,actor='admin-id',source='web')
'''
                result = subprocess.run([sys.executable,'-B','-c',code,str(root),phase],capture_output=True)
                self.assertEqual(result.returncode, 73, result.stderr.decode())
                authority = MaintenanceAuthority(root)
                self.assertTrue(authority.status()['enabled'])
                self.assertTrue(authority.status()['transition_pending'])
                with self.assertRaisesRegex(MaintenanceControlError,'^transition_requires_host_repair$'):
                    authority.change(False,actor='admin-id',source='web')
                self.assertTrue(authority.recover_hold(actor='host-root')['enabled'])

    def test_hardlinked_audit_is_refused_without_writing_foreign_file(self):
        foreign = self.root / 'foreign'
        foreign.write_bytes(b'untouched')
        foreign.chmod(0o600)
        self.authority.audit.hardlink_to(foreign)
        with self.assertRaisesRegex(MaintenanceControlError,'^transition_incomplete$'):
            self.enable()
        self.assertEqual(foreign.read_bytes(), b'untouched')

    def test_invalid_actor_and_non_boolean_never_create_transition(self):
        for value,actor in ((1,'admin-id'),(False,'admin\nsecret'),(False,'')):
            with self.subTest(value=value,actor=actor):
                with self.assertRaisesRegex(MaintenanceControlError,'^invalid_request$'):
                    self.authority.change(value, actor=actor, source='web')
                self.assertFalse(self.authority.pending.exists())

    def test_socket_transport_and_peer_policy(self):
        socket_path = self.root / 'control.sock'
        with MaintenanceServer(socket_path,self.authority,allowed_uid=os.geteuid(),socket_gid=os.getegid()) as server:
            thread = Thread(target=server.serve_forever, kwargs={'poll_interval':0.01}, daemon=True)
            thread.start()
            try:
                client = MaintenanceClient(socket_path)
                self.assertFalse(client.request('status')['enabled'])
                self.assertTrue(client.request('enable',actor='admin-id')['enabled'])
                self.authority.recovery_lock.mkdir()
                with self.assertRaisesRegex(MaintenanceControlError,'^recovery_held$'):
                    client.request('disable',actor='admin-id')
                with self.assertRaisesRegex(MaintenanceControlError,'^peer_not_permitted$'):
                    server.dispatch({'operation':'status'},peer_uid=max(os.geteuid(),65534)+1)
                for payload in ({'operation':'recover_hold'}, {'operation':'disable','actor':'admin-id','path':'/tmp/x'},
                                {'operation':'status','actor':'admin-id'}, ['status']):
                    with self.subTest(payload=payload), self.assertRaisesRegex(MaintenanceControlError,'^invalid_request$'):
                        server.dispatch(payload,peer_uid=os.geteuid())
            finally:
                server.shutdown()
                thread.join(timeout=5)
        self.assertFalse(socket_path.exists())

    def test_socket_outage_is_fixed_failure(self):
        with self.assertRaisesRegex(MaintenanceControlError,'^control_unavailable$'):
            MaintenanceClient(self.root / 'missing.sock').request('status')


if __name__ == '__main__':
    unittest.main()
