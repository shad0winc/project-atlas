from __future__ import annotations
from urllib.parse import urlencode
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from atlas.jellyfin_live_streams import LiveStreamOwnershipError
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.playback_capabilities import (
    PlaybackCapabilityService,
    PlaybackCapabilityError,
)
from atlas_api.routes import playback_gateway
from atlas_api.routes.v1 import playback

PARAMS = {
    "LiveStreamId": "live-one",
    "MediaSourceId": "source-one",
    "PlaySessionId": "play-one",
}
PATH = "/videos/item/live.m3u8"


def session():
    service = PlaybackCapabilityService(AtlasAPISettings(jwt_secret="x" * 64))
    bootstrap = service.create_bootstrap(
        user_id="user-one",
        playable_target_id="item",
        stream_path=PATH + "?" + urlencode(PARAMS),
    )
    return service, service.exchange_bootstrap(bootstrap).token


@pytest.mark.parametrize("field", list(PARAMS))
@pytest.mark.parametrize("change", ["replace", "omit", "duplicate"])
def test_live_identity_cannot_be_changed_removed_or_duplicated(field, change):
    service, token = session()
    pairs = list(PARAMS.items())
    if change == "replace":
        pairs = [(k, "other" if k == field else v) for k, v in pairs]
    if change == "omit":
        pairs = [(k, v) for k, v in pairs if k != field]
    if change == "duplicate":
        pairs.append((field, PARAMS[field]))
    with pytest.raises(PlaybackCapabilityError):
        service.authorize_session(token, request_uri=PATH + "?" + urlencode(pairs))


def test_segments_may_omit_identity_but_cannot_change_it():
    service, token = session()
    claims = service.authorize_session(token, request_uri="/videos/item/hls1/main/0.ts")
    assert claims["sub"] == "user-one"
    with pytest.raises(PlaybackCapabilityError):
        service.authorize_session(
            token, request_uri="/videos/item/hls1/main/0.ts?LiveStreamId=other"
        )


@pytest.mark.parametrize("owner_exists", [True, False])
def test_gateway_checks_owned_live_stream_before_returning_private_auth(
    monkeypatch, owner_exists
):
    service, token = session()
    calls = []

    class Playback:
        def authorize_live_stream(self, **kwargs):
            calls.append(kwargs)
            if not owner_exists:
                raise LiveStreamOwnershipError("expired")

    monkeypatch.setattr(playback_gateway, "_capabilities", lambda: service)
    monkeypatch.setattr(playback, "get_playback_service", lambda: Playback())
    monkeypatch.setenv("ATLAS_JELLYFIN_API_KEY", "private-key")
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"x-forwarded-uri", (PATH + "?" + urlencode(PARAMS)).encode())
            ],
        }
    )
    if owner_exists:
        result = playback_gateway.authorize_playback(request, atlas_playback=token)
        assert result.status_code == 200
    else:
        with pytest.raises(HTTPException) as exc:
            playback_gateway.authorize_playback(request, atlas_playback=token)
        assert exc.value.status_code == 401
    assert calls == [
        {
            "user_id": "user-one",
            "item_id": "item",
            "live_stream_id": "live-one",
            "play_session_id": "play-one",
            "media_source_id": "source-one",
        }
    ]
