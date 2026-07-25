"""Authentication provider implementations for the Atlas API."""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.exceptions import AuthenticationProviderError
from atlas_api.auth.models import AuthenticatedUser


class AuthenticationProvider(Protocol):
    """Provider interface used to authenticate Atlas users."""

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> AuthenticatedUser | None:
        """Authenticate credentials and return a normalized user."""


class JellyfinAuthenticator(Protocol):
    """Minimal Jellyfin credential-authentication interface."""

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> Mapping[str, Any] | None:
        """Return the authenticated Jellyfin user or None."""


RequestOpener = Callable[..., Any]


class JellyfinAuthenticationClient:
    """Authenticate user credentials against the Jellyfin HTTP API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        client_name: str = "Project Atlas",
        client_version: str = "0.1.0",
        device_name: str = "Atlas API",
        device_id: str = "atlas-api",
        opener: RequestOpener = urlopen,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("Jellyfin base URL cannot be empty.")

        if timeout_seconds <= 0:
            raise ValueError("Jellyfin timeout must be greater than zero.")

        self._base_url = normalized_url
        self._timeout_seconds = timeout_seconds
        self._opener = opener
        self._authorization = (
            f'MediaBrowser Client="{client_name}", '
            f'Device="{device_name}", '
            f'DeviceId="{device_id}", '
            f'Version="{client_version}"'
        )

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> Mapping[str, Any] | None:
        """Validate credentials and return Jellyfin's user object."""

        payload = json.dumps(
            {
                "Username": username,
                "Pw": password,
            }
        ).encode("utf-8")

        request = Request(
            f"{self._base_url}/Users/AuthenticateByName",
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": self._authorization,
                "Content-Type": "application/json",
            },
        )

        try:
            with self._opener(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw_response = response.read()
        except HTTPError as error:
            if error.code in {400, 401, 403}:
                return None

            raise AuthenticationProviderError(
                f"Jellyfin authentication failed with HTTP {error.code}."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise AuthenticationProviderError(
                "Jellyfin authentication service is unavailable."
            ) from error

        try:
            result = json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AuthenticationProviderError(
                "Jellyfin returned an invalid authentication response."
            ) from error

        if not isinstance(result, dict):
            raise AuthenticationProviderError(
                "Jellyfin returned an invalid authentication response."
            )

        user = result.get("User")
        if not isinstance(user, dict):
            raise AuthenticationProviderError(
                "Jellyfin authentication response did not contain a user."
            )

        return user


class JellyfinAuthenticationProvider:
    """Authenticate with Jellyfin and resolve the linked Atlas profile."""

    def __init__(
        self,
        jellyfin: JellyfinAuthenticator,
        profiles: UserProfileStore,
    ) -> None:
        self._jellyfin = jellyfin
        self._profiles = profiles

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> AuthenticatedUser | None:
        """Authenticate credentials and map them to an Atlas identity."""

        jellyfin_user = self._jellyfin.authenticate(username, password)
        if jellyfin_user is None:
            return None

        jellyfin_user_id = self._required_string(
            jellyfin_user,
            "Id",
            "Jellyfin authentication response is missing the user ID.",
        ).lower()

        jellyfin_username = self._required_string(
            jellyfin_user,
            "Name",
            "Jellyfin authentication response is missing the username.",
        )

        try:
            profile = self._find_profile(jellyfin_user_id)
        except UserProfileError as error:
            raise AuthenticationProviderError(
                "Atlas could not read the authenticated user's profile."
            ) from error

        # Do not reveal whether an authenticated Jellyfin account is unlinked
        # or disabled. Both cases are presented as unsuccessful login.
        if profile is None or profile["status"] != "active":
            return None

        return AuthenticatedUser(
            user_id=profile["user_id"],
            username=profile["username"],
            display_name=profile["display_name"],
            roles=(profile["role"],),
            provider="jellyfin",
            metadata={
                "jellyfin_user_id": jellyfin_user_id,
                "jellyfin_username": jellyfin_username,
            },
        )

    def _find_profile(
        self,
        jellyfin_user_id: str,
    ) -> dict[str, Any] | None:
        matches = [
            profile
            for profile in self._profiles.list_users()
            if profile.get("jellyfin_user_id") == jellyfin_user_id
        ]

        if not matches:
            return None

        if len(matches) > 1:
            raise AuthenticationProviderError(
                "Multiple Atlas profiles are linked to the same Jellyfin user."
            )

        return matches[0]

    @staticmethod
    def _required_string(
        value: Mapping[str, Any],
        key: str,
        message: str,
    ) -> str:
        result = value.get(key)
        if not isinstance(result, str) or not result.strip():
            raise AuthenticationProviderError(message)
        return result.strip()
