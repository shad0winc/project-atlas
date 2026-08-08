"""Read and validate Atlas Retention Intelligence snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .models import StorageSummary


class SnapshotReaderError(ValueError):
    """Raised when an ARI snapshot cannot be read or validated."""


def _normalize_required_text(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise SnapshotReaderError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise SnapshotReaderError(f"{field_name} must not be empty.")

    return normalized


def _normalize_nonnegative_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotReaderError(f"{field_name} must be an integer.")

    if value < 0:
        raise SnapshotReaderError(f"{field_name} must not be negative.")

    return value


def _require_mapping(
    value: object,
    *,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SnapshotReaderError(f"{field_name} must be an object.")

    return value


@dataclass(frozen=True, slots=True)
class ARISnapshot:
    """Validated source data read from one ARI JSON document."""

    timestamp: str
    schema_version: int
    storage: StorageSummary
    library_counts: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        timestamp = _normalize_required_text(
            self.timestamp,
            field_name="timestamp",
        )
        schema_version = _normalize_nonnegative_integer(
            self.schema_version,
            field_name="schema_version",
        )

        if schema_version < 1:
            raise SnapshotReaderError(
                "schema_version must be at least 1."
            )

        if not isinstance(self.storage, StorageSummary):
            raise TypeError("storage must be a StorageSummary.")

        if not isinstance(self.library_counts, tuple):
            raise TypeError(
                "library_counts must be a tuple of name/count pairs."
            )

        normalized_counts: list[tuple[str, int]] = []
        seen_names: set[str] = set()

        for index, entry in enumerate(self.library_counts):
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
            ):
                raise TypeError(
                    "library_counts must contain two-value tuples."
                )

            raw_name, raw_count = entry

            name = _normalize_required_text(
                raw_name,
                field_name=f"library_counts[{index}].name",
            ).lower()

            count = _normalize_nonnegative_integer(
                raw_count,
                field_name=f"library_counts[{index}].count",
            )

            if name in seen_names:
                raise SnapshotReaderError(
                    f"Duplicate library name: {name}."
                )

            seen_names.add(name)
            normalized_counts.append((name, count))

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(
            self,
            "library_counts",
            tuple(normalized_counts),
        )

    def library_count(self, name: str) -> int:
        """Return the count for one normalized library."""

        normalized_name = _normalize_required_text(
            name,
            field_name="name",
        ).lower()

        for library_name, count in self.library_counts:
            if library_name == normalized_name:
                return count

        raise KeyError(normalized_name)

    def to_dict(self) -> dict[str, object]:
        """Serialize the validated ARI source snapshot."""

        return {
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "storage": self.storage.to_dict(),
            "libraries": {
                name: {
                    "count": count,
                }
                for name, count in self.library_counts
            },
        }


class SnapshotReader:
    """Read ARI JSON documents from disk."""

    def read(self, path: str | Path) -> ARISnapshot:
        """Read one ARI snapshot file."""

        snapshot_path = self._normalize_path(path)

        try:
            raw_content = snapshot_path.read_text(
                encoding="utf-8"
            )
        except FileNotFoundError as error:
            raise SnapshotReaderError(
                f"ARI snapshot does not exist: {snapshot_path}"
            ) from error
        except OSError as error:
            raise SnapshotReaderError(
                f"Unable to read ARI snapshot: {snapshot_path}"
            ) from error

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as error:
            raise SnapshotReaderError(
                f"ARI snapshot contains invalid JSON: {snapshot_path}"
            ) from error

        return self.read_document(payload)

    def read_document(
        self,
        payload: object,
    ) -> ARISnapshot:
        """Validate an already-loaded ARI snapshot document."""

        document = _require_mapping(
            payload,
            field_name="snapshot",
        )

        timestamp = _normalize_required_text(
            document.get("timestamp"),
            field_name="timestamp",
        )

        atlas = _require_mapping(
            document.get("atlas"),
            field_name="atlas",
        )

        schema_version = _normalize_nonnegative_integer(
            atlas.get("schema_version"),
            field_name="atlas.schema_version",
        )

        storage_document = _require_mapping(
            document.get("storage"),
            field_name="storage",
        )

        total_bytes = _normalize_nonnegative_integer(
            storage_document.get("capacity_bytes"),
            field_name="storage.capacity_bytes",
        )
        used_bytes = _normalize_nonnegative_integer(
            storage_document.get("used_bytes"),
            field_name="storage.used_bytes",
        )
        free_bytes = _normalize_nonnegative_integer(
            storage_document.get("available_bytes"),
            field_name="storage.available_bytes",
        )

        utilization_percent = (
            used_bytes / total_bytes * 100
            if total_bytes
            else 0.0
        )

        try:
            storage = StorageSummary(
                total_bytes=total_bytes,
                used_bytes=used_bytes,
                free_bytes=free_bytes,
                utilization_percent=utilization_percent,
            )
        except (TypeError, ValueError) as error:
            raise SnapshotReaderError(
                f"Invalid ARI storage contract: {error}"
            ) from error

        libraries_document = _require_mapping(
            document.get("libraries"),
            field_name="libraries",
        )

        library_counts: list[tuple[str, int]] = []

        for raw_name, raw_library in libraries_document.items():
            name = _normalize_required_text(
                raw_name,
                field_name="libraries name",
            ).lower()

            library_document = _require_mapping(
                raw_library,
                field_name=f"libraries.{name}",
            )

            count = _normalize_nonnegative_integer(
                library_document.get("count"),
                field_name=f"libraries.{name}.count",
            )

            library_counts.append((name, count))

        library_counts.sort(key=lambda entry: entry[0])

        return ARISnapshot(
            timestamp=timestamp,
            schema_version=schema_version,
            storage=storage,
            library_counts=tuple(library_counts),
        )

    @staticmethod
    def _normalize_path(path: str | Path) -> Path:
        if isinstance(path, Path):
            snapshot_path = path
        elif isinstance(path, str):
            normalized = path.strip()

            if not normalized:
                raise SnapshotReaderError(
                    "ARI snapshot path must not be empty."
                )

            snapshot_path = Path(normalized)
        else:
            raise TypeError(
                "ARI snapshot path must be a string or Path."
            )

        if not str(snapshot_path).strip():
            raise SnapshotReaderError(
                "ARI snapshot path must not be empty."
            )

        return snapshot_path


__all__ = [
    "ARISnapshot",
    "SnapshotReader",
    "SnapshotReaderError",
]
