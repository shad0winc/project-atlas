#!/usr/bin/env python3

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import recorder
import recordings


TEST_ID = f"atlas-sports-scheduler-{uuid.uuid4().hex[:8]}"
TEST_ROOT = Path(
    tempfile.mkdtemp(
        prefix=f"{TEST_ID}-",
    )
)
TEST_RECORDINGS_FILE = TEST_ROOT / "recordings.json"
FIXTURE_FILE = TEST_ROOT / "fixture.mkv"

CLEANUP_PATHS: set[Path] = set()


def heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def check(
    condition: bool,
    description: str,
) -> None:
    if not condition:
        print(f"FAIL {description}")
        raise AssertionError(description)

    print(f"PASS {description}")


def timestamp(value: datetime) -> str:
    return value.astimezone(
        timezone.utc
    ).isoformat()


def create_fixture() -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=320x180:rate=15",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:sample_rate=48000",
        "-t",
        "1",
        "-c:v",
        "mpeg4",
        "-c:a",
        "aac",
        str(FIXTURE_FILE),
    ]

    subprocess.run(
        command,
        check=True,
    )

    check(
        FIXTURE_FILE.exists()
        and FIXTURE_FILE.stat().st_size > 0,
        "Deterministic scheduler fixture created",
    )


def build_recording(
    *,
    recording_id: str,
    stream_url: str,
    now: datetime,
) -> dict[str, Any]:
    return {
        "id": recording_id,
        "game_id": f"game-{recording_id}",
        "game": recording_id,
        "league": "Atlas Integration League",
        "home_team": "Atlas Home",
        "away_team": "Atlas Away",
        "stream_url": stream_url,
        "scheduled_start": timestamp(
            now - timedelta(seconds=1)
        ),
        "scheduled_end": timestamp(
            now + timedelta(seconds=2)
        ),
        "status": "pending",
        "subscription_count": 1,
        "subscription_ids": [
            f"subscription-{recording_id}"
        ],
        "subscribed_users": [
            "atlas-integration"
        ],
        "created_at": timestamp(now),
        "updated_at": timestamp(now),
    }


def remember_artifacts(
    recording: dict[str, Any],
) -> None:
    for field in (
        "output_file",
        "partial_file",
        "exit_file",
        "log_file",
    ):
        value = recording.get(field)

        if value:
            CLEANUP_PATHS.add(
                Path(str(value))
            )


def wait_for_recorder(
    recording: dict[str, Any],
    timeout_seconds: int = 20,
) -> None:
    pid = int(recording["pid"])
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if not recorder.process_is_running(pid):
            break

        time.sleep(0.1)
    else:
        recorder.stop_recording(
            pid,
            timeout_seconds=2,
        )
        raise TimeoutError(
            f"Recorder did not exit: {pid}"
        )

    exit_file = Path(
        str(recording["exit_file"])
    )

    sidecar_deadline = time.monotonic() + 5

    while time.monotonic() < sidecar_deadline:
        if exit_file.exists():
            return

        time.sleep(0.05)

    raise TimeoutError(
        f"Exit sidecar was not written: {exit_file}"
    )


