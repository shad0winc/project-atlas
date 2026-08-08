"""Immutable file repository for Atlas Operations reports."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Final, Protocol

from atlas.atomic import write_json_atomic

from .models import (
    OperationsModelError,
    OperationsReport,
)


DEFAULT_OPERATIONS_DIRECTORY: Final = Path(
    "/mnt/storage/configs/atlas/operations",
)


class OperationsRepositoryError(RuntimeError):
    """Raised when Operations persistence cannot complete safely."""


class OperationsReportNotFoundError(OperationsRepositoryError):
    """Raised when a requested Operations report does not exist."""


class OperationsRepository(Protocol):
    """Persistence contract for immutable Operations reports."""

    def save(self, report: OperationsReport) -> Path:
        """Persist one immutable report and return its snapshot path."""

        ...

    def latest(self) -> OperationsReport:
        """Return the latest persisted Operations report."""

        ...

    def history(
        self,
        limit: int = 25,
    ) -> tuple[OperationsReport, ...]:
        """Return persisted reports in newest-first order."""

        ...


class FileOperationsRepository:
    """Persist immutable Operations reports as atomic JSON files."""

    def __init__(
        self,
        root: str | Path = DEFAULT_OPERATIONS_DIRECTORY,
    ) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        """Return the configured repository root."""

        return self._root

    @property
    def history_directory(self) -> Path:
        """Return the immutable report-history directory."""

        return self.root / "history"

    @property
    def latest_path(self) -> Path:
        """Return the latest-report path."""

        return self.root / "latest.json"

    def save(self, report: OperationsReport) -> Path:
        """Persist one immutable snapshot and update latest.json."""

        if not isinstance(report, OperationsReport):
            raise OperationsRepositoryError(
                "report must be an OperationsReport",
            )

        snapshot_path = self._snapshot_path(report)

        if snapshot_path.exists():
            raise OperationsRepositoryError(
                "Operations report snapshot already exists: "
                f"{snapshot_path}",
            )

        payload = report.to_dict()

        try:
            write_json_atomic(
                snapshot_path,
                payload,
            )
        except OSError as error:
            raise OperationsRepositoryError(
                "unable to persist Operations report snapshot: "
                f"{snapshot_path}",
            ) from error

        try:
            write_json_atomic(
                self.latest_path,
                payload,
            )
        except OSError as error:
            raise OperationsRepositoryError(
                "snapshot persisted but latest report could not be "
                f"updated: {self.latest_path}",
            ) from error

        return snapshot_path

    def latest(self) -> OperationsReport:
        """Load and validate the latest persisted report."""

        if not self.latest_path.exists():
            raise OperationsReportNotFoundError(
                "latest Operations report was not found: "
                f"{self.latest_path}",
            )

        return self._load(
            self.latest_path,
        )

    def history(
        self,
        limit: int = 25,
    ) -> tuple[OperationsReport, ...]:
        """Load report history in deterministic newest-first order."""

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
        ):
            raise OperationsRepositoryError(
                "limit must be a positive integer",
            )

        if not self.history_directory.exists():
            return ()

        if not self.history_directory.is_dir():
            raise OperationsRepositoryError(
                "Operations history path is not a directory: "
                f"{self.history_directory}",
            )

        try:
            paths = tuple(
                sorted(
                    self.history_directory.glob("*.json"),
                    reverse=True,
                )[:limit]
            )
        except OSError as error:
            raise OperationsRepositoryError(
                "unable to list Operations report history: "
                f"{self.history_directory}",
            ) from error

        return tuple(
            self._load(path)
            for path in paths
        )

    def _snapshot_path(
        self,
        report: OperationsReport,
    ) -> Path:
        filename = (
            report.generated_at.replace(":", "-")
            + ".json"
        )

        return self.history_directory / filename

    def _load(
        self,
        path: Path,
    ) -> OperationsReport:
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except FileNotFoundError as error:
            raise OperationsReportNotFoundError(
                f"Operations report was not found: {path}",
            ) from error
        except PermissionError as error:
            raise OperationsRepositoryError(
                f"Operations report is not readable: {path}",
            ) from error
        except json.JSONDecodeError as error:
            raise OperationsRepositoryError(
                "Operations report contains invalid JSON: "
                f"{path}",
            ) from error
        except OSError as error:
            raise OperationsRepositoryError(
                f"unable to read Operations report: {path}",
            ) from error

        if not isinstance(payload, Mapping):
            raise OperationsRepositoryError(
                "Operations report must contain an object: "
                f"{path}",
            )

        try:
            return OperationsReport.from_dict(
                payload,
            )
        except OperationsModelError as error:
            raise OperationsRepositoryError(
                f"Operations report is invalid: {path}: {error}",
            ) from error
