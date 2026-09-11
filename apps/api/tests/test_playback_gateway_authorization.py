from __future__ import annotations

from starlette.requests import Request

from atlas.media.jellyfin_auth import (
    build_jellyfin_authorization,
)
from atlas_api.routes import playback_gateway


class FakeCapabilities:
    def __init__(self) -> None:
        self.session_token: str | None = None
        self.request_uri: str | None = None

    def authorize_session(
        self,
        token: str,
        *,
        request_uri: str,
    ) -> None:
        self.session_token = token
        self.request_uri = request_uri


def _request(
    *,
    forwarded_uri: str,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/_atlas/playback/authorize",
            "raw_path": b"/_atlas/playback/authorize",
            "query_string": b"",
            "headers": [
                (
                    b"x-forwarded-uri",
                    forwarded_uri.encode("ascii"),
                ),
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


def test_authorize_returns_canonical_private_jellyfin_authorization(
    monkeypatch,
) -> None:
    capabilities = FakeCapabilities()

    monkeypatch.setattr(
        playback_gateway,
        "_capabilities",
        lambda: capabilities,
    )
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_API_KEY",
        "test-jellyfin-key",
    )

    response = playback_gateway.authorize_playback(
        _request(
            forwarded_uri=(
                "/videos/item-1/master.m3u8"
                "?MediaSourceId=source-1"
            ),
        ),
        atlas_playback="gateway-session",
    )

    expected = build_jellyfin_authorization(
        token="test-jellyfin-key",
    )

    assert response.status_code == 200
    assert (
        response.headers[
            "X-Atlas-Jellyfin-Authorization"
        ]
        == expected
    )
    assert (
        "X-Atlas-Jellyfin-Token"
        not in response.headers
    )
    assert (
        "X-Emby-Token"
        not in response.headers
    )
    assert capabilities.session_token == "gateway-session"
    assert capabilities.request_uri == (
        "/videos/item-1/master.m3u8"
        "?MediaSourceId=source-1"
    )


def test_private_authorization_uses_shared_mediabrowser_contract(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_API_KEY",
        "test-jellyfin-key",
    )

    value = playback_gateway._jellyfin_authorization()

    assert value.startswith("MediaBrowser ")
    assert 'Client="Project Atlas"' in value
    assert 'Device="Atlas API"' in value
    assert 'DeviceId="atlas-api"' in value
    assert 'Version="0.1.0"' in value
    assert 'Token="test-jellyfin-key"' in value


def test_bootstrap_source_contains_no_private_jellyfin_auth_header() -> None:
    source = (
        __import__(
            "inspect"
        ).getsource(
            playback_gateway.bootstrap_playback
        )
    )

    assert "X-Atlas-Jellyfin-Authorization" not in source
    assert "X-Atlas-Jellyfin-Token" not in source
    assert "X-Emby-Token" not in source
