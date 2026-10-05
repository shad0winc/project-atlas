"""Durable, replay-safe journal publication for submission outbox events only.

No journal is created, repaired, rotated or cleared here. Generic event
publication and external notification retry semantics remain separate.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .events import MediaRequestEventType

DEFAULT_JOURNAL = Path("/mnt/storage/configs/atlas/runtime/events.jsonl")
MAX_RECORD_BYTES = 16_384
MAX_JOURNAL_BYTES = 64 * 1024 * 1024


class SubmissionEventPublicationError(RuntimeError):
    """Publication is unverified; the outbox must remain pending."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class SubmissionEventJournalPublisher:
    """Publish one logical event once; a successful replay also confirms fsync.

    Writers using this contract serialize on the journal inode. Lock contention
    fails immediately and retains pending work. Reads and writes are bounded.
    A complete existing record is authoritative after fsync; payload/identity
    conflicts, duplicate logical records and partial tails require reconciliation.
    """

    def __init__(self, path: str | Path, *, max_journal_bytes: int = MAX_JOURNAL_BYTES):
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("Submission journal path must be absolute")
        if type(max_journal_bytes) is not int or max_journal_bytes < MAX_RECORD_BYTES:
            raise ValueError("Submission journal budget is invalid")
        self.max_journal_bytes = max_journal_bytes

    @classmethod
    def from_environment(cls):
        configured = os.getenv("ATLAS_EVENT_LOG", str(DEFAULT_JOURNAL)).strip()
        if not configured:
            raise ValueError("Submission journal path is required")
        return cls(configured)

    def publish(self, event_name: str, payload: Mapping[str, object]) -> bool:
        """Return True for a new append, False for a verified durable replay."""
        try:
            if not isinstance(payload, Mapping) or not isinstance(event_name, str):
                raise ValueError("Invalid submission event")
            normalized = json.loads(_canonical(dict(payload)))
            metadata = normalized.get("metadata")
            key = metadata.get("submission_event_id") if isinstance(metadata, dict) else None
            match = re.fullmatch(r"([a-f0-9]{32}):(request\.[a-z]+)", key) if isinstance(key, str) else None
            if (match is None or match.group(2) != event_name
                    or event_name not in {item.value for item in MediaRequestEventType}
                    or event_name == "request.created"):
                raise ValueError("Invalid submission event identity")
            fingerprint = _canonical(normalized)
            stable_id = "evt-submission-" + hashlib.sha256(key.encode()).hexdigest()
            record = dict(schema=2, id=stable_id, source="atlas-requests", event=event_name,
                          timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          payload=normalized)
            encoded = _canonical(record) + b"\n"
            if len(encoded) > MAX_RECORD_BYTES:
                raise ValueError("Submission event record exceeds budget")
        except (ValueError, TypeError, OverflowError):
            raise SubmissionEventPublicationError("Submission event contract is invalid") from None

        descriptor = None
        try:
            descriptor = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o007:
                raise SubmissionEventPublicationError("Submission journal permissions/type are invalid")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            size = os.fstat(descriptor).st_size
            if size > self.max_journal_bytes:
                raise SubmissionEventPublicationError("Submission journal scan budget exceeded")
            raw = bytearray()
            while len(raw) < size:
                chunk = os.pread(descriptor, min(65_536, size - len(raw)), len(raw))
                if not chunk:
                    raise SubmissionEventPublicationError("Submission journal changed during read")
                raw.extend(chunk)
            if raw and not raw.endswith(b"\n"):
                raise SubmissionEventPublicationError("Submission journal has an incomplete tail")
            matches = 0
            for line in raw.splitlines():
                if not line.strip():
                    continue
                if len(line) > MAX_RECORD_BYTES:
                    raise SubmissionEventPublicationError("Submission journal record exceeds budget")
                existing = json.loads(line, object_pairs_hook=_unique_object)
                if not isinstance(existing, dict):
                    raise ValueError("Invalid journal record")
                existing_payload = existing.get("payload")
                existing_metadata = existing_payload.get("metadata") if isinstance(existing_payload, dict) else None
                existing_key = existing_metadata.get("submission_event_id") if isinstance(existing_metadata, dict) else None
                if existing_key == key or existing.get("id") == stable_id:
                    if (existing_key != key or existing.get("event") != event_name
                            or existing.get("schema") != 2 or not isinstance(existing.get("id"), str)
                            or existing.get("source") not in {"atlas-api", "atlas-requests"}
                            or _canonical(existing_payload) != fingerprint):
                        raise SubmissionEventPublicationError("Submission event identity conflicts with journal evidence")
                    matches += 1
            if matches > 1:
                raise SubmissionEventPublicationError("Duplicate submission journal evidence requires reconciliation")
            if os.fstat(descriptor).st_size != size:
                raise SubmissionEventPublicationError("Submission journal changed during scan")
            if matches:
                self._confirm_durable_path(descriptor)
                return False
            if size + len(encoded) > self.max_journal_bytes:
                raise SubmissionEventPublicationError("Submission journal append budget exceeded")
            written = os.write(descriptor, encoded)
            if written != len(encoded):
                raise SubmissionEventPublicationError("Submission journal append is incomplete")
            self._confirm_durable_path(descriptor)
            return True
        except SubmissionEventPublicationError:
            raise
        except (OSError, ValueError, TypeError, OverflowError):
            raise SubmissionEventPublicationError("Submission publication remains unverified") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def _confirm_durable_path(self, descriptor):
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
        current = os.stat(self.path, follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise SubmissionEventPublicationError("Submission journal path changed during publication")
