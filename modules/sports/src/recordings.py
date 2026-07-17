#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from recorder import (
    launch_recording,
    process_is_running,
    stop_recording,
)

RECORDINGS_FILE = Path(
    os.getenv(
        "SPORTS_RECORDINGS_FILE",
        "/mnt/storage/configs/sportyfin/recordings/recordings.json",
    )
)

PREROLL_MINUTES = int(
    os.getenv(
        "SPORTS_RECORDING_PREROLL_MINUTES",
        "5",
    )
)

POSTROLL_MINUTES = int(
    os.getenv(
        "SPORTS_RECORDING_POSTROLL_MINUTES",
        "15",
    )
)


def parse_timestamp(
    value: str,
) -> datetime:
    parsed = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def format_timestamp(
    value: datetime,
) -> str:
    return value.astimezone(
        timezone.utc
    ).isoformat()


def load_recordings() -> dict[str, dict[str, Any]]:
    if not RECORDINGS_FILE.exists():
        return {}

    try:
        data = json.loads(
            RECORDINGS_FILE.read_text(
                encoding="utf-8",
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {}

    if not isinstance(data, dict):
        return {}

    return {
        str(recording_id): recording
        for recording_id, recording in data.items()
        if isinstance(recording, dict)
    }


def write_recordings(
    recordings: dict[str, dict[str, Any]],
) -> None:
    RECORDINGS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = RECORDINGS_FILE.with_suffix(
        ".tmp"
    )

    temporary_file.write_text(
        json.dumps(
            recordings,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_file.replace(
        RECORDINGS_FILE
    )


def recording_id_for_game(
    game: dict[str, Any],
) -> str:
    return f"recording-{game['id']}"


def build_recording_plan(
    game: dict[str, Any],
) -> dict[str, Any] | None:
    stream_url = str(
        game.get(
            "stream_url",
            "",
        )
    ).strip()

    start_at = str(
        game.get(
            "start_at",
            "",
        )
    ).strip()

    if not stream_url or not start_at:
        return None

    start_time = parse_timestamp(
        start_at
    )

    duration_minutes = int(
        game.get(
            "duration_minutes",
            240,
        )
    )

    recording_start = (
        start_time
        - timedelta(
            minutes=PREROLL_MINUTES
        )
    )

    recording_end = (
        start_time
        + timedelta(
            minutes=(
                duration_minutes
                + POSTROLL_MINUTES
            )
        )
    )

    return {
        "id": recording_id_for_game(game),
        "game_id": game["id"],
        "provider": game.get("provider"),
        "provider_event_id": game.get(
            "provider_event_id"
        ),
        "game": game.get(
            "name",
            game["id"],
        ),
        "league": game.get("league"),
        "home_team": game.get("home_team"),
        "away_team": game.get("away_team"),
        "stream_url": stream_url,
        "scheduled_start": format_timestamp(
            recording_start
        ),
        "scheduled_end": format_timestamp(
            recording_end
        ),
        "status": "pending",
        "subscription_count": int(
            game.get(
                "subscription_count",
                0,
            )
        ),
        "subscription_ids": list(
            game.get(
                "subscription_ids",
                [],
            )
        ),
        "subscribed_users": list(
            game.get(
                "subscribed_users",
                [],
            )
        ),
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def plan_recordings(
    games: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    recordings = load_recordings()

    for game in games:
        plan = build_recording_plan(
            game
        )

        if plan is None:
            continue

        recording_id = plan["id"]

        existing = recordings.get(
            recording_id
        )

        if existing:
            updated = deepcopy(existing)

            for key, value in plan.items():
                if key in {
                    "created_at",
                    "status",
                }:
                    continue

                updated[key] = value

            updated["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            recordings[recording_id] = updated

        else:
            recordings[recording_id] = plan

    write_recordings(
        recordings
    )

    return recordings

def recording_status(
    recording: dict[str, Any],
    now: datetime,
) -> str:
    current_status = str(
        recording.get(
            "status",
            "pending",
        )
    )

    if current_status in {
        "completed",
        "failed",
        "cancelled",
    }:
        return current_status

    scheduled_start = parse_timestamp(
        str(
            recording[
                "scheduled_start"
            ]
        )
    )

    scheduled_end = parse_timestamp(
        str(
            recording[
                "scheduled_end"
            ]
        )
    )

    if current_status == "recording":
        pid = recording.get("pid")

        if now >= scheduled_end:
            return "completed"

        if not process_is_running(pid):
            return "failed"

        return "recording"

    if now >= scheduled_end:
        return "completed"

    if now >= scheduled_start:
        return "recording"

    return "pending"

def update_recording_statuses(
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    if now is None:
        now = datetime.now(
            timezone.utc
        )

    recordings = load_recordings()

    for recording_id, recording in recordings.items():
        previous_status = str(
            recording.get(
                "status",
                "pending",
            )
        )

        current_status = recording_status(
            recording,
            now,
        )

        if (
            previous_status == "pending"
            and current_status == "recording"
        ):
            try:
                launch_result = launch_recording(
                    recording
                )

                recording["pid"] = int(
                    launch_result["pid"]
                )
                recording["log_file"] = str(
                    launch_result["log_file"]
                )
                recording["output_file"] = str(
                    launch_result[
                        "output_file"
                    ]
                )
                recording["recorder_mode"] = str(
                    launch_result[
                        "recorder_mode"
                    ]
                )
                recording["recorder_command"] = list(
                    launch_result.get(
                        "command",
                        [],
                    )
                )
                recording["started_at"] = (
                    recording.get(
                        "started_at"
                    )
                    or format_timestamp(now)
                )
                recording["launch_error"] = None

            except Exception as exc:
                current_status = "failed"

                recording["failed_at"] = (
                    format_timestamp(now)
                )
                recording["failure_reason"] = (
                    "recorder_launch_failed"
                )
                recording["launch_error"] = str(
                    exc
                )

        if (
            previous_status == "recording"
            and current_status == "completed"
        ):
            pid = recording.get("pid")

            stopped = stop_recording(
                pid
            )

            if not stopped:
                current_status = "failed"

                recording["failed_at"] = (
                    format_timestamp(now)
                )
                recording["failure_reason"] = (
                    "recorder_stop_failed"
                )
            else:
                recording["completed_at"] = (
                    recording.get(
                        "completed_at"
                    )
                    or format_timestamp(now)
                )
                recording["stopped_at"] = (
                    format_timestamp(now)
                )

        if (
            previous_status == "recording"
            and current_status == "failed"
        ):
            recording["failed_at"] = (
                recording.get(
                    "failed_at"
                )
                or format_timestamp(now)
            )
            recording["failure_reason"] = (
                recording.get(
                    "failure_reason"
                )
                or "recorder_exited_early"
            )

        if (
            previous_status == "pending"
            and current_status == "completed"
        ):
            recording["completed_at"] = (
                recording.get(
                    "completed_at"
                )
                or format_timestamp(now)
            )

        if current_status != previous_status:
            recording["status"] = (
                current_status
            )
            recording["updated_at"] = (
                format_timestamp(now)
            )

        recordings[recording_id] = recording

    write_recordings(
        recordings
    )

    return recordings
