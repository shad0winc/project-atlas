"""Contracts for the privileged Jellyfin identity client."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from atlas_api.services.jellyfin_identity import (
    JellyfinIdentityClient,
    JellyfinIdentityConflictError,
    JellyfinIdentityError,
    JellyfinIdentityNotFoundError,
)


class FakeResponse:
    def __init__(self, payload: bytes = b"") -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._payload


def test_create_user_uses_admin_api_key_and_validates_identity() -> None:
    observed: dict[str, object] = {}

    def opener(request, *, timeout):
        observed["url"] = request.full_url
        observed["method"] = request.get_method()
        observed["headers"] = dict(request.header_items())
        observed["payload"] = json.loads(
            request.data.decode("utf-8")
        )
        observed["timeout"] = timeout

        return FakeResponse(
            json.dumps(
                {
                    "Id": "ABCDEF0123456789",
                    "Name": "Michael",
                }
            ).encode("utf-8")
        )

    client = JellyfinIdentityClient(
        "http://jellyfin:8096/",
        "admin-api-key",
        opener=opener,
    )

    result = client.create_user("Michael")

    assert result == {
        "id": "abcdef0123456789",
        "name": "Michael",
    }
    assert observed["url"] == "http://jellyfin:8096/Users/New"
    assert observed["method"] == "POST"
    assert observed["payload"] == {"Name": "Michael"}
    assert observed["timeout"] == 10.0

    headers = {
        str(key).lower(): value
        for key, value in observed["headers"].items()
    }

    assert headers["x-emby-token"] == "admin-api-key"
    assert headers["content-type"] == "application/json"


def test_create_user_rejects_mismatched_returned_username() -> None:
    def opener(request, *, timeout):
        return FakeResponse(
            json.dumps(
                {
                    "Id": "abcdef",
                    "Name": "someone-else",
                }
            ).encode("utf-8")
        )

    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        "admin-api-key",
        opener=opener,
    )

    with pytest.raises(
        JellyfinIdentityError,
        match="mismatched created username",
    ):
        client.create_user("michael")


def test_set_password_uses_jellyfin_password_contract() -> None:
    observed: dict[str, object] = {}

    def opener(request, *, timeout):
        observed["url"] = request.full_url
        observed["method"] = request.get_method()
        observed["payload"] = json.loads(
            request.data.decode("utf-8")
        )
        return FakeResponse()

    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        "admin-api-key",
        opener=opener,
    )

    client.set_password(
        "ABC DEF",
        "correct horse battery staple",
    )

    assert (
        observed["url"]
        == "http://jellyfin:8096/Users/ABC%20DEF/Password"
    )
    assert observed["method"] == "POST"
    assert observed["payload"] == {
        "NewPw": "correct horse battery staple",
        "ResetPassword": False,
    }


def test_delete_user_uses_compensation_endpoint() -> None:
    observed: dict[str, object] = {}

    def opener(request, *, timeout):
        observed["url"] = request.full_url
        observed["method"] = request.get_method()
        observed["data"] = request.data
        return FakeResponse()

    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        "admin-api-key",
        opener=opener,
    )

    client.delete_user("ABC DEF")

    assert observed["url"] == "http://jellyfin:8096/Users/ABC%20DEF"
    assert observed["method"] == "DELETE"
    assert observed["data"] is None


@pytest.mark.parametrize("status_code", [400, 409])
def test_create_conflict_is_normalized(status_code: int) -> None:
    def opener(request, *, timeout):
        raise HTTPError(
            request.full_url,
            status_code,
            "conflict",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        "admin-api-key",
        opener=opener,
    )

    with pytest.raises(JellyfinIdentityConflictError):
        client.create_user("michael")


def test_delete_missing_user_is_normalized() -> None:
    def opener(request, *, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "not found",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        "admin-api-key",
        opener=opener,
    )

    with pytest.raises(JellyfinIdentityNotFoundError):
        client.delete_user("missing")


def test_admin_authorization_failure_does_not_expose_api_key() -> None:
    def opener(request, *, timeout):
        raise HTTPError(
            request.full_url,
            403,
            "forbidden",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    secret = "never-print-this-key"

    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        secret,
        opener=opener,
    )

    with pytest.raises(JellyfinIdentityError) as captured:
        client.create_user("michael")

    assert secret not in str(captured.value)


@pytest.mark.parametrize(
    ("base_url", "api_key"),
    [
        ("", "key"),
        ("http://jellyfin:8096", ""),
    ],
)
def test_constructor_rejects_missing_configuration(
    base_url: str,
    api_key: str,
) -> None:
    with pytest.raises(ValueError):
        JellyfinIdentityClient(
            base_url,
            api_key,
        )


def test_rejects_empty_username_before_http() -> None:
    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        "admin-api-key",
        opener=lambda *_args, **_kwargs: pytest.fail(
            "HTTP must not be attempted."
        ),
    )

    with pytest.raises(
        ValueError,
        match="username is required",
    ):
        client.create_user("   ")


def test_rejects_empty_password_before_http() -> None:
    client = JellyfinIdentityClient(
        "http://jellyfin:8096",
        "admin-api-key",
        opener=lambda *_args, **_kwargs: pytest.fail(
            "HTTP must not be attempted."
        ),
    )

    with pytest.raises(
        ValueError,
        match="password is required",
    ):
        client.set_password("user-id", "")
