"""Bounded Runtime Bus terminal convergence for Q.6 finalization.

The 48-hour Q.6 history remains immutable evidence.  This module models a
separate terminal proof: freeze the Runtime Bus journal tail at the start of
finalization, then prove that Notifications consumes through that exact target
within a bounded observation window.

Events published after the frozen target do not prevent convergence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .evaluator import MAX_HEARTBEAT_AGE_SECONDS
from .models import RuntimeBusObservation


TERMINAL_CONVERGENCE_TIMEOUT_SECONDS = 180

_STATUS_PENDING = "pending"
_STATUS_PASSED = "passed"
_STATUS_FAILED = "failed"

_VALID_STATUSES = frozenset(
    {
        _STATUS_PENDING,
        _STATUS_PASSED,
        _STATUS_FAILED,
    }
)


def _non_negative_integer(
    value: object,
    *,
    field: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")

    if value < 0:
        raise ValueError(f"{field} cannot be negative")

    return value


def _positive_integer(
    value: object,
    *,
    field: str,
) -> int:
    normalized = _non_negative_integer(
        value,
        field=field,
    )

    if normalized == 0:
        raise ValueError(f"{field} must be greater than zero")

    return normalized


@dataclass(frozen=True)
class RuntimeBusTerminalProbe:
    """One read-only observation in the terminal convergence window."""

    elapsed_seconds: int
    runtime_bus: RuntimeBusObservation

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "elapsed_seconds",
            _non_negative_integer(
                self.elapsed_seconds,
                field="elapsed_seconds",
            ),
        )

        if not isinstance(
            self.runtime_bus,
            RuntimeBusObservation,
        ):
            raise TypeError(
                "runtime_bus must be a RuntimeBusObservation"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the terminal probe."""

        return {
            "elapsed_seconds": self.elapsed_seconds,
            "runtime_bus": self.runtime_bus.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "RuntimeBusTerminalProbe":
        """Build a terminal probe from serialized data."""

        if not isinstance(value, Mapping):
            raise TypeError(
                "RuntimeBusTerminalProbe payload must be an object"
            )

        runtime_bus = value.get("runtime_bus")

        if not isinstance(runtime_bus, Mapping):
            raise TypeError("runtime_bus must be an object")

        return cls(
            elapsed_seconds=value.get("elapsed_seconds"),
            runtime_bus=RuntimeBusObservation.from_dict(
                runtime_bus
            ),
        )


@dataclass(frozen=True)
class RuntimeBusTerminalEvaluation:
    """Result of one bounded terminal convergence assessment."""

    status: str
    target_journal_lines: int
    timeout_seconds: int
    max_heartbeat_age_seconds: int
    probe_count: int
    final_elapsed_seconds: int
    final_journal_lines: int
    final_cursor_value: int
    failed_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status, str)
            or self.status not in _VALID_STATUSES
        ):
            raise ValueError(
                "status must be pending, passed, or failed"
            )

        for field in (
            "target_journal_lines",
            "max_heartbeat_age_seconds",
            "probe_count",
            "final_elapsed_seconds",
            "final_journal_lines",
            "final_cursor_value",
        ):
            object.__setattr__(
                self,
                field,
                _non_negative_integer(
                    getattr(self, field),
                    field=field,
                ),
            )

        object.__setattr__(
            self,
            "timeout_seconds",
            _positive_integer(
                self.timeout_seconds,
                field="timeout_seconds",
            ),
        )

        if self.probe_count == 0:
            raise ValueError(
                "probe_count must be greater than zero"
            )

        if not isinstance(self.failed_codes, tuple):
            raise TypeError("failed_codes must be a tuple")

        if not all(
            isinstance(code, str) and code.strip()
            for code in self.failed_codes
        ):
            raise ValueError(
                "failed_codes must contain non-empty strings"
            )

        if (
            self.status == _STATUS_FAILED
            and not self.failed_codes
        ):
            raise ValueError(
                "failed terminal evaluation requires failed_codes"
            )

        if (
            self.status != _STATUS_FAILED
            and self.failed_codes
        ):
            raise ValueError(
                "non-failed terminal evaluation cannot have failed_codes"
            )

    @property
    def passed(self) -> bool:
        """Return whether terminal convergence is certified."""

        return self.status == _STATUS_PASSED

    @property
    def failed(self) -> bool:
        """Return whether terminal convergence has hard-failed."""

        return self.status == _STATUS_FAILED

    @property
    def pending(self) -> bool:
        """Return whether more bounded observations are required."""

        return self.status == _STATUS_PENDING

    def to_dict(self) -> dict[str, Any]:
        """Serialize the terminal evaluation."""

        return {
            "status": self.status,
            "passed": self.passed,
            "failed": self.failed,
            "pending": self.pending,
            "target_journal_lines": self.target_journal_lines,
            "timeout_seconds": self.timeout_seconds,
            "max_heartbeat_age_seconds": (
                self.max_heartbeat_age_seconds
            ),
            "probe_count": self.probe_count,
            "final_elapsed_seconds": self.final_elapsed_seconds,
            "final_journal_lines": self.final_journal_lines,
            "final_cursor_value": self.final_cursor_value,
            "failed_codes": list(self.failed_codes),
        }


