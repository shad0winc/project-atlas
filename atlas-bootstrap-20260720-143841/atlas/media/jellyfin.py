"""Jellyfin media provider adapter."""
from __future__ import annotations
import json, os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from atlas.media.provider import MediaItem, MediaProviderError

_TYPE_MAP = {"movie": "movie", "series": "tv", "season": "tv", "episode": "tv"}

@dataclass(frozen=True)
class JellyfinProvider:
    base_url: str
    api_key: str
    timeout: float = 10.0

    @property
    def name(self) -> str:
        return "jellyfin"

    def get_user(self, user_id: str) -> dict[str, Any]:
        normalized_id = _required(user_id, "user_id")
        user = self._get_json(f"/Users/{quote(normalized_id, safe='')}")

        if not isinstance(user, dict):
            raise MediaProviderError("Jellyfin returned an invalid user response")

        returned_id = _required(user.get("Id"), "Jellyfin user ID")
        name = _required(user.get("Name"), "Jellyfin user name")

        if returned_id.lower() != normalized_id.lower():
            raise MediaProviderError("Jellyfin returned a mismatched user response")

        return {
            "id": returned_id,
            "name": name,
        }

    def get_item(self, item_id: str) -> MediaItem:
        normalized_id = _required(item_id, "item_id")
        item = self._get_json(f"/Items/{quote(normalized_id, safe='')}")
        if not isinstance(item, dict):
            raise MediaProviderError("Jellyfin returned an invalid item response")
        title = _required(item.get("Name"), "Jellyfin item name")
        raw_type = str(item.get("Type") or "").strip().lower()
        metadata: dict[str, Any] = {"jellyfin_type": item.get("Type") or "Unknown"}
        if isinstance(item.get("ProductionYear"), int): metadata["year"] = item["ProductionYear"]
        if isinstance(item.get("Path"), str) and item["Path"].strip(): metadata["path"] = item["Path"].strip()
        if isinstance(item.get("SeriesName"), str) and item["SeriesName"].strip(): metadata["series_name"] = item["SeriesName"].strip()
        library = self._library_name(normalized_id)
        if library: metadata["library"] = library
        return MediaItem(self.name, normalized_id, _TYPE_MAP.get(raw_type, "other"), title, metadata)

    def _library_name(self, item_id: str) -> str | None:
        try:
            ancestors = self._get_json(f"/Items/{quote(item_id, safe='')}/Ancestors")
        except MediaProviderError:
            return None
        if not isinstance(ancestors, list): return None
        for ancestor in ancestors:
            if isinstance(ancestor, dict) and str(ancestor.get("Type") or "").lower() == "collectionfolder":
                name = ancestor.get("Name")
                if isinstance(name, str) and name.strip(): return name.strip()
        return None

    def _get_json(self, path: str) -> Any:
        if not self.api_key.strip(): raise MediaProviderError("ATLAS_JELLYFIN_API_KEY is required")
        request = Request(f"{self.base_url.rstrip('/')}{path}", headers={"Accept":"application/json","X-Emby-Token":self.api_key.strip()})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise MediaProviderError("Jellyfin resource not found") from exc
            raise MediaProviderError(f"Jellyfin request failed with HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise MediaProviderError(f"Jellyfin is unreachable: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MediaProviderError("Jellyfin returned invalid JSON") from exc

def default_jellyfin_provider() -> JellyfinProvider:
    return JellyfinProvider(os.getenv("ATLAS_JELLYFIN_URL", "http://127.0.0.1:8096"), os.getenv("ATLAS_JELLYFIN_API_KEY", ""))

def _required(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip(): raise MediaProviderError(f"{field} is required")
    return value.strip()
