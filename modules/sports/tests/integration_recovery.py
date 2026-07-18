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


TEST_ID = (
    f"atlas-sports-recovery-"
    f"{uuid.uuid4().hex[:8]}"
)

TEST_ROOT = Path(
    tempfile.mkdtemp(
        prefix=f"{TEST_ID}-",
    )
)

TEST_RECORDINGS_FILE = (
    TEST_ROOT / "recordings.json"
)

CLEANUP_PROCESSES: list[
    subprocess.Popen[Any]
] = []


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


def build_recording(
    *,
    recording_id: str,
    now: datetime,
    status: str,
    pid: int | None = None,
) -> dict[str, Any]:
    output_file = (
        TEST_ROOT
        / f"{recording_id}.mkv"
    )

    partial_file = Path(
        f"{output_file}.partial"
    )

    exit_file = recorder.recording_exit_file(
        {
            "id": recording_id,
        }
    )

    log_file = (
        TEST_ROOT
        / f"{recording_id}.log"
    )

    recording: dict[str, Any] = {
        "id": recording_id,
        "game_id": f"game-{recording_id}",
        "game": recording_id,
        "league": "Atlas Recovery League",
        "home_team": "Atlas Home",
        "away_team": "Atlas Away",
        "stream_url": (
            "https://example.invalid/"
            f"{recording_id}.m3u8"
        ),
        "scheduled_start": timestamp(
            now - timedelta(minutes=1)
        ),
        "scheduled_end": timestamp(
            now + timedelta(minutes=5)
        ),
        "status": status,
        "subscription_count": 1,
        "subscription_ids": [
            f"subscription-{recording_id}"
        ],
        "subscribed_users": [
            "atlas-recovery"
        ],
        "created_at": timestamp(
            now - timedelta(minutes=2)
        ),
        "updated_at": timestamp(now),
        "log_file": str(log_file),
        "output_file": str(output_file),
        "partial_file": str(partial_file),
        "exit_file": str(exit_file),
        "recorder_mode": "recovery-test",
    }

    if pid is not None:
        recording["pid"] = pid

    return recording


