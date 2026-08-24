from atlas.sustained_use import RuntimeBusObservation
from atlas.sustained_use.lifecycle import _observe_runtime_bus_terminal_convergence

def bus(*, journal: int, cursor: int, heartbeat: int = 1) -> RuntimeBusObservation:
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

class Clock:
    def __init__(self) -> None:
        self.value = 0.0
    def monotonic(self) -> float:
        return self.value
    def sleep(self, seconds: float) -> None:
        self.value += seconds

def test_terminal_observer_returns_immediate_pass_when_caught_up() -> None:
    calls = 0
    def collector() -> RuntimeBusObservation:
        nonlocal calls
        calls += 1
        return bus(journal=10, cursor=10)
    result = _observe_runtime_bus_terminal_convergence(
        bus(journal=10, cursor=10), collector=collector
    )
    assert result.passed is True
    assert result.probe_count == 1
    assert calls == 0

def test_terminal_observer_converges_to_frozen_target() -> None:
    clock = Clock()
    observations = iter((bus(journal=14, cursor=9), bus(journal=15, cursor=10)))
    result = _observe_runtime_bus_terminal_convergence(
        bus(journal=10, cursor=9),
        collector=lambda: next(observations),
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
        timeout_seconds=180,
        poll_seconds=1,
    )
    assert result.passed is True
    assert result.target_journal_lines == 10
    assert result.final_journal_lines == 15
    assert result.final_cursor_value == 10
    assert result.probe_count == 3

def test_terminal_observer_times_out_fail_closed() -> None:
    clock = Clock()
    result = _observe_runtime_bus_terminal_convergence(
        bus(journal=10, cursor=9),
        collector=lambda: bus(journal=20, cursor=9),
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
        timeout_seconds=3,
        poll_seconds=1,
    )
    assert result.failed is True
    assert result.failed_codes == ("runtime_bus.terminal.timeout",)
    assert result.final_elapsed_seconds == 3

def test_terminal_observer_allows_post_target_events() -> None:
    clock = Clock()
    result = _observe_runtime_bus_terminal_convergence(
        bus(journal=3917, cursor=3916),
        collector=lambda: bus(journal=3925, cursor=3917),
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
        timeout_seconds=180,
        poll_seconds=1,
    )
    assert result.passed is True
    assert result.target_journal_lines == 3917
    assert result.final_journal_lines == 3925
    assert result.final_cursor_value == 3917
