"""Bounded work, rotating backlog coverage and preserved submission barriers."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from atlas.media_requests.models import MediaRequest, MediaRequestStatus
from atlas.media_requests.providers.jellyseerr import JellyseerrMediaRequestProvider
from atlas.media_requests.repository import MediaRequestRepositoryError
from atlas.media_requests.service import MediaRequestServiceError
from atlas.media_requests.submission_batches import submission_batch
from atlas.media_requests.submission_reconciler import reconcile_submission_receipts
from atlas.media_requests.submission_recovery import SubmissionRecoveryRepository, SubmissionRecoveryService


class SubmissionBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / "requests.json"
        self.repo = SubmissionRecoveryRepository(self.root)
        self.provider = JellyseerrMediaRequestProvider("http://unused.invalid", "synthetic")
        self.published = []
        self.service = SubmissionRecoveryService(self.repo, [self.provider],
            event_publisher=lambda name, payload: self.published.append(payload["request_id"]))

    def rows(self, count):
        return tuple(MediaRequest(request_id=str(i), user_id="viewer", media_type="movie",
            provider="jellyseerr", provider_media_id=str(i + 1), title="Synthetic",
            status=MediaRequestStatus.SUBMITTING) for i in range(count))

    def outbox(self, count):
        self.registry.write_text(json.dumps(dict(schema_version=2, requests={}, submissions={},
            submission_outbox={f"{i:032x}:request.submitted": dict(event="request.submitted",
                payload=dict(request_id=str(i), metadata=dict(submission_event_id=f"{i:032x}:request.submitted")),
                delivered=False) for i in range(count)})))

    def test_stable_backlog_is_covered_in_rotating_bounded_windows(self):
        seen = set()
        for minute in range(3):
            batch = submission_batch(range(250), limit=100, offset=minute * 100)
            self.assertEqual(100, len(batch))
            seen.update(batch)
        self.assertEqual(set(range(250)), seen)
        self.assertEqual((2, 0, 1), submission_batch(range(3), offset=100 * 2))

    def test_empty_and_small_backlogs_do_not_duplicate_items(self):
        self.assertEqual((), submission_batch([]))
        self.assertEqual(3, len(set(submission_batch(range(3), offset=10**12))))

    def test_invalid_limits_and_offsets_are_rejected(self):
        for limit in (False, 0, 101, 1.0, "1"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                submission_batch([], limit=limit)
        for offset in (True, -1, 1.0, "1"):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                submission_batch([], offset=offset)

    def test_receipt_free_barriers_do_not_call_recovery_or_submit(self):
        with patch.object(self.service, "list_recovery_required_requests", return_value=self.rows(101)), patch.object(
            self.repo, "get_attempt", return_value=SimpleNamespace(receipt_id=None)), patch.object(
            self.service, "recover_submission") as recover, patch.object(JellyseerrMediaRequestProvider, "submit_with_receipt") as post:
            outcome = reconcile_submission_receipts(self.service)
        self.assertEqual((100, 0, 100), (outcome.considered, outcome.recovered, outcome.needs_correlation))
        recover.assert_not_called()
        post.assert_not_called()
        self.assertFalse(self.registry.exists())

    def test_item_lookup_failure_does_not_block_later_receipt(self):
        with patch.object(self.service, "list_recovery_required_requests", return_value=self.rows(2)), patch.object(
            self.repo, "get_attempt", side_effect=[MediaRequestRepositoryError("synthetic"), SimpleNamespace(receipt_id=7)]), patch.object(
            self.service, "recover_submission") as recover:
            outcome = reconcile_submission_receipts(self.service)
        self.assertEqual((1, 1), (outcome.unverified, outcome.recovered))
        recover.assert_called_once_with("1")

    def test_failed_verification_does_not_block_next_item(self):
        with patch.object(self.service, "list_recovery_required_requests", return_value=self.rows(2)), patch.object(
            self.repo, "get_attempt", return_value=SimpleNamespace(receipt_id=7)), patch.object(
            self.service, "recover_submission", side_effect=[MediaRequestServiceError("synthetic"), None]):
            outcome = reconcile_submission_receipts(self.service)
        self.assertEqual((1, 1), (outcome.unverified, outcome.recovered))

    def test_rotating_receipt_pass_reaches_item_after_blocked_prefix(self):
        with patch.object(self.service, "list_recovery_required_requests", return_value=self.rows(101)), patch.object(
            self.repo, "get_attempt", return_value=SimpleNamespace(receipt_id=7)), patch.object(
            self.service, "recover_submission") as recover:
            outcome = reconcile_submission_receipts(self.service, limit=1, offset=100)
        self.assertEqual(1, outcome.considered)
        recover.assert_called_once_with("100")

    def test_non_submitting_recovery_items_are_skipped(self):
        row = replace(self.rows(1)[0], status=MediaRequestStatus.CANCELLING, provider_request_id="7")
        with patch.object(self.service, "list_recovery_required_requests", return_value=(row,)), patch.object(
            self.repo, "get_attempt") as lookup:
            outcome = reconcile_submission_receipts(self.service)
        self.assertEqual(1, outcome.skipped)
        lookup.assert_not_called()

    def test_default_outbox_pass_attempts_at_most_one_hundred(self):
        self.outbox(101)
        self.assertEqual(100, self.service.drain_submission_events())
        self.assertEqual(100, len(self.published))
        self.assertEqual(100, self.service.submission_event_attempts)
        self.assertEqual(1, len(self.repo.pending_submission_events()))
        self.assertEqual(1, self.service.drain_submission_events())
        self.assertEqual({}, self.repo.pending_submission_events())

    def test_failed_publication_counts_against_limit_and_preserves_pending(self):
        self.outbox(5)
        attempts = []
        def publish(name, payload):
            attempts.append(payload["request_id"])
            raise OSError("synthetic")
        self.service._submission_event_publisher = publish
        raw = self.registry.read_bytes()
        self.assertEqual(0, self.service.drain_submission_events(limit=2))
        self.assertEqual(["0", "1"], attempts)
        self.assertEqual(2, self.service.submission_event_attempts)
        self.assertEqual(raw, self.registry.read_bytes())
        self.service.drain_submission_events(limit=2, offset=2)
        self.assertEqual(["0", "1", "2", "3"], attempts)
        self.assertEqual(raw, self.registry.read_bytes())

    def test_acknowledgement_failure_retains_item_and_continues_batch(self):
        self.outbox(3)
        original = self.repo.acknowledge_submission_event
        def acknowledge(key):
            if key.startswith("0" * 32):
                raise OSError("synthetic")
            original(key)
        with patch.object(self.repo, "acknowledge_submission_event", side_effect=acknowledge):
            self.assertEqual(1, self.service.drain_submission_events(limit=2))
        self.assertEqual(2, len(self.repo.pending_submission_events()))
        self.assertEqual(["0", "1"], self.published)


if __name__ == "__main__":
    unittest.main()
