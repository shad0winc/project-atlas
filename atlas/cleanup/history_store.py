"""Cleanup execution-history persistence for Project Atlas."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Any

from atlas.cleanup.execution_events import (
    CleanupExecutionEvent,
)
from atlas.cleanup.history_models import (
    CleanupHistoryEntry,
    CleanupHistoryError,
)
from atlas.cleanup.models import CleanupError


class CleanupHistoryStore(ABC):
    """Abstract cleanup execution-history reader."""

    @abstractmethod
    def list_entries(
        self,
    ) -> tuple[CleanupHistoryEntry, ...]:
        """Return all persisted cleanup history entries."""
        raise NotImplementedError


class JsonlCleanupHistoryStore(CleanupHistoryStore):
    """Read cleanup execution history from a JSONL audit log."""

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = _normalize_path(path)

    @property
    def path(self) -> Path:
        """Return the configured history file path."""

        return self._path

    def list_entries(
        self,
    ) -> tuple[CleanupHistoryEntry, ...]:
        """Read and reconstruct all persisted executions."""

        if not self._path.exists():
            return ()

        try:
            lines = self._path.read_text(
                encoding="utf-8",
            ).splitlines()
        except OSError as exc:
            raise CleanupHistoryError(
                f"failed to read cleanup history: {exc}"
            ) from exc

        grouped_events: dict[
            str,
            list[CleanupExecutionEvent],
        ] = defaultdict(list)

        for line_number, line in enumerate(
            lines,
            start=1,
        ):
            if not line.strip():
                continue

            event = self._parse_event(
                line,
                line_number=line_number,
            )

            grouped_events[event.execution_id].append(event)

        entries: list[CleanupHistoryEntry] = []

        for execution_id, events in grouped_events.items():
            first_event = events[0]

            try:
                entry = CleanupHistoryEntry(
                    execution_id=execution_id,
                    provider=first_event.provider,
                    mode=first_event.mode,
                    events=tuple(events),
                )
            except CleanupHistoryError as exc:
                raise CleanupHistoryError(
                    "invalid cleanup history execution "
                    f"{execution_id}: {exc}"
                ) from exc

            entries.append(entry)

        entries.sort(
            key=lambda entry: (
                entry.started_at,
                entry.execution_id,
            ),
            reverse=True,
        )

        return tuple(entries)

    @staticmethod
    def _parse_event(
        line: str,
        *,
        line_number: int,
    ) -> CleanupExecutionEvent:
        """Parse and validate one JSONL event."""

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CleanupHistoryError(
                "invalid cleanup history JSON "
                f"at line {line_number}: {exc.msg}"
            ) from exc

        if not isinstance(payload, dict):
            raise CleanupHistoryError(
                "invalid cleanup history event "
                f"at line {line_number}: "
                "JSON value must be an object"
            )

        try:
            return _event_from_dict(payload)
        except (
            CleanupError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise CleanupHistoryError(
                "invalid cleanup history event "
                f"at line {line_number}: {exc}"
            ) from exc


def _event_from_dict(
    payload: dict[str, Any],
) -> CleanupExecutionEvent:
    """Reconstruct one execution event from serialized data."""

    required_fields = {
        "execution_id",
        "provider",
        "item_id",
        "action",
        "mode",
        "status",
        "message",
        "modified",
        "occurred_at",
    }

    missing_fields = sorted(
        required_fields.difference(payload)
    )

    if missing_fields:
        raise ValueError(
            "missing required fields: "
            + ", ".join(missing_fields)
        )

    unexpected_fields = sorted(
        set(payload).difference(required_fields)
    )

    if unexpected_fields:
        raise ValueError(
            "unexpected fields: "
            + ", ".join(unexpected_fields)
        )

    occurred_at = payload["occurred_at"]

    if not isinstance(occurred_at, str):
        raise ValueError(
            "occurred_at must be an ISO-8601 string"
        )

    from datetime import datetime

    try:
        parsed_timestamp = datetime.fromisoformat(
            occurred_at.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as exc:
        raise ValueError(
            "occurred_at must be an ISO-8601 timestamp"
        ) from exc

    return CleanupExecutionEvent(
        execution_id=payload["execution_id"],
        provider=payload["provider"],
        item_id=payload["item_id"],
        action=payload["action"],
        mode=payload["mode"],
        status=payload["status"],
        message=payload["message"],
        modified=payload["modified"],
        occurred_at=parsed_timestamp,
    )


def _normalize_path(
    value: Path | str,
) -> Path:
    """Normalize and validate a history path."""

    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            raise CleanupHistoryError(
                "path must not be empty"
            )

        path = Path(normalized)
    else:
        raise CleanupHistoryError(
            "path must be a pathlib.Path or string"
        )

    if not str(path).strip():
        raise CleanupHistoryError(
            "path must not be empty"
        )

    if path.exists() and path.is_dir():
        raise CleanupHistoryError(
            "path must reference a file"
        )

    return path
