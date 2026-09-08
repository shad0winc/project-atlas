"""Shared Atlas Sports upstream-resource lease coordination."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Iterator
from uuid import uuid4


SPORTS_RESOURCE_POOL_VERSION = 1
DEFAULT_SPORTS_RESOURCE_LEASE_TTL_SECONDS = 90
SPORTS_RESOURCE_POOL_FILE_MODE = 0o660


class SportsResourcePoolError(RuntimeError):
    """Base error for Sports upstream resource coordination."""


class SportsResourcePoolExhausted(SportsResourcePoolError):
    """No candidate source has a free upstream connection slot."""


class SportsResourceUserLimitExceeded(SportsResourcePoolError):
    """Authenticated user already owns the allowed Sports leases."""


class SportsResourceLeaseNotFound(SportsResourcePoolError):
    """Requested Sports resource lease does not exist or is not owned."""


class SportsResourcePoolStateError(SportsResourcePoolError):
    """Shared Sports resource state is invalid or unreadable."""


@dataclass(frozen=True, slots=True)
class SportsResourceLease:
    lease_id: str
    user_id: str
    target_id: str
    source_id: str
    created_at: float
    last_seen_at: float


@dataclass(frozen=True, slots=True)
class SportsResourceSourceSnapshot:
    source_id: str
    capacity: int
    active: int
    available: int


@dataclass(frozen=True, slots=True)
class SportsResourcePoolSnapshot:
    total_capacity: int
    active: int
    available: int
    sources: tuple[SportsResourceSourceSnapshot, ...]
    leases: tuple[SportsResourceLease, ...]


class SportsResourcePool:
    """Coordinate upstream Sports resource leases across Atlas processes."""

    def __init__(
        self,
        path: Path,
        *,
        ttl_seconds: int = DEFAULT_SPORTS_RESOURCE_LEASE_TTL_SECONDS,
        clock: Callable[[], float] | None = None,
        lease_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or ttl_seconds <= 0
        ):
            raise ValueError(
                "Sports resource lease TTL must be a positive integer."
            )

        self.path = Path(path)
        self.lock_path = self.path.with_name(
            self.path.name + ".lock"
        )
        self.ttl_seconds = ttl_seconds
        self._clock = clock or time.time
        self._lease_id_factory = (
            lease_id_factory
            or (lambda: uuid4().hex)
        )

    def acquire(
        self,
        *,
        user_id: str,
        target_id: str,
        candidate_source_ids: Sequence[str],
        capacities: Mapping[str, int],
        user_limit: int | None = None,
    ) -> SportsResourceLease:
        """Acquire the highest-ranked candidate with available capacity."""

        normalized_user = _required_identifier(
            user_id,
            "Sports resource user ID",
        )
        normalized_target = _required_identifier(
            target_id,
            "Sports resource target ID",
        )
        candidates = _normalized_candidates(
            candidate_source_ids
        )
        normalized_capacities = _normalized_capacities(
            capacities
        )

        if user_limit is not None and (
            isinstance(user_limit, bool)
            or not isinstance(user_limit, int)
            or user_limit <= 0
        ):
            raise ValueError(
                "Sports resource user limit must be "
                "a positive integer."
            )

        if not candidates:
            raise SportsResourcePoolExhausted(
                "No Sports resource candidates are available."
            )

        now = self._clock()

        with self._locked():
            state = self._read_state()
            leases = self._prune_stale(
                state["leases"],
                now,
            )

            if user_limit is not None:
                active_for_user = sum(
                    1
                    for payload in leases.values()
                    if payload["user_id"]
                    == normalized_user
                )

                if active_for_user >= user_limit:
                    raise SportsResourceUserLimitExceeded(
                        "Sports session limit reached."
                    )

            active_by_source: dict[str, int] = {}

            for payload in leases.values():
                source_id = payload["source_id"]
                active_by_source[source_id] = (
                    active_by_source.get(source_id, 0)
                    + 1
                )

            selected_source: str | None = None

            for source_id in candidates:
                capacity = normalized_capacities.get(
                    source_id,
                    0,
                )

                if capacity <= 0:
                    continue

                if (
                    active_by_source.get(source_id, 0)
                    < capacity
                ):
                    selected_source = source_id
                    break

            if selected_source is None:
                raise SportsResourcePoolExhausted(
                    "Sports upstream capacity is exhausted."
                )

            lease_id = _required_identifier(
                self._lease_id_factory(),
                "Sports resource lease ID",
            )

            if lease_id in leases:
                raise SportsResourcePoolStateError(
                    "Sports resource lease identifier "
                    "is already active."
                )

            lease = SportsResourceLease(
                lease_id=lease_id,
                user_id=normalized_user,
                target_id=normalized_target,
                source_id=selected_source,
                created_at=now,
                last_seen_at=now,
            )

            leases[lease_id] = _lease_payload(
                lease
            )

            self._write_state(
                {
                    "version": SPORTS_RESOURCE_POOL_VERSION,
                    "leases": leases,
                }
            )

            return lease

    def heartbeat(
        self,
        *,
        lease_id: str,
        user_id: str,
    ) -> SportsResourceLease:
        """Refresh one owned Sports resource lease."""

        normalized_lease = _required_identifier(
            lease_id,
            "Sports resource lease ID",
        )
        normalized_user = _required_identifier(
            user_id,
            "Sports resource user ID",
        )
        now = self._clock()

        with self._locked():
            state = self._read_state()
            leases = self._prune_stale(
                state["leases"],
                now,
            )

            payload = leases.get(
                normalized_lease
            )

            if (
                payload is None
                or payload["user_id"]
                != normalized_user
            ):
                self._write_state(
                    {
                        "version": SPORTS_RESOURCE_POOL_VERSION,
                        "leases": leases,
                    }
                )
                raise SportsResourceLeaseNotFound(
                    "Sports resource lease was not found."
                )

            refreshed = SportsResourceLease(
                lease_id=normalized_lease,
                user_id=payload["user_id"],
                target_id=payload["target_id"],
                source_id=payload["source_id"],
                created_at=payload["created_at"],
                last_seen_at=now,
            )

            leases[normalized_lease] = (
                _lease_payload(refreshed)
            )

            self._write_state(
                {
                    "version": SPORTS_RESOURCE_POOL_VERSION,
                    "leases": leases,
                }
            )

            return refreshed

    def release(
        self,
        *,
        lease_id: str,
        user_id: str,
    ) -> bool:
        """Release one owned Sports resource lease."""

        normalized_lease = _required_identifier(
            lease_id,
            "Sports resource lease ID",
        )
        normalized_user = _required_identifier(
            user_id,
            "Sports resource user ID",
        )
        now = self._clock()

        with self._locked():
            state = self._read_state()
            leases = self._prune_stale(
                state["leases"],
                now,
            )

            payload = leases.get(
                normalized_lease
            )

            if (
                payload is None
                or payload["user_id"]
                != normalized_user
            ):
                self._write_state(
                    {
                        "version": SPORTS_RESOURCE_POOL_VERSION,
                        "leases": leases,
                    }
                )
                return False

            leases.pop(
                normalized_lease,
                None,
            )

            self._write_state(
                {
                    "version": SPORTS_RESOURCE_POOL_VERSION,
                    "leases": leases,
                }
            )

            return True

    def snapshot(
        self,
        *,
        capacities: Mapping[str, int],
    ) -> SportsResourcePoolSnapshot:
        """Return credential-safe current utilization."""

        normalized_capacities = _normalized_capacities(
            capacities
        )
        now = self._clock()

        with self._locked():
            state = self._read_state()
            leases = self._prune_stale(
                state["leases"],
                now,
            )

            self._write_state(
                {
                    "version": SPORTS_RESOURCE_POOL_VERSION,
                    "leases": leases,
                }
            )

        lease_objects = tuple(
            sorted(
                (
                    _lease_from_payload(
                        lease_id,
                        payload,
                    )
                    for lease_id, payload
                    in leases.items()
                ),
                key=lambda lease: (
                    lease.source_id,
                    lease.user_id,
                    lease.lease_id,
                ),
            )
        )

        active_by_source: dict[str, int] = {}

        for lease in lease_objects:
            active_by_source[lease.source_id] = (
                active_by_source.get(
                    lease.source_id,
                    0,
                )
                + 1
            )

        sources = tuple(
            SportsResourceSourceSnapshot(
                source_id=source_id,
                capacity=capacity,
                active=active_by_source.get(
                    source_id,
                    0,
                ),
                available=max(
                    0,
                    capacity
                    - active_by_source.get(
                        source_id,
                        0,
                    ),
                ),
            )
            for source_id, capacity
            in sorted(
                normalized_capacities.items()
            )
        )

        total_capacity = sum(
            source.capacity
            for source in sources
        )
        active = sum(
            source.active
            for source in sources
        )

        return SportsResourcePoolSnapshot(
            total_capacity=total_capacity,
            active=active,
            available=max(
                0,
                total_capacity - active,
            ),
            sources=sources,
            leases=lease_objects,
        )

    @contextmanager
    def _locked(
        self,
    ) -> Iterator[None]:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd = os.open(
            self.lock_path,
            os.O_CREAT | os.O_RDWR,
            SPORTS_RESOURCE_POOL_FILE_MODE,
        )

        try:
            # os.open() creation mode is filtered through the process umask.
            # The shared Sports runtime directory supplies the canonical group;
            # force the exact private group-writable mode after opening so all
            # Atlas API workers can coordinate on the same lock.
            os.fchmod(
                fd,
                SPORTS_RESOURCE_POOL_FILE_MODE,
            )

            fcntl.flock(
                fd,
                fcntl.LOCK_EX,
            )
            yield
        finally:
            fcntl.flock(
                fd,
                fcntl.LOCK_UN,
            )
            os.close(fd)

    def _read_state(
        self,
    ) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "version": SPORTS_RESOURCE_POOL_VERSION,
                "leases": {},
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
            raise SportsResourcePoolStateError(
                "Sports resource pool state "
                "is unreadable."
            ) from exc

        if not isinstance(payload, dict):
            raise SportsResourcePoolStateError(
                "Sports resource pool state "
                "must be an object."
            )

        if (
            payload.get("version")
            != SPORTS_RESOURCE_POOL_VERSION
        ):
            raise SportsResourcePoolStateError(
                "Sports resource pool state "
                "version is unsupported."
            )

        leases = payload.get("leases")

        if not isinstance(leases, dict):
            raise SportsResourcePoolStateError(
                "Sports resource pool leases "
                "must be an object."
            )

        validated: dict[
            str,
            dict[str, Any],
        ] = {}

        for lease_id, lease in leases.items():
            normalized_lease = (
                _required_identifier(
                    lease_id,
                    "Sports resource lease ID",
                )
            )

            if not isinstance(
                lease,
                dict,
            ):
                raise SportsResourcePoolStateError(
                    "Sports resource lease "
                    "entry is invalid."
                )

            expected_keys = {
                "user_id",
                "target_id",
                "source_id",
                "created_at",
                "last_seen_at",
            }

            if set(lease) != expected_keys:
                raise SportsResourcePoolStateError(
                    "Sports resource lease "
                    "schema is invalid."
                )

            user_id = _required_identifier(
                lease["user_id"],
                "Sports resource user ID",
            )
            target_id = _required_identifier(
                lease["target_id"],
                "Sports resource target ID",
            )
            source_id = _required_identifier(
                lease["source_id"],
                "Sports resource source ID",
            )

            created_at = _required_timestamp(
                lease["created_at"],
                "Sports resource created timestamp",
            )
            last_seen_at = _required_timestamp(
                lease["last_seen_at"],
                "Sports resource heartbeat timestamp",
            )

            if last_seen_at < created_at:
                raise SportsResourcePoolStateError(
                    "Sports resource lease timestamps "
                    "are inconsistent."
                )

            validated[normalized_lease] = {
                "user_id": user_id,
                "target_id": target_id,
                "source_id": source_id,
                "created_at": created_at,
                "last_seen_at": last_seen_at,
            }

        return {
            "version": SPORTS_RESOURCE_POOL_VERSION,
            "leases": validated,
        }

    def _write_state(
        self,
        state: Mapping[str, Any],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd, temporary_name = tempfile.mkstemp(
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=self.path.parent,
        )

        temporary = Path(
            temporary_name
        )

        try:
            # mkstemp() creates a private 0600 file. Promote it to the
            # canonical private shared-runtime mode before atomically
            # replacing the authoritative Sports resource-pool state.
            os.fchmod(
                fd,
                SPORTS_RESOURCE_POOL_FILE_MODE,
            )

            with os.fdopen(
                fd,
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
                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temporary,
                self.path,
            )
        except Exception:
            try:
                temporary.unlink(
                    missing_ok=True
                )
            finally:
                raise

    def _prune_stale(
        self,
        leases: dict[str, dict[str, Any]],
        now: float,
    ) -> dict[str, dict[str, Any]]:
        return {
            lease_id: payload
            for lease_id, payload
            in leases.items()
            if (
                now
                - payload["last_seen_at"]
                < self.ttl_seconds
            )
        }


def _normalized_candidates(
    values: Sequence[str],
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = _required_identifier(
            value,
            "Sports resource candidate source ID",
        )

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(normalized)

    return tuple(result)


def _normalized_capacities(
    capacities: Mapping[str, int],
) -> dict[str, int]:
    normalized: dict[str, int] = {}

    for source_id, capacity in capacities.items():
        key = _required_identifier(
            source_id,
            "Sports resource source ID",
        )

        if (
            isinstance(capacity, bool)
            or not isinstance(capacity, int)
            or capacity < 0
        ):
            raise ValueError(
                "Sports resource source capacity "
                "must be a non-negative integer."
            )

        normalized[key] = capacity

    return normalized


def _required_identifier(
    value: object,
    label: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            f"{label} must be a string."
        )

    normalized = value.strip()

    if (
        not normalized
        or len(normalized) > 256
        or any(
            ord(character) < 32
            for character in normalized
        )
    ):
        raise ValueError(
            f"{label} is invalid."
        )

    return normalized


def _required_timestamp(
    value: object,
    label: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
    ):
        raise SportsResourcePoolStateError(
            f"{label} is invalid."
        )

    return float(value)


def _lease_payload(
    lease: SportsResourceLease,
) -> dict[str, Any]:
    return {
        "user_id": lease.user_id,
        "target_id": lease.target_id,
        "source_id": lease.source_id,
        "created_at": lease.created_at,
        "last_seen_at": lease.last_seen_at,
    }


def _lease_from_payload(
    lease_id: str,
    payload: Mapping[str, Any],
) -> SportsResourceLease:
    return SportsResourceLease(
        lease_id=lease_id,
        user_id=str(
            payload["user_id"]
        ),
        target_id=str(
            payload["target_id"]
        ),
        source_id=str(
            payload["source_id"]
        ),
        created_at=float(
            payload["created_at"]
        ),
        last_seen_at=float(
            payload["last_seen_at"]
        ),
    )


__all__ = [
    "DEFAULT_SPORTS_RESOURCE_LEASE_TTL_SECONDS",
    "SPORTS_RESOURCE_POOL_VERSION",
    "SportsResourceLease",
    "SportsResourceLeaseNotFound",
    "SportsResourcePool",
    "SportsResourcePoolError",
    "SportsResourcePoolExhausted",
    "SportsResourceUserLimitExceeded",
    "SportsResourcePoolSnapshot",
    "SportsResourcePoolStateError",
    "SportsResourceSourceSnapshot",
]
