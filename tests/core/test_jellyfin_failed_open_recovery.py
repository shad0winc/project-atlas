"""Behavioral gates for the operator-only unidentified-open recovery method."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from atlas.jellyfin_live_streams import (
    JellyfinProcessRetirement, LiveStreamOwnershipError, OwnedJellyfinLiveStreams,
)


class FailedOpenRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.path = self.root / 'streams.json'
        self.row = dict(user_id='viewer', item_id='channel', last_seen=100.0,
                        status='blocked', live_stream_id=None,
                        play_session_id='exact-job', media_source_id='exact-source')
        self.state = {'version': 1, 'streams': {'owner': self.row}}
        self.save()
        self.store = OwnedJellyfinLiveStreams(self.path, clock=lambda: 500.0)
        self.proof = JellyfinProcessRetirement(
            old_generation='old-process', new_generation='new-process',
            old_started_at=50.0, new_started_at=400.0, observed_at=499.0,
            old_process_absent=True, new_provider_healthy=True,
            admission_quiesced=True, native_upstream_closed=True,
            native_consumers_absent=True,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def save(self):
        self.path.write_text(json.dumps(self.state))
        self.path.chmod(0o600)
        self.before = self.path.read_bytes()

    def recover(self, verify=None, **overrides):
        values = dict(session_id='owner', user_id='viewer', item_id='channel',
                      expected_sha256=hashlib.sha256(self.before).hexdigest(),
                      backup_file=self.root / 'before.json',
                      receipt_file=self.root / 'intent.json',
                      verify_retirement=verify or (lambda row: self.proof))
        values.update(overrides)
        return self.store.reconcile_failed_open_after_retirement(**values)

    def test_verified_retirement_preserves_private_evidence_before_removal(self):
        calls = []
        def verify(row):
            self.assertEqual(self.path.read_bytes(), self.before)
            self.assertEqual(row, self.row)
            calls.append(row)
            return self.proof
        self.recover(verify)
        self.assertEqual(len(calls), 2)
        self.assertEqual((self.root / 'before.json').read_bytes(), self.before)
        self.assertEqual(json.loads(self.path.read_bytes()), {'version':1,'streams':{}})
        intent = json.loads((self.root / 'intent.json').read_bytes())
        self.assertEqual(intent['registry_after_sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(intent['status'], 'prepared')
        for name in ('before.json', 'intent.json', 'streams.json'):
            self.assertEqual((self.root / name).stat().st_mode & 0o777, 0o600)

    def test_recovery_does_not_repeat_after_digest_changes(self):
        self.recover()
        with self.assertRaises(LiveStreamOwnershipError):
            self.recover()
        self.assertEqual(json.loads(self.path.read_bytes())['streams'], {})

    def test_owner_item_and_digest_guards_precede_verifier(self):
        for overrides in ({'session_id':'other'}, {'user_id':'other'},
                          {'item_id':'other'}, {'expected_sha256':'0'*64}):
            with self.subTest(overrides=overrides):
                def unexpected(row):
                    self.fail('Invalid scope must not consult provider verifier')
                with self.assertRaises(LiveStreamOwnershipError):
                    self.recover(unexpected, **overrides)
                self.assertEqual(self.path.read_bytes(), self.before)
                self.assertFalse((self.root / 'before.json').exists())

    def test_known_stream_or_nonblocked_state_is_excluded(self):
        for status, stream_id in (('blocked','known-stream'),('opening',None),
                                  ('active','known-stream'),('closing','known-stream')):
            with self.subTest(status=status):
                self.row.update(status=status, live_stream_id=stream_id)
                self.save()
                with self.assertRaises(LiveStreamOwnershipError):
                    self.recover()
                self.assertEqual(self.path.read_bytes(), self.before)

    def test_other_owners_are_preserved_and_recovery_refused(self):
        self.state['streams']['second'] = dict(self.row, user_id='another')
        self.save()
        with self.assertRaises(LiveStreamOwnershipError):
            self.recover()
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_missing_write_ahead_job_or_source_is_refused(self):
        for key in ('play_session_id','media_source_id'):
            with self.subTest(key=key):
                old = self.row[key]
                self.row[key] = None
                self.save()
                with self.assertRaises(LiveStreamOwnershipError):
                    self.recover()
                self.assertEqual(self.path.read_bytes(), self.before)
                self.row[key] = old

    def test_insufficient_stale_or_invalid_evidence_never_removes_owner(self):
        cases = [
            replace(self.proof, old_generation='new-process'),
            replace(self.proof, old_started_at=101),
            replace(self.proof, new_started_at=100),
            replace(self.proof, observed_at=501),
            replace(self.proof, observed_at=450),
            replace(self.proof, observed_at=float('nan')),
            replace(self.proof, old_started_at=True),
            replace(self.proof, new_generation=''),
            replace(self.proof, old_process_absent=False),
            replace(self.proof, new_provider_healthy=False),
            replace(self.proof, admission_quiesced=False),
            replace(self.proof, native_upstream_closed=False),
            replace(self.proof, native_consumers_absent=1),
            None,
        ]
        for evidence in cases:
            with self.subTest(evidence=evidence):
                with self.assertRaises(LiveStreamOwnershipError):
                    self.recover(lambda row: evidence)
                self.assertEqual(self.path.read_bytes(), self.before)
                self.assertFalse((self.root / 'before.json').exists())

    def test_verifier_failure_leaves_latch_intact(self):
        def unavailable(row):
            raise TimeoutError()
        with self.assertRaises(LiveStreamOwnershipError):
            self.recover(unavailable)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_generation_change_between_checks_preserves_latch_and_evidence(self):
        answers = iter((self.proof, replace(self.proof, new_generation='third-process')))
        with self.assertRaises(LiveStreamOwnershipError):
            self.recover(lambda row: next(answers))
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual((self.root / 'before.json').read_bytes(), self.before)
        self.assertTrue((self.root / 'intent.json').exists())

    def test_archive_collision_never_overwrites_evidence_or_removes_owner(self):
        backup = self.root / 'before.json'
        backup.write_bytes(b'existing-evidence')
        with self.assertRaises(FileExistsError):
            self.recover()
        self.assertEqual(backup.read_bytes(), b'existing-evidence')
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_archive_symlink_and_public_directory_are_refused(self):
        target = self.root / 'target'
        target.write_bytes(b'preserve')
        link = self.root / 'before.json'
        link.symlink_to(target)
        with self.assertRaises(OSError):
            self.recover()
        self.assertEqual(target.read_bytes(), b'preserve')
        link.unlink()
        self.root.chmod(0o755)
        with self.assertRaises(LiveStreamOwnershipError):
            self.recover()
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_callback_cannot_mutate_owner_via_input_copy(self):
        def verify(row):
            row['user_id'] = 'injected'
            return self.proof
        self.recover(verify)
        saved = json.loads((self.root / 'before.json').read_bytes())
        self.assertEqual(saved['streams']['owner']['user_id'], 'viewer')

    def test_failed_archive_write_keeps_owner(self):
        missing = self.root / 'missing' / 'receipt.json'
        with self.assertRaises(LiveStreamOwnershipError):
            self.recover(receipt_file=missing)
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual((self.root / 'before.json').read_bytes(), self.before)

    def test_success_reenables_normal_open_with_new_durable_identity(self):
        self.recover()
        with self.store.scope(session_id='new-owner', user_id='viewer',
                              item_id='channel', close=lambda value: None) as owner:
            owner.open(lambda: {'MediaSource': {'LiveStreamId':'new-live-stream'}},
                       play_session_id='new-job', media_source_id='new-source')
        state = json.loads(self.path.read_bytes())
        self.assertEqual(state['streams']['new-owner']['status'], 'active')


if __name__ == '__main__':
    unittest.main()
