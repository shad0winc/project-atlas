"""Secret-safe Dispatcharr administration client.

Credential values may be sent to Dispatcharr but are never returned by
this module. Atlas lifecycle metadata must not contain these values.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


class DispatcharrAdminError(RuntimeError):
    """Dispatcharr administration could not be completed safely."""


class DispatcharrAuthError(DispatcharrAdminError):
    """Dispatcharr administrative authentication failed."""


class DispatcharrAccountNotFoundError(
    DispatcharrAdminError
):
    """Requested Dispatcharr account does not exist."""


@dataclass(frozen=True, slots=True)
class SafeDispatcharrAccount:
    account_id: int
    name: str
    account_type: str
    enabled: bool
    configured_max_connections: int
    credentials_configured: bool

    def to_mapping(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "name": self.name,
            "account_type": self.account_type,
            "enabled": self.enabled,
            "configured_max_connections": (
                self.configured_max_connections
            ),
            "credentials_configured": (
                self.credentials_configured
            ),
        }


@dataclass(frozen=True, slots=True)
class SafeConnectionTest:
    ok: bool
    status: str
    expires_at: str | None
    provider_max_connections: int | None
    active_connections: int | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "expires_at": self.expires_at,
            "provider_max_connections": (
                self.provider_max_connections
            ),
            "active_connections": (
                self.active_connections
            ),
        }


class DispatcharrAdminClient:
    """Minimal authenticated client for private Dispatcharr administration."""

    def __init__(
        self,
        *,
        base_url: str,
        admin_username: str,
        admin_password: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._base_url = (
            base_url.rstrip("/")
        )
        self._admin_username = (
            admin_username
        )
        self._admin_password = (
            admin_password
        )
        self._timeout_seconds = (
            timeout_seconds
        )

        if not self._base_url:
            raise DispatcharrAdminError(
                "Dispatcharr internal URL is required."
            )

        if (
            not self._admin_username
            or not self._admin_password
        ):
            raise DispatcharrAdminError(
                "Dispatcharr administrative "
                "credentials are not configured."
            )

    @classmethod
    def from_environment(
        cls,
    ) -> "DispatcharrAdminClient":
        return cls(
            base_url=os.environ.get(
                "DISPATCHARR_INTERNAL_URL",
                "",
            ),
            admin_username=os.environ.get(
                "DISPATCHARR_ADMIN_USERNAME",
                "",
            ),
            admin_password=os.environ.get(
                "DISPATCHARR_ADMIN_PASSWORD",
                "",
            ),
        )

    def _json_request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        access_token: str | None = None,
    ) -> Any:
        body = (
            json.dumps(
                dict(payload)
            ).encode("utf-8")
            if payload is not None
            else None
        )

        headers = {
            "Accept": "application/json",
        }

        if body is not None:
            headers[
                "Content-Type"
            ] = "application/json"

        if access_token:
            headers[
                "Authorization"
            ] = f"Bearer {access_token}"

        request = urllib.request.Request(
            self._base_url + path,
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw = response.read()

        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise DispatcharrAuthError(
                    "Dispatcharr authentication failed."
                ) from error

            if error.code == 404:
                raise DispatcharrAccountNotFoundError(
                    "Dispatcharr account was not found."
                ) from error

            raise DispatcharrAdminError(
                "Dispatcharr request failed."
            ) from error

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
        ) as error:
            raise DispatcharrAdminError(
                "Dispatcharr is unavailable."
            ) from error

        try:
            return json.loads(
                raw.decode("utf-8")
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise DispatcharrAdminError(
                "Dispatcharr returned invalid JSON."
            ) from error

    def _access_token(self) -> str:
        payload = self._json_request(
            "POST",
            "/api/accounts/auth/login/",
            {
                "username": (
                    self._admin_username
                ),
                "password": (
                    self._admin_password
                ),
            },
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise DispatcharrAuthError(
                "Dispatcharr authentication "
                "returned an invalid response."
            )

        access = str(
            payload.get(
                "access",
                "",
            )
        ).strip()

        if not access:
            raise DispatcharrAuthError(
                "Dispatcharr authentication "
                "did not return an access token."
            )

        return access

    def _raw_account(
        self,
        account_id: int,
    ) -> dict[str, Any]:
        token = self._access_token()

        payload = self._json_request(
            "GET",
            f"/api/m3u/accounts/{account_id}/",
            access_token=token,
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise DispatcharrAdminError(
                "Dispatcharr returned an invalid "
                "account response."
            )

        return payload

    @staticmethod
    def _safe_account(
        raw: Mapping[str, Any],
    ) -> SafeDispatcharrAccount:
        try:
            account_id = int(
                raw["id"]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise DispatcharrAdminError(
                "Dispatcharr account identity "
                "is invalid."
            ) from error

        name = str(
            raw.get(
                "name",
                "",
            )
        ).strip()

        account_type = str(
            raw.get(
                "account_type",
                "",
            )
        ).strip()

        if not name or not account_type:
            raise DispatcharrAdminError(
                "Dispatcharr account metadata "
                "is incomplete."
            )

        try:
            max_connections = int(
                raw.get(
                    "max_streams",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise DispatcharrAdminError(
                "Dispatcharr connection limit "
                "is invalid."
            ) from error

        # Dispatcharr's privileged serializer may
        # include password. Never forward its value.
        credentials_configured = bool(
            str(
                raw.get(
                    "username",
                    "",
                )
            ).strip()
            and str(
                raw.get(
                    "password",
                    "",
                )
            )
        )

        return SafeDispatcharrAccount(
            account_id=account_id,
            name=name,
            account_type=account_type,
            enabled=bool(
                raw.get(
                    "is_active",
                    False,
                )
            ),
            configured_max_connections=(
                max_connections
            ),
            credentials_configured=(
                credentials_configured
            ),
        )

    def read_account(
        self,
        account_id: int,
    ) -> SafeDispatcharrAccount:
        return self._safe_account(
            self._raw_account(
                account_id
            )
        )

    def update_credentials(
        self,
        *,
        account_id: int,
        server_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> SafeDispatcharrAccount:
        current = self._raw_account(
            account_id
        )

        body: dict[str, Any] = {}

        if server_url is not None:
            normalized = (
                server_url.strip()
            )

            if not normalized:
                raise DispatcharrAdminError(
                    "Server URL cannot be blank."
                )

            parsed = urllib.parse.urlsplit(
                normalized
            )

            if (
                parsed.scheme
                not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
            ):
                raise DispatcharrAdminError(
                    "Server URL is invalid."
                )

            body["server_url"] = normalized

        if username is not None:
            normalized = (
                username.strip()
            )

            if not normalized:
                raise DispatcharrAdminError(
                    "Username cannot be blank."
                )

            body["username"] = normalized

        # Blank password means retain current password.
        if password is not None and password != "":
            body["password"] = password

        if not body:
            return self._safe_account(
                current
            )

        token = self._access_token()

        payload = self._json_request(
            "PATCH",
            f"/api/m3u/accounts/{account_id}/",
            body,
            access_token=token,
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise DispatcharrAdminError(
                "Dispatcharr returned an invalid "
                "credential update response."
            )

        return self._safe_account(
            payload
        )

    def test_connection(
        self,
        *,
        account_id: int,
    ) -> SafeConnectionTest:
        """Authenticate without activating or importing the account."""

        raw = self._raw_account(
            account_id
        )

        if str(
            raw.get(
                "account_type",
                "",
            )
        ).strip().upper() != "XC":
            raise DispatcharrAdminError(
                "Test Connection currently "
                "supports Xtream Codes accounts."
            )

        server_url = str(
            raw.get(
                "server_url",
                "",
            )
        ).strip()

        username = str(
            raw.get(
                "username",
                "",
            )
        ).strip()

        password = str(
            raw.get(
                "password",
                "",
            )
        )

        if (
            not server_url
            or not username
            or not password
        ):
            raise DispatcharrAdminError(
                "Provider credentials "
                "are incomplete."
            )

        parsed = urllib.parse.urlsplit(
            server_url
        )

        if (
            parsed.scheme
            not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
        ):
            raise DispatcharrAdminError(
                "Provider server URL is invalid."
            )

        # Xtream account authentication is intentionally
        # isolated from Dispatcharr activation/import.
        #
        # Credentials are required by the upstream
        # player_api.php protocol. Never log or return
        # the constructed URI.
        query = urllib.parse.urlencode(
            {
                "username": username,
                "password": password,
            }
        )

        base_path = parsed.path.rstrip("/")

        request_url = urllib.parse.urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                base_path
                + "/player_api.php",
                query,
                "",
            )
        )

        request = urllib.request.Request(
            request_url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Project-Atlas-Sports/"
                    "1.0"
                ),
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw_body = response.read()

        except urllib.error.HTTPError as error:
            # Never include error URL/reason because the
            # request URI contains provider credentials.
            raise DispatcharrAdminError(
                "Provider authentication failed."
            ) from error

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
        ) as error:
            raise DispatcharrAdminError(
                "Provider is unavailable."
            ) from error

        try:
            info = json.loads(
                raw_body.decode(
                    "utf-8"
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise DispatcharrAdminError(
                "Provider returned invalid "
                "account information."
            ) from error

        if not isinstance(
            info,
            dict,
        ):
            raise DispatcharrAdminError(
                "Provider returned invalid "
                "account information."
            )

        user_info = info.get(
            "user_info",
            info,
        )

        if not isinstance(
            user_info,
            dict,
        ):
            raise DispatcharrAdminError(
                "Provider returned invalid "
                "account information."
            )

        status = str(
            user_info.get(
                "status",
                "",
            )
        ).strip()

        def optional_int(
            key: str,
        ) -> int | None:
            raw_value = user_info.get(
                key
            )

            if raw_value in {
                None,
                "",
            }:
                return None

            try:
                return int(
                    raw_value
                )
            except (
                TypeError,
                ValueError,
            ):
                return None

        exp_raw = user_info.get(
            "exp_date"
        )

        expires_at = (
            str(exp_raw).strip()
            if exp_raw
            else None
        )

        return SafeConnectionTest(
            ok=(
                status.lower()
                == "active"
            ),
            status=(
                status
                or "unknown"
            ),
            expires_at=expires_at,
            provider_max_connections=(
                optional_int(
                    "max_connections"
                )
            ),
            active_connections=(
                optional_int(
                    "active_cons"
                )
            ),
        )


__all__ = [
    "DispatcharrAccountNotFoundError",
    "DispatcharrAdminClient",
    "DispatcharrAdminError",
    "DispatcharrAuthError",
    "SafeConnectionTest",
    "SafeDispatcharrAccount",
]
