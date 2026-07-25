"""Tests for Atlas authentication providers."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError

from atlas.user_profiles import UserProfileStore
from atlas_api.auth.exceptions import AuthenticationProviderError
from atlas_api.auth.provider import (
    JellyfinAuthenticationClient,
    JellyfinAuthenticationProvider,
)


class FakeHTTPResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *_arguments: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class FakeJellyfinAuthenticator:
    def __init__(self, user: dict[str, object] | None) -> None:
        self.user = user
        self.calls: list[tuple[str, str]] = []

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> dict[str, object] | None:
        self.calls.append((username, password))
        return self.user


class JellyfinAuthenticationClientTests(unittest.TestCase):
    def test_authenticates_and_returns_user(self) -> None:
        captured: dict[str, object] = {}

        def opener(request: object, *, timeout: float) -> FakeHTTPResponse:
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeHTTPResponse(
                {
                    "User": {
                        "Id": "a" * 32,
                        "Name": "michael",
                    }
                }
            )

        client = JellyfinAuthenticationClient(
            "http://jellyfin:8096/",
            opener=opener,
        )

        user = client.authenticate("michael", "secret")

        self.assertIsNotNone(user)
        self.assertEqual(user["Id"], "a" * 32)
        self.assertEqual(captured["timeout"], 10.0)

        request = captured["request"]
        self.assertEqual(
            request.full_url,
            "http://jellyfin:8096/Users/AuthenticateByName",
        )
        self.assertEqual(request.get_method(), "POST")

        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "Username": "michael",
                "Pw": "secret",
            },
        )

    def test_invalid_credentials_return_none(self) -> None:
        def opener(request: object, *, timeout: float) -> object:
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                io.BytesIO(),
            )

        client = JellyfinAuthenticationClient(
            "http://jellyfin:8096",
            opener=opener,
        )

        self.assertIsNone(client.authenticate("michael", "wrong"))

    def test_server_failure_raises_provider_error(self) -> None:
        def opener(request: object, *, timeout: float) -> object:
            raise HTTPError(
                request.full_url,
                500,
                "Server Error",
                {},
                io.BytesIO(),
            )

        client = JellyfinAuthenticationClient(
            "http://jellyfin:8096",
            opener=opener,
        )

        with self.assertRaises(AuthenticationProviderError):
            client.authenticate("michael", "secret")

    def test_unavailable_server_raises_provider_error(self) -> None:
        def opener(request: object, *, timeout: float) -> object:
            raise URLError("connection refused")

        client = JellyfinAuthenticationClient(
            "http://jellyfin:8096",
            opener=opener,
        )

        with self.assertRaises(AuthenticationProviderError):
            client.authenticate("michael", "secret")


class JellyfinAuthenticationProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.profiles = UserProfileStore(
            Path(self.temporary_directory.name) / "users"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_returns_linked_active_atlas_user(self) -> None:
        jellyfin_id = "a" * 32
        profile = self.profiles.create_user(
            "michael",
            display_name="Michael",
            role="admin",
            jellyfin_user_id=jellyfin_id,
        )

        jellyfin = FakeJellyfinAuthenticator(
            {
                "Id": jellyfin_id,
                "Name": "Michael",
            }
        )

        provider = JellyfinAuthenticationProvider(
            jellyfin,
            self.profiles,
        )

        user = provider.authenticate("michael", "secret")

        self.assertIsNotNone(user)
        self.assertEqual(user.user_id, profile["user_id"])
        self.assertEqual(user.username, "michael")
        self.assertEqual(user.display_name, "Michael")
        self.assertEqual(user.roles, ("global_admin",))
        self.assertEqual(user.provider, "jellyfin")
        self.assertEqual(
            user.metadata["jellyfin_user_id"],
            jellyfin_id,
        )
        self.assertEqual(
            jellyfin.calls,
            [("michael", "secret")],
        )

    def test_rejects_invalid_jellyfin_credentials(self) -> None:
        provider = JellyfinAuthenticationProvider(
            FakeJellyfinAuthenticator(None),
            self.profiles,
        )

        self.assertIsNone(
            provider.authenticate("michael", "wrong")
        )

    def test_rejects_unlinked_jellyfin_user(self) -> None:
        provider = JellyfinAuthenticationProvider(
            FakeJellyfinAuthenticator(
                {
                    "Id": "a" * 32,
                    "Name": "michael",
                }
            ),
            self.profiles,
        )

        self.assertIsNone(
            provider.authenticate("michael", "secret")
        )

    def test_rejects_disabled_atlas_profile(self) -> None:
        jellyfin_id = "a" * 32
        profile = self.profiles.create_user(
            "michael",
            jellyfin_user_id=jellyfin_id,
        )
        self.profiles.update_user(
            profile["user_id"],
            {"status": "disabled"},
        )

        provider = JellyfinAuthenticationProvider(
            FakeJellyfinAuthenticator(
                {
                    "Id": jellyfin_id,
                    "Name": "michael",
                }
            ),
            self.profiles,
        )

        self.assertIsNone(
            provider.authenticate("michael", "secret")
        )

    def test_rejects_malformed_jellyfin_user(self) -> None:
        provider = JellyfinAuthenticationProvider(
            FakeJellyfinAuthenticator(
                {
                    "Name": "michael",
                }
            ),
            self.profiles,
        )

        with self.assertRaises(AuthenticationProviderError):
            provider.authenticate("michael", "secret")


if __name__ == "__main__":
    unittest.main()
