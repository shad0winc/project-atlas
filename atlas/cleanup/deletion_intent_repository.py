"""Durable cleanup deletion-intent repository."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
from typing import Any
from atlas.cleanup.deletion_intents import (
    CleanupDeletionIntent,
)
from atlas.cleanup.models import CleanupError


SCHEMA_VERSION = 1


class CleanupDeletionIntentRepositoryError(ValueError):
    """Raised when deletion-intent persistence cannot be completed safely."""


class CleanupDeletionIntentConflictError(
    CleanupDeletionIntentRepositoryError
):
    """Raised when a provider item already has a pending deletion intent."""


class JsonCleanupDeletionIntentRepository:
    """Persist pending cleanup deletions in one atomic JSON registry."""

    def __init__(
        self,
        root: str | Path,
    ) -> None:
        self.root = Path(root)
        self.registry_file = (
            self.root / "deletion-intents.json"
        )
        self.lock_file = (
            self.root / "deletion-intents.lock"
        )

    def initialize(self) -> None:
        """Create the repository layout if needed."""

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        if self.registry_file.exists():
            return

        with self._exclusive_lock():
            if not self.registry_file.exists():
                self._write_document(
                    self._empty_document()
                )

    def save(
        self,
        intent: CleanupDeletionIntent,
    ) -> CleanupDeletionIntent:
        """Persist a pending intent and reject replay conflicts."""

        if not isinstance(
            intent,
            CleanupDeletionIntent,
        ):
            raise CleanupDeletionIntentRepositoryError(
                "intent must be a CleanupDeletionIntent"
            )

        self.initialize()

        with self._exclusive_lock():
            document = self._load_document_initialized()
            intents = list(document["intents"])

            conflict = self._find_in_records(
                intents,
                intent.provider,
                intent.item_id,
            )

            if conflict is not None:
                raise CleanupDeletionIntentConflictError(
                    "cleanup deletion intent already exists: "
                    f"{intent.provider}:{intent.item_id}"
                )

            intents.append(intent.to_dict())

            self._write_document(
                self._document(intents)
            )

        return intent

    def get(
        self,
        provider: object,
        item_id: object,
    ) -> CleanupDeletionIntent | None:
        """Return one pending intent by provider media identity."""

        normalized_provider = _required_text(
            provider,
            "provider",
            lowercase=True,
        )
        normalized_item_id = _required_text(
            item_id,
            "item_id",
        )

        document = self._load_document()

        return self._find_in_records(
            document["intents"],
            normalized_provider,
            normalized_item_id,
        )

    def list(
        self,
    ) -> tuple[CleanupDeletionIntent, ...]:
        """Return all pending intents in deterministic order."""

        document = self._load_document()

        intents = tuple(
            self._intent_from_payload(payload)
            for payload in document["intents"]
        )

        return tuple(
            sorted(
                intents,
                key=lambda intent: (
                    intent.created_at,
                    intent.provider,
                    intent.item_id,
                ),
            )
        )

    def remove(
        self,
        provider: object,
        item_id: object,
    ) -> CleanupDeletionIntent:
        """Remove one reconciled or finalized pending intent."""

        normalized_provider = _required_text(
            provider,
            "provider",
            lowercase=True,
        )
        normalized_item_id = _required_text(
            item_id,
            "item_id",
        )

        self.initialize()

        with self._exclusive_lock():
            document = self._load_document_initialized()
            records = list(document["intents"])

            match = self._find_in_records(
                records,
                normalized_provider,
                normalized_item_id,
            )

            if match is None:
                raise CleanupDeletionIntentRepositoryError(
                    "cleanup deletion intent not found: "
                    f"{normalized_provider}:{normalized_item_id}"
                )

            remaining = [
                record
                for record in records
                if not self._record_matches(
                    record,
                    normalized_provider,
                    normalized_item_id,
                )
            ]

            self._write_document(
                self._document(remaining)
            )

        return match

    def _load_document(
        self,
    ) -> dict[str, Any]:
        self.initialize()
        return self._load_document_initialized()

    def _load_document_initialized(
        self,
    ) -> dict[str, Any]:
        try:
            raw = self.registry_file.read_text(
                encoding="utf-8",
            )
        except OSError as exc:
            raise CleanupDeletionIntentRepositoryError(
                "unable to read cleanup deletion-intent registry: "
                f"{self.registry_file}"
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CleanupDeletionIntentRepositoryError(
                "cleanup deletion-intent registry contains invalid JSON: "
                f"{self.registry_file}"
            ) from exc

        if not isinstance(payload, Mapping):
            raise CleanupDeletionIntentRepositoryError(
                "cleanup deletion-intent registry must be an object"
            )

        if payload.get("schema_version") != SCHEMA_VERSION:
            raise CleanupDeletionIntentRepositoryError(
                "unsupported cleanup deletion-intent "
                "registry schema_version"
            )

        records = payload.get("intents")

        if not isinstance(records, list):
            raise CleanupDeletionIntentRepositoryError(
                "cleanup deletion-intent registry intents "
                "must be an array"
            )

        normalized_records: list[Mapping[str, Any]] = []

        seen_targets: set[tuple[str, str]] = set()

        for payload_record in records:
            if not isinstance(payload_record, Mapping):
                raise CleanupDeletionIntentRepositoryError(
                    "cleanup deletion-intent record "
                    "must be an object"
                )

            intent = self._intent_from_payload(
                payload_record
            )
            target = (
                intent.provider,
                intent.item_id,
            )

            if target in seen_targets:
                raise CleanupDeletionIntentRepositoryError(
                    "cleanup deletion-intent registry "
                    "contains duplicate provider item"
                )

            seen_targets.add(target)
            normalized_records.append(
                intent.to_dict()
            )

        return {
            "schema_version": SCHEMA_VERSION,
            "intents": normalized_records,
        }

    def _write_document(
        self,
        document: Mapping[str, Any],
    ) -> None:
        """Durably replace the deletion-intent registry."""

        serialized = (
            json.dumps(
                document,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        temporary_path = self.registry_file.with_name(
            f".{self.registry_file.name}.tmp"
        )

        try:
            self.registry_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary_path,
                self.registry_file,
            )

            self._sync_directory(
                self.registry_file.parent
            )
        except OSError as exc:
            raise CleanupDeletionIntentRepositoryError(
                "unable to durably persist cleanup "
                "deletion-intent registry: "
                f"{self.registry_file}"
            ) from exc
        finally:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

    @staticmethod
    def _sync_directory(
        directory: Path,
    ) -> None:
        """Synchronize a completed atomic replacement."""

        flags = os.O_RDONLY

        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY

        descriptor = os.open(
            directory,
            flags,
        )

        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _empty_document() -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "intents": [],
        }

    @staticmethod
    def _document(
        records: list[Mapping[str, Any] | dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "intents": records,
        }

    @staticmethod
    def _intent_from_payload(
        payload: Mapping[str, Any],
    ) -> CleanupDeletionIntent:
        allowed_fields = {
            "execution_id",
            "provider",
            "item_id",
            "created_at",
        }

        missing = sorted(
            allowed_fields.difference(payload)
        )

        if missing:
            raise CleanupDeletionIntentRepositoryError(
                "cleanup deletion-intent record missing fields: "
                + ", ".join(missing)
            )

        unexpected = sorted(
            set(payload).difference(allowed_fields)
        )

        if unexpected:
            raise CleanupDeletionIntentRepositoryError(
                "cleanup deletion-intent record has unexpected fields: "
                + ", ".join(unexpected)
            )

        created_at = payload["created_at"]

        if not isinstance(created_at, str):
            raise CleanupDeletionIntentRepositoryError(
                "cleanup deletion-intent created_at "
                "must be an ISO-8601 string"
            )

        try:
            parsed = datetime.fromisoformat(
                created_at.replace(
                    "Z",
                    "+00:00",
                )
            )
            return CleanupDeletionIntent(
                execution_id=payload["execution_id"],
                provider=payload["provider"],
                item_id=payload["item_id"],
                created_at=parsed,
            )
        except (
            CleanupError,
            TypeError,
            ValueError,
        ) as exc:
            raise CleanupDeletionIntentRepositoryError(
                "invalid cleanup deletion-intent record"
            ) from exc

    @classmethod
    def _find_in_records(
        cls,
        records: list[Mapping[str, Any]],
        provider: str,
        item_id: str,
    ) -> CleanupDeletionIntent | None:
        for record in records:
            if cls._record_matches(
                record,
                provider,
                item_id,
            ):
                return cls._intent_from_payload(
                    record
                )

        return None

    @staticmethod
    def _record_matches(
        record: Mapping[str, Any],
        provider: str,
        item_id: str,
    ) -> bool:
        return (
            record.get("provider") == provider
            and record.get("item_id") == item_id
        )

    @contextmanager
    def _exclusive_lock(
        self,
    ) -> Iterator[None]:
        try:
            self.root.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self.lock_file.open(
                "a+",
                encoding="utf-8",
            ) as lock:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_EX,
                )
                try:
                    yield
                finally:
                    fcntl.flock(
                        lock.fileno(),
                        fcntl.LOCK_UN,
                    )
        except OSError as exc:
            raise CleanupDeletionIntentRepositoryError(
                "unable to lock cleanup deletion-intent repository: "
                f"{self.lock_file}"
            ) from exc


def _required_text(
    value: object,
    field_name: str,
    *,
    lowercase: bool = False,
) -> str:
    if not isinstance(value, str):
        raise CleanupDeletionIntentRepositoryError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise CleanupDeletionIntentRepositoryError(
            f"{field_name} must not be empty"
        )

    if lowercase:
        normalized = normalized.lower()

    return normalized
