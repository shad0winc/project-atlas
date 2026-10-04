"""Shared acquisition conflicts, authoritative instance reads and lifecycle gates."""
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import Mock, patch

from atlas.media_requests import (
    JsonMediaRequestRepository, JellyseerrMediaRequestProvider, MediaRequest,
    MediaRequestProviderError, MediaRequestService, MediaRequestServiceError,
    MediaRequestServiceConflictError, MediaRequestStatus,
)
from atlas.media_requests.provider import ProviderStatusResult
from atlas.media_requests.providers.managed_profiles import (
    ArrManagedProfileReader, ArrProfileBinding, ManagedProfileEvidence,
)

STAMP = "2026-10-03T00:00:00Z"


def request(**changes):
    fields = dict(request_id="guard", user_id="viewer", media_type="anime_tv",
                  provider="jellyseerr", provider_media_id="123", title="Fixture",
                  season_number=1, created_at=STAMP, audio_preference="english_required")
    fields.update(changes)
    return MediaRequest(**fields)


def evidence(row, server, profile=8, item=42):
    return ManagedProfileEvidence(row.media_type.value, server, int(row.provider_media_id), item, profile)


def provider(reader=None):
    return JellyseerrMediaRequestProvider(
        "http://unused.invalid", "synthetic", movie_server_id=0, tv_server_id=0,
        anime_movie_server_id=1, anime_tv_server_id=1,
        audio_profile_ids={(c, "english_required"): 8 for c in ("movie", "tv", "anime_movie", "anime_tv")},
        managed_profile_reader=reader,
    )


REPLY = dict(id=9, status=2, serverId=1, profileId=8, createdAt=STAMP, updatedAt=STAMP)


