"""Explicit acquisition wiring; importing this module never activates policy."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
import re

from ..models import MediaAudioPreference, MediaRequest
from ..provider import MediaRequestProviderError
from .jellyseerr import JellyseerrMediaRequestProvider
from .managed_profiles import (
    ArrManagedProfileReader, ArrProfileBinding, CATEGORIES, positive_id, server_id,
)


@dataclass(frozen=True)
class SeerrTVDBResolver:
    """Resolve verified TMDB metadata for an exact configured TV category/server.

    read_json must be a trusted, GET-only, bounded, no-redirect transport.
    Its URL and credential configuration stay outside this identity resolver.
    """

    category_servers: Mapping[str, int]
    read_json: Callable[[str], object] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.category_servers, Mapping) or not callable(self.read_json):
            raise MediaRequestProviderError("TVDB resolver configuration is invalid")
        copied = {}
        for category, configured_server in self.category_servers.items():
            if category not in {"tv", "anime_tv"}:
                raise MediaRequestProviderError("TVDB resolver category is invalid")
            copied[category] = server_id(configured_server)
        object.__setattr__(self, "category_servers", MappingProxyType(copied))

    def __call__(self, request: MediaRequest, configured_server: int) -> int:
        try:
            if not isinstance(request, MediaRequest) or request.provider != "jellyseerr":
                raise ValueError("Invalid provider")
            category = request.media_type.value
            if (category not in self.category_servers
                    or server_id(configured_server) != self.category_servers[category]):
                raise ValueError("Unbound category/server")
            # Canonical decimal identities only; never title matching or integer coercion.
            raw_id = request.provider_media_id
            if not isinstance(raw_id, str) or re.fullmatch(r"[1-9][0-9]*", raw_id) is None:
                raise ValueError("Invalid TMDB identity")
            tmdb_id = positive_id(int(raw_id))
            details = self.read_json(f"/api/v1/tv/{tmdb_id}")
            if not isinstance(details, Mapping) or positive_id(details.get("id")) != tmdb_id:
                raise ValueError("Conflicting TMDB identity")
            external = details.get("externalIds")
            if not isinstance(external, Mapping):
                raise ValueError("Missing external identity")
            tvdb_id = positive_id(external.get("tvdbId"))
            # Some managed titles include mediaInfo. When present, it must corroborate.
            info = details.get("mediaInfo")
            if info is not None:
                if not isinstance(info, Mapping):
                    raise ValueError("Malformed media identity")
                for key, expected in (("tmdbId", tmdb_id), ("tvdbId", tvdb_id)):
                    if key in info and info[key] is not None and positive_id(info[key]) != expected:
                        raise ValueError("Conflicting managed identity")
            return tvdb_id
        except Exception:
            raise MediaRequestProviderError("TVDB identity could not be verified") from None


def build_acquisition_provider(
    *,
    base_url: str,
    api_key: str,
    category_servers: Mapping[str, int],
    bindings: Mapping[tuple[str, int], ArrProfileBinding],
    profile_ids: Mapping[tuple[str, str], int],
    read_tv_metadata: Callable[[str], object],
) -> JellyseerrMediaRequestProvider:
    """Build an explicit provider from reviewed backend configuration.

    This foundation does not alter either default factory or allocate native
    profiles. Numeric IDs must already have passed native profile readback.
    """
    if not isinstance(category_servers, Mapping) or set(category_servers) != CATEGORIES:
        raise MediaRequestProviderError("Acquisition category routing is incomplete")
    routes = {category: server_id(value) for category, value in category_servers.items()}
    if not isinstance(bindings, Mapping) or set(bindings) != {
        (category, value) for category, value in routes.items()
    }:
        raise MediaRequestProviderError("Acquisition instance bindings do not match routing")
    expected_policies = {
        (category, mode.value) for category in CATEGORIES for mode in MediaAudioPreference
    }
    if not isinstance(profile_ids, Mapping) or set(profile_ids) != expected_policies:
        raise MediaRequestProviderError("Acquisition policy profile mapping is incomplete")
    profiles = {key: positive_id(value) for key, value in profile_ids.items()}
    # Policies must not accidentally alias inside one native instance. IDs may
    # repeat across distinct instances; native IDs are not globally unique.
    for category in CATEGORIES:
        if len({profiles[(category, mode.value)] for mode in MediaAudioPreference}) != 3:
            raise MediaRequestProviderError("Acquisition policy profiles must be distinct")
    resolver = SeerrTVDBResolver(
        {category: routes[category] for category in ("tv", "anime_tv")}, read_tv_metadata,
    )
    reader = ArrManagedProfileReader(bindings, resolve_tvdb_id=resolver)
    return JellyseerrMediaRequestProvider(
        base_url=base_url, api_key=api_key,
        movie_server_id=routes["movie"], tv_server_id=routes["tv"],
        anime_movie_server_id=routes["anime_movie"], anime_tv_server_id=routes["anime_tv"],
        audio_profile_ids=profiles, managed_profile_reader=reader,
    )