def stop_process(
    process: subprocess.Popen[Any],
) -> None:
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def run_live_process_recovery_test() -> None:
    heading("Live Recorder Recovery Test")

    now = datetime.now(timezone.utc)

    process = subprocess.Popen(
        ["sleep", "30"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    CLEANUP_PROCESSES.append(process)

    check(
        recorder.process_is_running(
            process.pid
        ),
        "Controlled recorder process is running",
    )

    recording_id = (
        f"{TEST_ID}-live"
    )

    recording = build_recording(
        recording_id=recording_id,
        now=now,
        status="recording",
        pid=process.pid,
    )

    recordings.write_recordings(
        {
            recording_id: recording,
        }
    )

    original_launch_recording = (
        recordings.launch_recording
    )

    launch_called = False

    def reject_duplicate_launch(
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal launch_called

        launch_called = True

        raise AssertionError(
            "Scheduler attempted a duplicate "
            "recorder launch"
        )

    recordings.launch_recording = (
        reject_duplicate_launch
    )

    try:
        recovered = (
            recordings.update_recording_statuses(
                now + timedelta(seconds=1)
            )[recording_id]
        )
    finally:
        recordings.launch_recording = (
            original_launch_recording
        )

    check(
        recovered["status"] == "recording",
        "Recovered recording remains active",
    )

    check(
        int(recovered["pid"])
        == process.pid,
        "Recovered recording retained original PID",
    )

    check(
        not launch_called,
        "Scheduler did not launch duplicate recorder",
    )

    check(
        recorder.process_is_running(
            process.pid
        ),
        "Original recorder remains running",
    )

    persisted = (
        recordings.load_recordings()[
            recording_id
        ]
    )

    check(
        int(persisted["pid"])
        == process.pid,
        "Recovered PID persisted to recordings file",
    )

    check(
        persisted["status"] == "recording",
        "Recovered active state persisted",
    )

    adoption = recorder.launch_recording(
        recovered
    )

    check(
        int(adoption["pid"])
        == process.pid,
        "Recorder launcher adopted existing process",
    )

    for field in (
        "log_file",
        "output_file",
        "partial_file",
        "exit_file",
    ):
        check(
            str(adoption[field])
            == str(recovered[field]),
            f"Recorder adoption preserved {field}",
        )

    stop_process(process)


def run_completed_process_recovery_test() -> None:
    heading("Completed Recorder Recovery Test")

    now = datetime.now(timezone.utc)

    recording_id = (
        f"{TEST_ID}-completed"
    )

    recording = build_recording(
        recording_id=recording_id,
        now=now,
        status="recording",
        pid=99999999,
    )

    recording["scheduled_end"] = timestamp(
        now - timedelta(seconds=1)
    )

    partial_file = Path(
        str(recording["partial_file"])
    )

    exit_file = Path(
        str(recording["exit_file"])
    )

    partial_file.write_bytes(
        b"atlas recovery recording fixture\n"
    )

    exit_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    exit_file.write_text(
        "0\n",
        encoding="utf-8",
    )

    recordings.write_recordings(
        {
            recording_id: recording,
        }
    )

    check(
        not recorder.process_is_running(
            int(recording["pid"])
        ),
        "Recovered recorder PID is no longer running",
    )

    recovered = (
        recordings.update_recording_statuses(
            now
        )[recording_id]
    )

    check(
        recovered["status"] == "completed",
        "Exited recorder reconciled to completed",
    )

    check(
        recovered.get("exit_code") == 0,
        "Recovered recording captured exit code 0",
    )

    check(
        recovered.get("finalized") is True,
        "Recovered recording finalized successfully",
    )

    output_file = Path(
        str(recovered["output_file"])
    )

    check(
        output_file.exists(),
        "Recovered final output exists",
    )

    check(
        output_file.read_bytes()
        == b"atlas recovery recording fixture\n",
        "Recovered output preserved partial data",
    )

    check(
        not partial_file.exists(),
        "Recovered partial output was removed",
    )

    persisted = (
        recordings.load_recordings()[
            recording_id
        ]
    )

    check(
        persisted["status"] == "completed",
        "Recovered completion state persisted",
    )

    check(
        persisted.get("exit_code") == 0,
        "Recovered exit code persisted",
    )

    check(
        persisted.get("finalized") is True,
        "Recovered finalization state persisted",
    )


def cleanup() -> None:
    for process in CLEANUP_PROCESSES:
        try:
            stop_process(process)
        except (
            OSError,
            subprocess.SubprocessError,
        ):
            pass

    for suffix in (
        "-live",
        "-completed",
    ):
        exit_file = recorder.recording_exit_file(
            {
                "id": f"{TEST_ID}{suffix}",
            }
        )

        try:
            exit_file.unlink()
        except FileNotFoundError:
            pass

    shutil.rmtree(
        TEST_ROOT,
        ignore_errors=True,
    )


def main() -> int:
    print("Project Atlas")
    print("Sports Recovery Integration Tests")
    print("=================================")
    print(f"Test ID: {TEST_ID}")

    original_recordings_file = (
        recordings.RECORDINGS_FILE
    )

    original_recorder_mode = (
        recorder.RECORDER_MODE
    )

    recordings.RECORDINGS_FILE = (
        TEST_RECORDINGS_FILE
    )

    recorder.RECORDER_MODE = "ffmpeg"

    try:
        run_live_process_recovery_test()
        run_completed_process_recovery_test()

        print()
        print(
            "Sports Recovery Integration Tests: PASS"
        )

        return 0

    except Exception as exc:
        print()
        print(
            "Sports Recovery Integration Tests: FAIL"
        )
        print(f"Error: {exc}")

        return 1

    finally:
        recordings.RECORDINGS_FILE = (
            original_recordings_file
        )

        recorder.RECORDER_MODE = (
            original_recorder_mode
        )

        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
