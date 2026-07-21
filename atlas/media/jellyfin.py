"""Jellyfin media provider adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
)
from atlas.media.provider import (
    MediaItem,
    MediaProviderError,
    ProviderMutationResult,
    ProviderOperation,
)


class _JellyfinResourceNotFoundError(MediaProviderError):
    """Raised when Jellyfin returns HTTP 404."""


_TYPE_MAP = {
    "movie": "movie",
    "series": "tv",
    "season": "tv",
    "episode": "tv",
}


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class JellyfinProvider:
    """Jellyfin-backed Atlas media provider."""

    base_url: str
    api_key: str
    timeout: float = 10.0
    clock: Clock = field(
        default=_utc_now,
        repr=False,
        compare=False,
    )

    @property
    def name(self) -> str:
        """Return the normalized provider name."""

        return "jellyfin"

    def get_capabilities(self) -> ProviderCapabilities:
        """Return the immutable Jellyfin capability contract."""

        return ProviderCapabilities(
            provider=self.name,
            capabilities=frozenset(
                {
                    ProviderCapability.LIST_MEDIA,
                    ProviderCapability.PREVIEW_DELETE,
                }
            ),
            supports_batch_listing=True,
            supports_batch_preview=False,
            max_batch_size=200,
        )

    def get_user(self, user_id: str) -> dict[str, Any]:
        """Return a normalized Jellyfin user identity."""

        normalized_id = _required(user_id, "user_id")
        user = self._get_json(
            f"/Users/{quote(normalized_id, safe='')}"
        )

        if not isinstance(user, dict):
            raise MediaProviderError(
                "Jellyfin returned an invalid user response"
            )

        returned_id = _required(
            user.get("Id"),
            "Jellyfin user ID",
        )
        name = _required(
            user.get("Name"),
            "Jellyfin user name",
        )

        if returned_id.lower() != normalized_id.lower():
            raise MediaProviderError(
                "Jellyfin returned a mismatched user response"
            )

        return {
            "id": returned_id,
            "name": name,
        }

    def get_item(self, item_id: str) -> MediaItem:
        """Return normalized metadata for one Jellyfin item."""

        normalized_id = _required(item_id, "item_id")
        item = self._get_json(
            f"/Items/{quote(normalized_id, safe='')}"
        )

        if not isinstance(item, dict):
            raise MediaProviderError(
                "Jellyfin returned an invalid item response"
            )

        title = _required(
            item.get("Name"),
            "Jellyfin item name",
        )
        raw_type = str(
            item.get("Type") or ""
        ).strip().lower()

        metadata: dict[str, Any] = {
            "jellyfin_type": item.get("Type") or "Unknown"
        }

        if isinstance(item.get("ProductionYear"), int):
            metadata["year"] = item["ProductionYear"]

        if (
            isinstance(item.get("Path"), str)
            and item["Path"].strip()
        ):
            metadata["path"] = item["Path"].strip()

        if (
            isinstance(item.get("SeriesName"), str)
            and item["SeriesName"].strip()
        ):
            metadata["series_name"] = (
                item["SeriesName"].strip()
            )

        library = self._library_name(normalized_id)

        if library:
            metadata["library"] = library

        return MediaItem(
            self.name,
            normalized_id,
            _TYPE_MAP.get(raw_type, "other"),
            title,
            metadata,
        )

    def preview_delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        """Verify an item for deletion without modifying Jellyfin."""

        normalized_id = _required(
            item_id,
            "item_id",
        )

        try:
            self.get_item(normalized_id)
        except _JellyfinResourceNotFoundError:
            return ProviderMutationResult(
                provider=self.name,
                operation=ProviderOperation.DELETE,
                item_id=normalized_id,
                success=False,
                message="Item not found",
                executed_at=self._executed_at(),
            )

        return ProviderMutationResult(
            provider=self.name,
            operation=ProviderOperation.DELETE,
            item_id=normalized_id,
            success=True,
            message="Preview verified",
            executed_at=self._executed_at(),
        )

    def _executed_at(self) -> str:
        """Return a validated UTC provider-operation timestamp."""

        value = self.clock()

        if not isinstance(value, datetime):
            raise MediaProviderError(
                "clock must return a datetime"
            )

        if value.tzinfo is None or value.utcoffset() is None:
            raise MediaProviderError(
                "clock must return a timezone-aware datetime"
            )

        return (
            value.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def list_media_item_ids(
        self,
        *,
        page_size: int = 200,
    ) -> tuple[str, ...]:
        """Return all top-level movie and series identifiers."""

        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size <= 0
        ):
            raise MediaProviderError(
                "page_size must be a positive integer"
            )

        item_ids: list[str] = []
        seen: set[str] = set()
        start_index = 0

        while True:
            query = urlencode(
                {
                    "Recursive": "true",
                    "IncludeItemTypes": "Movie,Series",
                    "StartIndex": start_index,
                    "Limit": page_size,
                }
            )

            payload = self._get_json(
                f"/Items?{query}"
            )

            if not isinstance(payload, dict):
                raise MediaProviderError(
                    "Jellyfin returned an invalid item list response"
                )

            items = payload.get("Items")
            total = payload.get("TotalRecordCount")

            if not isinstance(items, list):
                raise MediaProviderError(
                    "Jellyfin item list is invalid"
                )

            if (
                isinstance(total, bool)
                or not isinstance(total, int)
                or total < 0
            ):
                raise MediaProviderError(
                    "Jellyfin item count is invalid"
                )

            for item in items:
                if not isinstance(item, dict):
                    raise MediaProviderError(
                        "Jellyfin returned an invalid item entry"
                    )

                item_id = _required(
                    item.get("Id"),
                    "Jellyfin item ID",
                )
                normalized_id = item_id.lower()

                if normalized_id in seen:
                    raise MediaProviderError(
                        "Jellyfin returned a duplicate item ID"
                    )

                seen.add(normalized_id)
                item_ids.append(item_id)

            start_index += len(items)

            if not items or start_index >= total:
                break

        return tuple(item_ids)

    def _library_name(
        self,
        item_id: str,
    ) -> str | None:
        """Return the collection-folder name for an item."""

        try:
            ancestors = self._get_json(
                f"/Items/{quote(item_id, safe='')}/Ancestors"
            )
        except MediaProviderError:
            return None

        if not isinstance(ancestors, list):
            return None

        for ancestor in ancestors:
            if (
                isinstance(ancestor, dict)
                and str(
                    ancestor.get("Type") or ""
                ).lower() == "collectionfolder"
            ):
                name = ancestor.get("Name")

                if isinstance(name, str) and name.strip():
                    return name.strip()

        return None

    def _get_json(self, path: str) -> Any:
        """Perform an authenticated Jellyfin JSON request."""

        if not self.api_key.strip():
            raise MediaProviderError(
                "ATLAS_JELLYFIN_API_KEY is required"
            )

        request = Request(
            f"{self.base_url.rstrip('/')}{path}",
            headers={
                "Accept": "application/json",
                "X-Emby-Token": self.api_key.strip(),
            },
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )
        except HTTPError as exc:
            if exc.code == 404:
                raise _JellyfinResourceNotFoundError(
                    "Jellyfin resource not found"
                ) from exc

            raise MediaProviderError(
                f"Jellyfin request failed with HTTP {exc.code}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise MediaProviderError(
                f"Jellyfin is unreachable: {exc}"
            ) from exc
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise MediaProviderError(
                "Jellyfin returned invalid JSON"
            ) from exc


def default_jellyfin_provider() -> JellyfinProvider:
    """Build the configured Jellyfin provider."""

    return JellyfinProvider(
        os.getenv(
            "ATLAS_JELLYFIN_URL",
            "http://127.0.0.1:8096",
        ),
        os.getenv(
            "ATLAS_JELLYFIN_API_KEY",
            "",
        ),
    )


def _required(
    value: object,
    field: str,
) -> str:
    """Validate and normalize a required string."""

    if not isinstance(value, str) or not value.strip():
        raise MediaProviderError(
            f"{field} is required"
        )

    return value.strip()
