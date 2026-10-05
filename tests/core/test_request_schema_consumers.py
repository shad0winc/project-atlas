"""Schema selection, journal preservation and production consumer compatibility."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlas.media_requests.construction import build_request_service, open_request_repository
from atlas.media_requests.models import MediaRequest
from atlas.media_requests.providers.jellyseerr import JellyseerrMediaRequestProvider
from atlas.media_requests.repository import JsonMediaRequestRepository, MediaRequestRepositoryError
from atlas.media_requests.service import MediaRequestService, MediaRequestServiceError
from atlas.media_requests.submission_recovery import SubmissionRecoveryRepository, SubmissionRecoveryService


class RepositorySelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / "requests.json"
        self.provider = JellyseerrMediaRequestProvider("http://unused.invalid", "synthetic")

    def write(self, schema, **extra):
        self.registry.write_text(json.dumps(dict(schema_version=schema, requests={}, **extra)))
        return self.registry.read_bytes()

    def test_absent_state_does_not_initialize_or_create_schema_two(self):
        root = self.root / "missing"
        repository = open_request_repository(root)
        service = build_request_service(repository, [self.provider])
        self.assertIs(type(repository), JsonMediaRequestRepository)
        self.assertIs(type(service), MediaRequestService)
        self.assertFalse(root.exists())

    def test_schema_one_construction_preserves_bytes_mode_and_directory(self):
        raw = self.write(1)
        self.registry.chmod(0o640)
        before = set(self.root.iterdir())
        repository = open_request_repository(self.root)
        publisher = lambda name, payload: None
        service = build_request_service(repository, [self.provider], event_publisher=publisher)
        self.assertIs(type(service), MediaRequestService)
        self.assertIs(service._event_publisher, publisher)
        self.assertEqual(self.registry.read_bytes(), raw)
        self.assertEqual(self.registry.stat().st_mode & 0o777, 0o640)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_schema_two_pairs_recovery_service_without_initialization(self):
        raw = self.write(2, submissions={}, submission_outbox={})
        repository = open_request_repository(self.root)
        service = build_request_service(repository, [self.provider])
        self.assertIs(type(repository), SubmissionRecoveryRepository)
        self.assertIs(type(service), SubmissionRecoveryService)
        self.assertEqual(self.registry.read_bytes(), raw)
        self.assertEqual(set(self.root.iterdir()), {self.registry})

    def test_invalid_or_unknown_contract_is_rejected_without_rewriting(self):
        for document in (
            [], {}, {"schema_version": True, "requests": {}},
            {"schema_version": 1.0, "requests": {}},
            {"schema_version": 3, "requests": {}},
            {"schema_version": 1, "requests": []},
            {"schema_version": 1, "requests": {}, "submissions": {}},
            {"schema_version": 2, "requests": {}},
            {"schema_version": 2, "requests": {}, "submissions": [], "submission_outbox": {}},
        ):
            with self.subTest(document=document):
                self.registry.write_text(json.dumps(document))
                raw = self.registry.read_bytes()
                with self.assertRaises(MediaRequestRepositoryError):
                    open_request_repository(self.root)
                self.assertEqual(self.registry.read_bytes(), raw)
        self.registry.write_bytes(b"\xffprivate-invalid-json")
        with self.assertRaisesRegex(MediaRequestRepositoryError, "contract is invalid"):
            open_request_repository(self.root)
        self.assertEqual(self.registry.read_bytes(), b"\xffprivate-invalid-json")

    def test_symlink_and_fifo_fail_without_following_or_blocking(self):
        target = self.root / "target"
        target.write_text('{"schema_version": 1, "requests": {}}')
        self.registry.symlink_to(target)
        with self.assertRaises(MediaRequestRepositoryError):
            open_request_repository(self.root)
        self.assertTrue(self.registry.is_symlink())
        self.registry.unlink()
        os.mkfifo(self.registry)
        with self.assertRaises(MediaRequestRepositoryError):
            open_request_repository(self.root)

    def test_unknown_post_barrier_survives_new_service_and_forbids_repost(self):
        repository = SubmissionRecoveryRepository(self.root)
        request = MediaRequest(
            request_id="fixture", user_id="viewer", media_type="movie",
            provider="jellyseerr", provider_media_id="123", title="Fixture",
            audio_preference="english_required", created_at="2026-10-05T00:00:00Z",
        )
        repository.save(request)
        repository.begin_submission(request, server=0, profile=8, started_at=request.created_at)
        raw = self.registry.read_bytes()
        service = build_request_service(open_request_repository(self.root), [self.provider])
        with patch.object(JellyseerrMediaRequestProvider, "submit_with_receipt") as post:
            with self.assertRaises(MediaRequestServiceError):
                service.submit_request(request.request_id)
            post.assert_not_called()
        self.assertEqual(self.registry.read_bytes(), raw)

    def test_pending_outbox_survives_schema_selection_and_request_writes(self):
        self.write(2, submissions={}, submission_outbox={
            "stable": {"event": "request.submitted", "payload": {
                "metadata": {"submission_event_id": "stable"}}, "delivered": False},
        })
        repository = open_request_repository(self.root)
        repository.save(MediaRequest(
            request_id="legacy", user_id="viewer", media_type="movie",
            provider="jellyseerr", provider_media_id="123", title="Fixture",
        ))
        self.assertEqual(list(repository.pending_submission_events()), ["stable"])

    def test_cached_consumer_rejects_schema_change_without_rewriting(self):
        self.write(1)
        legacy = open_request_repository(self.root)
        raw = self.write(2, submissions={}, submission_outbox={})
        with self.assertRaises(MediaRequestRepositoryError):
            legacy.list()
        self.assertEqual(self.registry.read_bytes(), raw)
        recovery = open_request_repository(self.root)
        raw = self.write(1)
        with self.assertRaises(MediaRequestRepositoryError):
            recovery.list()
        self.assertEqual(self.registry.read_bytes(), raw)

    def test_restore_validator_accepts_both_schemas_without_migrating(self):
        script = Path(__file__).resolve().parents[2] / "scripts/lib/validate-recovery-state.py"
        spec = importlib.util.spec_from_file_location("request_restore_fixture", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for schema in (1, 2):
            raw = self.write(schema, **({"submissions": {}, "submission_outbox": {}} if schema == 2 else {}))
            self.assertEqual(module._validate_requests(self.root), "0 requests")
            self.assertEqual(self.registry.read_bytes(), raw)


class SchedulerConsumerTests(unittest.TestCase):
    def test_scheduler_uses_persisted_schema_and_preserves_publisher(self):
        from atlas.media_requests.scheduled_reconcile import build_default_service
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            provider = JellyseerrMediaRequestProvider("http://unused.invalid", "synthetic")
            for schema in (1, 2):
                raw = json.dumps(dict(schema_version=schema, requests={}, **(
                    {"submissions": {}, "submission_outbox": {}} if schema == 2 else {}))).encode()
                (root / "requests.json").write_bytes(raw)
                with patch.dict(os.environ, {"ATLAS_REQUESTS_DIR": folder}), patch(
                    "atlas.media_requests.scheduled_reconcile.default_jellyseerr_media_request_provider",
                    return_value=provider,
                ), patch("atlas.media_requests.scheduled_reconcile.publish_core_event") as publish:
                    service = build_default_service()
                    self.assertIs(type(service), SubmissionRecoveryService if schema == 2 else MediaRequestService)
                    service._event_publisher("request.available", {})
                    publish.assert_called_once_with("request.available", {}, source="atlas-requests")
                self.assertEqual((root / "requests.json").read_bytes(), raw)
