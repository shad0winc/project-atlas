import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from atlas.sports_session_registry import SportsSessionRegistry, SportsSessionStateError

class RetainedObservationTests(unittest.TestCase):
    def test_expired_snapshot_preserves_bytes_metadata_and_lease(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"sessions.json";now=[100.0]
            store=SportsSessionRegistry(path,clock=lambda:now[0])
            record=store.admit(user_id="owner",target_id="game",limit=1,resource_lease_id="lease")
            before=path.read_bytes();metadata=path.stat()
            store.lock_path.unlink();now[0]=1000.0
            observed=store.observe_retained()
            self.assertEqual(observed.state_sha256,hashlib.sha256(before).hexdigest())
            self.assertEqual(observed.sessions[0].heartbeat_age_seconds,900)
            self.assertEqual(observed.sessions[0].session_id,record.session_id)
            self.assertEqual(path.read_bytes(),before)
            after=path.stat()
            self.assertEqual((after.st_ino,after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)),(metadata.st_ino,metadata.st_uid,metadata.st_gid,stat.S_IMODE(metadata.st_mode)))
            self.assertFalse(store.lock_path.exists())
            self.assertEqual(json.loads(before)["sessions"][record.session_id]["resource_lease_id"],"lease")

    def test_missing_state_does_not_create_paths_or_invent_zero(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"absent/sessions.json"
            with self.assertRaises(SportsSessionStateError):SportsSessionRegistry(path).observe_retained()
            self.assertFalse(path.parent.exists())

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            real=Path(td)/"real";real.write_text('{"version":2,"sessions":{}}')
            path=Path(td)/"link";path.symlink_to(real)
            with self.assertRaises(SportsSessionStateError):SportsSessionRegistry(path).observe_retained()

    def test_legacy_snapshot_does_not_migrate_file(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"sessions.json"
            raw=json.dumps({"version":1,"sessions":{"old":{"user_id":"owner","target_id":"game","created_at":1,"last_seen_at":1}}}).encode()
            path.write_bytes(raw)
            observed=SportsSessionRegistry(path,clock=lambda:1000).observe_retained()
            self.assertEqual(observed.sessions[0].session_id,"old")
            self.assertEqual(path.read_bytes(),raw)

    def test_invalid_or_directory_state_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaises(SportsSessionStateError):SportsSessionRegistry(root).observe_retained()
            path=root/"bad";path.write_text('{"version":2,"sessions":{"bad":{}}}')
            with self.assertRaises(SportsSessionStateError):SportsSessionRegistry(path).observe_retained()

    def test_new_instance_observes_durable_record(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"sessions.json";one=SportsSessionRegistry(path,clock=lambda:100)
            record=one.admit(user_id="owner",target_id="game",limit=1)
            self.assertEqual(SportsSessionRegistry(path,clock=lambda:110).observe_retained().sessions[0].session_id,record.session_id)
