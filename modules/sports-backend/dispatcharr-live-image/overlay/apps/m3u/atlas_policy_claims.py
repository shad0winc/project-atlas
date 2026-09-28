"""Read-only Atlas source authority client for future verified live admission.

This client never accepts a viewer-supplied URL or token. It does not make a
provider capacity observation or install itself into the live proxy.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID


class AtlasPolicyUnavailable(RuntimeError):
    """The authenticated Atlas source claim could not be verified."""


@dataclass(frozen=True, slots=True)
class AtlasPolicyClaim:
    channel_uuid: str
    source_id: str
    account_id: int
    configured_max_connections: int
    credential_realm: str
    provider: str
    provider_event_id: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise AtlasPolicyUnavailable("Atlas policy redirected")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AtlasPolicyUnavailable("Atlas policy response contains duplicate keys")
        result[key] = value
    return result


class AtlasPolicyClaimClient:
    def __init__(self, *, origin: str, token: str, timeout_seconds: float = 3.0,
                 opener=None) -> None:
        if not isinstance(origin, str) or not isinstance(token, str):
            raise AtlasPolicyUnavailable("Atlas policy client is not configured")
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or len(token) < 32
                or not (0 < timeout_seconds <= 10)):
            raise AtlasPolicyUnavailable("Atlas policy client is not configured")
        self._origin = origin.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())

    def fetch(self, channel_uuid: str) -> tuple[AtlasPolicyClaim, ...]:
        try:
            if str(UUID(channel_uuid)) != channel_uuid:
                raise ValueError("noncanonical UUID")
        except (TypeError, ValueError, AttributeError):
            raise AtlasPolicyUnavailable("Invalid channel identity") from None
        url = self._origin + "/internal/v1/live-policy/" + channel_uuid
        request = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + self._token,
        }, method="GET")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise AtlasPolicyUnavailable("Atlas policy status unavailable")
                payload = response.read(65537)
        except AtlasPolicyUnavailable:
            raise
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise AtlasPolicyUnavailable("Atlas policy service unavailable") from None
        if len(payload) > 65536:
            raise AtlasPolicyUnavailable("Atlas policy response too large")
        try:
            document = json.loads(payload, object_pairs_hook=_unique_pairs)
        except AtlasPolicyUnavailable:
            raise
        except (ValueError, UnicodeDecodeError):
            raise AtlasPolicyUnavailable("Atlas policy response invalid") from None
        if not isinstance(document, dict) or set(document) != {"claims"}:
            raise AtlasPolicyUnavailable("Atlas policy response invalid")
        rows = document["claims"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
            raise AtlasPolicyUnavailable("Atlas policy claim count invalid")
        claims = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "channel_uuid", "source_id", "account_id", "configured_max_connections",
                "credential_realm", "provider", "provider_event_id",
            }:
                raise AtlasPolicyUnavailable("Atlas policy claim invalid")
            source_id = row["source_id"]
            if (row["channel_uuid"] != channel_uuid
                    or not isinstance(source_id, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", source_id)
                    or type(row["account_id"]) is not int or row["account_id"] <= 0
                    or type(row["configured_max_connections"]) is not int
                    or row["configured_max_connections"] <= 0
                    or not isinstance(row["credential_realm"], str)
                    or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,127}",
                                        row["credential_realm"])
                    or not isinstance(row["provider"], str) or not row["provider"]
                    or not isinstance(row["provider_event_id"], str)
                    or not row["provider_event_id"]):
                raise AtlasPolicyUnavailable("Atlas policy claim invalid")
            claims.append(AtlasPolicyClaim(**row))
        if (len({c.account_id for c in claims}) != len(claims)
                or len({c.source_id for c in claims}) != len(claims)
                or len({(c.provider, c.provider_event_id) for c in claims}) != 1):
            raise AtlasPolicyUnavailable("Atlas policy claims conflict")
        return tuple(claims)

    def for_account(self, channel_uuid: str, account_id: int) -> AtlasPolicyClaim:
        if type(account_id) is not int or account_id <= 0:
            raise AtlasPolicyUnavailable("Invalid account identity")
        matches = [claim for claim in self.fetch(channel_uuid)
                   if claim.account_id == account_id]
        if len(matches) != 1:
            raise AtlasPolicyUnavailable("Account is not authorized for event")
        return matches[0]
