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
class SafeDispatcharrStream:
    """Secret-free Dispatcharr stream identity for Sports resolution."""

    stream_id: int
    name: str
    m3u_account_id: int
    group_name: str | None
    is_stale: bool

    def to_mapping(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "name": self.name,
            "m3u_account_id": self.m3u_account_id,
            "group_name": self.group_name,
            "is_stale": self.is_stale,
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

    def create_account(
        self,
        *,
        name: str,
        server_url: str,
        username: str,
        password: str,
        max_connections: int,
    ) -> SafeDispatcharrAccount:
        """Create one disabled-by-Atlas Xtream account in Dispatcharr."""

        normalized_name = str(
            name
            or ""
        ).strip()

        if not normalized_name:
            raise DispatcharrAdminError(
                "Account name cannot be blank."
            )

        normalized_server_url = str(
            server_url
            or ""
        ).strip()

        if not normalized_server_url:
            raise DispatcharrAdminError(
                "Server URL cannot be blank."
            )

        parsed = urllib.parse.urlsplit(
            normalized_server_url
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

        normalized_username = str(
            username
            or ""
        ).strip()

        if not normalized_username:
            raise DispatcharrAdminError(
                "Username cannot be blank."
            )

        if (
            not isinstance(password, str)
            or password == ""
        ):
            raise DispatcharrAdminError(
                "Password cannot be blank."
            )

        if isinstance(
            max_connections,
            bool,
        ):
            raise DispatcharrAdminError(
                "Maximum connections must "
                "be an integer."
            )

        try:
            normalized_max_connections = int(
                max_connections
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise DispatcharrAdminError(
                "Maximum connections must "
                "be an integer."
            ) from error

        if not (
            1
            <= normalized_max_connections
            <= 1000
        ):
            raise DispatcharrAdminError(
                "Maximum connections must "
                "be between 1 and 1000."
            )

        # Keep this allowlist intentionally narrow.
        #
        # Dispatcharr owns provider credentials and
        # discovery. Atlas owns pool participation.
        # Newly discovered groups must not be
        # automatically enabled by account creation.
        body: dict[str, Any] = {
            "name": normalized_name,
            "server_url": (
                normalized_server_url
            ),
            "account_type": "XC",
            "username": (
                normalized_username
            ),
            "password": password,
            "max_streams": (
                normalized_max_connections
            ),
            "is_active": True,
            "enable_vod": False,
            "auto_enable_new_groups_live": (
                False
            ),
            "auto_enable_new_groups_vod": (
                False
            ),
            "auto_enable_new_groups_series": (
                False
            ),
        }

        token = self._access_token()

        payload = self._json_request(
            "POST",
            "/api/m3u/accounts/",
            body,
            access_token=token,
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise DispatcharrAdminError(
                "Dispatcharr returned an invalid "
                "account creation response."
            )

        # Dispatcharr may include credentials in its
        # administrator response. Always pass the
        # response through the existing safe mapper.
        return self._safe_account(
            payload
        )

    def delete_account(
        self,
        *,
        account_id: int,
    ) -> None:
        """Delete one Dispatcharr account after caller-owned safety guards."""

        if isinstance(
            account_id,
            bool,
        ):
            raise DispatcharrAdminError(
                "Account identifier is invalid."
            )

        try:
            normalized_account_id = int(
                account_id
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise DispatcharrAdminError(
                "Account identifier is invalid."
            ) from error

        if normalized_account_id < 1:
            raise DispatcharrAdminError(
                "Account identifier is invalid."
            )

        token = self._access_token()

        payload = self._json_request(
            "DELETE",
            (
                "/api/m3u/accounts/"
                f"{normalized_account_id}/"
            ),
            {},
            access_token=token,
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise DispatcharrAdminError(
                "Dispatcharr returned an invalid "
                "account deletion response."
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

    @staticmethod
    def _positive_identifier(
        value: object,
        *,
        field: str,
    ) -> int:
        if isinstance(value, bool):
            raise DispatcharrAdminError(
                f"Dispatcharr {field} is invalid."
            )

        try:
            normalized = int(value)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise DispatcharrAdminError(
                f"Dispatcharr {field} is invalid."
            ) from error

        if normalized < 1:
            raise DispatcharrAdminError(
                f"Dispatcharr {field} is invalid."
            )

        return normalized

    def _paginated_get(
        self,
        path: str,
        *,
        access_token: str,
        page_size: int = 10000,
    ) -> tuple[Mapping[str, Any], ...]:
        """Read all rows from one DRF list endpoint without exposing next URLs."""

        rows: list[Mapping[str, Any]] = []
        page = 1

        while True:
            separator = "&" if "?" in path else "?"

            payload = self._json_request(
                "GET",
                (
                    f"{path}{separator}"
                    f"page={page}&page_size={page_size}"
                ),
                access_token=access_token,
            )

            if isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, Mapping):
                        raise DispatcharrAdminError(
                            "Dispatcharr returned an invalid list response."
                        )
                    rows.append(item)

                return tuple(rows)

            if not isinstance(payload, Mapping):
                raise DispatcharrAdminError(
                    "Dispatcharr returned an invalid list response."
                )

            results = payload.get("results")

            if not isinstance(results, list):
                raise DispatcharrAdminError(
                    "Dispatcharr returned an invalid paginated response."
                )

            for item in results:
                if not isinstance(item, Mapping):
                    raise DispatcharrAdminError(
                        "Dispatcharr returned an invalid list response."
                    )
                rows.append(item)

            next_page = payload.get("next")

            if not next_page:
                return tuple(rows)

            page += 1

            # Defensive bound against malformed/non-advancing pagination.
            if page > 10000:
                raise DispatcharrAdminError(
                    "Dispatcharr pagination did not terminate."
                )

    def _group_names(
        self,
        *,
        access_token: str,
    ) -> dict[int, str]:
        rows = self._paginated_get(
            "/api/channels/groups/",
            access_token=access_token,
        )

        groups: dict[int, str] = {}

        for raw in rows:
            group_id = self._positive_identifier(
                raw.get("id"),
                field="channel group identifier",
            )

            name = str(
                raw.get(
                    "name",
                    "",
                )
            ).strip()

            if not name:
                raise DispatcharrAdminError(
                    "Dispatcharr channel group metadata is incomplete."
                )

            if group_id in groups:
                raise DispatcharrAdminError(
                    "Dispatcharr returned duplicate channel group identifiers."
                )

            groups[group_id] = name

        return groups

    @classmethod
    def _safe_stream(
        cls,
        raw: Mapping[str, Any],
        *,
        expected_account_id: int,
        group_names: Mapping[int, str],
    ) -> SafeDispatcharrStream:
        # Use Dispatcharr's database PK. Its serializer also exposes a
        # provider-side stream_id which is only unique within an account
        # and must not cross the Atlas resolution boundary.
        stream_id = cls._positive_identifier(
            raw.get("id"),
            field="stream identifier",
        )

        account_id = cls._positive_identifier(
            raw.get("m3u_account"),
            field="stream account identifier",
        )

        if account_id != expected_account_id:
            raise DispatcharrAdminError(
                "Dispatcharr returned a stream for the wrong account."
            )

        name = str(
            raw.get(
                "name",
                "",
            )
        ).strip()

        if not name:
            raise DispatcharrAdminError(
                "Dispatcharr stream metadata is incomplete."
            )

        raw_group = raw.get("channel_group")
        group_name: str | None = None

        if raw_group is not None:
            group_id = cls._positive_identifier(
                raw_group,
                field="stream channel group identifier",
            )

            group_name = group_names.get(
                group_id
            )

            if group_name is None:
                raise DispatcharrAdminError(
                    "Dispatcharr stream references an unknown channel group."
                )

        return SafeDispatcharrStream(
            stream_id=stream_id,
            name=name,
            m3u_account_id=account_id,
            group_name=group_name,
            is_stale=bool(
                raw.get(
                    "is_stale",
                    False,
                )
            ),
        )

    def list_streams(
        self,
        *,
        account_id: int,
    ) -> tuple[SafeDispatcharrStream, ...]:
        """Return secret-free imported streams for one Dispatcharr account."""

        normalized_account_id = self._positive_identifier(
            account_id,
            field="account identifier",
        )

        token = self._access_token()

        group_names = self._group_names(
            access_token=token,
        )

        query = urllib.parse.urlencode(
            {
                "m3u_account": normalized_account_id,
            }
        )

        rows = self._paginated_get(
            (
                "/api/channels/streams/"
                f"?{query}"
            ),
            access_token=token,
        )

        streams = tuple(
            self._safe_stream(
                raw,
                expected_account_id=(
                    normalized_account_id
                ),
                group_names=group_names,
            )
            for raw in rows
        )

        stream_ids = [
            stream.stream_id
            for stream in streams
        ]

        if len(stream_ids) != len(
            set(stream_ids)
        ):
            raise DispatcharrAdminError(
                "Dispatcharr returned duplicate stream identifiers."
            )

        return streams

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
    "SafeDispatcharrStream",
]
