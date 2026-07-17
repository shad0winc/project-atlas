#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import recordings
from providers.thesportsdb import TheSportsDBProvider
from resolver import resolve_subscribed_games


def pass_check(message: str) -> None:
    print(f"PASS {message}")


def fail_check(message: str) -> None:
    print(f"FAIL {message}", file=sys.stderr)
    raise AssertionError(message)


def assert_equal(
    actual: Any,
    expected: Any,
    message: str,
) -> None:
    if actual != expected:
        fail_check(
            f"{message}: expected {expected!r}, "
            f"received {actual!r}"
        )

    pass_check(message)


def assert_true(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        fail_check(message)

    pass_check(message)


def build_provider_event() -> dict[str, Any]:
    start_time = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
    ).replace(
        microsecond=0
    )

    return {
        "idEvent": "atlas-provider-event-001",
        "idLeague": "atlas-league-001",
        "strEvent": "Atlas Home vs Atlas Away",
        "strSport": "Test Sport",
        "strLeague": "Atlas Test League",
        "strHomeTeam": "Atlas Home",
        "strAwayTeam": "Atlas Away",
        "idHomeTeam": "atlas-team-home",
        "idAwayTeam": "atlas-team-away",
        "strTimestamp": start_time.isoformat(),
        "strStatus": "Not Started",
    }


def build_subscription(
    event_id: str,
) -> dict[str, Any]:
    return {
        "subscription_id": "sub-provider-test",
        "type": "event",
        "provider": "thesportsdb",
        "id": event_id,
        "name": "Atlas Provider Test Event",
        "user": "integration-user",
        "enabled": True,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def read_persisted_recordings(
    path: Path,
) -> dict[str, dict[str, Any]]:
    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, dict):
        fail_check(
            "Persisted recordings payload is a dictionary"
        )

    return data


