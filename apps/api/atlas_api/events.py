"""API-native publishing into the durable Atlas runtime event journal."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
from typing import Any
import uuid


DEFAULT_EVENT_JOURNAL_PATH = Path(
    "/mnt/storage/configs/atlas/runtime/events.jsonl"
)

MAX_EVENT_RECORD_BYTES = 16_384


class RuntimeEventJournalError(RuntimeError):
    """Raised when an API runtime event cannot be safely appended."""


class RuntimeEventJournalPublisher:
    """Append schema-2 events without depending on the Atlas shell CLI."""

    def __init__(
        self,
        path: str | Path,
        *,
        source: str = "atlas-api",
    ) -> None:
        candidate = Path(path)

        if not str(candidate).strip():
            raise ValueError(
                "Runtime event journal path cannot be empty."
            )

        normalized_source = source.strip()

        if not normalized_source:
            raise ValueError(
                "Runtime event source cannot be empty."
            )

        self._path = candidate
        self._source = normalized_source

    @classmethod
    def from_environment(
        cls,
    ) -> "RuntimeEventJournalPublisher":
        """Build from the API's explicitly mounted runtime journal."""

        configured = os.getenv(
            "ATLAS_EVENT_LOG",
            str(DEFAULT_EVENT_JOURNAL_PATH),
        ).strip()

        if not configured:
            raise ValueError(
                "ATLAS_EVENT_LOG cannot be empty."
            )

        return cls(
            configured
        )

    @property
    def path(self) -> Path:
        """Return the configured runtime journal path."""

        return self._path

    @property
    def source(self) -> str:
        """Return the source written into schema-2 events."""

        return self._source

    def publish(
        self,
        event_name: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        """Append one schema-2 event using one O_APPEND write."""

        if not isinstance(
            event_name,
            str,
        ):
            raise ValueError(
                "Runtime event name must be text."
            )

        event = event_name.strip()

        if not event:
            raise ValueError(
                "Runtime event name cannot be empty."
            )

        if (
            payload is not None
            and not isinstance(
                payload,
                Mapping,
            )
        ):
            raise ValueError(
                "Runtime event payload must be a mapping or null."
            )

        normalized_payload = dict(
            payload or {}
        )

        record = {
            "schema": 2,
            "id": f"evt-{uuid.uuid4()}",
            "timestamp": (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
            ),
            "source": self._source,
            "event": event,
            "payload": normalized_payload,
        }

        try:
            encoded = (
                json.dumps(
                    record,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        except (
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeEventJournalError(
                "Runtime event payload is not JSON serializable."
            ) from error

        if len(encoded) > MAX_EVENT_RECORD_BYTES:
            raise RuntimeEventJournalError(
                "Runtime event record is too large."
            )

        flags = (
            os.O_WRONLY
            | os.O_APPEND
        )

        if hasattr(
            os,
            "O_CLOEXEC",
        ):
            flags |= os.O_CLOEXEC

        if hasattr(
            os,
            "O_NOFOLLOW",
        ):
            flags |= os.O_NOFOLLOW

        try:
            descriptor = os.open(
                self._path,
                flags,
            )
        except OSError as error:
            raise RuntimeEventJournalError(
                "Runtime event journal is unavailable."
            ) from error

        try:
            metadata = os.fstat(
                descriptor
            )

            if not stat.S_ISREG(
                metadata.st_mode
            ):
                raise RuntimeEventJournalError(
                    "Runtime event journal must be a regular file."
                )

            if metadata.st_mode & 0o007:
                raise RuntimeEventJournalError(
                    "Runtime event journal must not grant other permissions."
                )

            written = os.write(
                descriptor,
                encoded,
            )

            if written != len(encoded):
                raise RuntimeEventJournalError(
                    "Runtime event journal append was incomplete."
                )
        except OSError as error:
            raise RuntimeEventJournalError(
                "Runtime event journal append failed."
            ) from error
        finally:
            os.close(
                descriptor
            )
