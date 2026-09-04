from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

STATE_VERSION = 1
_WRITE_LOCK = Lock()


class LiveTvBindingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LiveTvBinding:
    atlas_channel_id: str
    jellyfin_item_id: str

    def safe_dict(self) -> dict[str, str]:
        return {
            "atlas_channel_id": self.atlas_channel_id,
            "jellyfin_item_id": self.jellyfin_item_id,
        }


def _required_identifier(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise LiveTvBindingError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise LiveTvBindingError(f"{field} is required")
    if len(value) > 256:
        raise LiveTvBindingError(f"{field} exceeds 256 characters")
    if any(ord(ch) < 32 for ch in value):
        raise LiveTvBindingError(f"{field} contains control characters")
    return value


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LiveTvBindingError(
                f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


class LiveTvBindingRegistry:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"version": STATE_VERSION, "bindings": {}}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            raw = json.loads(
                self.path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except LiveTvBindingError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise LiveTvBindingError(
                "live TV binding state could not be read"
            ) from exc

        if not isinstance(raw, dict):
            raise LiveTvBindingError(
                "live TV binding state root must be an object"
            )
        if raw.get("version") != STATE_VERSION:
            raise LiveTvBindingError(
                "unsupported live TV binding state version"
            )
        bindings = raw.get("bindings")
        if not isinstance(bindings, dict):
            raise LiveTvBindingError(
                "live TV bindings must be an object"
            )

        normalized: dict[str, dict[str, str]] = {}
        seen_jellyfin: set[str] = set()
        for atlas_id_raw, entry in bindings.items():
            atlas_id = _required_identifier(
                atlas_id_raw, "atlas_channel_id"
            )
            if not isinstance(entry, dict):
                raise LiveTvBindingError(
                    "live TV binding entries must be objects"
                )
            if set(entry) != {"jellyfin_item_id"}:
                raise LiveTvBindingError(
                    "live TV binding entry contains unsupported fields"
                )
            jellyfin_id = _required_identifier(
                entry.get("jellyfin_item_id"),
                "jelyfin_item_id",
            )
            if jellyfin_id in seen_jellyfin:
                raise LiveTvBindingError(
                    "one Jellyfin item cannot bind to multiple Atlas channels"
                )
            seen_jellyfin.add(jellyfin_id)
            normalized[atlas_id] = {
                "jellyfin_item_id": jellyfin_id
            }

        return {"version": STATE_VERSION, "bindings": normalized}

    def _write(self, document: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp.write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise

    def ensure(self) -> None:
        with _WRITE_LOCK:
            if self.path.exists():
                self._load()
            else:
                self._write(self._empty())

    def list_bindings(self) -> tuple[LiveTvBinding, ...]:
        doc = self._load()
        return tuple(
            LiveTvBinding(
                atlas_channel_id=atlas_id,
                jellyfin_item_id=entry["jellyfin_item_id"],
            )
            for atlas_id, entry in sorted(doc["bindings"].items())
        )

    def resolve(self, atlas_channel_id: str) -> str | None:
        atlas_id = _required_identifier(
            atlas_channel_id, "atlas_channel_id"
        )
        entry = self._load()["bindings"].get(atlas_id)
        return None if entry is None else entry["jellyfin_item_id"]

    def set(
        self,
        atlas_channel_id: str,
        jellyfin_item_id: str,
    ) -> LiveTvBinding:
        atlas_id = _required_identifier(
            atlas_channel_id, "atlas_channel_id"
        )
        jellyfin_id = _required_identifier(
            jellyfin_item_id, "jellyfin_item_id"
        )
        with _WRITE_LOCK:
            doc = self._load()
            for other_atlas_id, entry in doc["bindings"].items():
                if (
                    other_atlas_id != atlas_id
                    and entry["jellyfin_item_id"] == jellyfin_id
                ):
                    raise LiveTvBindingError(
                        "Jellyfin item is already bound to another Atlas channel"
                    )
            doc["bindings"][atlas_id] = {
                "jellyfin_item_id": jellyfin_id
            }
            self._write(doc)

        return LiveTvBinding(atlas_id, jellyfin_id)

    def delete(self, atlas_channel_id: str) -> bool:
        atlas_id = _required_identifier(
            atlas_channel_id, "atlas_channel_id"
        )
        with _WRITE_LOCK:
            doc = self._load()
            if atlas_id not in doc["bindings"]:
                return False
            del doc["bindings"][atlas_id]
            self._write(doc)
            return True


def default_live_tv_binding_registry() -> LiveTvBindingRegistry:
    return LiveTvBindingRegistry(
        os.getenv(
            "SPORTS_LIVE_TV_BINDINGS_FILE",
            "/mnt/storage/configs/sportyfin/state/live-tv-bindings.json",
         )
    )
