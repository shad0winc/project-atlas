"""Private client for privileged Atlas identity mutations."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class IdentityWriterError(RuntimeError):
    """Identity writer request failed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class IdentityWriterClient:
    """Mutation-only client for the private identity writer."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        base_url = base_url.strip().rstrip("/")
        token = token.strip()

        if not base_url:
            raise ValueError(
                "Identity writer URL is required."
            )

        if not token:
            raise ValueError(
                "Identity writer token is required."
            )

        self.base_url = base_url
        self.token = token
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read()
        except HTTPError as error:
            try:
                body = json.loads(
                    error.read().decode("utf-8")
                )
                message = str(
                    body.get("detail")
                    or "Identity writer rejected the request."
                )
            except (ValueError, UnicodeDecodeError):
                message = (
                    "Identity writer rejected the request."
                )

            raise IdentityWriterError(
                message,
                status_code=error.code,
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise IdentityWriterError(
                "Identity writer is unavailable.",
                status_code=502,
            ) from error

        try:
            result = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise IdentityWriterError(
                "Identity writer returned an invalid response.",
                status_code=502,
            ) from error

        if not isinstance(result, dict):
            raise IdentityWriterError(
                "Identity writer returned an invalid response.",
                status_code=502,
            )

        return result

    def create_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        roles: list[str],
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        discord_account: str | None = None,
        email_notifications_enabled: bool = False,
        discord_notifications_enabled: bool = False,
    ) -> dict[str, Any]:
        """Request privileged Atlas/Jellyfin user provisioning."""

        return self._request(
            "POST",
            "/internal/v1/users",
            {
                "username": username,
                "email": email,
                "password": password,
                "roles": roles,
                "display_name": display_name,
                "first_name": first_name,
                "last_name": last_name,
                "discord_account": discord_account,
                "email_notifications_enabled": (
                    email_notifications_enabled
                ),
                "discord_notifications_enabled": (
                    discord_notifications_enabled
                ),
            },
        )

    def update_user(
        self,
        identifier: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        identifier = quote(
            identifier,
            safe="",
        )

        return self._request(
            "PATCH",
            f"/internal/v1/users/{identifier}",
            updates,
        )

    def set_user_password(
        self,
        identifier: str,
        new_password: str,
    ) -> dict[str, Any]:
        identifier = quote(identifier, safe="")

        return self._request(
            "POST",
            f"/internal/v1/users/{identifier}/password",
            {
                "new_password": new_password,
            },
        )

    def create_custom_role(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/internal/v1/roles", payload)

    def update_custom_role(
        self,
        role_name: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        role_name = quote(role_name, safe="")
        return self._request("PATCH", f"/internal/v1/roles/{role_name}", updates)

    def delete_custom_role(self, role_name: str) -> dict[str, Any]:
        role_name = quote(role_name, safe="")
        return self._request("DELETE", f"/internal/v1/roles/{role_name}", {})

    def create_invitation(
        self,
        *,
        email: str | None,
        role: str,
        days: int,
        created_by: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/internal/v1/invitations",
            {
                "email": email,
                "role": role,
                "days": days,
                "created_by": created_by,
            },
        )

    def revoke_invitation(
        self,
        invite_id: str,
        *,
        revoked_by: str,
    ) -> dict[str, Any]:
        invite_id = quote(
            invite_id,
            safe="",
        )

        return self._request(
            "POST",
            (
                "/internal/v1/invitations/"
                f"{invite_id}/revoke"
            ),
            {
                "revoked_by": revoked_by,
            },
        )
