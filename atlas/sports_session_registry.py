"""Cross-process Sports Live user-session admission registry."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Iterator
from uuid import uuid4


STATE_VERSION = 1
DEFAULT_SPORTS_SESSION_TTL_SECONDS = 90


class SportsSessionError(RuntimeError):
    """Base error for shared Sports session admission."""


class SportsSessionLimitExceeded(SportsSessionError):
    """Raised when a user has reached the effective Sports session limit."""


class SportsSessionNotFound(SportsSessionError):
    """Raised when an owned Sports session cannot be found."""


class SportsSessionStateError(SportsSessionError):
    """Raised when durable Sports session state is invalid."""


@dataclass(frozen=True, slots=True)
class SportsSessionRecord:
    session_id: str
    user_id: str
    target_id: str
    created_at: float
    last_seen_at: float


@dataclass(frozen=True, slots=True)
class SportsSessionSnapshot:
    session_id: str
    user_id: str
    target_id: str
    age_seconds: int
    heartbeat_age_seconds: int


class SportsSessionRegistry:
    """File-backed cross-process Sports Live session registry."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        ttl_seconds: int = DEFAULT_SPORTS_SESSION_TTL_SECONDS,
        clock: Callable[[], float] | None = None,
        session_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or ttl_seconds <= 0
        ):
            raise ValueError(
                "Sports-session TTL must be a positive integer."
            )

        self.path = Path(path)
        self.lock_path = Path(f"{self.path}.lock")
        self.ttl_seconds = ttl_seconds
        self._clock = clock or time.time
        self._session_id_factory = (
            session_id_factory or (lambda: uuid4().hex)
        )

    def admit(
        self,
        *,
        user_id: str,
        target_id: str,
        limit: int,
    ) -> SportsSessionRecord:
        normalized_user = _required_identifier(
            user_id,
            "Sports-session user ID",
        )
        normalized_target = _required_identifier(
            target_id,
            "Sports-session target ID",
        )

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
        ):
            raise ValueError(
                "Sports-session limit must be a positive integer."
            )

        now = self._clock()

        with self._locked():
            state = self._read_state()
            self._prune_stale(state, now)

            active_for_user = sum(
                1
                for payload in state["sessions"].values()
                if payload["user_id"] == normalized_user
            )

            if active_for_user >= limit:
                raise SportsSessionLimitExceeded(
                    "Sports session limit reached."
                )

            session_id = _required_identifier(
                self._session_id_factory(),
                "Sports-session identifier",
            )

            if session_id in state["sessions"]:
                raise SportsSessionStateError(
                    "Sports-session identifier is already active."
                )

            payload = {
                "user_id": normalized_user,
                "target_id": normalized_target,
                "created_at": now,
                "last_seen_at": now,
            }

            state["sessions"][session_id] = payload
            self._write_state(state)

            return _record(session_id, payload)

    def heartbeat(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> SportsSessionRecord:
        normalized_session = _required_identifier(
            session_id,
            "Sports-session identifier",
        )
        normalized_user = _required_identifier(
            user_id,
            "Sports-session user ID",
        )
        now = self._clock()

        with self._locked():
            state = self._read_state()
            changed = self._prune_stale(state, now)

            payload = state["sessions"].get(normalized_session)

            if (
                payload is None
                or payload["user_id"] != normalized_user
            ):
                if changed:
                    self._write_state(state)
                raise SportsSessionNotFound(
                    "Sports session was not found."
                )

            payload["last_seen_at"] = now
            self._write_state(state)

            return _record(normalized_session, payload)

    def release(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> bool:
        normalized_session = _required_identifier(
            session_id,
            "Sports-session identifier",
        )
        normalized_user = _required_identifier(
            user_id,
            "Sports-session user ID",
        )
        now = self._clock()

        with self._locked():
            state = self._read_state()
            changed = self._prune_stale(state, now)

            payload = state["sessions"].get(normalized_session)

            if (
                payload is None
                or payload["user_id"] != normalized_user
            ):
                if changed:
                    self._write_state(state)
                return False

            state["sessions"].pop(normalized_session)
            self._write_state(state)
            return True

    def active_count_for_user(
        self,
        user_id: str,
    ) -> int:
        normalized_user = _required_identifier(
            user_id,
            "Sports-session user ID",
        )

        with self._locked():
            state = self._read_state()
            changed = self._prune_stale(
                state,
                self._clock(),
            )

            if changed:
                self._write_state(state)

            return sum(
                1
                for payload in state["sessions"].values()
                if payload["user_id"] == normalized_user
            )

    def list_active_for_user(
        self,
        user_id: str,
    ) -> tuple[SportsSessionRecord, ...]:
        normalized_user = _required_identifier(
            user_id,
            "Sports-session user ID",
        )

        with self._locked():
            state = self._read_state()
            changed = self._prune_stale(
                state,
                self._clock(),
            )

            if changed:
                self._write_state(state)

            records = [
                _record(session_id, payload)
                for session_id, payload
                in state["sessions"].items()
                if payload["user_id"] == normalized_user
            ]

            return tuple(
                sorted(
                    records,
                    key=lambda record: record.session_id,
                )
            )

    def snapshot_active(
        self,
    ) -> tuple[SportsSessionSnapshot, ...]:
        now = self._clock()

        with self._locked():
            state = self._read_state()
            changed = self._prune_stale(state, now)

            if changed:
                self._write_state(state)

            return tuple(
                SportsSessionSnapshot(
                    session_id=session_id,
                    user_id=payload["user_id"],
                    target_id=payload["target_id"],
                    age_seconds=int(
                        max(
                            0.0,
                            now - payload["created_at"],
                        )
                    ),
                    heartbeat_age_seconds=int(
                        max(
                            0.0,
                            now - payload["last_seen_at"],
                        )
                    ),
                )
                for session_id, payload
                in sorted(
                    state["sessions"].items(),
                    key=lambda item: (
                        item[1]["user_id"],
                        item[0],
                    ),
                )
            )

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        descriptor = os.open(
            self.lock_path,
            os.O_RDWR | os.O_CREAT,
            0o600,
        )

        try:
            with os.fdopen(
                descriptor,
                "a+",
                encoding="utf-8",
            ) as lock_file:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX,
                )
                yield
        finally:
            # fdopen closes the descriptor.
            pass

    def _read_state(self) -> dict[str, object]:
        if not self.path.exists():
            return {
                "version": STATE_VERSION,
                "sessions": {},
            }

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise SportsSessionStateError(
                "Sports-session state is unavailable."
            ) from exc

        if not isinstance(payload, dict):
            raise SportsSessionStateError(
                "Sports-session state is invalid."
            )

        if set(payload) != {
            "version",
            "sessions",
        }:
            raise SportsSessionStateError(
                "Sports-session state is invalid."
            )

        if payload.get("version") != STATE_VERSION:
            raise SportsSessionStateError(
                "Sports-session state version is unsupported."
            )

        sessions = payload.get("sessions")

        if not isinstance(sessions, dict):
            raise SportsSessionStateError(
                "Sports-session state is invalid."
            )

        normalized: dict[str, dict[str, object]] = {}

        for session_id, raw in sessions.items():
            normalized_session = _required_state_identifier(
                session_id
            )

            if not isinstance(raw, dict):
                raise SportsSessionStateError(
                    "Sports-session state is invalid."
                )

            if set(raw) != {
                "user_id",
                "target_id",
                "created_at",
                "last_seen_at",
            }:
                raise SportsSessionStateError(
                    "Sports-session state is invalid."
                )

            user_id = _required_state_identifier(
                raw.get("user_id")
            )
            target_id = _required_state_identifier(
                raw.get("target_id")
            )
            created_at = _required_timestamp(
                raw.get("created_at")
            )
            last_seen_at = _required_timestamp(
                raw.get("last_seen_at")
            )

            if last_seen_at < created_at:
                raise SportsSessionStateError(
                    "Sports-session state is invalid."
                )

            normalized[normalized_session] = {
                "user_id": user_id,
                "target_id": target_id,
                "created_at": created_at,
                "last_seen_at": last_seen_at,
            }

        return {
            "version": STATE_VERSION,
            "sessions": normalized,
        }

    def _write_state(
        self,
        state: dict[str, object],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )

        temporary_path = Path(temporary_name)

        try:
            os.fchmod(descriptor, 0o600)

            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    state,
                    handle,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary_path,
                self.path,
            )
            os.chmod(
                self.path,
                0o600,
            )
        except Exception:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass
            raise

    def _prune_stale(
        self,
        state: dict[str, object],
        now: float,
    ) -> bool:
        sessions = state["sessions"]
        assert isinstance(sessions, dict)

        stale = [
            session_id
            for session_id, payload
            in sessions.items()
            if (
                now
                - payload["last_seen_at"]
                >= self.ttl_seconds
            )
        ]

        for session_id in stale:
            sessions.pop(session_id, None)

        return bool(stale)


