"""Expiry must not erase the link required for explicit owned lease release."""
import json
from pathlib import Path
import tempfile
import unittest
from atlas.sports_session_registry import SportsSessionRegistry

class ExpiredReleaseTests(unittest.TestCase):
    def test_expired_owned_session_returns_original_lease_link(self):
        with tempfile.TemporaryDirectory() as directory:
            now=[100.0]
            store=SportsSessionRegistry(Path(directory)/'sessions.json',clock=lambda:now[0])
            admitted=store.admit(user_id='viewer',target_id='game',limit=1,resource_lease_id='shared-lease')
            now[0]+=1000
            self.assertEqual(store.release_record(session_id=admitted.session_id,user_id='viewer'),admitted)
            self.assertIsNone(store.release_record(session_id=admitted.session_id,user_id='viewer'))
            self.assertEqual(json.loads(store.path.read_bytes())['sessions'],{})

    def test_wrong_user_cannot_prune_expired_owner_or_lose_lease_link(self):
        with tempfile.TemporaryDirectory() as directory:
            now=[100.0]
            store=SportsSessionRegistry(Path(directory)/'sessions.json',clock=lambda:now[0])
            admitted=store.admit(user_id='owner',target_id='game',limit=1,resource_lease_id='shared-lease')
            before=store.path.read_bytes();now[0]+=1000
            self.assertIsNone(store.release_record(session_id=admitted.session_id,user_id='other'))
            self.assertEqual(store.path.read_bytes(),before)
            self.assertIsNone(store.release_record(session_id='unknown',user_id='owner'))
            self.assertEqual(store.path.read_bytes(),before)

    def test_explicit_release_preserves_other_expired_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            now=[100.0]
            store=SportsSessionRegistry(Path(directory)/'sessions.json',clock=lambda:now[0])
            first=store.admit(user_id='first',target_id='game',limit=1,resource_lease_id='first-lease')
            second=store.admit(user_id='second',target_id='game',limit=1,resource_lease_id='second-lease')
            now[0]+=1000
            self.assertEqual(store.release_record(session_id=first.session_id,user_id='first'),first)
            remaining=json.loads(store.path.read_bytes())['sessions']
            self.assertEqual(set(remaining),{second.session_id})
            self.assertEqual(remaining[second.session_id]['resource_lease_id'],'second-lease')
