"""Credential-safe security audit events for the Atlas API."""

from __future__ import annotations

import json
import os
import stat
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SECURITY_AUDIT_PATH = Path(
    "/mnt/storage/configs/atlas/runtime/events.jsonl"
)
MAX_AUDIT_RECORD_BYTES = 16_384
_SENSITIVE_KEY_COMPONENTS = (
    "credential",
    "jwt",
    "password",
    "secret",
    "token",
)


class SecurityAuditError(RuntimeError):
    """Raised when a security audit event cannot be safely persisted."""


class SecurityAuditWriter:
    """Append schema-2 security events to an existing Atlas event journal."""

    def __init__(self, path: str | Path) -> None:
        candidate = Path(path)
        if not str(candidate).strip():
            raise ValueError("Security audit path cannot be empty.")
        self._path = candidate

    @classmethod
    def from_environment(cls) -> "SecurityAuditWriter":
        """Build the writer from the API's explicitly mounted journal path."""

        configured = os.getenv(
            "ATLAS_SECURITY_AUDIT_PATH",
            str(DEFAULT_SECURITY_AUDIT_PATH),
        ).strip()
        if not configured:
            raise ValueError("ATLAS_SECURITY_AUDIT_PATH cannot be empty.")
        return cls(configured)

    @property
    def path(self) -> Path:
        """Return the configured event journal path."""

        return self._path

    def publish(
        self,
        event_name: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        """Append one credential-free security event with a single write."""

        event = event_name.strip()
        if not event.startswith("security.") or len(event) <= len("security."):
            raise ValueError("Security audit event names must start with 'security.'.")

        normalized_payload = dict(payload or {})
        self._reject_sensitive_keys(normalized_payload)

        record = {
            "schema": 2,
            "id": f"evt-{uuid.uuid4()}",
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            ),
            "source": "atlas-api",
            "event": event,
            "payload": normalized_payload,
        }

        try:
            encoded = (
                json.dumps(record, separators=(",", ":"), sort_keys=True)
                + "\n"
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise SecurityAuditError(
                "Security audit payload is not JSON serializable."
            ) from exc

        if len(encoded) > MAX_AUDIT_RECORD_BYTES:
            raise SecurityAuditError("Security audit event is too large.")

        flags = os.O_WRONLY | os.O_APPEND
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        try:
            descriptor = os.open(self._path, flags)
        except OSError as exc:
            raise SecurityAuditError(
                "Security audit journal is unavailable."
            ) from exc

        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise SecurityAuditError(
                    "Security audit journal must be a regular file."
                )
            if metadata.st_mode & 0o007:
                raise SecurityAuditError(
                    "Security audit journal must not grant other permissions."
                )

            written = os.write(descriptor, encoded)
            if written != len(encoded):
                raise SecurityAuditError(
                    "Security audit journal append was incomplete."
                )
        except OSError as exc:
            raise SecurityAuditError(
                "Security audit journal append failed."
            ) from exc
        finally:
            os.close(descriptor)

    @classmethod
    def _reject_sensitive_keys(cls, value: object) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized_key = str(key).strip().lower().replace("-", "_")
                if any(
                    component in normalized_key
                    for component in _SENSITIVE_KEY_COMPONENTS
                ):
                    raise ValueError(
                        "Security audit payload contains a sensitive key."
                    )
                cls._reject_sensitive_keys(child)
            return

        if isinstance(value, (list, tuple)):
            for child in value:
                cls._reject_sensitive_keys(child)
