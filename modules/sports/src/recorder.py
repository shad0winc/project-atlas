#!/usr/bin/env python3

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Any


RECORDING_LOG_DIR = Path(
    os.getenv(
        "SPORTS_RECORDING_LOG_DIR",
        "/mnt/storage/configs/sportyfin/logs/recordings",
    )
)

FAKE_RECORDER_SECONDS = int(
    os.getenv(
        "SPORTS_FAKE_RECORDER_SECONDS",
        "300",
    )
)


def recording_log_file(
    recording: dict[str, Any],
) -> Path:
    recording_id = str(
        recording.get(
            "id",
            "unknown-recording",
        )
    )

    return (
        RECORDING_LOG_DIR
        / f"{recording_id}.log"
    )

def process_is_running(
    pid: int | None,
) -> bool:
    if not pid:
        return False

    try:
        process_id = int(pid)
    except (
        TypeError,
        ValueError,
    ):
        return False

    try:
        waited_pid, _ = os.waitpid(
            process_id,
            os.WNOHANG,
        )

        if waited_pid == process_id:
            return False

    except ChildProcessError:
        pass

    except OSError:
        return False

    stat_file = Path(
        f"/proc/{process_id}/stat"
    )

    try:
        stat_fields = stat_file.read_text(
            encoding="utf-8"
        ).split()

        if len(stat_fields) >= 3:
            process_state = stat_fields[2]

            if process_state == "Z":
                return False

    except (
        FileNotFoundError,
        PermissionError,
        OSError,
    ):
        return False

    try:
        os.kill(
            process_id,
            0,
        )
    except (
        OSError,
        ValueError,
    ):
        return False

    return True

def launch_recording(
    recording: dict[str, Any],
) -> dict[str, Any]:
    existing_pid = recording.get("pid")

    if process_is_running(existing_pid):
        return {
            "pid": int(existing_pid),
            "log_file": str(
                recording.get(
                    "log_file",
                    recording_log_file(recording),
                )
            ),
            "started": False,
        }

    RECORDING_LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_file = recording_log_file(
        recording
    )

    log_handle = log_file.open(
        "ab",
    )

    try:
        process = subprocess.Popen(
            [
                "sleep",
                str(FAKE_RECORDER_SECONDS),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_handle.close()

    return {
        "pid": process.pid,
        "log_file": str(log_file),
        "started": True,
    }


def stop_recording(
    pid: int | None,
    timeout_seconds: int = 10,
) -> bool:
    if not process_is_running(pid):
        return True

    process_id = int(pid)

    try:
        os.killpg(
            process_id,
            signal.SIGTERM,
        )
    except ProcessLookupError:
        return True

    for _ in range(
        timeout_seconds * 10
    ):
        if not process_is_running(
            process_id
        ):
            return True

        import time

        time.sleep(0.1)

    try:
        os.killpg(
            process_id,
            signal.SIGKILL,
        )
    except ProcessLookupError:
        return True

    return not process_is_running(
        process_id
    )
