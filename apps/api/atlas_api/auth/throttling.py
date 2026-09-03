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


class PasswordRecoveryRequestLimiter:
    """Limit recovery requests for one normalized email address."""

    def __init__(
        self,
        *,
        max_requests: int = 5,
        window_seconds: int = 300,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_requests <= 0:
            raise ValueError(
                "Maximum password recovery requests must be positive."
            )
        if window_seconds <= 0:
            raise ValueError(
                "Password recovery throttle window must be positive."
            )

        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._requests: dict[str, deque[float]] = {}
        self._lock = RLock()

    def retry_after(self, email: str) -> int | None:
        """Return blocking seconds when this email has reached its limit."""

        key = _recovery_key(email)
        now = self._clock()

        with self._lock:
            requests = self._active_requests(key, now)

            if len(requests) < self._max_requests:
                return None

            remaining = self._window_seconds - (now - requests[0])
            return max(1, ceil(remaining))

    def record(self, email: str) -> None:
        """Record one recovery request regardless of account existence."""

        key = _recovery_key(email)
        now = self._clock()

        with self._lock:
            requests = self._active_requests(key, now)

            if key not in self._requests:
                self._requests[key] = requests

            requests.append(now)

    def _active_requests(
        self,
        key: str,
        now: float,
    ) -> deque[float]:
        requests = self._requests.get(key)

        if requests is None:
            return deque()

        while requests and now - requests[0] >= self._window_seconds:
            requests.popleft()

        if not requests:
            self._requests.pop(key, None)
            return deque()

        return requests


def _recovery_key(email: str) -> str:
    normalized = email.strip().casefold()

    if not normalized:
        raise ValueError(
            "Password recovery throttle email cannot be empty."
        )

    return normalized


def _account_key(username: str) -> str:
    normalized = username.strip().casefold()

    if not normalized:
        raise ValueError("Login throttle username cannot be empty.")

    return normalized