def evaluate_runtime_bus_terminal_convergence(
    probes: tuple[RuntimeBusTerminalProbe, ...],
    *,
    target_journal_lines: int,
    timeout_seconds: int = TERMINAL_CONVERGENCE_TIMEOUT_SECONDS,
    max_heartbeat_age_seconds: int = MAX_HEARTBEAT_AGE_SECONDS,
) -> RuntimeBusTerminalEvaluation:
    """Assess bounded convergence through a frozen Runtime Bus target.

    The target is the journal tail observed at elapsed time zero.  The live
    journal may continue growing after that boundary.  Certification succeeds
    as soon as the Notifications cursor reaches or exceeds the frozen target.

    Monotonic journal/cursor behavior and a fresh Notifications heartbeat are
    required throughout the observations used to reach the terminal result.
    """

    if not isinstance(probes, tuple):
        raise TypeError("probes must be a tuple")

    if not probes:
        raise ValueError("probes cannot be empty")

    if not all(
        isinstance(item, RuntimeBusTerminalProbe)
        for item in probes
    ):
        raise TypeError(
            "probes must contain RuntimeBusTerminalProbe values"
        )

    target = _non_negative_integer(
        target_journal_lines,
        field="target_journal_lines",
    )

    timeout = _positive_integer(
        timeout_seconds,
        field="timeout_seconds",
    )

    max_heartbeat = _non_negative_integer(
        max_heartbeat_age_seconds,
        field="max_heartbeat_age_seconds",
    )

    first = probes[0]

    if first.elapsed_seconds != 0:
        return _evaluation(
            _STATUS_FAILED,
            probes,
            target=target,
            timeout=timeout,
            max_heartbeat=max_heartbeat,
            failed_codes=(
                "runtime_bus.terminal.initial_elapsed",
            ),
        )

    if first.runtime_bus.journal_lines != target:
        return _evaluation(
            _STATUS_FAILED,
            probes,
            target=target,
            timeout=timeout,
            max_heartbeat=max_heartbeat,
            failed_codes=(
                "runtime_bus.terminal.target_mismatch",
            ),
        )

    previous = first

    for index, probe in enumerate(probes):
        bus = probe.runtime_bus

        if index > 0:
            if probe.elapsed_seconds < previous.elapsed_seconds:
                return _evaluation(
                    _STATUS_FAILED,
                    probes[: index + 1],
                    target=target,
                    timeout=timeout,
                    max_heartbeat=max_heartbeat,
                    failed_codes=(
                        "runtime_bus.terminal.time_regression",
                    ),
                )

            if (
                bus.journal_lines
                < previous.runtime_bus.journal_lines
            ):
                return _evaluation(
                    _STATUS_FAILED,
                    probes[: index + 1],
                    target=target,
                    timeout=timeout,
                    max_heartbeat=max_heartbeat,
                    failed_codes=(
                        "runtime_bus.terminal.journal_regression",
                    ),
                )

            if (
                bus.cursor_value
                < previous.runtime_bus.cursor_value
            ):
                return _evaluation(
                    _STATUS_FAILED,
                    probes[: index + 1],
                    target=target,
                    timeout=timeout,
                    max_heartbeat=max_heartbeat,
                    failed_codes=(
                        "runtime_bus.terminal.cursor_regression",
                    ),
                )

        if bus.heartbeat_age_seconds > max_heartbeat:
            return _evaluation(
                _STATUS_FAILED,
                probes[: index + 1],
                target=target,
                timeout=timeout,
                max_heartbeat=max_heartbeat,
                failed_codes=(
                    "runtime_bus.terminal.heartbeat_stale",
                ),
            )

        if probe.elapsed_seconds > timeout:
            return _evaluation(
                _STATUS_FAILED,
                probes[: index + 1],
                target=target,
                timeout=timeout,
                max_heartbeat=max_heartbeat,
                failed_codes=(
                    "runtime_bus.terminal.timeout",
                ),
            )

        if bus.cursor_value >= target:
            return _evaluation(
                _STATUS_PASSED,
                probes[: index + 1],
                target=target,
                timeout=timeout,
                max_heartbeat=max_heartbeat,
            )

        if probe.elapsed_seconds == timeout:
            return _evaluation(
                _STATUS_FAILED,
                probes[: index + 1],
                target=target,
                timeout=timeout,
                max_heartbeat=max_heartbeat,
                failed_codes=(
                    "runtime_bus.terminal.timeout",
                ),
            )

        previous = probe

    return _evaluation(
        _STATUS_PENDING,
        probes,
        target=target,
        timeout=timeout,
        max_heartbeat=max_heartbeat,
    )


def _evaluation(
    status: str,
    probes: tuple[RuntimeBusTerminalProbe, ...],
    *,
    target: int,
    timeout: int,
    max_heartbeat: int,
    failed_codes: tuple[str, ...] = (),
) -> RuntimeBusTerminalEvaluation:
    final = probes[-1]

    return RuntimeBusTerminalEvaluation(
        status=status,
        target_journal_lines=target,
        timeout_seconds=timeout,
        max_heartbeat_age_seconds=max_heartbeat,
        probe_count=len(probes),
        final_elapsed_seconds=final.elapsed_seconds,
        final_journal_lines=final.runtime_bus.journal_lines,
        final_cursor_value=final.runtime_bus.cursor_value,
        failed_codes=failed_codes,
    )
