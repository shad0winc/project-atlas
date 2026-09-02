"""Read-only Downloads service backed only by the bounded runtime snapshot."""

from __future__ import annotations

from pathlib import Path

from .models import DownloadsSnapshot
from .runtime import DEFAULT_MAX_AGE_SECONDS, read_snapshot


class DownloadsService:
    """Serve current bounded download activity from one runtime snapshot."""

    def __init__(
        self,
        snapshot_path: str | Path,
        *,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    ) -> None:
        self._snapshot_path = Path(snapshot_path).expanduser()
        self._max_age_seconds = max_age_seconds

    def current(self) -> DownloadsSnapshot:
        return read_snapshot(
            self._snapshot_path,
            max_age_seconds=self._max_age_seconds,
        )
