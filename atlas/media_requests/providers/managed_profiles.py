"""Read managed profiles from explicitly bound Arr instances; never mutate them."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import json
from types import MappingProxyType
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..models import MediaRequest
from ..provider import MediaRequestProviderError

CATEGORIES = frozenset({"movie", "tv", "anime_movie", "anime_tv"})


class AcquisitionProfileConflict(MediaRequestProviderError):
    """A shared managed title uses an incompatible acquisition profile."""


def positive_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MediaRequestProviderError("Managed profile identity is invalid")
    return value


def server_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MediaRequestProviderError("Managed server identity is invalid")
    return value


@dataclass(frozen=True)
class ManagedProfileEvidence:
    category: str
    server_id: int
    tmdb_id: int
    managed_item_id: int | None
    quality_profile_id: int | None

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise MediaRequestProviderError("Managed media category is invalid")
        server_id(self.server_id)
        positive_id(self.tmdb_id)
        if (self.managed_item_id is None) != (self.quality_profile_id is None):
            raise MediaRequestProviderError("Managed profile evidence is incomplete")
        if self.managed_item_id is not None:
            positive_id(self.managed_item_id)
            positive_id(self.quality_profile_id)


@dataclass(frozen=True)
class ArrProfileBinding:
    """Trusted backend configuration, including the Arr /api/v3 URL prefix."""
    base_url: str
    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or not parsed.path.rstrip("/").endswith("/api/v3")):
            raise MediaRequestProviderError("Arr profile endpoint is invalid")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise MediaRequestProviderError("Arr profile credential is unavailable")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class ArrManagedProfileReader:
    bindings: Mapping[tuple[str, int], ArrProfileBinding]
    # Resolve TMDB to an authoritative TVDB ID. No title matching or default server fallback.
    resolve_tvdb_id: Callable[[MediaRequest, int], int] | None = field(default=None, repr=False)
    timeout: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, Mapping):
            raise MediaRequestProviderError("Arr profile bindings must be a mapping")
        copied = {}
        for key, value in self.bindings.items():
            if (not isinstance(key, tuple) or len(key) != 2 or key[0] not in CATEGORIES
                    or not isinstance(value, ArrProfileBinding)):
                raise MediaRequestProviderError("Arr profile binding is invalid")
            server_id(key[1])
            copied[key] = value
        if (isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float))
                or not 0 < self.timeout <= 60):
            raise MediaRequestProviderError("Arr profile timeout is invalid")
        if self.resolve_tvdb_id is not None and not callable(self.resolve_tvdb_id):
            raise MediaRequestProviderError("TVDB resolver must be callable")
        object.__setattr__(self, "bindings", MappingProxyType(copied))

    def _read_json(self, binding: ArrProfileBinding, endpoint: str):
        request = Request(binding.base_url.rstrip("/") + "/" + endpoint,
                          headers={"X-Api-Key": binding.api_key, "Accept": "application/json"},
                          method="GET")
        try:
            with build_opener(_NoRedirect()).open(request, timeout=self.timeout) as response:
                raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                raise ValueError("Oversized inventory")
            return json.loads(raw)
        except Exception:
            # Do not expose backend URLs, headers, credentials or raw response bodies.
            raise MediaRequestProviderError("Managed profile inventory could not be verified") from None

    def __call__(self, request: MediaRequest, configured_server: int) -> ManagedProfileEvidence:
        try:
            if not isinstance(request, MediaRequest):
                raise ValueError("Invalid request")
            category = request.media_type.value
            server_id(configured_server)
            binding = self.bindings.get((category, configured_server))
            if binding is None:
                raise ValueError("Missing instance binding")
            tmdb_id = positive_id(int(request.provider_media_id))
            television = category in {"tv", "anime_tv"}
            target_id = tmdb_id
            if television:
                if self.resolve_tvdb_id is None:
                    raise ValueError("Missing authoritative TVDB resolver")
                target_id = positive_id(self.resolve_tvdb_id(request, configured_server))
            identity_field = "tvdbId" if television else "tmdbId"
            rows = self._read_json(binding, "series" if television else "movie")
            if not isinstance(rows, list) or len(rows) > 5000:
                raise ValueError("Invalid complete inventory")
            matches = []
            managed_ids = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("Invalid inventory row")
                identity = positive_id(row.get(identity_field))
                item_id = positive_id(row.get("id"))
                profile_id = positive_id(row.get("qualityProfileId"))
                if item_id in managed_ids:
                    raise ValueError("Duplicate managed identity")
                managed_ids.add(item_id)
                if identity == target_id:
                    matches.append((item_id, profile_id))
            if len(matches) > 1:
                raise ValueError("Ambiguous managed identity")
            item_id, profile_id = matches[0] if matches else (None, None)
            return ManagedProfileEvidence(category, configured_server, tmdb_id, item_id, profile_id)
        except Exception:
            raise MediaRequestProviderError("Managed profile identity could not be verified") from None
