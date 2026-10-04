"""Real journal, restart, ownership and bounded receipt recovery behavior."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import Mock, patch

from atlas.media_requests import (
    MediaRequest, MediaRequestStatus, JsonMediaRequestRepository,
    MediaRequestServiceError, MediaRequestServiceConflictError,
)
from atlas.media_requests.repository import MediaRequestRepositoryError
from atlas.media_requests.providers.jellyseerr import JellyseerrMediaRequestProvider
from atlas.media_requests.providers.managed_profiles import ManagedProfileEvidence
from atlas.media_requests.submission_recovery import (
    SubmissionRecoveryRepository, SubmissionRecoveryService,
)

STAMP = "2026-10-04T03:00:00Z"
CLOCK = lambda: datetime(2026, 10, 4, 3, tzinfo=timezone.utc)


def request(**changes):
    fields = dict(request_id="recover", user_id="viewer", media_type="anime_tv",
                  provider="jellyseerr", provider_media_id="123", title="Fixture",
                  season_number=1, audio_preference="english_required", created_at=STAMP)
    fields.update(changes)
    return MediaRequest(**fields)


def backend(**changes):
    fields = dict(id=9, type="tv", is4k=False, serverId=1, profileId=8, status=2,
                  media=dict(tmdbId=123, mediaType="tv", status=3),
                  seasons=[dict(seasonNumber=1)], createdAt=STAMP, updatedAt=STAMP)
    fields.update(changes)
    return fields


def provider(reader=None):
    return JellyseerrMediaRequestProvider(
        "http://unused.invalid", "synthetic", movie_server_id=0, tv_server_id=0,
        anime_movie_server_id=1, anime_tv_server_id=1,
        audio_profile_ids={(c, "english_required"): 8 for c in ("movie", "tv", "anime_movie", "anime_tv")},
        managed_profile_reader=reader or (lambda r, s: ManagedProfileEvidence(r.media_type.value, s, int(r.provider_media_id), 42, 8)),
    )


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = SubmissionRecoveryRepository(self.temp.name)
        self.provider = provider()
        self.service = SubmissionRecoveryService(self.repo, [self.provider], clock=CLOCK)

    def prepare(self, row=None):
        row = self.service.create_request(row or request())
        return self.repo.begin_submission(row, server=1, profile=8, started_at=STAMP)

    def receipt(self):
        intent, attempt = self.prepare()
        return intent, self.repo.observe_receipt(intent, attempt, 9)

    def test_successful_post_captures_receipt_before_get_binding(self):
        self.service.create_request(request())
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", side_effect=[backend(), backend()]) as transport:
            bound = self.service.submit_request("recover")
        self.assertEqual("9", bound.provider_request_id)
        self.assertEqual(MediaRequestStatus.SEARCHING, bound.status)
        self.assertEqual(["POST", "GET"], [c.args[0] for c in transport.call_args_list])
        self.assertEqual("BOUND", self.repo.get_attempt("recover").phase)
        self.assertEqual(2, len(self.repo.pending_submission_events()))

    def test_delayed_arr_creation_receipt_survives_and_restart_recovers_once(self):
        state = [False]
        def reader(row, server):
            return ManagedProfileEvidence(row.media_type.value, server, int(row.provider_media_id),
                                          42 if state[0] else None, 8 if state[0] else None)
        self.provider = provider(reader)
        self.service = SubmissionRecoveryService(self.repo, [self.provider], clock=CLOCK)
        self.service.create_request(request())
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend()) as transport:
            with self.assertRaises(MediaRequestServiceError):
                self.service.submit_request("recover")
            row = self.repo.get("recover")
            self.assertEqual(MediaRequestStatus.SUBMITTING, row.status)
            self.assertIsNone(row.provider_request_id)
            self.assertEqual(9, self.repo.get_attempt("recover").receipt_id)
            with self.assertRaises(MediaRequestServiceError):
                self.service.submit_request("recover")
            state[0] = True
            restarted = SubmissionRecoveryService(SubmissionRecoveryRepository(self.temp.name), [self.provider], clock=CLOCK)
            self.assertEqual("9", restarted.recover_submission("recover").provider_request_id)
            self.assertEqual("9", restarted.recover_submission("recover").provider_request_id)
            self.assertEqual(1, sum(c.args[0] == "POST" for c in transport.call_args_list))
            self.assertEqual(2, len(self.repo.pending_submission_events()))

    def test_timeout_after_post_never_reposts_or_clears_barrier(self):
        self.service.create_request(request())
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", side_effect=TimeoutError("private URL")) as transport:
            for method in (self.service.submit_request, self.service.submit_request, self.service.recover_submission):
                with self.assertRaises(MediaRequestServiceError) as caught:
                    method("recover")
                self.assertNotIn("private", str(caught.exception))
            self.assertEqual(1, transport.call_count)
        self.assertEqual(MediaRequestStatus.SUBMITTING, self.repo.get("recover").status)
        self.assertIsNone(self.repo.get_attempt("recover").receipt_id)
        self.assertEqual({}, self.repo.pending_submission_events())

    def test_crash_after_intent_has_no_retry_permission(self):
        self.prepare()
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport:
            with self.assertRaises(MediaRequestServiceError):
                self.service.submit_request("recover")
            with self.assertRaises(MediaRequestServiceError):
                self.service.recover_submission("recover")
        transport.assert_not_called()

    def test_numeric_receipt_survives_malformed_status_time_and_routing(self):
        for reply in (backend(status=None), backend(createdAt="invalid"), backend(profileId=7)):
            with self.subTest(reply=reply), tempfile.TemporaryDirectory() as folder:
                repo = SubmissionRecoveryRepository(folder)
                service = SubmissionRecoveryService(repo, [self.provider], clock=CLOCK)
                service.create_request(request())
                with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=reply):
                    with self.assertRaises(MediaRequestServiceError):
                        service.submit_request("recover")
                self.assertEqual(9, repo.get_attempt("recover").receipt_id)
                self.assertEqual(MediaRequestStatus.SUBMITTING, repo.get("recover").status)

    def test_existing_profile_conflict_blocks_before_attempt_or_post(self):
        incompatible = provider(lambda r, s: ManagedProfileEvidence(r.media_type.value, s, 123, 42, 7))
        service = SubmissionRecoveryService(self.repo, [incompatible], clock=CLOCK)
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport:
            with self.assertRaises(MediaRequestServiceConflictError):
                service.create_request(request())
        self.assertFalse(self.repo.registry_file.exists())
        transport.assert_not_called()

    def test_conflict_added_after_creation_blocks_post_and_keeps_pending(self):
        row = self.service.create_request(request())
        incompatible = provider(lambda r, s: ManagedProfileEvidence(r.media_type.value, s, 123, 42, 7))
        service = SubmissionRecoveryService(self.repo, [incompatible], clock=CLOCK)
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport:
            with self.assertRaises(MediaRequestServiceConflictError):
                service.submit_request(row.request_id)
        self.assertEqual(MediaRequestStatus.PENDING, self.repo.get(row.request_id).status)
        self.assertIsNone(self.repo.get_attempt(row.request_id))
        transport.assert_not_called()

    def test_actual_native_profile_conflict_blocks_binding(self):
        self.receipt()
        incompatible = provider(lambda r, s: ManagedProfileEvidence(r.media_type.value, s, 123, 42, 7))
        service = SubmissionRecoveryService(self.repo, [incompatible], clock=CLOCK)
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend()):
            with self.assertRaises(MediaRequestServiceError):
                service.recover_submission("recover")
        self.assertEqual(MediaRequestStatus.SUBMITTING, self.repo.get("recover").status)

    def test_missing_or_wrong_resource_evidence_never_binds(self):
        self.receipt()
        cases = [backend(id=10), backend(id=True), backend(type="movie"), backend(is4k=True),
                 backend(is4k=0), backend(serverId=0), backend(serverId=True), backend(profileId=7),
                 backend(media=dict(tmdbId=124)), backend(media=dict(tmdbId=True)),
                 backend(media=dict(tmdbId=123, mediaType="movie")), backend(seasons=[]),
                 backend(seasons=[dict(seasonNumber=1), dict(seasonNumber=1)]),
                 backend(seasons=[dict(seasonNumber=True)]), backend(seasons=[dict(seasonNumber=2)]),
                 backend(profileId="8"), backend(serverId="1")]
        for key in ("id", "type", "is4k", "serverId", "profileId", "media", "seasons"):
            reply = backend(); del reply[key]; cases.append(reply)
        for reply in cases:
            with self.subTest(reply=reply), patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=reply):
                with self.assertRaises(MediaRequestServiceError):
                    self.service.recover_submission("recover")
        self.assertIsNone(self.repo.get("recover").provider_request_id)
        self.assertEqual({}, self.repo.pending_submission_events())

    def test_another_users_overlap_remains_conflict(self):
        self.prepare()
        with self.assertRaises(MediaRequestServiceConflictError):
            self.service.create_request(request(request_id="other", user_id="other-viewer"))
        self.assertEqual(1, len(self.repo.list()))

    def test_two_submit_callers_only_one_post(self):
        self.service.create_request(request())
        barrier = Barrier(2)
        original = self.service._validate_submission
        def validation(provider, row):
            original(provider, row)
            barrier.wait(timeout=5)
        def run():
            try:
                return self.service.submit_request("recover")
            except MediaRequestServiceError:
                return None
        with patch.object(self.service, "_validate_submission", side_effect=validation), patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend()) as transport:
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(1, sum(r is not None for r in results))
        self.assertEqual(1, sum(c.args[0] == "POST" for c in transport.call_args_list))

    def test_two_recovery_workers_bind_once(self):
        self.receipt()
        barrier = Barrier(2)
        def transport(*args):
            barrier.wait(timeout=5)
            return backend()
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", side_effect=transport):
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: self.service.recover_submission("recover"), range(2)))
        self.assertEqual(["9", "9"], [r.provider_request_id for r in results])
        self.assertEqual(2, len(self.repo.pending_submission_events()))

    def test_receipt_cannot_change_or_gain_second_owner(self):
        intent, observed = self.receipt()
        with self.assertRaises(MediaRequestRepositoryError):
            self.repo.observe_receipt(intent, observed, 10)
        other = self.service.create_request(request(request_id="other", provider_media_id="124"))
        other_intent, other_attempt = self.repo.begin_submission(other, server=1, profile=8, started_at=STAMP)
        with self.assertRaises(MediaRequestRepositoryError):
            self.repo.observe_receipt(other_intent, other_attempt, 9)
        self.assertIsNone(self.repo.get_attempt("other").receipt_id)

    def test_generic_replace_or_delete_cannot_clear_journal_barrier(self):
        intent, _ = self.receipt()
        for replacement in (replace(intent, status=MediaRequestStatus.PENDING), replace(intent, user_id="other")):
            with self.assertRaises(MediaRequestRepositoryError):
                self.repo.replace(replacement, expected=intent)
        with self.assertRaises(MediaRequestRepositoryError):
            self.repo.delete("recover")

    def test_stale_writer_cannot_regress_recovered_status(self):
        intent, _ = self.receipt()
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend()):
            bound = self.service.recover_submission("recover")
        with self.assertRaises(MediaRequestRepositoryError):
            self.repo.replace(replace(bound, status=MediaRequestStatus.APPROVED), expected=intent)
        self.assertEqual(bound, self.repo.get("recover"))

    def test_profile_config_drift_blocks_recovery_before_get(self):
        self.receipt()
        changed = replace(self.provider, anime_tv_server_id=2)
        service = SubmissionRecoveryService(self.repo, [changed], clock=CLOCK)
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport:
            with self.assertRaises(MediaRequestServiceError):
                service.recover_submission("recover")
        transport.assert_not_called()

    def test_backend_available_stays_processing(self):
        self.receipt()
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend(media=dict(tmdbId=123, status=5))):
            result = self.service.recover_submission("recover")
        self.assertEqual(MediaRequestStatus.PROCESSING, result.status)
        self.assertIsNone(result.available_at)

    def test_outbox_survives_publish_failure_and_replays_stable_ids(self):
        self.receipt()
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend()):
            self.service.recover_submission("recover")
        failed = SubmissionRecoveryService(self.repo, [self.provider], clock=CLOCK, event_publisher=Mock(side_effect=RuntimeError("secret")))
        ids = set(self.repo.pending_submission_events())
        self.assertEqual(0, failed.drain_submission_events())
        self.assertEqual(ids, set(self.repo.pending_submission_events()))
        self.assertNotIn("secret", str(failed.publication_errors))
        publisher = Mock()
        restarted = SubmissionRecoveryService(SubmissionRecoveryRepository(self.temp.name), [self.provider], clock=CLOCK, event_publisher=publisher)
        self.assertEqual(2, restarted.drain_submission_events())
        self.assertEqual(ids, {c.args[1]["metadata"]["submission_event_id"] for c in publisher.call_args_list})
        self.assertEqual(0, restarted.drain_submission_events())
        self.assertEqual({}, self.repo.pending_submission_events())

    def test_recovery_writer_preserves_journal_on_unrelated_request(self):
        self.receipt()
        other = self.service.create_request(request(request_id="other", provider_media_id="124"))
        self.repo.replace(replace(other, title="Updated"), expected=other)
        self.assertEqual(9, self.repo.get_attempt("recover").receipt_id)

    def test_old_reader_rejects_schema_two(self):
        self.prepare()
        with self.assertRaises(MediaRequestRepositoryError):
            JsonMediaRequestRepository(self.temp.name).list()

    def test_all_seasons_blocks_before_attempt_and_post(self):
        self.service.create_request(request(season_number=None))
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport:
            with self.assertRaises(MediaRequestServiceError):
                self.service.submit_request("recover")
        self.assertEqual(MediaRequestStatus.PENDING, self.repo.get("recover").status)
        self.assertIsNone(self.repo.get_attempt("recover"))
        transport.assert_not_called()

    def test_legacy_none_uses_legacy_post_and_no_attempt(self):
        self.service.create_request(request(audio_preference=None))
        with patch.object(JellyseerrMediaRequestProvider, "_post_json", return_value=backend()) as post:
            result = self.service.submit_request("recover")
        self.assertEqual("9", result.provider_request_id)
        self.assertIsNone(self.repo.get_attempt("recover"))
        post.assert_called_once()

    def test_movie_receipt_recovers_exact_family_without_seasons(self):
        row = self.service.create_request(request(media_type="movie", season_number=None))
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend(type="movie", serverId=0, seasons=[], media=dict(tmdbId=123, mediaType="movie", status=3))):
            bound = self.service.submit_request(row.request_id)
        self.assertEqual("9", bound.provider_request_id)
        self.assertEqual("movie", bound.media_type.value)

    def test_specials_scope_zero_is_valid_but_not_boolean(self):
        row = self.service.create_request(request(season_number=0))
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend(seasons=[dict(seasonNumber=0)])):
            bound = self.service.submit_request(row.request_id)
        self.assertEqual(0, bound.season_number)

    def test_corrupt_missing_or_orphaned_journal_is_rejected(self):
        self.receipt()
        original = self.repo.registry_file.read_text()
        for mutation in ("missing", "orphan", "owner", "fingerprint"):
            document = json.loads(original)
            if mutation == "missing":
                del document["submissions"]
            elif mutation == "orphan":
                del document["requests"]["recover"]
            elif mutation == "owner":
                document["requests"]["recover"]["user_id"] = "other"
            else:
                document["submissions"]["recover"]["fingerprint"] = "0" * 64
            self.repo.registry_file.write_text(json.dumps(document))
            with self.subTest(mutation=mutation), self.assertRaises(MediaRequestRepositoryError):
                self.repo.list()
        self.repo.registry_file.write_text(original)

    def test_failed_intent_persistence_never_posts(self):
        self.service.create_request(request())
        with patch("atlas.media_requests.submission_recovery.os.replace", side_effect=OSError("private path")), patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport:
            with self.assertRaises(MediaRequestServiceError):
                self.service.submit_request("recover")
        transport.assert_not_called()
        self.assertEqual(MediaRequestStatus.PENDING, self.repo.get("recover").status)
        self.assertIsNone(self.repo.get_attempt("recover"))

    def test_bounded_reconciler_preserves_receipt_free_attempt(self):
        from atlas.media_requests.submission_reconciler import reconcile_submission_receipts
        self.receipt()
        other = self.service.create_request(request(request_id="other", provider_media_id="124"))
        self.repo.begin_submission(other, server=1, profile=8, started_at=STAMP)
        with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend()) as transport:
            outcome = reconcile_submission_receipts(self.service)
        self.assertEqual((2, 1, 1, 0, 0), (outcome.considered, outcome.recovered, outcome.needs_correlation, outcome.unverified, outcome.skipped))
        self.assertEqual(1, transport.call_count)
        self.assertEqual(MediaRequestStatus.SUBMITTING, self.repo.get("other").status)


class MigrationTests(unittest.TestCase):
    def test_explicit_migration_keeps_byte_exact_backup_and_legacy_serialization(self):
        with tempfile.TemporaryDirectory() as folder:
            old = JsonMediaRequestRepository(folder)
            row = request(audio_preference=None)
            old.save(row)
            old.registry_file.chmod(0o640)
            original_stat = old.registry_file.stat()
            baseline = old.registry_file.read_bytes()
            backup = Path(folder) / "reviewed-backup.json"
            new = SubmissionRecoveryRepository.migrate_from_v1(folder, expected_sha256=hashlib.sha256(baseline).hexdigest(), backup_file=backup)
            self.assertEqual(baseline, backup.read_bytes())
            self.assertEqual(row.to_dict(), new.get(row.request_id).to_dict())
            self.assertEqual({}, new.pending_submission_events())
            with self.assertRaises(MediaRequestRepositoryError):
                old.list()
            self.assertEqual(0o600, backup.stat().st_mode & 0o777)
            migrated_stat = new.registry_file.stat()
            self.assertEqual(0o640, migrated_stat.st_mode & 0o777)
            self.assertEqual((original_stat.st_uid, original_stat.st_gid), (migrated_stat.st_uid, migrated_stat.st_gid))

    def test_migration_hash_drift_and_existing_backup_never_overwrite(self):
        for failure in ("drift", "backup_exists"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                old = JsonMediaRequestRepository(folder)
                old.save(request())
                raw = old.registry_file.read_bytes()
                backup = Path(folder) / "reviewed-backup.json"
                if failure == "backup_exists":
                    backup.write_bytes(b"preserve")
                expected = "0" * 64 if failure == "drift" else hashlib.sha256(raw).hexdigest()
                with self.assertRaises(MediaRequestRepositoryError):
                    SubmissionRecoveryRepository.migrate_from_v1(folder, expected_sha256=expected, backup_file=backup)
                self.assertEqual(raw, old.registry_file.read_bytes())
                if failure == "backup_exists":
                    self.assertEqual(b"preserve", backup.read_bytes())

    def test_constructor_does_not_implicitly_migrate_existing_v1(self):
        with tempfile.TemporaryDirectory() as folder:
            old = JsonMediaRequestRepository(folder)
            old.save(request())
            raw = old.registry_file.read_bytes()
            with self.assertRaises(MediaRequestRepositoryError):
                SubmissionRecoveryRepository(folder).list()
            self.assertEqual(raw, old.registry_file.read_bytes())


class TransportTests(unittest.TestCase):
    def test_transport_builds_exact_method_no_redirect_handler_and_bounded_timeout(self):
        from atlas.media_requests.providers.managed_profiles import _NoRedirect
        response = Mock()
        response.read.return_value = b'{"id":9}'
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch("urllib.request.build_opener", return_value=opener) as build:
            self.assertEqual({"id": 9}, provider()._recovery_json("GET", "/api/v1/request/9"))
        handler = build.call_args.args[0]
        self.assertIsInstance(handler, _NoRedirect)
        self.assertIsNone(handler.redirect_request(None, None, 302, "redirect", {}, "http://other.invalid"))
        self.assertEqual("GET", opener.open.call_args.args[0].get_method())
        self.assertEqual(10.0, opener.open.call_args.kwargs["timeout"])

    def test_recovery_transport_rejects_duplicate_fields_and_oversize(self):
        for raw in (b'{"id":9,"id":10}', b'x' * 2_000_001):
            response = Mock()
            response.read.return_value = raw
            opener = Mock()
            opener.open.return_value.__enter__ = Mock(return_value=response)
            opener.open.return_value.__exit__ = Mock(return_value=False)
            with self.subTest(size=len(raw)), patch("urllib.request.build_opener", return_value=opener):
                with self.assertRaises(ValueError):
                    provider()._recovery_json("GET", "/api/v1/request/9")
            response.read.assert_called_once_with(2_000_001)

    def test_exact_get_and_post_endpoints_only(self):
        with patch("urllib.request.build_opener") as opener:
            for method, path in (("GET", "/api/v1/request"), ("DELETE", "/api/v1/request/9"),
                                 ("POST", "/api/v1/request/9"), ("GET", "/api/v1/request/9?extra=1")):
                with self.assertRaises(ValueError):
                    provider()._recovery_json(method, path)
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
