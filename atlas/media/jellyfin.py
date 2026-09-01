"""Jellyfin media provider adapter."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
        query = urlencode(
            {
                "Ids": normalized_id,
                "Recursive": "true",
                "Limit": 1,
            }
        )
        payload = self._get_json(f"/Items?{query}")

        if not isinstance(payload, dict):
            raise MediaProviderError(
                "Jellyfin returned an invalid item response"
            )

        items = payload.get("Items")

        if not isinstance(items, list):
            raise MediaProviderError(
                "Jellyfin returned an invalid item response"
            )

        if not items:
            raise _JellyfinResourceNotFoundError(
                "Jellyfin resource not found"
            )

        if len(items) != 1 or not isinstance(items[0], dict):
            raise MediaProviderError(
                "Jellyfin returned an invalid item response"
            )

        item = items[0]
        returned_id = _required(
            item.get("Id"),
            "Jellyfin item ID",
        )

        if returned_id.lower() != normalized_id.lower():
            raise MediaProviderError(
                "Jellyfin returned a mismatched item response"
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

    def list_series_episodes(
        self,
        series_id: str,
    ) -> tuple[dict[str, Any], ...]:
        # Return ordered browser-safe episode identities for a Series.

        normalized_id = _required(series_id, "series_id")
        query = urlencode(
            {
                "ParentId": normalized_id,
                "Recursive": "true",
                "IncludeItemTypes": "Episode",
                "SortBy": "ParentIndexNumber,IndexNumber",
                "SortOrder": "Ascending",
                "Fields": (
                    "SeriesName,ParentIndexNumber,IndexNumber"
                ),
            }
        )

        payload = self._get_json(f"/Items?{query}")

        if not isinstance(payload, dict):
            raise MediaProviderError(
                "Jellyfin returned an invalid episode list response"
            )

        items = payload.get("Items")
        if not isinstance(items, list):
            raise MediaProviderError(
                "Jellyfin episode list is invalid"
            )

        episodes: list[dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                raise MediaProviderError(
                    "Jellyfin returned an invalid episode entry"
                )

            episode_id = _required(
                item.get("Id"),
                "Jellyfin episode ID",
            )
            title = _required(
                item.get("Name"),
                "Jellyfin episode name",
            )

            season_number = item.get("ParentIndexNumber")
            if (
                isinstance(season_number, bool)
                or not isinstance(season_number, int)
            ):
                season_number = None

            episode_number = item.get("IndexNumber")
            if (
                isinstance(episode_number, bool)
                or not isinstance(episode_number, int)
            ):
                episode_number = None

            series_name = item.get("SeriesName")
            if not isinstance(series_name, str):
                series_name = None
            elif not series_name.strip():
                series_name = None
            else:
                series_name = series_name.strip()

            episodes.append(
                {
                    "id": episode_id,
                    "title": title,
                    "series_name": series_name,
                    "season_number": season_number,
                    "episode_number": episode_number,
                }
            )

        return tuple(episodes)

    def get_playback_info(
        self,
        item_id: str,
        *,
        user_id: str,
        subtitle_stream_index: int | None = None,
    ) -> dict[str, Any]:
        normalized_id = _required(item_id, "item_id")
        normalized_user_id = _required(user_id, "user_id")

        if (
            subtitle_stream_index is not None
            and (
                isinstance(subtitle_stream_index, bool)
                or not isinstance(subtitle_stream_index, int)
                or subtitle_stream_index < -1
            )
        ):
            raise MediaProviderError(
                "subtitle_stream_index must be -1 or a non-negative integer"
            )
        playback_payload: dict[str, Any] = {
            "UserId": normalized_user_id,
            "EnableDirectPlay": True,
            "EnableDirectStream": True,
            "EnableTranscoding": True,
            "AllowVideoStreamCopy": True,
            "AllowAudioStreamCopy": True,
            "DeviceProfile": {
                "Name": "Atlas Theater Browser",
                "MaxStreamingBitrate": 120000000,
                "DirectPlayProfiles": [
                    {
                        "Container": "mp4,m4v",
                        "Type": "Video",
                        "VideoCodec": "h264",
                        "AudioCodec": "aac,mp3,ac3,eac3",
                    }
                ],
                "TranscodingProfiles": [
                    {
                        "Container": "ts",
                        "Type": "Video",
                        "Protocol": "hls",
                        "VideoCodec": "h264",
                        "AudioCodec": "aac",
                        "Context": "Streaming",
                        "EnableMpegtsM2TsMode": True,
                    }
                ],
                "CodecProfiles": [],
                "SubtitleProfiles": [
                    {"Format": "vtt", "Method": "External"},
                    {"Format": "srt", "Method": "External"},
                    {"Format": "subrip", "Method": "External"},
                    {"Format": "vtt", "Method": "Encode"},
                    {"Format": "srt", "Method": "Encode"},
                    {"Format": "subrip", "Method": "Encode"},
                    {"Format": "ass", "Method": "Encode"},
                    {"Format": "ssa", "Method": "Encode"},
                    {"Format": "pgs", "Method": "Encode"},
                    {"Format": "pgssub", "Method": "Encode"},
                    {"Format": "dvdsub", "Method": "Encode"},
                ],
            },
        }

        if subtitle_stream_index is not None:
            playback_payload["SubtitleStreamIndex"] = (
                subtitle_stream_index
            )

            if subtitle_stream_index >= 0:
                playback_payload[
                    "AlwaysBurnInSubtitleWhenTranscoding"
                ] = True

        payload = self._request_json(
            f"/Items/{quote(normalized_id, safe='')}/PlaybackInfo",
            method="POST",
            payload=playback_payload,
        )
        if not isinstance(payload, dict):
            raise MediaProviderError("Jellyfin returned invalid playback info")
        sources = payload.get("MediaSources")
        if not isinstance(sources, list) or not sources:
            raise MediaProviderError("Jellyfin returned no playable media source")
        source = next((entry for entry in sources if isinstance(entry, dict)), None)
        if source is None:
            raise MediaProviderError("Jellyfin returned no playable media source")

        media_source_id = str(source.get("Id") or "").strip()
        if not media_source_id:
            raise MediaProviderError("Jellyfin playback source has no ID")

        runtime = source.get("RunTimeTicks")
        duration_ticks = runtime if isinstance(runtime, int) and runtime >= 0 else None
        supports_direct_play = bool(source.get("SupportsDirectPlay"))
        supports_direct_stream = bool(source.get("SupportsDirectStream"))
        supports_transcoding = bool(source.get("SupportsTranscoding"))

        raw_stream_url = source.get("TranscodingUrl") or source.get("DirectStreamUrl")
        if not isinstance(raw_stream_url, str) or not raw_stream_url.strip():
            raise MediaProviderError("Jellyfin did not return a browser stream URL")
        stream_path = _safe_playback_stream_path(raw_stream_url, normalized_id)

        tracks: list[dict[str, Any]] = []
        streams = source.get("MediaStreams")
        if isinstance(streams, list):
            for stream in streams:
                if not isinstance(stream, dict):
                    continue
                kind = str(stream.get("Type") or "").strip().lower()
                if kind not in {"audio", "subtitle"}:
                    continue
                index = stream.get("Index")
                if not isinstance(index, int):
                    continue
                language = stream.get("Language")
                codec = stream.get("Codec")
                tracks.append(
                    {
                        "index": index,
                        "kind": kind,
                        "label": str(
                            stream.get("DisplayTitle")
                            or stream.get("Title")
                            or ("Audio" if kind == "audio" else "Subtitle")
                        ).strip(),
                        "language": (
                            str(language).strip()
                            if language is not None and str(language).strip()
                            else None
                        ),
                        "codec": (
                            str(codec).strip()
                            if codec is not None and str(codec).strip()
                            else None
                        ),
                        "default": bool(stream.get("IsDefault")),
                        "forced": bool(stream.get("IsForced")),
                    }
                )

        return {
            "media_source_id": media_source_id,
            "duration_ticks": duration_ticks,
            "can_seek": bool(
                supports_direct_play or supports_direct_stream or supports_transcoding
            ),
            "supports_direct_play": supports_direct_play,
            "supports_direct_stream": supports_direct_stream,
            "supports_transcoding": supports_transcoding,
            "tracks": tuple(tracks),
            "stream_path": stream_path,
        }

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
                ).lower() in {
                    "collectionfolder",
                    "folder",
                }
            ):
                name = ancestor.get("Name")

                if isinstance(name, str) and name.strip():
                    return name.strip()

        return None

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> Any:
        if not self.api_key.strip():
            raise MediaProviderError(
                "ATLAS_JELLYFIN_API_KEY is required"
            )

        body = None
        headers = {
            "Accept": "application/json",
            "X-Emby-Token": self.api_key.strip(),
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.base_url.rstrip('/')}{path}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
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
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MediaProviderError("Jellyfin returned invalid JSON") from exc

    def _get_json(self, path: str) -> Any:
        return self._request_json(path)



def _safe_playback_stream_path(raw_url: str, expected_item_id: str) -> str:
    parsed = urlsplit(raw_url.strip())
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise MediaProviderError("Jellyfin returned a non-relative playback URL")
    components = [part for part in parsed.path.split("/") if part]
    if len(components) < 3 or components[0].lower() != "videos":
        raise MediaProviderError("Jellyfin returned an unexpected playback path")
    if components[1].replace("-", "").lower() != expected_item_id.replace("-", "").lower():
        raise MediaProviderError(
            "Jellyfin playback path did not match the playable item"
        )
    forbidden = {"apikey", "api_key", "token", "x-emby-token"}
    safe_query = [
        (name, value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
        if name.lower() not in forbidden
    ]
    return urlunsplit(("", "", parsed.path, urlencode(safe_query), ""))

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
