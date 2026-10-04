"""Acquisition audio intent persists and cannot silently use a default profile."""
from dataclasses import replace
import tempfile
import unittest
from unittest.mock import patch

from atlas.media_requests import (
    MediaAudioPreference, MediaRequest, MediaRequestError,
    JsonMediaRequestRepository, JellyseerrMediaRequestProvider,
    MediaRequestProviderError, MediaRequestService, MediaRequestServiceError,
    MediaRequestServiceConflictError, MediaRequestStatus,
)

from atlas.media_requests.providers.managed_profiles import ManagedProfileEvidence

STAMP = "2026-10-03T00:00:00Z"

def request(**changes):
    fields = dict(request_id="req-audio", user_id="user-audio", media_type="anime_tv",
                  provider="jellyseerr", provider_media_id="123", title="Example",
                  season_number=1, created_at=STAMP)
    fields.update(changes)
    return MediaRequest(**fields)


def provider(mapping=None):
    return JellyseerrMediaRequestProvider(
        "http://seerr:5055", "test-credential", movie_server_id=0,
        tv_server_id=0, anime_tv_server_id=1, anime_movie_server_id=1,
        audio_profile_ids=mapping or {},
        managed_profile_reader=lambda row, server: ManagedProfileEvidence(
            row.media_type.value, server, int(row.provider_media_id), 42,
            (mapping or {}).get((row.media_type.value, row.audio_preference.value), 8),
        ),
    )


def reply(**changes):
    row = dict(id=9, status=2, createdAt=STAMP, updatedAt=STAMP,
               serverId=1, profileId=8)
    row.update(changes)
    return row


class AudioChoiceTests(unittest.TestCase):
    def test_legacy_shape_and_registry_remain_compatible(self):
        row = request()
        self.assertNotIn("audio_preference", row.to_dict())
        with tempfile.TemporaryDirectory() as folder:
            repo = JsonMediaRequestRepository(folder)
            repo.save(row)
            self.assertIsNone(repo.get(row.request_id).audio_preference)

    def test_all_choices_survive_registry_and_lifecycle_replace(self):
        for mode in MediaAudioPreference:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                row = request(audio_preference=mode.value)
                repo = JsonMediaRequestRepository(folder)
                repo.save(row)
                repo.replace(replace(row, status=MediaRequestStatus.SUBMITTING))
                self.assertEqual(mode, repo.get(row.request_id).audio_preference)
                self.assertEqual(mode.value, repo.get(row.request_id).to_dict()["audio_preference"])

    def test_invalid_intent_and_sports_are_rejected(self):
        for value in (True, 8, "dub", "", {}, []):
            with self.subTest(value=value), self.assertRaises(MediaRequestError):
                request(audio_preference=value)
        with self.assertRaises(MediaRequestError):
            request(media_type="sports", season_number=None, audio_preference="english_required")

    def test_missing_policy_is_rejected_before_persistence_or_post(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
            JellyseerrMediaRequestProvider, "_post_json"
        ) as post:
            repo = JsonMediaRequestRepository(folder)
            service = MediaRequestService(repo, [provider()])
            with self.assertRaises(MediaRequestServiceError):
                service.create_request(request(audio_preference="english_required"))
            self.assertFalse(repo.registry_file.exists())
            post.assert_not_called()

    def test_each_category_and_choice_routes_exact_profile(self):
        for category in ("movie", "tv", "anime_movie", "anime_tv"):
            for index, mode in enumerate(MediaAudioPreference, 8):
                server = 1 if category.startswith("anime") else 0
                with self.subTest(category=category, mode=mode), patch.object(
                    JellyseerrMediaRequestProvider, "_post_json",
                    return_value=reply(serverId=server, profileId=index),
                ) as post:
                    row = request(media_type=category, season_number=1 if category.endswith("tv") else None,
                                  audio_preference=mode)
                    provider({(category, mode.value): index}).submit(row)
                    payload = post.call_args.args[1]
                    self.assertEqual(index, payload["profileId"])
                    self.assertEqual(server, payload["serverId"])
                    self.assertNotIn("is4k", payload)
                    if category.endswith("tv"):
                        self.assertEqual([1], payload["seasons"])

    def test_mapping_is_immutable_and_rejects_invalid_profiles(self):
        mapping = {("anime_tv", "english_required"): 8}
        configured = provider(mapping)
        mapping[("anime_tv", "english_required")] = 99
        self.assertEqual(8, configured._audio_profile_id(request(audio_preference="english_required")))
        for value in (True, 0, -1, "8", None):
            with self.subTest(value=value), self.assertRaises(MediaRequestProviderError):
                provider({("anime_tv", "english_required"): value})
        with self.assertRaises(MediaRequestProviderError):
            provider({("sports", "english_required"): 8})

    def test_legacy_payload_does_not_override_profile(self):
        with patch.object(JellyseerrMediaRequestProvider, "_post_json", return_value=reply()) as post:
            provider().submit(request())
            self.assertNotIn("profileId", post.call_args.args[1])

    def test_unconfirmed_post_preserves_indeterminate_intent(self):
        for changes in ({"profileId": None}, {"profileId": 7}, {"serverId": 0}, {"profileId": True}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as folder, patch.object(
                JellyseerrMediaRequestProvider, "_post_json", return_value=reply(**changes)
            ) as post:
                repo = JsonMediaRequestRepository(folder)
                service = MediaRequestService(repo, [provider({("anime_tv", "english_required"): 8})])
                row = service.create_request(request(audio_preference="english_required"))
                with self.assertRaises(MediaRequestServiceError):
                    service.submit_request(row.request_id)
                self.assertEqual(1, post.call_count)
                self.assertEqual(MediaRequestStatus.SUBMITTING, repo.get(row.request_id).status)
                self.assertEqual(MediaAudioPreference.ENGLISH_REQUIRED, repo.get(row.request_id).audio_preference)

    def test_audio_choice_does_not_bypass_active_target_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = JsonMediaRequestRepository(folder)
            service = MediaRequestService(repo, [provider({
                ("anime_tv", "english_required"): 8,
                ("anime_tv", "original_subbed"): 9,
            })])
            service.create_request(request(audio_preference="english_required"))
            with self.assertRaises(MediaRequestServiceConflictError):
                service.create_request(request(request_id="req-other", user_id="other-user",
                                               audio_preference="original_subbed"))
