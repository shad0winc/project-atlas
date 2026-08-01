"""Read-only Prowlarr adapter for the Atlas Discovery domain."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from atlas.discovery.models import (
    DiscoveryCapability,
    DiscoveryIndexer,
)

from .base import (
    BaseDiscoveryProvider,
    DiscoveryProviderError,
)


@dataclass(frozen=True)
class ProwlarrDiscoveryProvider(BaseDiscoveryProvider):
    """Translate Prowlarr API resources into Atlas Discovery models."""

    def list_indexers(self) -> tuple[DiscoveryIndexer, ...]:
        """Return configured Prowlarr indexers as normalized models."""

        payload = self._get_json("/api/v1/indexer")
        items = _required_object_collection(
            payload,
            "Prowlarr indexer response",
        )

        tag_lookup = self._list_tag_lookup()

        indexers = tuple(
            self._normalize_indexer(
                item,
                tag_lookup=tag_lookup,
            )
            for item in items
        )

        return tuple(
            sorted(
                indexers,
                key=lambda indexer: (
                    indexer.name.casefold(),
                    indexer.identifier,
                ),
            )
        )

    def list_categories(self) -> tuple[str, ...]:
        """Return categories exposed by configured Prowlarr indexers."""

        payload = self._get_json("/api/v1/indexer")
        items = _required_object_collection(
            payload,
            "Prowlarr indexer response",
        )

        categories: set[str] = set()

        for item in items:
            capabilities = item.get("capabilities")

            if capabilities is None:
                continue

            if not isinstance(capabilities, Mapping):
                raise DiscoveryProviderError(
                    "Prowlarr indexer capabilities must be an object",
                )

            category_items = capabilities.get("categories", ())

            categories.update(
                _flatten_categories(
                    category_items,
                )
            )

        return tuple(sorted(categories))

    def list_applications(self) -> tuple[str, ...]:
        """Return enabled applications connected to Prowlarr."""

        payload = self._get_json("/api/v1/applications")
        items = _required_object_collection(
            payload,
            "Prowlarr application response",
        )

        applications: set[str] = set()

        for item in items:
            enabled = item.get("enable", True)

            if not isinstance(enabled, bool):
                raise DiscoveryProviderError(
                    "Prowlarr application enable must be a boolean",
                )

            if not enabled:
                continue

            applications.add(
                _required_text(
                    item.get("name"),
                    "Prowlarr application name",
                )
            )

        return tuple(
            sorted(
                applications,
                key=lambda application: (
                    application.casefold(),
                    application,
                ),
            )
        )

    def _list_tag_lookup(self) -> dict[int, str]:
        """Return Prowlarr tag IDs mapped to normalized labels."""

        payload = self._get_json("/api/v1/tag")
        items = _required_object_collection(
            payload,
            "Prowlarr tag response",
        )

        tags: dict[int, str] = {}

        for item in items:
            identifier = item.get("id")

            if (
                isinstance(identifier, bool)
                or not isinstance(identifier, int)
            ):
                raise DiscoveryProviderError(
                    "Prowlarr tag id must be an integer",
                )

            if identifier in tags:
                raise DiscoveryProviderError(
                    f"Prowlarr returned duplicate tag id: {identifier}",
                )

            tags[identifier] = _required_text(
                item.get("label"),
                "Prowlarr tag label",
            )

        return tags

    def _normalize_indexer(
        self,
        item: Mapping[str, Any],
        *,
        tag_lookup: Mapping[int, str],
    ) -> DiscoveryIndexer:
        """Translate one configured Prowlarr indexer payload."""

        enabled = item.get("enable")

        if not isinstance(enabled, bool):
            raise DiscoveryProviderError(
                "Prowlarr indexer enable must be a boolean",
            )

        priority = item.get("priority")

        if (
            priority is not None
            and (
                isinstance(priority, bool)
                or not isinstance(priority, int)
            )
        ):
            raise DiscoveryProviderError(
                "Prowlarr indexer priority must be an integer or null",
            )

        capabilities_payload = item.get("capabilities")

        if capabilities_payload is None:
            category_names: tuple[str, ...] = ()
        else:
            if not isinstance(capabilities_payload, Mapping):
                raise DiscoveryProviderError(
                    "Prowlarr indexer capabilities must be an object",
                )

            category_names = _flatten_categories(
                capabilities_payload.get("categories", ()),
            )

        tags = _normalize_tag_ids(
            item.get("tags", ()),
            tag_lookup=tag_lookup,
        )

        return DiscoveryIndexer(
            identifier=_required_identifier(
                item.get("id"),
                "Prowlarr indexer id",
            ),
            name=_required_text(
                item.get("name"),
                "Prowlarr indexer name",
            ),
            enabled=enabled,
            protocol=_required_text(
                item.get("protocol"),
                "Prowlarr indexer protocol",
            ),
            priority=priority,
            capabilities=_infer_capabilities(
                category_names,
            ),
            categories=category_names,
            tags=tags,
            created_at=_optional_timestamp(
                item.get("added"),
                "Prowlarr indexer added",
            ),
        )


def _required_object_collection(
    value: object,
    context: str,
) -> tuple[Mapping[str, Any], ...]:
    if (
        isinstance(value, (str, bytes, Mapping))
        or not isinstance(value, Iterable)
    ):
        raise DiscoveryProviderError(
            f"{context} must be an array",
        )

    normalized = tuple(value)

    for item in normalized:
        if not isinstance(item, Mapping):
            raise DiscoveryProviderError(
                f"{context} must contain objects",
            )

    return normalized


def _flatten_categories(
    value: object,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if (
        isinstance(value, (str, bytes, Mapping))
        or not isinstance(value, Iterable)
    ):
        raise DiscoveryProviderError(
            "Prowlarr categories must be an array",
        )

    categories: set[str] = set()

    for item in value:
        if not isinstance(item, Mapping):
            raise DiscoveryProviderError(
                "Prowlarr categories must contain objects",
            )

        categories.add(
            _required_text(
                item.get("name"),
                "Prowlarr category name",
            )
        )

        categories.update(
            _flatten_categories(
                item.get("subCategories", ()),
            )
        )

    return tuple(sorted(categories))


def _infer_capabilities(
    categories: Iterable[str],
) -> tuple[DiscoveryCapability, ...]:
    normalized = {
        category.casefold()
        for category in categories
    }

    capabilities: set[DiscoveryCapability] = set()

    if any(
        category == "movies"
        or category.startswith("movies/")
        or category == "movie"
        or category.startswith("movie/")
        for category in normalized
    ):
        capabilities.add(DiscoveryCapability.MOVIES)

    if any(
        category == "tv"
        or category.startswith("tv/")
        or category == "television"
        or category.startswith("television/")
        for category in normalized
    ):
        capabilities.add(DiscoveryCapability.TV)

    if any(
        "anime" in category
        for category in normalized
    ):
        capabilities.add(DiscoveryCapability.ANIME)

    if any(
        category == "audio"
        or category.startswith("audio/")
        or category == "music"
        or category.startswith("music/")
        for category in normalized
    ):
        capabilities.add(DiscoveryCapability.MUSIC)

    if any(
        category == "books"
        or category.startswith("books/")
        or category == "book"
        or category.startswith("book/")
        or category == "manga"
        or category.startswith("manga/")
        for category in normalized
    ):
        capabilities.add(DiscoveryCapability.BOOKS)

    if not capabilities:
        capabilities.add(DiscoveryCapability.GENERAL)

    return tuple(
        sorted(
            capabilities,
            key=lambda capability: capability.value,
        )
    )


def _normalize_tag_ids(
    value: object,
    *,
    tag_lookup: Mapping[int, str],
) -> tuple[str, ...]:
    if value is None:
        return ()

    if (
        isinstance(value, (str, bytes, Mapping))
        or not isinstance(value, Iterable)
    ):
        raise DiscoveryProviderError(
            "Prowlarr indexer tags must be an array",
        )

    tags: set[str] = set()

    for identifier in value:
        if (
            isinstance(identifier, bool)
            or not isinstance(identifier, int)
        ):
            raise DiscoveryProviderError(
                "Prowlarr indexer tag ids must be integers",
            )

        try:
            label = tag_lookup[identifier]
        except KeyError as exc:
            raise DiscoveryProviderError(
                f"Prowlarr indexer references unknown tag id: {identifier}",
            ) from exc

        tags.add(label)

    return tuple(sorted(tags))


def _required_identifier(
    value: object,
    field_name: str,
) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DiscoveryProviderError(
            f"{field_name} must be a string or integer",
        )

    normalized = str(value).strip()

    if not normalized:
        raise DiscoveryProviderError(
            f"{field_name} is required",
        )

    return normalized


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryProviderError(
            f"{field_name} is required",
        )

    return value.strip()


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise DiscoveryProviderError(
            f"{field_name} must be a timestamp or null",
        )

    return value.strip()
