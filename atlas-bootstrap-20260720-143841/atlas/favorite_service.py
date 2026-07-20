"""Favorites business service with provider enrichment and events."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from atlas.favorites import FavoriteError, FavoriteStore
from atlas.media.provider import MediaProvider, MediaProviderError
EventPublisher = Callable[[str, Mapping[str, Any]], None]

@dataclass(frozen=True)
class FavoriteMutationResult:
    record: dict[str, Any]
    event_error: str | None = None

@dataclass(frozen=True)
class FavoriteService:
    store: FavoriteStore
    providers: Mapping[str, MediaProvider]
    event_publisher: EventPublisher | None = None

    def add(self, user_id: str, provider_name: str, item_id: str, *, metadata: Mapping[str, Any] | None = None) -> FavoriteMutationResult:
        provider = self._provider(provider_name)
        try: item = provider.get_item(item_id)
        except MediaProviderError as exc: raise FavoriteError(str(exc)) from exc
        merged = dict(item.metadata); merged.update(dict(metadata or {}))
        record = self.store.add(user_id, item.provider, item.item_id, media_type=item.media_type, title=item.title, metadata=merged)
        return FavoriteMutationResult(record, self._publish("favorite.created", record))

    def remove(self, favorite_id: str) -> FavoriteMutationResult:
        record = self.store.remove(favorite_id)
        return FavoriteMutationResult(record, self._publish("favorite.removed", record))

    def _provider(self, name: str) -> MediaProvider:
        normalized = name.strip().lower() if isinstance(name, str) else ""
        if not normalized: raise FavoriteError("provider is required")
        provider = self.providers.get(normalized)
        if provider is None: raise FavoriteError(f"unsupported media provider: {normalized}")
        return provider

    def _publish(self, event_name: str, record: Mapping[str, Any]) -> str | None:
        if self.event_publisher is None: return None
        payload = {key: record[key] for key in ("favorite_id", "user_id", "provider", "item_id", "media_type", "title")}
        try: self.event_publisher(event_name, payload)
        except Exception as exc: return str(exc) or exc.__class__.__name__
        return None
