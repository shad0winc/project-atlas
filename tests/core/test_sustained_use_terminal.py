"""Tests for the Q.6 Runtime Bus terminal convergence foundation."""

from dataclasses import replace

import pytest

from atlas.sustained_use import (
    RuntimeBusObservation,
    RuntimeBusTerminalProbe,
    TERMINAL_CONVERGENCE_TIMEOUT_SECONDS,
    evaluate_runtime_bus_terminal_convergence,
)


def bus(
    *,
    journal: int,
    cursor: int,
    heartbeat: int = 1,
) -> RuntimeBusObservation:
    return RuntimeBusObservation(
        journal_lines=journal,
        cursor_value=cursor,
        journal_uid=1000,
        journal_gid=20000,
        journal_mode=640,
        journal_readable=True,
        journal_writable=False,
        heartbeat_age_seconds=heartbeat,
    )


def probe(
    elapsed: int,
    *,
    journal: int,
    cursor: int,
    heartbeat: int = 1,
) -> RuntimeBusTerminalProbe:
    return RuntimeBusTerminalProbe(
        elapsed_seconds=elapsed,
        runtime_bus=bus(
            journal=journal,
            cursor=cursor,
            heartbeat=heartbeat,
        ),
    )


def evaluate(
    *values: RuntimeBusTerminalProbe,
    target: int = 10,
    timeout: int = TERMINAL_CONVERGENCE_TIMEOUT_SECONDS,
):
    return evaluate_runtime_bus_terminal_convergence(
        tuple(values),
        target_journal_lines=target,
        timeout_seconds=timeout,
    )


def test_terminal_probe_round_trip() -> None:
    value = probe(
        30,
        journal=12,
        cursor=11,
    )

    restored = RuntimeBusTerminalProbe.from_dict(
        value.to_dict()
    )

    assert restored == value


def test_terminal_target_already_consumed_passes() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=10,
        )
    )

    assert result.passed is True
    assert result.status == "passed"
    assert result.failed_codes == ()


def test_terminal_backlog_one_can_converge() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=9,
        ),
        probe(
            30,
            journal=10,
            cursor=10,
        ),
    )

    assert result.passed is True
    assert result.final_cursor_value == 10
    assert result.probe_count == 2


def test_terminal_new_events_after_target_do_not_block_pass() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=9,
        ),
        probe(
            30,
            journal=14,
            cursor=10,
        ),
    )

    assert result.passed is True
    assert result.target_journal_lines == 10
    assert result.final_journal_lines == 14
    assert result.final_cursor_value == 10


def test_terminal_progress_before_timeout_is_pending() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=7,
        ),
        probe(
            60,
            journal=12,
            cursor=9,
        ),
    )

    assert result.pending is True
    assert result.passed is False
    assert result.failed is False
    assert result.failed_codes == ()


def test_terminal_timeout_without_target_is_failure() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=7,
        ),
        probe(
            60,
            journal=11,
            cursor=8,
        ),
        probe(
            180,
            journal=12,
            cursor=9,
        ),
    )

    assert result.failed is True
    assert result.failed_codes == (
        "runtime_bus.terminal.timeout",
    )


def test_terminal_stagnant_cursor_times_out() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=9,
        ),
        probe(
            180,
            journal=13,
            cursor=9,
        ),
    )

    assert result.failed_codes == (
        "runtime_bus.terminal.timeout",
    )


def test_terminal_cursor_regression_is_hard_failure() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=8,
        ),
        probe(
            30,
            journal=11,
            cursor=7,
        ),
    )

    assert result.failed_codes == (
        "runtime_bus.terminal.cursor_regression",
    )


def test_terminal_journal_regression_is_hard_failure() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=8,
        ),
        probe(
            30,
            journal=9,
            cursor=8,
        ),
    )

    assert result.failed_codes == (
        "runtime_bus.terminal.journal_regression",
    )


def test_terminal_stale_heartbeat_is_hard_failure() -> None:
    from atlas.sustained_use import MAX_HEARTBEAT_AGE_SECONDS

    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=9,
        ),
        probe(
            30,
            journal=11,
            cursor=9,
            heartbeat=MAX_HEARTBEAT_AGE_SECONDS + 1,
        ),
    )

    assert result.failed_codes == (
        "runtime_bus.terminal.heartbeat_stale",
    )


def test_terminal_target_must_equal_initial_journal_tail() -> None:
    result = evaluate_runtime_bus_terminal_convergence(
        (
            probe(
                0,
                journal=10,
                cursor=9,
            ),
        ),
        target_journal_lines=11,
    )

    assert result.failed_codes == (
        "runtime_bus.terminal.target_mismatch",
    )


def test_terminal_initial_probe_must_be_at_elapsed_zero() -> None:
    result = evaluate(
        probe(
            1,
            journal=10,
            cursor=9,
        )
    )

    assert result.failed_codes == (
        "runtime_bus.terminal.initial_elapsed",
    )


def test_terminal_elapsed_time_cannot_regress() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=7,
        ),
        probe(
            60,
            journal=11,
            cursor=8,
        ),
        probe(
            30,
            journal=12,
            cursor=9,
        ),
    )

    assert result.failed_codes == (
        "runtime_bus.terminal.time_regression",
    )


def test_terminal_evaluation_serializes_contract() -> None:
    result = evaluate(
        probe(
            0,
            journal=10,
            cursor=10,
        )
    )

    assert result.to_dict() == {
        "status": "passed",
        "passed": True,
        "failed": False,
        "pending": False,
        "target_journal_lines": 10,
        "timeout_seconds": 180,
        "max_heartbeat_age_seconds": (
            result.max_heartbeat_age_seconds
        ),
        "probe_count": 1,
        "final_elapsed_seconds": 0,
        "final_journal_lines": 10,
        "final_cursor_value": 10,
        "failed_codes": [],
    }


def test_terminal_probe_requires_runtime_bus_observation() -> None:
    with pytest.raises(
        TypeError,
        match="runtime_bus must be a RuntimeBusObservation",
    ):
        RuntimeBusTerminalProbe(
            elapsed_seconds=0,
            runtime_bus=object(),
        )


def test_terminal_requires_tuple() -> None:
    with pytest.raises(
        TypeError,
        match="probes must be a tuple",
    ):
        evaluate_runtime_bus_terminal_convergence(
            [
                probe(
                    0,
                    journal=10,
                    cursor=10,
                )
            ],
            target_journal_lines=10,
        )


def test_terminal_requires_non_empty_probes() -> None:
    with pytest.raises(
        ValueError,
        match="probes cannot be empty",
    ):
        evaluate_runtime_bus_terminal_convergence(
            (),
            target_journal_lines=10,
        )


def test_terminal_timeout_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="timeout_seconds must be greater than zero",
    ):
        evaluate_runtime_bus_terminal_convergence(
            (
                probe(
                    0,
                    journal=10,
                    cursor=10,
                ),
            ),
            target_journal_lines=10,
            timeout_seconds=0,
        )
