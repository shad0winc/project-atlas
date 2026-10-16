"""Authenticated, bounded Atlas managed channel classifier for owner routing."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID


class AtlasManagedClassificationUnavailable(RuntimeError):
    """No authoritative managed/unmanaged decision can be made."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise AtlasManagedClassificationUnavailable("Atlas classification redirected")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AtlasManagedClassificationUnavailable("Duplicate classification field")
        result[key] = value
    return result


class AtlasManagedChannelClient:
    def __init__(self, *, origin: str, token: str,
                 timeout_seconds: float = 3.0, opener=None):
        if (not isinstance(origin, str) or not isinstance(token, str)
            or type(timeout_seconds) not in (int, float)):
            raise AtlasManagedClassificationUnavailable("Classifier is not configured")
        try:
            parsed = urllib.parse.urlsplit(origin)
            valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                     and parsed.port != 0 and not parsed.username
                     and not parsed.password and not parsed.query
                     and not parsed.fragment and parsed.path in ("", "/")
                     and len(token) >= 32 and 0 < timeout_seconds <= 10)
        except ValueError:
            valid = False
        if not valid:
            raise AtlasManagedClassificationUnavailable("Classifier is not configured")
        self._origin = origin.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())

    def classify(self, channel_uuid: str) -> bool:
        try:
            if str(UUID(channel_uuid)) != channel_uuid:
                raise ValueError("noncanonical UUID")
        except (TypeError, ValueError, AttributeError):
            raise AtlasManagedClassificationUnavailable("Invalid channel identity") from None
        request = urllib.request.Request(
            self._origin + "/internal/v1/live-policy-classification/" + channel_uuid,
            headers={"Accept": "application/json",
                     "Authorization": "Bearer " + self._token}, method="GET",
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise AtlasManagedClassificationUnavailable("Classification status unavailable")
                payload = response.read(4097)
        except AtlasManagedClassificationUnavailable:
            raise
        except (urllib.error.URLError, OSError, TimeoutError):
            raise AtlasManagedClassificationUnavailable("Classification service unavailable") from None
        if len(payload) > 4096:
            raise AtlasManagedClassificationUnavailable("Classification response too large")
        try:
            document = json.loads(payload, object_pairs_hook=_unique_pairs)
        except AtlasManagedClassificationUnavailable:
            raise
        except (ValueError, UnicodeDecodeError):
            raise AtlasManagedClassificationUnavailable("Invalid classification response") from None
        if (not isinstance(document, dict)
            or set(document) != {"channel_uuid", "managed"}
            or document["channel_uuid"] != channel_uuid
            or type(document["managed"]) is not bool):
            raise AtlasManagedClassificationUnavailable("Invalid classification response")
        return document["managed"]
