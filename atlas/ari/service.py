"""Atlas Retention Intelligence service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from atlas.ari.models import ARIReport


DEFAULT_ARI_DIRECTORY: Final = Path(
    "/mnt/storage/configs/atlas/ari",
)


class ARIService:
    """Loads and discovers ARI snapshot reports."""

    def __init__(
        self,
        snapshot_directory: Path | str = DEFAULT_ARI_DIRECTORY,
    ) -> None:
        self._snapshot_directory = Path(snapshot_directory)

    @property
    def snapshot_directory(self) -> Path:
        """Return the configured snapshot directory."""

        return self._snapshot_directory

    def latest_path(self) -> Path:
        """Return the latest snapshot path."""

        return self.snapshot_directory / "latest.json"

    def load(
        self,
        path: Path | str,
    ) -> ARIReport:
        """Load an ARI report from disk."""

        snapshot = Path(path)

        with snapshot.open(
            "r",
            encoding="utf-8",
        ) as handle:
            payload = json.load(handle)

        return ARIReport.from_dict(payload)

    def latest(self) -> ARIReport:
        """Load the latest snapshot."""

        return self.load(
            self.latest_path(),
        )

    def list_snapshots(
        self,
    ) -> list[Path]:
        """Return all JSON snapshots."""

        return sorted(
            self.snapshot_directory.glob("*.json"),
        )
