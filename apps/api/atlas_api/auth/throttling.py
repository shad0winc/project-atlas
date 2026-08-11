"""Process-local authentication attempt throttling."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from math import ceil
from threading import RLock
import time


class LoginAttemptLimiter:
    """Limit failed credential attempts for one normalized account key."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 300,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_failures <= 0:
            raise ValueError("Maximum login failures must be positive.")
        if window_seconds <= 0:
            raise ValueError("Login throttle window must be positive.")

        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._failures: dict[str, deque[float]] = {}
        self._lock = RLock()

    def retry_after(self, username: str) -> int | None:
        """Return blocking seconds when the account has reached its limit."""

        key = _account_key(username)
        now = self._clock()

        with self._lock:
            failures = self._active_failures(key, now)

            if len(failures) < self._max_failures:
                return None

            remaining = self._window_seconds - (now - failures[0])
            return max(1, ceil(remaining))

    def record_failure(self, username: str) -> None:
        """Record one failed credential authentication attempt."""

        key = _account_key(username)
        now = self._clock()

        with self._lock:
            failures = self._active_failures(key, now)
            if key not in self._failures:
                self._failures[key] = failures
            failures.append(now)

    def reset(self, username: str) -> None:
        """Clear failures after a successful authentication."""

        key = _account_key(username)

        with self._lock:
            self._failures.pop(key, None)

    def _active_failures(
        self,
        key: str,
        now: float,
    ) -> deque[float]:
        failures = self._failures.get(key)

        if failures is None:
            return deque()

        while failures and now - failures[0] >= self._window_seconds:
            failures.popleft()

        if not failures:
            self._failures.pop(key, None)
            return deque()

        return failures


def _account_key(username: str) -> str:
    normalized = username.strip().casefold()

    if not normalized:
        raise ValueError("Login throttle username cannot be empty.")

    return normalized
