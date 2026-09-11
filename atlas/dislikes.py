"""Durable user dislike relationships for Project Atlas.

Dislikes are metadata references. This subsystem never copies, moves, or links
media files; provider integration and retention protection are layered on later.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from atlas.atomic import write_json_atomic

SCHEMA_VERSION = 1
REGISTRY_SCHEMA_VERSION = 1
VALID_MEDIA_TYPES = frozenset({"movie", "tv", "anime", "sports", "other"})
_USER_ID_PATTERN = re.compile(r"^usr_[a-f0-9]{32}$")
_PROVIDER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")


class DislikeError(ValueError):
    """Raised when a dislike operation cannot be completed."""


@dataclass(frozen=True)
class DislikeStore:
    root: Path
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    @property
    def dislikes_root(self) -> Path:
        return self.root / "dislikes"

    @property
    def records_directory(self) -> Path:
        return self.dislikes_root / "records"

    @property
    def registry_file(self) -> Path:
        return self.dislikes_root / "dislikes.json"

    def initialize(self) -> None:
        self.records_directory.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            write_json_atomic(
                self.registry_file,
                {"schema_version": REGISTRY_SCHEMA_VERSION, "dislikes": {}},
            )

    def add(
        self,
        user_id: str,
        provider: str,
        item_id: str,
        *,
        media_type: str,
        title: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        user_id = normalize_user_id(user_id)
        provider = normalize_provider(provider)
        item_id = _required_text(item_id, "item_id", maximum=256)
        media_type = normalize_media_type(media_type)
        title = _optional_text(title, "title", maximum=512)
        safe_metadata = normalize_metadata(metadata)
        registry = self._load_registry()

        for dislike_id, entry in registry["dislikes"].items():
            if (
                entry["user_id"] == user_id
                and entry["provider"] == provider
                and entry["item_id"] == item_id
            ):
                raise DislikeError(f"dislike already exists: {dislike_id}")

        dislike_id = f"dis_{uuid.uuid4().hex}"
        timestamp = format_timestamp(self.clock())
        record = validate_dislike(
            {
                "schema_version": SCHEMA_VERSION,
                "dislike_id": dislike_id,
                "user_id": user_id,
                "provider": provider,
                "item_id": item_id,
                "media_type": media_type,
                "title": title,
                "metadata": safe_metadata,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        path = self._record_file(dislike_id)
        write_json_atomic(path, record)
        registry["dislikes"][dislike_id] = self._registry_entry(record, path)
        try:
            write_json_atomic(self.registry_file, registry)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return record

    def get(self, dislike_id: str) -> dict[str, Any]:
        self.initialize()
        registry = self._load_registry()
        entry = registry["dislikes"].get(dislike_id)
        if not isinstance(entry, dict):
            raise DislikeError(f"dislike not found: {dislike_id}")
        path = self._safe_path(entry.get("path"), dislike_id)
        return validate_dislike(_read_json(path))

    def list(
        self,
        *,
        user_id: str | None = None,
        provider: str | None = None,
        media_type: str | None = None,
    ) -> list[dict[str, Any]]:
        self.initialize()
        normalized_user = normalize_user_id(user_id) if user_id is not None else None
        normalized_provider = normalize_provider(provider) if provider is not None else None
        normalized_type = normalize_media_type(media_type) if media_type is not None else None
        records = []
        for dislike_id, entry in self._load_registry()["dislikes"].items():
            if normalized_user is not None and entry["user_id"] != normalized_user:
                continue
            if normalized_provider is not None and entry["provider"] != normalized_provider:
                continue
            if normalized_type is not None and entry["media_type"] != normalized_type:
                continue
            records.append(self.get(dislike_id))
        return sorted(records, key=lambda value: (value["created_at"], value["dislike_id"]))

    def remove(self, dislike_id: str) -> dict[str, Any]:
        self.initialize()
        registry = self._load_registry()
        entry = registry["dislikes"].get(dislike_id)
        if not isinstance(entry, dict):
            raise DislikeError(f"dislike not found: {dislike_id}")
        path = self._safe_path(entry.get("path"), dislike_id)
        record = validate_dislike(_read_json(path))
        updated = dict(registry)
        updated["dislikes"] = dict(registry["dislikes"])
        del updated["dislikes"][dislike_id]
        write_json_atomic(self.registry_file, updated)
        try:
            path.unlink()
        except Exception:
            write_json_atomic(self.registry_file, registry)
            raise
        return record

    def find(self, user_id: str, provider: str, item_id: str) -> dict[str, Any] | None:
        user_id = normalize_user_id(user_id)
        provider = normalize_provider(provider)
        item_id = _required_text(item_id, "item_id", maximum=256)
        for record in self.list(user_id=user_id, provider=provider):
            if record["item_id"] == item_id:
                return record
        return None

    def verify(self) -> list[str]:
        self.initialize()
        try:
            registry = self._load_registry()
        except (DislikeError, OSError, json.JSONDecodeError) as exc:
            return [str(exc)]
        errors: list[str] = []
        seen_relationships: set[tuple[str, str, str]] = set()
        referenced: set[Path] = set()
        for dislike_id, entry in registry["dislikes"].items():
            try:
                path = self._safe_path(entry["path"], dislike_id)
                referenced.add(path)
                record = validate_dislike(_read_json(path))
                if record["dislike_id"] != dislike_id:
                    errors.append(f"{dislike_id}: record ID does not match registry")
                for field in ("user_id", "provider", "item_id", "media_type"):
                    if record[field] != entry[field]:
                        errors.append(f"{dislike_id}: registry {field} does not match record")
                relationship = (record["user_id"], record["provider"], record["item_id"])
                if relationship in seen_relationships:
                    errors.append(f"{dislike_id}: duplicate dislike relationship")
                seen_relationships.add(relationship)
            except (KeyError, DislikeError, OSError, json.JSONDecodeError) as exc:
                errors.append(f"{dislike_id}: {exc}")
        for path in self.records_directory.glob("dis_*.json"):
            if path.resolve() not in referenced:
                errors.append(f"unregistered dislike record: {path}")
        return errors

    def _load_registry(self) -> dict[str, Any]:
        data = _read_json(self.registry_file)
        if not isinstance(data, dict) or data.get("schema_version") != REGISTRY_SCHEMA_VERSION:
            raise DislikeError("unsupported dislikes registry schema")
        dislikes = data.get("dislikes")
        if not isinstance(dislikes, dict):
            raise DislikeError("dislikes registry must contain a dislikes object")
        for dislike_id, entry in dislikes.items():
            if not isinstance(entry, dict):
                raise DislikeError(f"invalid dislikes registry entry: {dislike_id}")
            for field in ("path", "user_id", "provider", "item_id", "media_type"):
                if not isinstance(entry.get(field), str):
                    raise DislikeError(f"invalid dislikes registry {field}: {dislike_id}")
        return data

    def _record_file(self, dislike_id: str) -> Path:
        return self.records_directory / f"{dislike_id}.json"

    def _safe_path(self, value: object, dislike_id: str) -> Path:
        if not isinstance(value, str):
            raise DislikeError(f"invalid dislike path: {dislike_id}")
        path = (self.dislikes_root / value).resolve()
        try:
            path.relative_to(self.dislikes_root.resolve())
        except ValueError as exc:
            raise DislikeError(f"dislike path escapes dislikes directory: {dislike_id}") from exc
        return path

    def _registry_entry(self, record: Mapping[str, Any], path: Path) -> dict[str, str]:
        return {
            "path": path.relative_to(self.dislikes_root).as_posix(),
            "user_id": str(record["user_id"]),
            "provider": str(record["provider"]),
            "item_id": str(record["item_id"]),
            "media_type": str(record["media_type"]),
        }


def default_dislike_store() -> DislikeStore:
    root = Path(os.getenv("ATLAS_IDENTITY_DIR", "/mnt/storage/configs/atlas/identity"))
    return DislikeStore(root.expanduser().resolve())


def validate_dislike(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema_version") != SCHEMA_VERSION:
        raise DislikeError("unsupported dislike schema")
    dislike_id = _required_text(value.get("dislike_id"), "dislike_id", maximum=40)
    if not re.fullmatch(r"dis_[a-f0-9]{32}", dislike_id):
        raise DislikeError("invalid dislike_id")
    created_at = normalize_timestamp(value.get("created_at"), "created_at")
    updated_at = normalize_timestamp(value.get("updated_at"), "updated_at")
    return {
        "schema_version": SCHEMA_VERSION,
        "dislike_id": dislike_id,
        "user_id": normalize_user_id(value.get("user_id")),
        "provider": normalize_provider(value.get("provider")),
        "item_id": _required_text(value.get("item_id"), "item_id", maximum=256),
        "media_type": normalize_media_type(value.get("media_type")),
        "title": _optional_text(value.get("title"), "title", maximum=512),
        "metadata": normalize_metadata(value.get("metadata")),
        "created_at": created_at,
        "updated_at": updated_at,
    }


def normalize_user_id(value: object) -> str:
    text = _required_text(value, "user_id", maximum=36).lower()
    if not _USER_ID_PATTERN.fullmatch(text):
        raise DislikeError("invalid Atlas user_id")
    return text


def normalize_provider(value: object) -> str:
    text = _required_text(value, "provider", maximum=32).lower()
    if not _PROVIDER_PATTERN.fullmatch(text):
        raise DislikeError("invalid dislike provider")
    return text


def normalize_media_type(value: object) -> str:
    text = _required_text(value, "media_type", maximum=16).lower()
    if text not in VALID_MEDIA_TYPES:
        raise DislikeError("invalid dislike media_type")
    return text


def normalize_metadata(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DislikeError("dislike metadata must be an object")
    try:
        serialized = json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise DislikeError("dislike metadata must be JSON serializable") from exc
    if len(serialized.encode("utf-8")) > 8192:
        raise DislikeError("dislike metadata exceeds 8192 bytes")
    return json.loads(serialized)


def normalize_timestamp(value: object, field: str) -> str:
    text = _required_text(value, field, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DislikeError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        raise DislikeError(f"{field} must include timezone")
    return format_timestamp(parsed)


def format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise DislikeError("timestamp must include timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _required_text(value: object, field: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DislikeError(f"{field} is required")
    text = value.strip()
    if len(text) > maximum:
        raise DislikeError(f"{field} exceeds {maximum} characters")
    return text


def _optional_text(value: object, field: str, *, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DislikeError(f"{field} must be text")
    text = value.strip()
    if not text:
        return None
    if len(text) > maximum:
        raise DislikeError(f"{field} exceeds {maximum} characters")
    return text


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
