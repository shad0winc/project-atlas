"""Bounded authenticated reads of exact Jellyfin item artwork."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from atlas.media.jellyfin import default_jellyfin_provider
from atlas.media.jellyfin_auth import build_jellyfin_authorization

MAX_ARTWORK_BYTES = 256 * 1024
ARTWORK_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"})

class MediaArtworkError(RuntimeError):
    """Artwork could not be read safely."""

class MediaArtworkNotFound(MediaArtworkError):
    """The exact item has no primary image."""

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args):
        return None

@dataclass(frozen=True)
class MediaArtwork:
    media_type: str
    data_base64: str

@dataclass(frozen=True)
class MediaArtworkService:
    base_url: str
    api_key: str = field(repr=False)

    def read_primary(self, item_id: str) -> MediaArtwork:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item_id):
            raise MediaArtworkNotFound("Artwork not found")
        url = urlsplit(self.base_url)
        if (url.scheme not in {"http", "https"} or not url.hostname
                or url.username or url.password or url.query or url.fragment
                or not self.api_key.strip()):
            raise MediaArtworkError("Artwork provider is unavailable")
        request = Request(
            self.base_url.rstrip("/") + f"/Items/{item_id}/Images/Primary?maxWidth=240&quality=80",
            headers={"Authorization": build_jellyfin_authorization(token=self.api_key),
                     "Accept": ", ".join(sorted(ARTWORK_TYPES))},
            method="GET",
        )
        try:
            # A redirect must never forward the provider credential elsewhere.
            opener = build_opener(ProxyHandler({}), _NoRedirect())
            with opener.open(request, timeout=5) as response:
                media_type = response.headers.get_content_type().lower()
                if media_type not in ARTWORK_TYPES:
                    raise MediaArtworkError("Artwork format is unavailable")
                raw = response.read(MAX_ARTWORK_BYTES + 1)
            if not raw or len(raw) > MAX_ARTWORK_BYTES:
                raise MediaArtworkError("Artwork size is unavailable")
        except HTTPError as error:
            if error.code == 404:
                raise MediaArtworkNotFound("Artwork not found") from None
            raise MediaArtworkError("Artwork provider is unavailable") from None
        except (URLError, TimeoutError, OSError):
            raise MediaArtworkError("Artwork provider is unavailable") from None
        return MediaArtwork(media_type, base64.b64encode(raw).decode("ascii"))

def build_default_media_artwork_service() -> MediaArtworkService:
    provider = default_jellyfin_provider()
    return MediaArtworkService(provider.base_url, provider.api_key)