def _record(
    session_id: str,
    payload: dict[str, object],
) -> SportsSessionRecord:
    return SportsSessionRecord(
        session_id=session_id,
        user_id=str(payload["user_id"]),
        target_id=str(payload["target_id"]),
        created_at=float(payload["created_at"]),
        last_seen_at=float(payload["last_seen_at"]),
    )


def _required_identifier(
    value: object,
    label: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string.")

    normalized = value.strip()

    if (
        not normalized
        or len(normalized) > 256
        or any(
            ord(character) < 32
            for character in normalized
        )
    ):
        raise ValueError(f"{label} is invalid.")

    return normalized


def _required_state_identifier(
    value: object,
) -> str:
    try:
        return _required_identifier(
            value,
            "Sports-session state identifier",
        )
    except ValueError as exc:
        raise SportsSessionStateError(
            "Sports-session state is invalid."
        ) from exc


def _required_timestamp(
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
    ):
        raise SportsSessionStateError(
            "Sports-session state is invalid."
        )

    normalized = float(value)

    if normalized < 0:
        raise SportsSessionStateError(
            "Sports-session state is invalid."
        )

    return normalized


__all__ = [
    "DEFAULT_SPORTS_SESSION_TTL_SECONDS",
    "SportsSessionError",
    "SportsSessionLimitExceeded",
    "SportsSessionNotFound",
    "SportsSessionRecord",
    "SportsSessionRegistry",
    "SportsSessionSnapshot",
    "SportsSessionStateError",
]
