"""Privileged Jellyfin identity lifecycle client.

This module is intentionally separate from media browsing/playback adapters.
It is intended for the private Atlas identity mutation boundary only.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


RequestOpener = Callable[..., Any]


class JellyfinIdentityError(RuntimeError):
    """Base failure for Jellyfin identity lifecycle operations."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class JellyfinIdentityConflictError(JellyfinIdentityError):
    """Jellyfin rejected creation because the identity conflicts."""


class JellyfinIdentityNotFoundError(JellyfinIdentityError):
    """Requested Jellyfin identity does not exist."""


class JellyfinIdentityClient:
    """Perform privileged Jellyfin user lifecycle mutations."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        opener: RequestOpener = urlopen,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        normalized_key = api_key.strip()

        if not normalized_url:
            raise ValueError("Jellyfin base URL is required.")

        if not normalized_key:
            raise ValueError("Jellyfin API key is required.")

        if timeout_seconds <= 0:
            raise ValueError(
                "Jellyfin timeout must be greater than zero."
            )

        self._base_url = normalized_url
        self._api_key = normalized_key
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def create_user(
        self,
        username: str,
    ) -> dict[str, str]:
        """Create one Jellyfin user and return its normalized identity."""

        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError("Jellyfin username is required.")

        result = self._request_json(
            "POST",
            "/Users/New",
            {
                "Name": normalized_username,
            },
        )

        user_id = self._required_string(
            result,
            "Id",
            "Jellyfin create-user response is missing the user ID.",
        )

        returned_name = self._required_string(
            result,
            "Name",
            "Jellyfin create-user response is missing the username.",
        )

        if returned_name.casefold() != normalized_username.casefold():
            raise JellyfinIdentityError(
                "Jellyfin returned a mismatched created username."
            )

        return {
            "id": user_id.lower(),
            "name": returned_name,
        }

    def set_password(
        self,
        user_id: str,
        password: str,
    ) -> None:
        """Set the initial password for one Jellyfin user."""

        normalized_user_id = self._required_identifier(
            user_id,
            "Jellyfin user ID",
        )

        if not isinstance(password, str) or not password:
            raise ValueError("Jellyfin password is required.")

        self._request_empty(
            "POST",
            (
                "/Users/"
                f"{quote(normalized_user_id, safe='')}"
                "/Password"
            ),
            {
                "NewPw": password,
                "ResetPassword": False,
            },
        )

    def delete_user(
        self,
        user_id: str,
    ) -> None:
        """Delete one Jellyfin user.

        This operation is primarily intended as compensation when Atlas
        provisioning fails after Jellyfin creation.
        """

        normalized_user_id = self._required_identifier(
            user_id,
            "Jellyfin user ID",
        )

        self._request_empty(
            "DELETE",
            f"/Users/{quote(normalized_user_id, safe='')}",
            None,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        raw = self._request(
            method,
            path,
            payload,
        )

        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise JellyfinIdentityError(
                "Jellyfin returned an invalid identity response."
            ) from error

        if not isinstance(result, dict):
            raise JellyfinIdentityError(
                "Jellyfin returned an invalid identity response."
            )

        return result

    def _request_empty(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None,
    ) -> None:
        self._request(
            method,
            path,
            payload,
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None,
    ) -> bytes:
        body = (
            json.dumps(dict(payload)).encode("utf-8")
            if payload is not None
            else None
        )

        request = Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "X-Emby-Token": self._api_key,
                **(
                    {"Content-Type": "application/json"}
                    if body is not None
                    else {}
                ),
            },
        )

        try:
            with self._opener(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                return response.read()
        except HTTPError as error:
            if error.code == 404:
                raise JellyfinIdentityNotFoundError(
                    "Jellyfin user was not found.",
                    status_code=404,
                ) from error

            if error.code in {400, 409}:
                raise JellyfinIdentityConflictError(
                    "Jellyfin rejected the identity mutation.",
                    status_code=409,
                ) from error

            if error.code in {401, 403}:
                raise JellyfinIdentityError(
                    "Jellyfin denied the identity mutation.",
                    status_code=502,
                ) from error

            raise JellyfinIdentityError(
                (
                    "Jellyfin identity mutation failed "
                    f"with HTTP {error.code}."
                ),
                status_code=502,
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise JellyfinIdentityError(
                "Jellyfin identity service is unavailable.",
                status_code=502,
            ) from error

    @staticmethod
    def _required_identifier(
        value: str,
        label: str,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} is required.")

        return value.strip()

    @staticmethod
    def _required_string(
        value: Mapping[str, Any],
        key: str,
        message: str,
    ) -> str:
        result = value.get(key)

        if not isinstance(result, str) or not result.strip():
            raise JellyfinIdentityError(message)

        return result.strip()


__all__ = [
    "JellyfinIdentityClient",
    "JellyfinIdentityConflictError",
    "JellyfinIdentityError",
    "JellyfinIdentityNotFoundError",
]
