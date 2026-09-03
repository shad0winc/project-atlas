"""Process-local refresh-token session tracking.

Atlas intentionally keeps this registry in memory. API restart therefore
invalidates every outstanding refresh session instead of restoring old session
state. Only refresh-token identifiers are retained; raw tokens are never
stored.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
import time

from atlas_api.auth.models import TokenClaims, TokenType


class RefreshSessionRegistry:
    """Track active refresh JWT identifiers with single-use consumption."""

    def __init__(
        self,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._clock = clock or _epoch_seconds
        self._sessions: dict[str, tuple[str, int]] = {}
        self._lock = RLock()

    def register(self, claims: TokenClaims) -> None:
        """Register one newly issued refresh token."""

        _require_refresh_claims(claims)
        now = self._clock()

        if claims.expires_at <= now:
            raise ValueError("Refresh session is already expired.")

        with self._lock:
            self._prune_expired(now)

            if claims.token_id in self._sessions:
                raise ValueError("Refresh token identifier is already active.")

            self._sessions[claims.token_id] = (
                claims.subject,
                claims.expires_at,
            )

    def consume(self, claims: TokenClaims) -> bool:
        """Atomically consume one refresh token exactly once."""

        _require_refresh_claims(claims)

        with self._lock:
            self._prune_expired(self._clock())
            session = self._sessions.pop(claims.token_id, None)

        return session == (
            claims.subject,
            claims.expires_at,
        )

    def revoke(self, claims: TokenClaims) -> bool:
        """Revoke a refresh token if it is currently active."""

        _require_refresh_claims(claims)

        with self._lock:
            self._prune_expired(self._clock())
            session = self._sessions.pop(claims.token_id, None)

        return session == (
            claims.subject,
            claims.expires_at,
        )

    def revoke_subject(self, subject: str) -> int:
        """Revoke every active refresh session for one Atlas subject."""

        normalized_subject = subject.strip()

        if not normalized_subject:
            raise ValueError("Refresh-session subject cannot be empty.")

        with self._lock:
            self._prune_expired(self._clock())

            token_ids = [
                token_id
                for token_id, (session_subject, _) in self._sessions.items()
                if session_subject == normalized_subject
            ]

            for token_id in token_ids:
                self._sessions.pop(token_id, None)

        return len(token_ids)

    @property
    def active_count(self) -> int:
        """Return the number of unexpired active refresh sessions."""

        with self._lock:
            self._prune_expired(self._clock())
            return len(self._sessions)

    def _prune_expired(self, now: int) -> None:
        expired = [
            token_id
            for token_id, (_, expires_at) in self._sessions.items()
            if expires_at <= now
        ]

        for token_id in expired:
            self._sessions.pop(token_id, None)


def _require_refresh_claims(claims: TokenClaims) -> None:
    if claims.token_type is not TokenType.REFRESH:
        raise ValueError("Refresh-session claims must be a refresh token.")

    if not claims.token_id.strip():
        raise ValueError("Refresh-token identifier cannot be empty.")

    if not claims.subject.strip():
        raise ValueError("Refresh-token subject cannot be empty.")


def _epoch_seconds() -> int:
    return int(time.time())