def run_matching_subscription_test(
    recordings_file: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    print()
    print("Matching Event Subscription Test")
    print("--------------------------------")

    provider = TheSportsDBProvider()

    game = provider.normalize_event(
        build_provider_event()
    )

    game["stream_url"] = (
        "https://example.invalid/"
        "atlas-provider-test.m3u8"
    )
    game["duration_minutes"] = 180

    subscription = build_subscription(
        str(game["provider_event_id"])
    )

    resolved_games = resolve_subscribed_games(
        [game],
        [subscription],
    )

    assert_equal(
        len(resolved_games),
        1,
        "Resolver returned one subscribed game",
    )

    resolved_game = resolved_games[0]

    assert_equal(
        resolved_game["id"],
        "thesportsdb-atlas-provider-event-001",
        "Provider event normalized to stable Atlas ID",
    )
    assert_equal(
        resolved_game["subscription_count"],
        1,
        "Resolver stored subscription count",
    )
    assert_equal(
        resolved_game["subscription_ids"],
        ["sub-provider-test"],
        "Resolver stored subscription ID",
    )
    assert_equal(
        resolved_game["subscription_types"],
        ["event"],
        "Resolver stored subscription type",
    )
    assert_equal(
        resolved_game["subscribed_users"],
        ["integration-user"],
        "Resolver stored subscribed user",
    )

    planned = recordings.plan_recordings(
        resolved_games
    )

    recording_id = (
        "recording-"
        "thesportsdb-atlas-provider-event-001"
    )

    assert_equal(
        len(planned),
        1,
        "Planner created one recording",
    )
    assert_true(
        recording_id in planned,
        "Planner generated stable recording ID",
    )

    recording = planned[recording_id]

    assert_equal(
        recording["status"],
        "pending",
        "Recording starts in pending state",
    )
    assert_equal(
        recording["provider"],
        "thesportsdb",
        "Recording preserved provider",
    )
    assert_equal(
        recording["provider_event_id"],
        "atlas-provider-event-001",
        "Recording preserved provider event ID",
    )
    assert_equal(
        recording["stream_url"],
        game["stream_url"],
        "Recording preserved stream URL",
    )
    assert_equal(
        recording["subscription_count"],
        1,
        "Recording preserved subscription count",
    )
    assert_equal(
        recording["subscription_ids"],
        ["sub-provider-test"],
        "Recording preserved subscription IDs",
    )
    assert_equal(
        recording["subscribed_users"],
        ["integration-user"],
        "Recording preserved subscribed users",
    )
    assert_true(
        bool(recording["scheduled_start"]),
        "Recording contains scheduled start",
    )
    assert_true(
        bool(recording["scheduled_end"]),
        "Recording contains scheduled end",
    )
    assert_true(
        recordings_file.exists(),
        "Recordings file created",
    )

    persisted = read_persisted_recordings(
        recordings_file
    )

    assert_equal(
        persisted,
        planned,
        "Recording plan persisted to recordings file",
    )
    assert_equal(
        recordings.load_recordings(),
        planned,
        "Recording plan reload matches persisted state",
    )

    return resolved_game, recording


def run_duplicate_planning_test(
    resolved_game: dict[str, Any],
    original_recording: dict[str, Any],
) -> None:
    print()
    print("Duplicate Planning Test")
    print("-----------------------")

    recording_id = str(
        original_recording["id"]
    )
    original_created_at = str(
        original_recording["created_at"]
    )
    original_updated_at = str(
        original_recording["updated_at"]
    )

    time.sleep(0.01)

    planned_again = recordings.plan_recordings(
        [resolved_game]
    )

    assert_equal(
        len(planned_again),
        1,
        "Duplicate planning retained one recording",
    )

    updated_recording = planned_again[
        recording_id
    ]

    assert_equal(
        updated_recording["created_at"],
        original_created_at,
        "Duplicate planning preserved creation time",
    )
    assert_equal(
        updated_recording["status"],
        "pending",
        "Duplicate planning preserved recording status",
    )
    assert_true(
        str(updated_recording["updated_at"])
        != original_updated_at,
        "Duplicate planning refreshed update time",
    )


def run_unmatched_subscription_test(
    recordings_file: Path,
) -> None:
    print()
    print("Unmatched Subscription Test")
    print("---------------------------")

    recordings.write_recordings({})

    provider = TheSportsDBProvider()

    game = provider.normalize_event(
        build_provider_event()
    )

    game["stream_url"] = (
        "https://example.invalid/"
        "atlas-provider-test.m3u8"
    )

    unmatched_subscription = build_subscription(
        "different-provider-event"
    )

    resolved_games = resolve_subscribed_games(
        [game],
        [unmatched_subscription],
    )

    assert_equal(
        resolved_games,
        [],
        "Resolver excluded unmatched event",
    )

    planned = recordings.plan_recordings(
        resolved_games
    )

    assert_equal(
        planned,
        {},
        "Planner created no unmatched recordings",
    )

    persisted = read_persisted_recordings(
        recordings_file
    )

    assert_equal(
        persisted,
        {},
        "Empty unmatched plan persisted correctly",
    )


def main() -> int:
    print("Project Atlas")
    print("Sports Provider Integration Tests")
    print("=================================")

    with tempfile.TemporaryDirectory(
        prefix="atlas-sports-provider-"
    ) as temporary_directory:
        temporary_path = Path(
            temporary_directory
        )

        recordings_file = (
            temporary_path
            / "recordings.json"
        )

        original_recordings_file = (
            recordings.RECORDINGS_FILE
        )

        recordings.RECORDINGS_FILE = (
            recordings_file
        )

        try:
            (
                resolved_game,
                original_recording,
            ) = run_matching_subscription_test(
                recordings_file
            )

            run_duplicate_planning_test(
                resolved_game,
                original_recording,
            )

            run_unmatched_subscription_test(
                recordings_file
            )

        finally:
            recordings.RECORDINGS_FILE = (
                original_recordings_file
            )

    print()
    print(
        "Sports Provider Integration Tests: PASS"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError:
        print()
        print(
            "Sports Provider Integration Tests: FAIL",
            file=sys.stderr,
        )
        raise SystemExit(1)
