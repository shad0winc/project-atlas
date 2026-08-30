"""Bounded read-only Downloads runtime domain."""

from .job_ids import is_opaque_job_id, opaque_job_id
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
    "is_opaque_job_id",
    "opaque_job_id",
    "publish_snapshot",
    "read_snapshot",
]
