"""Atlas Retention Intelligence service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from atlas.ari.models import (
    ARIError,
    ARIReport,
)


DEFAULT_ARI_DIRECTORY: Final = Path(
    "/mnt/storage/configs/atlas/ari",
)


class ARIServiceError(RuntimeError):
    """Raised when an ARI snapshot cannot be loaded."""


class ARIService:
    """Loads and discovers ARI snapshot reports."""

    def __init__(
        self,
        snapshot_directory: Path | str = DEFAULT_ARI_DIRECTORY,
    ) -> None:
        self._snapshot_directory = Path(
            snapshot_directory,
        )

    @property
    def snapshot_directory(self) -> Path:
        """Return the configured ARI directory."""

        return self._snapshot_directory

    @property
    def history_directory(self) -> Path:
        """Return the historical snapshot directory."""

        return self.snapshot_directory / "snapshots"

    def latest_path(self) -> Path:
        """Return the configured latest snapshot path."""

        return self.snapshot_directory / "latest.json"

    def load(
        self,
        path: Path | str,
    ) -> ARIReport:
        """Load and validate an ARI report from disk."""

        snapshot = Path(path)

        try:
            with snapshot.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except FileNotFoundError as error:
            raise ARIServiceError(
                f"ARI snapshot not found: {snapshot}",
            ) from error
        except PermissionError as error:
            raise ARIServiceError(
                f"ARI snapshot is not readable: {snapshot}",
            ) from error
        except json.JSONDecodeError as error:
            raise ARIServiceError(
                f"ARI snapshot contains invalid JSON: {snapshot}",
            ) from error
        except OSError as error:
            raise ARIServiceError(
                f"unable to read ARI snapshot: {snapshot}",
            ) from error

        try:
            return ARIReport.from_dict(payload)
        except ARIError as error:
            raise ARIServiceError(
                f"ARI snapshot is invalid: {snapshot}: {error}",
            ) from error

    def latest(self) -> ARIReport:
        """Load the latest ARI snapshot."""

        return self.load(
            self.latest_path(),
        )

    def list_snapshots(
        self,
    ) -> list[Path]:
        """Return the latest and historical ARI report paths."""

        snapshots: list[Path] = []

        latest = self.latest_path()

        if latest.is_file():
            snapshots.append(latest)

        history = self.history_directory

        if not history.exists():
            return snapshots

        if not history.is_dir():
            raise ARIServiceError(
                "ARI snapshot history path is not a directory: "
                f"{history}",
            )

        try:
            snapshots.extend(
                sorted(
                    history.glob("*.json"),
                ),
            )
        except OSError as error:
            raise ARIServiceError(
                "unable to list ARI snapshot history: "
                f"{history}",
            ) from error

        return snapshots
