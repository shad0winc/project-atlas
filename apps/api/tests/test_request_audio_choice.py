"""API boundary preserves acquisition policy without caller-controlled profiles."""
import unittest
from pydantic import ValidationError
from atlas.media_requests import MediaAudioPreference, MediaRequest
from atlas_api.schemas.requests import MediaRequestCreateRequest, MediaRequestResponse

class AudioChoiceSchemaTests(unittest.TestCase):
    def test_supported_choices_roundtrip(self):
        for mode in MediaAudioPreference:
            with self.subTest(mode=mode):
                payload = MediaRequestCreateRequest(media_type="anime_tv", provider_media_id="123",
                                                    title="Example", audio_preference=mode.value)
                row = MediaRequest(request_id="req-audio", user_id="user-audio", provider="jellyseerr",
                                   **payload.model_dump())
                self.assertEqual(mode.value, MediaRequestResponse.from_domain(row).model_dump(mode="json")["audio_preference"])

    def test_legacy_response_shape_unchanged(self):
        row = MediaRequest(request_id="req-audio", user_id="user-audio", provider="jellyseerr",
                           media_type="tv", provider_media_id="123", title="Example")
        self.assertNotIn("audio_preference", MediaRequestResponse.from_domain(row).model_dump(mode="json"))

    def test_unknown_policy_or_caller_profile_is_rejected(self):
        for extra in ({"audio_preference": "dub"}, {"audio_preference": True},
                      {"profileId": 8}, {"audio_profile_ids": {"tv": 8}}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                MediaRequestCreateRequest(media_type="tv", provider_media_id="123", title="Example", **extra)


def test_audio_choice_http_mapping_and_legacy_compatibility():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from atlas_api.auth.models import AuthenticatedUser
    from atlas_api.routes.v1 import requests

    calls = []
    class Service:
        def create_for_user(self, user_id, **fields):
            calls.append((user_id, fields))
            return MediaRequest(request_id="req-route", user_id=user_id,
                                provider="jellyseerr", **fields)

    user = AuthenticatedUser(user_id="user-audio", username="audio",
                             display_name="Audio", provider="test")
    app = FastAPI()
    app.include_router(requests.router, prefix="/api/v1")
    app.dependency_overrides[requests.require_requests_create] = lambda: user
    app.dependency_overrides[requests.get_media_requests_api_service] = lambda: Service()
    client = TestClient(app)
    base = {"media_type": "anime_tv", "provider_media_id": "123", "title": "Example"}
    for mode in MediaAudioPreference:
        response = client.post("/api/v1/requests", json={**base, "audio_preference": mode.value})
        assert response.status_code == 201
        assert response.json()["audio_preference"] == mode.value
        assert calls[-1][0] == user.user_id
        assert calls[-1][1]["audio_preference"] == mode.value
    response = client.post("/api/v1/requests", json=base)
    assert response.status_code == 201
    assert "audio_preference" not in calls[-1][1]
    assert "audio_preference" not in response.json()
    count = len(calls)
    for extra in ({"audio_preference": "dub"}, {"profileId": 8}):
        response = client.post("/api/v1/requests", json={**base, **extra})
        assert response.status_code == 422
    assert len(calls) == count


def test_application_service_persists_selected_audio_policy(tmp_path):
    from unittest.mock import patch
    from atlas.media_requests import (JsonMediaRequestRepository,
                                     JellyseerrMediaRequestProvider, MediaRequestService)
    from atlas_api.services.requests import MediaRequestsAPIService
    repo = JsonMediaRequestRepository(tmp_path)
    provider = JellyseerrMediaRequestProvider(
        "http://seerr:5055", "test-credential", anime_tv_server_id=1,
        audio_profile_ids={("anime_tv", "english_required"): 8},
    )
    service = MediaRequestsAPIService(repo, MediaRequestService(repo, [provider]),
                                     request_id_factory=lambda: "req-application")
    # Use the current time to keep mocked provider timestamps ordered after creation.
    from datetime import datetime, timezone
    def reply(*args):
        stamp = datetime.now(timezone.utc).isoformat()
        return {"id": 9, "status": 2, "createdAt": stamp, "updatedAt": stamp,
                "serverId": 1, "profileId": 8}
    with patch.object(JellyseerrMediaRequestProvider, "_post_json", side_effect=reply) as post:
        row = service.create_for_user("user-audio", media_type="anime_tv",
                                     provider_media_id="123", title="Example",
                                     season_number=1, audio_preference="english_required")
    assert row.audio_preference is MediaAudioPreference.ENGLISH_REQUIRED
    assert repo.get(row.request_id).audio_preference is MediaAudioPreference.ENGLISH_REQUIRED
    assert post.call_args.args[1]["profileId"] == 8
