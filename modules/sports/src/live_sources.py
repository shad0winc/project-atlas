"""Provider-neutral authorized Sports live-source catalog."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


class LiveSourceCatalogError(ValueError):
    """Raised when an authorized live-source catalog is invalid."""


@dataclass(frozen=True, slots=True)
class LiveSource:
    source_id: str
    name: str
    stream_url: str
    provider: str | None = None
    provider_event_id: str | None = None
    standalone: bool = False

    @property
    def event_key(self) -> tuple[str, str] | None:
        if not self.provider or not self.provider_event_id:
            return None
        return (self.provider, self.provider_event_id)

    @property
    def atlas_channel_id(self) -> str:
        return f"sports-live-{self.source_id}"


def _required(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LiveSourceCatalogError(f"{field} is required")
    return value.strip()


def _optional(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LiveSourceCatalogError(
            "optional live-source fields must be strings"
        )
    value = value.strip()
    return value or None


def _stream_url(value: object) -> str:
    url = _required(value, "stream_url")
    parsed = urlsplit(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LiveSourceCatalogError(
            "stream_url must use an absolute http or https URL"
        )

    if parsed.username or parsed.password:
        raise LiveSourceCatalogError(
            "stream_url must not contain URL userinfo credentials"
        )

    return url


def _parse_source(entry: object) -> LiveSource:
    if not isinstance(entry, dict):
        raise LiveSourceCatalogError(
            "live source entries must be objects"
        )

    source_id = _required(entry.get("id"), "id")
    name = _required(entry.get("name"), "name")
    stream_url = _stream_url(entry.get("stream_url"))
    provider = _optional(entry.get("provider"))
    provider_event_id = _optional(entry.get("provider_event_id"))
    standalone = bool(entry.get("standalone", False))

    if bool(provider) != bool(provider_event_id):
        raise LiveSourceCatalogError(
            "provider and provider_event_id must be supplied together"
        )

    if standalone and provider_event_id:
        raise LiveSourceCatalogError(
            "standalone sources cannot also bind to a provider event"
        )

    if not standalone and not provider_event_id:
        raise LiveSourceCatalogError(
            "a live source must be standalone or explicitly event-bound"
        )

    return LiveSource(
        source_id=source_id,
        name=name,
        stream_url=stream_url,
        provider=provider.lower() if provider else None,
        provider_event_id=provider_event_id,
        standalone=standalone,
    )


class LiveSourceCatalog:
    """Read-only authorized live-source mappings."""

    def __init__(self, sources: tuple[LiveSource, ...]) -> None:
        self._sources = sources
        self._by_event: dict[tuple[str, str], LiveSource] = {}
        seen_ids: set[str] = set()

        for source in sources:
            if source.source_id in seen_ids:
                raise LiveSourceCatalogError(
                    f"duplicate live source id: {source.source_id}"
                )
            seen_ids.add(source.source_id)

            if source.event_key is not None:
                if source.event_key in self._by_event:
                    raise LiveSourceCatalogError(
                        "duplicate live source event mapping: "
                        f"{source.event_key[0]}:{source.event_key[1]}"
                    )
                self._by_event[source.event_key] = source

    @property
    def sources(self) -> tuple[LiveSource, ...]:
        return self._sources

    def for_event(
        self,
        provider: str,
        provider_event_id: str,
    ) -> LiveSource | None:
        return self._by_event.get(
            (
                _required(provider, "provider").lower(),
                _required(provider_event_id, "provider_event_id"),
            )
        )

    def standalone_sources(self) -> tuple[LiveSource, ...]:
        return tuple(
            source
            for source in self._sources
            if source.standalone
        )


def load_live_source_catalog(
    path: str | os.PathLike[str] | None = None,
) -> LiveSourceCatalog:
    """Load the catalog; an unset path intentionally means no live sources."""

    configured = (
        str(path)
        if path is not None
        else os.getenv("SPORTS_LIVE_SOURCE_CATALOG_PATH", "")
    ).strip()

    if not configured:
        return LiveSourceCatalog(())

    catalog_path = Path(configured)

    try:
        raw = json.loads(
            catalog_path.read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise LiveSourceCatalogError(
            f"live source catalog does not exist: {catalog_path}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveSourceCatalogError(
            "live source catalog could not be read"
        ) from exc

    if not isinstance(raw, dict):
        raise LiveSourceCatalogError(
            "live source catalog root must be an object"
        )

    entries = raw.get("sources", [])

    if not isinstance(entries, list):
        raise LiveSourceCatalogError(
            "live source catalog sources must be a list"
        )

    return LiveSourceCatalog(
        tuple(_parse_source(entry) for entry in entries)
    )


def safe_source_summary(source: LiveSource) -> dict[str, object]:
    """Return source metadata that never exposes its raw stream URL."""

    return {
        "id": source.source_id,
        "name": source.name,
        "provider": source.provider,
        "provider_event_id": source.provider_event_id,
        "standalone": source.standalone,
    }
