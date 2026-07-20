"""Append-only cleanup audit persistence for Project Atlas."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from atlas.cleanup.execution_events import CleanupExecutionEvent


class CleanupAuditError(RuntimeError):
    """Raised when cleanup audit persistence fails."""


class CleanupAuditWriter(ABC):
    """Abstract cleanup execution-event writer."""

    @abstractmethod
    def write(
        self,
        event: CleanupExecutionEvent,
    ) -> None:
        """Persist one cleanup execution event."""
        raise NotImplementedError


class JsonlCleanupAuditWriter(CleanupAuditWriter):
    """Append cleanup execution events to a UTF-8 JSONL file."""

    def __init__(
        self,
        path: Path | str,
        *,
        durable: bool = True,
    ) -> None:
        self._path = _normalize_path(path)

        if not isinstance(durable, bool):
            raise CleanupAuditError(
                "durable must be a boolean"
            )

        self._durable = durable

    @property
    def path(self) -> Path:
        """Return the configured audit-log path."""

        return self._path

    @property
    def durable(self) -> bool:
        """Return whether writes are synchronized to storage."""

        return self._durable

    def write(
        self,
        event: CleanupExecutionEvent,
    ) -> None:
        """Append one normalized event as one JSON line."""

        if not isinstance(event, CleanupExecutionEvent):
            raise CleanupAuditError(
                "event must be a CleanupExecutionEvent"
            )

        try:
            self._path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            serialized = json.dumps(
                event.to_dict(),
                separators=(",", ":"),
                sort_keys=True,
            )

            with self._path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(serialized)
                handle.write("\n")
                handle.flush()

                if self._durable:
                    os.fsync(handle.fileno())

        except CleanupAuditError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise CleanupAuditError(
                f"failed to append cleanup audit event: {exc}"
            ) from exc


def _normalize_path(value: Path | str) -> Path:
    """Normalize and validate an audit-log path."""

    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            raise CleanupAuditError(
                "path must not be empty"
            )

        path = Path(normalized)
    else:
        raise CleanupAuditError(
            "path must be a pathlib.Path or string"
        )

    if not str(path).strip():
        raise CleanupAuditError(
            "path must not be empty"
        )

    if path.exists() and path.is_dir():
        raise CleanupAuditError(
            "path must reference a file"
        )

    return path
