"""Bounded read-only Downloads runtime domain."""

from .models import (
    SCHEMA_VERSION,
    DownloadItem,
    DownloadsError,
    DownloadsSnapshot,
    DownloadState,
    DownloadSummary,
)
from .qbittorrent import QBittorrentReadOnlyClient
from .runtime import DEFAULT_MAX_AGE_SECONDS, publish_snapshot, read_snapshot
from .service import DownloadsService

__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_MAX_AGE_SECONDS",
    "DownloadItem",
    "DownloadsError",
    "DownloadsService",
    "DownloadsSnapshot",
    "DownloadState",
    "DownloadSummary",
    "QBittorrentReadOnlyClient",
    "publish_snapshot",
    "read_snapshot",
]
