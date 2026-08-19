from __future__ import annotations

from datetime import datetime, timezone

import pytest

from atlas.sustained_use import (
    SustainedUseContract,
    SustainedUseSession,
)
from atlas.sustained_use.cadence import (
    CadenceAction,
    DEFAULT_CADENCE_LATENESS_SECONDS,
    SustainedUseCadenceError,
    cadence_decision,
    fixed_sample_time,
)


COMMIT = "dad7c6174213200199b06d0d5e33f94ffc2ac401"


def session() -> SustainedUseSession:
    contract = SustainedUseContract(
        git_commit=COMMIT,
    )

    return SustainedUseSession.from_contract(
        run_id="q6-fixed-cadence-test",
        started_at="2026-08-17T23:20:28.663215Z",
        scheduled_end_at="2026-08-19T23:20:28.663215Z",
        contract=contract,
    )


def utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
) -> datetime:
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        second,
        tzinfo=timezone.utc,
    )


def test_default_lateness_window_is_bounded() -> None:
    assert DEFAULT_CADENCE_LATENESS_SECONDS == 180
    assert DEFAULT_CADENCE_LATENESS_SECONDS < 900


def test_sample_one_is_exactly_t0() -> None:
    value = fixed_sample_time(
        session(),
        1,
    )

    assert value == datetime.fromisoformat(
        "2026-08-17T23:20:28.663215+00:00"
    )


def test_sample_two_is_t0_plus_one_interval() -> None:
    value = fixed_sample_time(
        session(),
        2,
    )

    assert value == datetime.fromisoformat(
        "2026-08-17T23:35:28.663215+00:00"
    )


def test_sample_193_is_exact_scheduled_end() -> None:
    value = fixed_sample_time(
        session(),
        193,
    )

    assert value == datetime.fromisoformat(
        "2026-08-19T23:20:28.663215+00:00"
    )


def test_next_slot_is_derived_from_t0_not_previous_success() -> None:
    value = fixed_sample_time(
        session(),
        3,
    )

    assert value == datetime.fromisoformat(
        "2026-08-17T23:50:28.663215+00:00"
    )


def test_before_next_slot_is_not_due() -> None:
    decision = cadence_decision(
        session=session(),
        sample_count=1,
        now=datetime.fromisoformat(
            "2026-08-17T23:35:27+00:00"
        ),
    )

    assert decision.action is CadenceAction.NOT_DUE
    assert decision.next_sample_number == 2
    assert decision.expected_at == (
        "2026-08-17T23:35:28.663215Z"
    )
    assert decision.lateness_seconds < 0


def test_exact_slot_is_sample() -> None:
    decision = cadence_decision(
        session=session(),
        sample_count=1,
        now=datetime.fromisoformat(
            "2026-08-17T23:35:28.663215+00:00"
        ),
    )

    assert decision.action is CadenceAction.SAMPLE
    assert decision.lateness_seconds == 0


def test_dispatcher_jitter_does_not_move_next_slot() -> None:
    second = cadence_decision(
        session=session(),
        sample_count=1,
        now=datetime.fromisoformat(
            "2026-08-17T23:36:59+00:00"
        ),
    )

    assert second.action is CadenceAction.SAMPLE

    third = cadence_decision(
        session=session(),
        sample_count=2,
        now=datetime.fromisoformat(
            "2026-08-17T23:50:59+00:00"
        ),
    )

    assert third.action is CadenceAction.SAMPLE
    assert third.expected_at == (
        "2026-08-17T23:50:28.663215Z"
    )


def test_lateness_at_tolerance_is_sample() -> None:
    expected = fixed_sample_time(
        session(),
        2,
    )

    decision = cadence_decision(
        session=session(),
        sample_count=1,
        now=expected.replace(
            microsecond=663215,
        )
        + __import__("datetime").timedelta(
            seconds=180,
        ),
    )

    assert decision.action is CadenceAction.SAMPLE


def test_lateness_beyond_tolerance_is_missed() -> None:
    expected = fixed_sample_time(
        session(),
        2,
    )

    decision = cadence_decision(
        session=session(),
        sample_count=1,
        now=(
            expected
            + __import__("datetime").timedelta(
                seconds=181,
            )
        ),
    )

    assert decision.action is CadenceAction.MISSED
    assert decision.next_sample_number == 2


def test_entire_missed_slot_is_never_backfilled() -> None:
    decision = cadence_decision(
        session=session(),
        sample_count=1,
        now=datetime.fromisoformat(
            "2026-08-17T23:51:00+00:00"
        ),
    )

    assert decision.action is CadenceAction.MISSED
    assert decision.next_sample_number == 2

    # Critically, the decision does not jump ahead and pretend
    # that sample 3 can substitute for the missing sample 2.
    assert decision.expected_at == (
        "2026-08-17T23:35:28.663215Z"
    )


def test_repeated_polling_before_slot_remains_not_due() -> None:
    for second in (
        "2026-08-17T23:34:00+00:00",
        "2026-08-17T23:35:00+00:00",
        "2026-08-17T23:35:28+00:00",
    ):
        decision = cadence_decision(
            session=session(),
            sample_count=1,
            now=datetime.fromisoformat(second),
        )

        assert decision.action is CadenceAction.NOT_DUE


def test_complete_history_has_no_next_slot() -> None:
    decision = cadence_decision(
        session=session(),
        sample_count=193,
        now=datetime.fromisoformat(
            "2026-08-19T23:21:00+00:00"
        ),
    )

    assert decision.action is CadenceAction.COMPLETE
    assert decision.next_sample_number is None
    assert decision.expected_at is None
    assert decision.lateness_seconds is None


def test_sample_number_zero_is_invalid() -> None:
    with pytest.raises(
        SustainedUseCadenceError,
        match="outside",
    ):
        fixed_sample_time(
            session(),
            0,
        )


def test_sample_number_beyond_contract_is_invalid() -> None:
    with pytest.raises(
        SustainedUseCadenceError,
        match="outside",
    ):
        fixed_sample_time(
            session(),
            194,
        )


@pytest.mark.parametrize(
    "value",
    [
        -1,
        194,
    ],
)
def test_invalid_sample_count_is_rejected(
    value: int,
) -> None:
    with pytest.raises(
        SustainedUseCadenceError,
    ):
        cadence_decision(
            session=session(),
            sample_count=value,
            now=utc(
                2026,
                8,
                17,
                23,
                20,
                29,
            ),
        )


def test_naive_now_is_rejected() -> None:
    with pytest.raises(
        SustainedUseCadenceError,
        match="timezone",
    ):
        cadence_decision(
            session=session(),
            sample_count=1,
            now=datetime(
                2026,
                8,
                17,
                23,
                35,
                28,
            ),
        )


@pytest.mark.parametrize(
    "value",
    [
        -1,
        900,
        901,
    ],
)
def test_lateness_window_must_be_less_than_interval(
    value: int,
) -> None:
    with pytest.raises(
        SustainedUseCadenceError,
    ):
        cadence_decision(
            session=session(),
            sample_count=1,
            now=utc(
                2026,
                8,
                17,
                23,
                35,
                29,
            ),
            max_lateness_seconds=value,
        )


def test_decision_serializer_is_stable() -> None:
    decision = cadence_decision(
        session=session(),
        sample_count=1,
        now=datetime.fromisoformat(
            "2026-08-17T23:36:00+00:00"
        ),
    )

    payload = decision.to_dict()

    assert payload["action"] == "sample"
    assert payload["sample_count"] == 1
    assert payload["next_sample_number"] == 2
    assert payload["expected_at"] == (
        "2026-08-17T23:35:28.663215Z"
    )