def run_success_test() -> None:
    heading("Successful Scheduler Test")

    launch_time = datetime.now(
        timezone.utc
    )

    recording_id = (
        f"{TEST_ID}-success"
    )

    recording = build_recording(
        recording_id=recording_id,
        stream_url=str(FIXTURE_FILE),
        now=launch_time,
    )

    recordings.write_recordings(
        {
            recording_id: recording,
        }
    )

    launched = recordings.update_recording_statuses(
        launch_time
    )[recording_id]

    remember_artifacts(launched)

    check(
        launched["status"] == "recording",
        "Scheduler transitioned pending to recording",
    )

    check(
        bool(launched.get("pid")),
        "Scheduler stored recorder PID",
    )

    check(
        bool(launched.get("exit_file")),
        "Scheduler stored exit-code sidecar path",
    )

    wait_for_recorder(
        launched
    )

    completion_time = (
        launch_time
        + timedelta(seconds=3)
    )

    completed = (
        recordings.update_recording_statuses(
            completion_time
        )[recording_id]
    )

    remember_artifacts(completed)

    check(
        completed["status"] == "completed",
        "Scheduler transitioned recording to completed",
    )

    check(
        completed.get("exit_code") == 0,
        "Scheduler captured recorder exit code 0",
    )

    check(
        completed.get("finalized") is True,
        "Scheduler finalized successful recording",
    )

    output_file = Path(
        str(completed["output_file"])
    )

    partial_file = Path(
        str(completed["partial_file"])
    )

    check(
        output_file.exists()
        and output_file.stat().st_size > 0,
        "Scheduler final output exists and is nonempty",
    )

    check(
        not partial_file.exists(),
        "Scheduler removed partial output",
    )

    persisted = recordings.load_recordings()[
        recording_id
    ]

    check(
        persisted["status"] == "completed",
        "Completed state persisted to recordings file",
    )


def run_failure_test() -> None:
    heading("Failed Scheduler Test")

    launch_time = datetime.now(
        timezone.utc
    )

    recording_id = (
        f"{TEST_ID}-failure"
    )

    recording = build_recording(
        recording_id=recording_id,
        stream_url=(
            f"/tmp/{TEST_ID}-missing-input.mkv"
        ),
        now=launch_time,
    )

    recordings.write_recordings(
        {
            recording_id: recording,
        }
    )

    launched = recordings.update_recording_statuses(
        launch_time
    )[recording_id]

    remember_artifacts(launched)

    check(
        launched["status"] == "recording",
        "Scheduler launched invalid recording request",
    )

    wait_for_recorder(
        launched
    )

    completion_time = (
        launch_time
        + timedelta(seconds=3)
    )

    failed = recordings.update_recording_statuses(
        completion_time
    )[recording_id]

    remember_artifacts(failed)

    exit_code = failed.get("exit_code")

    check(
        failed["status"] == "failed",
        "Scheduler transitioned recording to failed",
    )

    check(
        isinstance(exit_code, int)
        and exit_code != 0,
        f"Scheduler captured nonzero exit code ({exit_code})",
    )

    check(
        failed.get("failure_reason")
        == f"recorder_exit_code_{exit_code}",
        "Scheduler stored recorder exit-code failure reason",
    )

    check(
        failed.get("finalized") is False,
        "Scheduler skipped finalization after recorder failure",
    )

    output_file = Path(
        str(failed["output_file"])
    )

    check(
        not output_file.exists(),
        "Failed scheduler recording created no final output",
    )

    persisted = recordings.load_recordings()[
        recording_id
    ]

    check(
        persisted["status"] == "failed",
        "Failed state persisted to recordings file",
    )


def cleanup() -> None:
    for path in sorted(
        CLEANUP_PATHS,
        key=lambda item: len(str(item)),
        reverse=True,
    ):
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
        except OSError:
            pass

    shutil.rmtree(
        TEST_ROOT,
        ignore_errors=True,
    )


def main() -> int:
    print("Project Atlas")
    print("Sports Scheduler Integration Tests")
    print("==================================")
    print(f"Test ID: {TEST_ID}")

    original_recordings_file = (
        recordings.RECORDINGS_FILE
    )

    recordings.RECORDINGS_FILE = (
        TEST_RECORDINGS_FILE
    )

    try:
        create_fixture()
        run_success_test()
        run_failure_test()

        print()
        print(
            "Sports Scheduler Integration Tests: PASS"
        )
        return 0

    except Exception as exc:
        print()
        print(
            "Sports Scheduler Integration Tests: FAIL"
        )
        print(f"Error: {exc}")
        return 1

    finally:
        recordings.RECORDINGS_FILE = (
            original_recordings_file
        )
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
