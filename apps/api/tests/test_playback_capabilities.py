from __future__ import annotations

import jwt
import pytest

from atlas_api.core.settings import AtlasAPISettings
from atlas_api.playback_capabilities import (
    PlaybackCapabilityError,
    PlaybackCapabilityService,
)


def _service() -> PlaybackCapabilityService:
    return PlaybackCapabilityService(
        AtlasAPISettings(
            jwt_secret="p" * 64,
            jwt_issuer="project-atlas-test",
            jwt_audience="atlas-portal-test",
        )
    )


def test_bootstrap_token_contains_no_jellyfin_secret() -> None:
    service = _service()
    token = service.create_bootstrap(
        user_id="usr-example",
        playable_target_id="a" * 32,
        stream_path=(
            "/videos/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/"
            "master.m3u8?MediaSourceId=source&PlaySessionId=session"
        ),
    )
    payload = jwt.decode(
        token,
        options={"verify_signature": False, "verify_aud": False},
    )
    serialized = repr(payload).lower()
    assert "apikey" not in serialized
    assert "x-emby-token" not in serialized
    assert "jellyfin_user_id" not in serialized


def test_bootstrap_exchange_scopes_cookie_to_one_video() -> None:
    service = _service()
    bootstrap = service.create_bootstrap(
        user_id="usr-example",
        playable_target_id="a" * 32,
        stream_path=(
            "/videos/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/"
            "master.m3u8?MediaSourceId=source"
        ),
    )
    session = service.exchange_bootstrap(bootstrap)
    assert session.path_prefix == "/videos/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/"
    service.authorize_session(
        session.token,
        request_uri=(
            "/videos/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/"
            "main.m3u8?MediaSourceId=source"
        ),
    )
    with pytest.raises(PlaybackCapabilityError, match="outside the authorized scope"):
        service.authorize_session(
            session.token,
            request_uri=(
                "/videos/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/main.m3u8"
            ),
        )


def test_stream_scope_rejects_jellyfin_auth_query() -> None:
    service = _service()
    with pytest.raises(PlaybackCapabilityError, match="authentication material"):
        service.create_bootstrap(
            user_id="usr-example",
            playable_target_id="a" * 32,
            stream_path=(
                "/videos/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/"
                "master.m3u8?ApiKey=secret"
            ),
        )
