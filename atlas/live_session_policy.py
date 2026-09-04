# Durable per-user Atlas Live playback concurrency policy.

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
import tempfile
from typing import Any


POLICY_VERSION = 1
DEFAULT_LIVE_SESSION_LIMIT = 5


class LiveSessionPolicyError(RuntimeError):
    pass


class LiveSessionPolicyStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write(
                    {
                        "version": POLICY_VERSION,
                        "default_limit": DEFAULT_LIVE_SESSION_LIMIT,
                        "overrides": {},
                    }
                )
            else:
                self._read()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = self._read()
            return {
                "version": payload["version"],
                "default_limit": payload["default_limit"],
                "overrides": dict(payload["overrides"]),
            }

    def effective_limit(self, user_id: str) -> int:
        normalized = _user_id(user_id)
        with self._lock:
            payload = self._read()
            return payload["overrides"].get(
                normalized,
                payload["default_limit"],
            )

    def set_default_limit(self, limit: int) -> int:
        normalized = _limit(limit)
        with self._lock:
            payload = self._read()
            payload["default_limit"] = normalized
            self._write(payload)
        return normalized

    def set_override(self, user_id: str, limit: int) -> int:
        normalized_user = _user_id(user_id)
        normalized_limit = _limit(limit)
        with self._lock:
            payload = self._read()
            payload["overrides"][normalized_user] = normalized_limit
            self._write(payload)
        return normalized_limit

    def clear_override(self, user_id: str) -> bool:
        normalized_user = _user_id(user_id)
        with self._lock:
            payload = self._read()
            removed = payload["overrides"].pop(normalized_user, None)
            if removed is not None:
                self._write(payload)
        return removed is not None

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            raise LiveSessionPolicyError("Live-session policy is unavailable.")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LiveSessionPolicyError("Live-session policy is unreadable.") from exc

        if not isinstance(payload, dict) or set(payload) != {
            "version",
            "default_limit",
            "overrides",
        }:
            raise LiveSessionPolicyError("Live-session policy schema is invalid.")
        if payload["version"] != POLICY_VERSION:
            raise LiveSessionPolicyError("Live-session policy version is unsupported.")

        default_limit = _limit(payload["default_limit"])
        raw_overrides = payload["overrides"]
        if not isinstance(raw_overrides, dict):
            raise LiveSessionPolicyError(
                "Live-session policy overrides must be an object."
            )

        overrides: dict[str, int] = {}
        for raw_user_id, raw_limit in raw_overrides.items():
            normalized_user = _user_id(raw_user_id)
            if normalized_user in overrides:
                raise LiveSessionPolicyError(
                    "Live-session policy contains duplicate users."
                )
            overrides[normalized_user] = _limit(raw_limit)

        return {
            "version": POLICY_VERSION,
            "default_limit": default_limit,
            "overrides": overrides,
        }

    def _write(self, payload: dict[str, Any]) -> None:
        validated = _validated_payload(payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(validated, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise


def default_live_session_policy_store() -> LiveSessionPolicyStore:
    users_root = Path(
        os.getenv(
            "ATLAS_USERS_DIR",
            "/mnt/storage/configs/atlas/users",
        )
    ).expanduser().resolve()

    configured = os.getenv(
        "ATLAS_LIVE_SESSION_POLICY_PATH",
        "",
    ).strip()

    path = (
        Path(configured).expanduser().resolve()
        if configured
        else users_root / "live-session-policy.json"
    )

    return LiveSessionPolicyStore(path)


def _validated_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LiveSessionPolicyError(
            "Live-session policy payload must be an object."
        )

    default_limit = _limit(payload.get("default_limit"))
    raw_overrides = payload.get("overrides", {})
    if not isinstance(raw_overrides, dict):
        raise LiveSessionPolicyError(
            "Live-session policy overrides must be an object."
        )

    overrides = {
        _user_id(user_id): _limit(limit)
        for user_id, limit in raw_overrides.items()
    }

    return {
        "version": POLICY_VERSION,
        "default_limit": default_limit,
        "overrides": dict(sorted(overrides.items())),
    }


def _limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LiveSessionPolicyError(
            "Live-session limit must be a positive integer."
        )
    return value


def _user_id(value: object) -> str:
    if not isinstance(value, str):
        raise LiveSessionPolicyError(
            "Live-session policy user ID must be a string."
        )
    normalized = value.strip()
    if not normalized or len(normalized) > 256:
        raise LiveSessionPolicyError(
            "Live-session policy user ID is invalid."
        )
    if any(ord(character) < 32 for character in normalized):
        raise LiveSessionPolicyError(
            "Live-session policy user ID is invalid."
        )
    return normalized


__all__ = [
    "DEFAULT_LIVE_SESSION_LIMIT",
    "LiveSessionPolicyError",
    "LiveSessionPolicyStore",
    "POLICY_VERSION",
    "default_live_session_policy_store",
]
