"""Real-file replay, durability, contention and outbox acknowledgement contracts."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlas.media_requests.construction import build_request_service
from atlas.media_requests.submission_events import (
    MAX_RECORD_BYTES, SubmissionEventJournalPublisher, SubmissionEventPublicationError,
)
from atlas.media_requests.providers.jellyseerr import JellyseerrMediaRequestProvider
from atlas.media_requests.submission_recovery import SubmissionRecoveryRepository

EVENT = "request.submitted"
KEY = "a" * 32 + ":" + EVENT


def payload():
    return {"request_id": "fixture", "metadata": {"submission_event_id": KEY}}


class SubmissionPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = self.root / "events.jsonl"
        self.journal.touch(mode=0o640)
        self.publisher = SubmissionEventJournalPublisher(self.journal)
        self.provider = JellyseerrMediaRequestProvider("http://unused.invalid", "synthetic")

    def blocked(self, raw):
        self.journal.write_bytes(raw)
        with self.assertRaises(SubmissionEventPublicationError):
            self.publisher.publish(EVENT, payload())
        self.assertEqual(raw, self.journal.read_bytes())

    def test_restart_replay_keeps_one_identical_record_and_fsyncs(self):
        self.assertTrue(self.publisher.publish(EVENT, payload()))
        raw = self.journal.read_bytes()
        with patch("atlas.media_requests.submission_events.os.fsync", wraps=os.fsync) as sync:
            self.assertFalse(SubmissionEventJournalPublisher(self.journal).publish(EVENT, payload()))
            sync.assert_called_once()
        self.assertEqual(raw, self.journal.read_bytes())
        record = json.loads(raw)
        self.assertEqual("atlas-requests", record["source"])
        self.assertTrue(record["id"].startswith("evt-submission-"))

    def test_conflicting_reuse_preserves_evidence(self):
        self.publisher.publish(EVENT, payload())
        raw = self.journal.read_bytes()
        changed = payload()
        changed["request_id"] = "another"
        with self.assertRaises(SubmissionEventPublicationError):
            self.publisher.publish(EVENT, changed)
        self.assertEqual(raw, self.journal.read_bytes())

    def test_legacy_random_identity_is_replayed_without_another_append(self):
        for source in ("atlas-api", "atlas-requests"):
            with self.subTest(source=source):
                raw = (json.dumps(dict(schema=2, id="evt-old", source=source,
                    event=EVENT, payload=payload())) + "\n").encode()
                self.journal.write_bytes(raw)
                self.assertFalse(self.publisher.publish(EVENT, payload()))
                self.assertEqual(raw, self.journal.read_bytes())

    def test_duplicate_logical_records_require_reconciliation(self):
        self.publisher.publish(EVENT, payload())
        raw = self.journal.read_bytes()
        self.blocked(raw + raw)

    def test_stable_outer_identity_collision_is_rejected(self):
        self.publisher.publish(EVENT, payload())
        record = json.loads(self.journal.read_bytes())
        record["payload"]["metadata"]["submission_event_id"] = "b" * 32 + ":" + EVENT
        self.blocked((json.dumps(record) + "\n").encode())

    def test_fsync_failure_can_replay_complete_append(self):
        with patch("atlas.media_requests.submission_events.os.fsync", side_effect=OSError("synthetic")):
            with self.assertRaises(SubmissionEventPublicationError):
                self.publisher.publish(EVENT, payload())
        raw = self.journal.read_bytes()
        self.assertFalse(self.publisher.publish(EVENT, payload()))
        self.assertEqual(raw, self.journal.read_bytes())

    def test_replaced_journal_path_is_not_acknowledged(self):
        original = self.root / "original.jsonl"
        real_sync = os.fsync
        def replace_after_sync(fd):
            real_sync(fd)
            self.journal.rename(original)
            self.journal.touch(mode=0o640)
        with patch("atlas.media_requests.submission_events.os.fsync", side_effect=replace_after_sync):
            with self.assertRaises(SubmissionEventPublicationError):
                self.publisher.publish(EVENT, payload())
        self.assertEqual(1, len(original.read_bytes().splitlines()))
        self.assertEqual(b"", self.journal.read_bytes())

    def test_short_write_leaves_pending_partial_tail_without_repair(self):
        real_write = os.write
        with patch("atlas.media_requests.submission_events.os.write", side_effect=lambda fd, raw: real_write(fd, raw[:10])):
            with self.assertRaises(SubmissionEventPublicationError):
                self.publisher.publish(EVENT, payload())
        raw = self.journal.read_bytes()
        self.assertEqual(10, len(raw))
        self.blocked(raw)

    def test_corrupt_or_incomplete_records_are_preserved(self):
        for raw in (b'{"unfinished":', b'not-json\n', b'[]\n', b'{"id":1,"id":2}\n', b'\xff\n'):
            with self.subTest(raw=raw):
                self.blocked(raw)

    def test_invalid_payloads_do_not_append(self):
        for candidate in ({}, {"metadata": {"submission_event_id": "invalid"}},
                          dict(payload(), title=float("nan")), dict(payload(), title="x" * MAX_RECORD_BYTES)):
            with self.subTest(candidate_type=type(candidate)):
                with self.assertRaises(SubmissionEventPublicationError):
                    self.publisher.publish(EVENT, candidate)
                self.assertEqual(b"", self.journal.read_bytes())
        with self.assertRaises(SubmissionEventPublicationError):
            self.publisher.publish("request.searching", payload())

    def test_missing_symlink_fifo_and_world_permissions_are_rejected(self):
        self.journal.unlink()
        with self.assertRaises(SubmissionEventPublicationError):
            self.publisher.publish(EVENT, payload())
        self.assertFalse(self.journal.exists())
        target = self.root / "target"
        target.touch(mode=0o640)
        self.journal.symlink_to(target)
        with self.assertRaises(SubmissionEventPublicationError):
            self.publisher.publish(EVENT, payload())
        self.assertEqual(b"", target.read_bytes())
        self.journal.unlink()
        os.mkfifo(self.journal, 0o640)
        with self.assertRaises(SubmissionEventPublicationError):
            self.publisher.publish(EVENT, payload())
        self.journal.unlink()
        self.journal.touch(mode=0o644)
        with self.assertRaises(SubmissionEventPublicationError):
            self.publisher.publish(EVENT, payload())
        self.assertEqual(b"", self.journal.read_bytes())

    def test_lock_contention_fails_without_append(self):
        with self.journal.open("rb") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(SubmissionEventPublicationError):
                self.publisher.publish(EVENT, payload())
        self.assertEqual(b"", self.journal.read_bytes())
        self.assertTrue(self.publisher.publish(EVENT, payload()))

    def test_concurrent_writers_and_retries_leave_one_record(self):
        def publish(_):
            try:
                return SubmissionEventJournalPublisher(self.journal).publish(EVENT, payload())
            except SubmissionEventPublicationError:
                return None  # Contention retains work for retry.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(publish, range(32)))
        self.assertEqual(1, results.count(True))
        self.assertFalse(self.publisher.publish(EVENT, payload()))
        self.assertEqual(1, len(self.journal.read_bytes().splitlines()))

    def test_scan_and_append_budgets_preserve_journal(self):
        bounded = SubmissionEventJournalPublisher(self.journal, max_journal_bytes=MAX_RECORD_BYTES)
        for raw in (b"\n" * (MAX_RECORD_BYTES + 1), b"\n" * (MAX_RECORD_BYTES - 1)):
            self.journal.write_bytes(raw)
            with self.assertRaises(SubmissionEventPublicationError):
                bounded.publish(EVENT, payload())
            self.assertEqual(raw, self.journal.read_bytes())

    def test_schema_two_factory_acknowledges_after_durable_replay_only(self):
        root = self.root / "requests"
        root.mkdir()
        registry = root / "requests.json"
        registry.write_text(json.dumps(dict(schema_version=2, requests={}, submissions={},
            submission_outbox={KEY: dict(event=EVENT, payload=payload(), delivered=False)})))
        repository = SubmissionRecoveryRepository(root)
        generic_calls = []
        with patch.dict(os.environ, {"ATLAS_EVENT_LOG": str(self.journal)}):
            service = build_request_service(repository, [self.provider], event_publisher=lambda *args: generic_calls.append(args))
        before = registry.read_bytes()
        with patch.object(repository, "acknowledge_submission_event", side_effect=OSError("synthetic crash boundary")):
            self.assertEqual(0, service.drain_submission_events())
        raw = self.journal.read_bytes()
        self.assertEqual(before, registry.read_bytes())
        restarted = SubmissionRecoveryRepository(root)
        with patch.dict(os.environ, {"ATLAS_EVENT_LOG": str(self.journal)}):
            service = build_request_service(restarted, [self.provider])
        self.assertEqual(1, service.drain_submission_events())
        self.assertEqual({}, restarted.pending_submission_events())
        self.assertEqual(raw, self.journal.read_bytes())
        self.assertEqual([], generic_calls)
        self.assertEqual(0, service.drain_submission_events())

    def test_publication_failure_does_not_acknowledge_outbox(self):
        root = self.root / "requests"
        root.mkdir()
        registry = root / "requests.json"
        registry.write_text(json.dumps(dict(schema_version=2, requests={}, submissions={},
            submission_outbox={KEY: dict(event=EVENT, payload=payload(), delivered=False)})))
        repository = SubmissionRecoveryRepository(root)
        with patch.dict(os.environ, {"ATLAS_EVENT_LOG": str(self.journal)}):
            service = build_request_service(repository, [self.provider])
        raw = registry.read_bytes()
        with patch("atlas.media_requests.submission_events.os.fsync", side_effect=OSError("synthetic")):
            self.assertEqual(0, service.drain_submission_events())
        self.assertEqual(raw, registry.read_bytes())
        self.assertEqual(1, service.drain_submission_events())
        self.assertEqual(1, len(self.journal.read_bytes().splitlines()))

    def test_constructor_has_no_journal_io_and_rejects_relative_paths(self):
        missing = self.root / "missing"
        SubmissionEventJournalPublisher(missing)
        self.assertFalse(missing.exists())
        with self.assertRaises(ValueError):
            SubmissionEventJournalPublisher("relative")


if __name__ == "__main__":
    unittest.main()
