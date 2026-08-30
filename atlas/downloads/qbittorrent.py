"""Read-only qBittorrent collector for bounded Downloads runtime data."""

from __future__ import annotations

import json
from http.cookiejar import CookieJar
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from .models import DownloadItem, DownloadsError, DownloadsSnapshot, DownloadState


MAX_DOWNLOAD_ITEMS = 100

_STATE_MAP: dict[str, DownloadState] = {
    "downloading": DownloadState.DOWNLOADING,
    "forcedDL": DownloadState.DOWNLOADING,
    "metaDL": DownloadState.DOWNLOADING,
    "queuedDL": DownloadState.QUEUED,
    "queuedUP": DownloadState.COMPLETED,
    "stalledDL": DownloadState.STALLED,
    "stalledUP": DownloadState.SEEDING,
    "pausedDL": DownloadState.PAUSED,
    "pausedUP": DownloadState.COMPLETED,
    "stoppedDL": DownloadState.PAUSED,
    "stoppedUP": DownloadState.COMPLETED,
    "checkingDL": DownloadState.CHECKING,
    "checkingUP": DownloadState.CHECKING,
    "checkingResumeData": DownloadState.CHECKING,
    "moving": DownloadState.MOVING,
    "uploading": DownloadState.SEEDING,
    "forcedUP": DownloadState.SEEDING,
    "error": DownloadState.ERROR,
    "missingFiles": DownloadState.ERROR,
}

_STATE_PRIORITY: dict[DownloadState, int] = {
    DownloadState.DOWNLOADING: 0,
    DownloadState.STALLED: 1,
    DownloadState.CHECKING: 2,
    DownloadState.MOVING: 3,
    DownloadState.QUEUED: 4,
    DownloadState.PAUSED: 5,
    DownloadState.ERROR: 6,
    DownloadState.UNKNOWN: 7,
    DownloadState.SEEDING: 8,
    DownloadState.COMPLETED: 9,
}


def _download_sort_key(item: DownloadItem) -> tuple[int, str, str]:
    return (
        _STATE_PRIORITY[item.state],
        item.name.casefold(),
        (item.category or "").casefold(),
    )


class QBittorrentReadOnlyClient:
    """Authenticate to qBittorrent and read only normalized activity."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: float = 5.0,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("qBittorrent base_url must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("qBittorrent base_url must not contain credentials")
        if not username:
            raise ValueError("qBittorrent username cannot be empty")
        if not password:
            raise ValueError("qBittorrent password cannot be empty")
        if timeout <= 0:
            raise ValueError("qBittorrent timeout must be positive")

        self._base_url = base_url.rstrip("/") + "/"
        self._username = username
        self._password = password
        self._timeout = timeout
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def collect(self) -> DownloadsSnapshot:
        self._login()
        torrents = self._json_get("api/v2/torrents/info")
        transfer = self._json_get("api/v2/transfer/info")

        if not isinstance(torrents, Sequence) or isinstance(
            torrents, (str, bytes, bytearray)
        ):
            raise DownloadsError("qBittorrent torrents response must be a list")
        if not isinstance(transfer, Mapping):
            raise DownloadsError("qBittorrent transfer response must be an object")

        normalized_items = (self._normalize_torrent(entry) for entry in torrents)
        items = tuple(
            sorted(normalized_items, key=_download_sort_key)[:MAX_DOWNLOAD_ITEMS]
        )
        return DownloadsSnapshot.build(
            items,
            total_download_rate=_bounded_int(transfer.get("dl_info_speed")),
            total_upload_rate=_bounded_int(transfer.get("up_info_speed")),
        )

    def _login(self) -> None:
        body = urlencode(
            {"username": self._username, "password": self._password}
        ).encode("utf-8")
        request = Request(
            urljoin(self._base_url, "api/v2/auth/login"),
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self._base_url,
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                payload = response.read(64).decode("utf-8", errors="replace").strip()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise DownloadsError("qBittorrent authentication failed") from exc

        if payload != "Ok.":
            raise DownloadsError("qBittorrent authentication failed")

    def _json_get(self, path: str) -> Any:
        request = Request(
            urljoin(self._base_url, path),
            method="GET",
            headers={"Accept": "application/json", "Referer": self._base_url},
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise DownloadsError("qBittorrent read failed") from exc

        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise DownloadsError("qBittorrent returned invalid JSON") from exc

    @staticmethod
    def _normalize_torrent(value: Any) -> DownloadItem:
        if not isinstance(value, Mapping):
            raise DownloadsError("qBittorrent torrent entry must be an object")

        name = str(value.get("name") or "").strip() or "Unnamed download"
        name = name[:300]
        category_value = value.get("category")
        category = str(category_value).strip()[:100] if category_value else None
        state = _STATE_MAP.get(str(value.get("state") or ""), DownloadState.UNKNOWN)
        progress = _bounded_float(value.get("progress"), minimum=0.0, maximum=1.0)
        eta_raw = _bounded_int(value.get("eta"))
        eta_seconds = None if eta_raw <= 0 or eta_raw >= 8_640_000 else eta_raw

        return DownloadItem(
            name=name,
            category=category,
            state=state,
            progress=progress,
            total_bytes=_bounded_int(value.get("size")),
            downloaded_bytes=_bounded_int(value.get("downloaded")),
            download_rate=_bounded_int(value.get("dlspeed")),
            upload_rate=_bounded_int(value.get("upspeed")),
            eta_seconds=eta_seconds,
        )


def _bounded_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _bounded_float(value: Any, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        return minimum
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return minimum
    return min(maximum, max(minimum, normalized))
