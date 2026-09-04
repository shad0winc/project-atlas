from __future__ import annotations

import io
import urllib.error

import pytest

from atlas_api.services.sports import (
    SportsLiveTvBindingNotFoundError,
    SportsWriterBackedAPIService,
    SportsWriterTransportError,
)


def _service() -> SportsWriterBackedAPIService:
    return SportsWriterBackedAPIService(
        base_url="http://sports-writer.invalid:8003",
        token="test-token",
    )


def test_binding_not_found_private_code_maps_to_specific_error(
    monkeypatch,
) -> None:
    def missing(request, timeout):
        body = (
            b'{"code":"sports_live_tv_binding_not_found",'
            b'"error":"Live TV binding was not found."}'
        )
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            io.BytesIO(body),
        )

    monkeypatch.setattr(
        "atlas_api.services.sports.urllib.request.urlopen",
        missing,
    )

    with pytest.raises(
        SportsLiveTvBindingNotFoundError,
        match="Live TV binding was not found",
    ):
        _service().get_live_tv_binding(
            atlas_channel_id="sports-event-001"
        )


def test_binding_identity_mismatch_fails_closed() -> None:
    service = _service()

    def request(method, path, payload=None):
        return {
            "binding": {
                "atlas_channel_id": "sports-other",
                "jellyfin_item_id": "jf-channel-1",
            }
        }

    service._request = request  # type: ignore[method-assign]

    with pytest.raises(
        SportsWriterTransportError,
        match="mismatched Live TV binding",
    ):
        service.get_live_tv_binding(
            atlas_channel_id="sports-event-001"
        )
