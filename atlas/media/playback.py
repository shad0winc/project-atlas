"""Provider-neutral playback actions for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import quote, urlsplit, urlunsplit


class PlaybackActionKind(str, Enum):
    WATCH_NOW = "watch_now"
    WATCH_LIVE = "watch_live"
    WATCH_RECORDING = "watch_recording"


class PlaybackSourceType(str, Enum):
    LIBRARY = "library"
    LIVE = "live"
    RECORDING = "recording"


@dataclass(frozen=True, slots=True)
class PlaybackAction:
    """A safe user-facing playback capability."""

    available: bool
    action: PlaybackActionKind
    label: str
    backend: str
    source_type: PlaybackSourceType
    provider: str
    target_id: str
    href: str | None

    @classmethod
    def jellyfin_library(
        cls,
        item_id: str,
        *,
        public_base_url: str,
    ) -> "PlaybackAction":
        normalized_item_id = item_id.strip()
        if not normalized_item_id:
            raise ValueError("item_id must not be empty")

        normalized_base = _public_https_base_url(public_base_url)

        return cls(
            available=True,
            action=PlaybackActionKind.WATCH_NOW,
            label="Watch Now",
            backend="jellyfin",
            source_type=PlaybackSourceType.LIBRARY,
            provider="jellyfin",
            target_id=normalized_item_id,
            href=(
                f"{normalized_base}/web/index.html#!/details?id="
                + quote(normalized_item_id, safe="")
            ),
        )


def _public_https_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
        raise ValueError("public_base_url must not be empty")

    parsed = urlsplit(normalized)

    if parsed.scheme != "https":
        raise ValueError("public_base_url must use https")

    if not parsed.netloc:
        raise ValueError("public_base_url must include a host")

    if parsed.query or parsed.fragment:
        raise ValueError(
            "public_base_url must not include query or fragment components"
        )

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )
