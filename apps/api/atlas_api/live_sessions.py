# Process-local active Live playback session admission state.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from threading import RLock
import time
from uuid import uuid4


DEFAULT_LIVE_SESSION_TTL_SECONDS = 90


class LiveSessionError(RuntimeError):
    pass


class LiveSessionLimitExceeded(LiveSessionError):
    pass


class LiveSessionNotFound(LiveSessionError):
    pass


@dataclass(frozen=True, slots=True)
class LiveSessionRecord:
    session_id: str
    user_id: str
    target_id: str
    created_at: float
    last_seen_at: float


class LiveSessionRegistry:
    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_LIVE_SESSION_TTL_SECONDS,
        clock: Callable[[], float] | None = None,
        session_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or ttl_seconds <= 0
        ):
            raise ValueError("Live-session TTL must be a positive integer.")

        self.ttl_seconds = ttl_seconds
        self._clock = clock or time.monotonic
        self._session_id_factory = session_id_factory or (lambda: uuid4().hex)
        self._sessions: dict[str, LiveSessionRecord] = {}
        self._lock = RLock()

    def admit(
        self,
        *,
        user_id: str,
        target_id: str,
        limit: int,
    ) -> LiveSessionRecord:
        normalized_user = _required_identifier(user_id, "Live-session user ID")
        normalized_target = _required_identifier(target_id, "Live-session target ID")

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("Live-session limit must be a positive integer.")

        now = self._clock()
        with self._lock:
            self._prune_stale(now)
            active = sum(
                1
                for record in self._sessions.values()
                if record.user_id == normalized_user
            )
            if active >= limit:
                raise LiveSessionLimitExceeded("Live-session limit reached.")

            session_id = _required_identifier(
                self._session_id_factory(),
                "Live-session identifier",
            )
            if session_id in self._sessions:
                raise LiveSessionError(
                    "Live-session identifier is already active."
                )

            record = LiveSessionRecord(
                session_id=session_id,
                user_id=normalized_user,
                target_id=normalized_target,
                created_at=now,
                last_seen_at=now,
            )
            self._sessions[session_id] = record
            return record

    def heartbeat(self, *, session_id: str, user_id: str) -> LiveSessionRecord:
        normalized_session = _required_identifier(
            session_id,
            "Live-session identifier",
        )
        normalized_user = _required_identifier(user_id, "Live-session user ID")
        now = self._clock()

        with self._lock:
            self._prune_stale(now)
            record = self._sessions.get(normalized_session)
            if record is None or record.user_id != normalized_user:
                raise LiveSessionNotFound("Live session was not found.")

            refreshed = LiveSessionRecord(
                session_id=record.session_id,
                user_id=record.user_id,
                target_id=record.target_id,
                created_at=record.created_at,
                last_seen_at=now,
            )
            self._sessions[normalized_session] = refreshed
            return refreshed

    def release(self, *, session_id: str, user_id: str) -> bool:
        normalized_session = _required_identifier(
            session_id,
            "Live-session identifier",
        )
        normalized_user = _required_identifier(user_id, "Live-session user ID")

        with self._lock:
            self._prune_stale(self._clock())
            record = self._sessions.get(normalized_session)
            if record is None or record.user_id != normalized_user:
                return False
            self._sessions.pop(normalized_session, None)
            return True

    def active_count_for_user(self, user_id: str) -> int:
        normalized_user = _required_identifier(user_id, "Live-session user ID")
        with self._lock:
            self._prune_stale(self._clock())
            return sum(
                1
                for record in self._sessions.values()
                if record.user_id == normalized_user
            )

    def list_active_for_user(self, user_id: str) -> tuple[LiveSessionRecord, ...]:
        normalized_user = _required_identifier(user_id, "Live-session user ID")
        with self._lock:
            self._prune_stale(self._clock())
            return tuple(
                sorted(
                    (
                        record
                        for record in self._sessions.values()
                        if record.user_id == normalized_user
                    ),
                    key=lambda record: record.session_id,
                )
            )

    def _prune_stale(self, now: float) -> None:
        stale = [
            session_id
            for session_id, record in self._sessions.items()
            if now - record.last_seen_at >= self.ttl_seconds
        ]
        for session_id in stale:
            self._sessions.pop(session_id, None)


def live_session_registry_from_environment() -> LiveSessionRegistry:
    raw = os.getenv(
        "ATLAS_LIVE_SESSION_TTL_SECONDS",
        str(DEFAULT_LIVE_SESSION_TTL_SECONDS),
    ).strip()
    try:
        ttl = int(raw)
    except ValueError as exc:
        raise ValueError(
            "ATLAS_LIVE_SESSION_TTL_SECONDS must be an integer."
        ) from exc
    return LiveSessionRegistry(ttl_seconds=ttl)


def _required_identifier(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string.")
    normalized = value.strip()
    if not normalized or len(normalized) > 256:
        raise ValueError(f"{label} is invalid.")
    if any(ord(character) < 32 for character in normalized):
        raise ValueError(f"{label} is invalid.")
    return normalized


__all__ = [
    "DEFAULT_LIVE_SESSION_TTL_SECONDS",
    "LiveSessionError",
    "LiveSessionLimitExceeded",
    "LiveSessionNotFound",
    "LiveSessionRecord",
    "LiveSessionRegistry",
    "live_session_registry_from_environment",
]
