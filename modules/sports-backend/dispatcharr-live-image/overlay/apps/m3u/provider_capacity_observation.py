"""Bounded, secret-safe Xtream capacity observation for verified admission.

The caller supplies effective transformed playback credentials. This module
does not persist provider responses or treat cached Dispatcharr profile JSON
as current evidence. It is not installed in the live proxy yet.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from apps.m3u.atlas_verified_policy_adapter import ProviderCapacityEvidence
from apps.m3u.verified_live_policy import VerifiedLivePolicyUnavailable


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise VerifiedLivePolicyUnavailable("Provider capacity redirect refused")


def _positive_limit(raw: object) -> int:
    if type(raw) is int:
        value = raw
    elif isinstance(raw, str) and raw.isascii() and raw.isdecimal():
        value = int(raw)
    else:
        raise VerifiedLivePolicyUnavailable("Provider limit unavailable")
    if not 1 <= value <= 1000:
        raise VerifiedLivePolicyUnavailable("Provider limit unavailable")
    return value


def _active_connections(raw: object, limit: int) -> int:
    if type(raw) is int:
        value = raw
    elif isinstance(raw, str) and raw.isascii() and raw.isdecimal():
        value = int(raw)
    else:
        raise VerifiedLivePolicyUnavailable("Provider activity unavailable")
    if not 0 <= value <= limit:
        raise VerifiedLivePolicyUnavailable("Provider activity unavailable")
    return value


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VerifiedLivePolicyUnavailable("Provider capacity response invalid")
        result[key] = value
    return result


class XtreamCapacityReader:
    def __init__(self, *, timeout_seconds: float = 3.0, opener=None,
                 clock=time.time) -> None:
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 10:
            raise ValueError("Invalid capacity timeout")
        self._timeout = timeout_seconds
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())
        self._clock = clock

    def __call__(self, account, credentials: tuple[str, str, str]) -> ProviderCapacityEvidence:
        try:
            if (type(account.id) is not int or account.id <= 0
                    or not isinstance(credentials, tuple) or len(credentials) != 3):
                raise VerifiedLivePolicyUnavailable("Provider identity unavailable")
            origin, username, password = credentials
            if not all(isinstance(value, str) and value for value in credentials):
                raise VerifiedLivePolicyUnavailable("Provider identity unavailable")
            parsed = urllib.parse.urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.query or parsed.fragment):
                raise VerifiedLivePolicyUnavailable("Provider origin unavailable")
            path = parsed.path.rstrip("/") + "/player_api.php"
            query = urllib.parse.urlencode({"username": username, "password": password})
            url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))
            user_agent = account.get_user_agent_string()
            if not isinstance(user_agent, str) or not user_agent.strip():
                raise VerifiedLivePolicyUnavailable("Provider user agent unavailable")
            request = urllib.request.Request(url, headers={
                "Accept": "application/json", "User-Agent": user_agent,
            }, method="GET")
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise VerifiedLivePolicyUnavailable("Provider capacity unavailable")
                body = response.read(65537)
            if len(body) > 65536:
                raise VerifiedLivePolicyUnavailable("Provider capacity response too large")
            document = json.loads(body, object_pairs_hook=_unique_keys)
            if not isinstance(document, dict) or not isinstance(document.get("user_info"), dict):
                raise VerifiedLivePolicyUnavailable("Provider capacity response invalid")
            user_info = document["user_info"]
            if user_info.get("status") != "Active" and user_info.get("status") != "active":
                raise VerifiedLivePolicyUnavailable("Provider account inactive")
            limit = _positive_limit(user_info.get("max_connections"))
            active = _active_connections(user_info.get("active_cons"), limit)
            observed_at = int(self._clock())
            if observed_at <= 0:
                raise VerifiedLivePolicyUnavailable("Provider observation clock unavailable")
            return ProviderCapacityEvidence(account.id, "active", limit, active, observed_at)
        except VerifiedLivePolicyUnavailable:
            raise
        except Exception:
            # urllib errors and malformed responses can contain the credential URL.
            raise VerifiedLivePolicyUnavailable("Provider capacity unavailable") from None