class ProfileGuardTests(unittest.TestCase):
    def test_missing_reader_blocks_before_persistence(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(JellyseerrMediaRequestProvider, "_post_json") as post:
            repo = JsonMediaRequestRepository(folder)
            with self.assertRaises(MediaRequestServiceError):
                MediaRequestService(repo, [provider()]).create_request(request())
            self.assertFalse(repo.registry_file.exists())
            post.assert_not_called()

    def test_conflicting_existing_profile_is_service_conflict(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(JellyseerrMediaRequestProvider, "_post_json") as post:
            repo = JsonMediaRequestRepository(folder)
            with self.assertRaises(MediaRequestServiceConflictError):
                MediaRequestService(repo, [provider(lambda r, s: evidence(r, s, 7))]).create_request(request())
            self.assertFalse(repo.registry_file.exists())
            post.assert_not_called()

    def test_identity_mismatch_and_reader_failure_are_rejected(self):
        readers = [lambda r, s: evidence(r, 0), lambda r, s: evidence(replace(r, provider_media_id="124"), s),
                   lambda r, s: evidence(replace(r, media_type="tv"), s),
                   Mock(side_effect=RuntimeError("private backend details")), lambda r, s: None]
        for reader in readers:
            with self.subTest(reader=type(reader)), self.assertRaises(MediaRequestProviderError):
                provider(reader).validate_submission(request())

    def test_conflict_added_after_creation_blocks_post(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(JellyseerrMediaRequestProvider, "_post_json") as post:
            current = [8]
            repo = JsonMediaRequestRepository(folder)
            service = MediaRequestService(repo, [provider(lambda r, s: evidence(r, s, current[0]))])
            row = service.create_request(request())
            current[0] = 7
            with self.assertRaises(MediaRequestServiceConflictError):
                service.submit_request(row.request_id)
            self.assertEqual(MediaRequestStatus.PENDING, repo.get(row.request_id).status)
            post.assert_not_called()

    def test_new_title_without_post_confirmation_retains_submitting_and_cannot_retry(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(JellyseerrMediaRequestProvider, "_post_json", return_value=REPLY) as post:
            repo = JsonMediaRequestRepository(folder)
            service = MediaRequestService(repo, [provider(lambda r, s: evidence(r, s, None, None))])
            row = service.create_request(request())
            with self.assertRaises(MediaRequestServiceError):
                service.submit_request(row.request_id)
            self.assertEqual(MediaRequestStatus.SUBMITTING, repo.get(row.request_id).status)
            with self.assertRaises(MediaRequestServiceError):
                service.submit_request(row.request_id)
            self.assertEqual(1, post.call_count)

    def test_post_confirmation_can_establish_new_title(self):
        reader = Mock(side_effect=[evidence(request(), 1, None, None), evidence(request(), 1)])
        with patch.object(JellyseerrMediaRequestProvider, "_post_json", return_value=REPLY) as post:
            result = provider(reader).submit(request())
            self.assertEqual("9", result.provider_request_id)
            self.assertEqual(2, reader.call_count)
            self.assertEqual(1, post.call_count)

    def test_post_profile_change_does_not_become_success(self):
        reader = Mock(side_effect=[evidence(request(), 1), evidence(request(), 1, 7)])
        with patch.object(JellyseerrMediaRequestProvider, "_post_json", return_value=REPLY):
            with self.assertRaises(MediaRequestProviderError):
                provider(reader).submit(request())

    def test_available_promotion_and_refresh_revalidate_profile(self):
        for method in ("mark_available", "refresh_request"):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as folder:
                repo = JsonMediaRequestRepository(folder)
                row = replace(request(), status=MediaRequestStatus.PROCESSING, provider_request_id="9")
                repo.save(row)
                service = MediaRequestService(repo, [provider(lambda r, s: evidence(r, s, 7))])
                result = ProviderStatusResult(provider="jellyseerr", provider_request_id="9", status=MediaRequestStatus.AVAILABLE,
                                              updated_at=STAMP, available_at=STAMP)
                with patch.object(JellyseerrMediaRequestProvider, "get_status", return_value=result):
                    with self.assertRaises(MediaRequestServiceError):
                        getattr(service, method)(row.request_id)
                self.assertEqual(MediaRequestStatus.PROCESSING, repo.get(row.request_id).status)

    def test_matching_profile_can_become_available(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = JsonMediaRequestRepository(folder)
            row = replace(request(), status=MediaRequestStatus.PROCESSING, provider_request_id="9")
            repo.save(row)
            service = MediaRequestService(repo, [provider(lambda r, s: evidence(r, s))])
            self.assertEqual(MediaRequestStatus.AVAILABLE, service.mark_available(row.request_id).status)

    def test_legacy_submission_never_reads_managed_profile(self):
        reader = Mock(side_effect=AssertionError("Legacy flow changed"))
        with patch.object(JellyseerrMediaRequestProvider, "_post_json", return_value=REPLY):
            provider(reader).submit(request(audio_preference=None))
        reader.assert_not_called()


class BoundReaderTests(unittest.TestCase):
    def test_all_categories_use_only_exact_bound_instance_and_identity(self):
        for category in ("movie", "tv", "anime_movie", "anime_tv"):
            with self.subTest(category=category):
                server = 1 if category.startswith("anime") else 0
                binding = ArrProfileBinding("http://unused.invalid/api/v3", "synthetic")
                resolver = Mock(return_value=456)
                reader = ArrManagedProfileReader({(category, server): binding}, resolver)
                television = category.endswith("tv")
                rows = [{"id": 42, "qualityProfileId": 8, "tvdbId" if television else "tmdbId": 456 if television else 123}]
                row = request(media_type=category, season_number=1 if television else None)
                with patch.object(ArrManagedProfileReader, "_read_json", return_value=rows) as read:
                    self.assertEqual(evidence(row, server), reader(row, server))
                    read.assert_called_once_with(binding, "series" if television else "movie")
                self.assertEqual(1 if television else 0, resolver.call_count)

    def test_missing_instance_never_falls_back_to_default(self):
        reader = ArrManagedProfileReader({("tv", 0): ArrProfileBinding("http://unused.invalid/api/v3", "synthetic")})
        with patch.object(ArrManagedProfileReader, "_read_json") as read:
            with self.assertRaises(MediaRequestProviderError):
                reader(request(), 1)
            read.assert_not_called()

    def test_missing_tvdb_resolver_blocks_inventory_read(self):
        reader = ArrManagedProfileReader({("anime_tv", 1): ArrProfileBinding("http://unused.invalid/api/v3", "synthetic")})
        with patch.object(ArrManagedProfileReader, "_read_json") as read:
            with self.assertRaises(MediaRequestProviderError):
                reader(request(), 1)
            read.assert_not_called()

    def test_empty_inventory_proves_absence_but_bad_or_duplicate_inventory_does_not(self):
        reader = ArrManagedProfileReader({("movie", 0): ArrProfileBinding("http://unused.invalid/api/v3", "synthetic")})
        row = request(media_type="movie", season_number=None)
        with patch.object(ArrManagedProfileReader, "_read_json", return_value=[]):
            self.assertIsNone(reader(row, 0).managed_item_id)
        one = {"id": 1, "tmdbId": 123, "qualityProfileId": 8}
        for rows in ({"Items": []}, [None], [{"id": True, "tmdbId": 123, "qualityProfileId": 8}],
                     [one, one], [one, {**one, "id": 2}], [{"id": 2, "tmdbId": 999}], [one] * 5001):
            with self.subTest(shape=type(rows)), patch.object(ArrManagedProfileReader, "_read_json", return_value=rows):
                with self.assertRaises(MediaRequestProviderError):
                    reader(row, 0)

    def test_bindings_immutable_and_credentials_not_in_repr(self):
        binding = ArrProfileBinding("http://unused.invalid/api/v3", "private-test-value")
        mapping = {("movie", 0): binding}
        reader = ArrManagedProfileReader(mapping)
        mapping.clear()
        self.assertEqual(1, len(reader.bindings))
        self.assertNotIn("private-test-value", repr(reader))
        for url in ("http://user:pass@host/api/v3", "file:///api/v3", "http://host/api/v3?x=1", "http://host/other"):
            with self.subTest(url=url), self.assertRaises(MediaRequestProviderError):
                ArrProfileBinding(url, "synthetic")

    def test_transport_is_get_only_bounded_and_rejects_redirects(self):
        from atlas.media_requests.providers import managed_profiles as module
        binding = ArrProfileBinding("http://unused.invalid/prefix/api/v3", "synthetic")
        reader = ArrManagedProfileReader({("movie", 0): binding})
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b"[]"
        opener = Mock()
        opener.open.return_value = response
        with patch.object(module, "build_opener", return_value=opener) as build:
            self.assertEqual([], reader._read_json(binding, "movie"))
            req = opener.open.call_args.args[0]
            self.assertEqual("GET", req.get_method())
            self.assertEqual("http://unused.invalid/prefix/api/v3/movie", req.full_url)
            response.read.assert_called_once_with(10_000_001)
            handler = build.call_args.args[0]
            self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "http://other"))
        with patch.object(module, "build_opener", side_effect=RuntimeError("private-test-value")):
            with self.assertRaises(MediaRequestProviderError) as raised:
                reader._read_json(binding, "movie")
            self.assertNotIn("private-test-value", str(raised.exception))
