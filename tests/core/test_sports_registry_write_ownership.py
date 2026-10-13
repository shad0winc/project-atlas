"""Privileged recovery must leave durable registries usable by the API owner."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from atlas.jellyfin_live_streams import JellyfinProcessRetirement, OwnedJellyfinLiveStreams
from atlas.sports_session_registry import SportsSessionRegistry

class RegistryOwnershipTests(unittest.TestCase):
    def test_session_release_preserves_existing_owner_and_private_mode(self):
        self.check_session(privileged=False)

    @unittest.skipUnless(os.geteuid() == 0, 'Cross-user recovery requires root')
    def test_root_session_recovery_preserves_api_owner(self):
        self.check_session(privileged=True)

    def check_session(self, privileged):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sessions.json'
            registry = SportsSessionRegistry(path, clock=lambda: 100)
            session = registry.admit(user_id='viewer', target_id='channel', limit=1)
            uid, gid = (999, 20000) if privileged else (os.getuid(), os.getgid())
            if privileged: os.chown(path, uid, gid)
            self.assertIsNotNone(registry.release_record(session_id=session.session_id, user_id='viewer'))
            self.assertEqual(json.loads(path.read_bytes())['sessions'], {})
            metadata = path.stat()
            self.assertEqual((metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)), (uid, gid, 0o600))

    def test_verified_stream_recovery_preserves_existing_owner(self):
        self.check_stream(privileged=False)

    @unittest.skipUnless(os.geteuid() == 0, 'Cross-user recovery requires root')
    def test_root_stream_recovery_preserves_api_owner(self):
        self.check_stream(privileged=True)

    def check_stream(self, privileged):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / 'streams.json'
            row = dict(user_id='viewer', item_id='channel', last_seen=100.0, status='blocked', live_stream_id=None, play_session_id='job', media_source_id='source')
            path.write_text(json.dumps({'version':1, 'streams':{'owner':row}}))
            path.chmod(0o600)
            uid, gid = (999, 20000) if privileged else (os.getuid(), os.getgid())
            if privileged: os.chown(path, uid, gid)
            before = path.read_bytes()
            proof = JellyfinProcessRetirement(old_generation='old', new_generation='new', old_started_at=50, new_started_at=400, observed_at=499, old_process_absent=True, new_provider_healthy=True, admission_quiesced=True, native_upstream_closed=True, native_consumers_absent=True)
            store = OwnedJellyfinLiveStreams(path, clock=lambda:500)
            store.reconcile_failed_open_after_retirement(session_id='owner', user_id='viewer', item_id='channel', expected_sha256=hashlib.sha256(before).hexdigest(), backup_file=root/'before.json', receipt_file=root/'intent.json', verify_retirement=lambda row:proof)
            self.assertEqual(json.loads(path.read_bytes())['streams'], {})
            self.assertEqual((root/'before.json').read_bytes(), before)
            metadata = path.stat()
            self.assertEqual((metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)), (uid, gid, 0o600))
            self.assertEqual((root/'before.json').stat().st_uid, os.getuid())

    def test_failed_owner_transfer_preserves_session_preimage(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sessions.json'
            registry = SportsSessionRegistry(path, clock=lambda:100)
            record = registry.admit(user_id='viewer', target_id='channel', limit=1)
            before = path.read_bytes()
            original = os.fstat
            def other_owner(fd):
                result = original(fd)
                values = list(result)
                values[4] = result.st_uid + 1
                return os.stat_result(values)
            with patch('atlas.sports_session_registry.os.fstat', side_effect=other_owner), patch('atlas.sports_session_registry.os.fchown', side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    registry.release_record(session_id=record.session_id, user_id='viewer')
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob('.sessions.json.*.tmp')), [])
