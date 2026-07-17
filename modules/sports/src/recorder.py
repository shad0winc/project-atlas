#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Any


RECORDER_MODE = os.getenv(
    "SPORTS_RECORDER_MODE",
    "fake",
).strip().lower()

RECORDING_LOG_DIR = Path(
    os.getenv(
        "SPORTS_RECORDING_LOG_DIR",
        "/mnt/storage/configs/sportyfin/logs/recordings",
    )
)

SPORTS_MEDIA_DIR = Path(
    os.getenv(
        "SPORTS_MEDIA_DIR",
        "/mnt/storage/media/Sports",
    )
)

FAKE_RECORDER_SECONDS = int(
    os.getenv(
        "SPORTS_FAKE_RECORDER_SECONDS",
        "300",
    )
)

FFMPEG_BINARY = os.getenv(
    "SPORTS_FFMPEG_BINARY",
    "ffmpeg",
)

FFMPEG_LOG_LEVEL = os.getenv(
    "SPORTS_FFMPEG_LOG_LEVEL",
    "warning",
)


def sanitize_filename(
    value: str,
) -> str:
    sanitized = re.sub(
        r"[^A-Za-z0-9._ -]+",
        "",
        value,
    )

    sanitized = re.sub(
        r"\s+",
        " ",
        sanitized,
    ).strip()

    sanitized = sanitized.replace(
        " ",
        "-",
    )

    return sanitized or "sports-recording"


def recording_log_file(
    recording: dict[str, Any],
) -> Path:
    recording_id = sanitize_filename(
        str(
            recording.get(
                "id",
                "unknown-recording",
            )
        )
    )

    return (
        RECORDING_LOG_DIR
        / f"{recording_id}.log"
    )

def recording_exit_file(
    recording: dict[str, Any],
) -> Path:
    recording_id = sanitize_filename(
        str(
            recording.get(
                "id",
                "unknown-recording",
            )
        )
    )

    return (
        RECORDING_LOG_DIR
        / f"{recording_id}.exit"
    )


def recording_exit_code(
    recording: dict[str, Any],
) -> int | None:
    exit_file = recording_exit_file(
        recording
    )

    try:
        raw_exit_code = exit_file.read_text(
            encoding="utf-8"
        ).strip()
    except (
        FileNotFoundError,
        PermissionError,
        OSError,
    ):
        return None

    try:
        return int(raw_exit_code)
    except ValueError:
        return None

def recording_output_file(
    recording: dict[str, Any],
) -> Path:
    existing_output = recording.get(
        "output_file"
    )

    if existing_output:
        return Path(
            str(existing_output)
        )

    game_name = str(
        recording.get(
            "game",
            recording.get(
                "id",
                "sports-recording",
            ),
        )
    )

    recording_id = str(
        recording.get(
            "id",
            "unknown-recording",
        )
    )

    filename = (
        f"{sanitize_filename(game_name)}"
        f"-{sanitize_filename(recording_id)}"
        ".mkv"
    )

    return SPORTS_MEDIA_DIR / filename

def recording_partial_file(
    recording: dict[str, Any],
) -> Path:
    existing_partial = recording.get(
        "partial_file"
    )

    if existing_partial:
        return Path(
            str(existing_partial)
        )

    output_file = recording_output_file(
        recording
    )

    return output_file.with_name(
        f"{output_file.name}.part"
    )


def finalize_recording(
    recording: dict[str, Any],
) -> dict[str, Any]:
    output_file = recording_output_file(
        recording
    )

    partial_file = recording_partial_file(
        recording
    )

    if RECORDER_MODE != "ffmpeg":
        return {
            "finalized": True,
            "output_file": str(output_file),
            "partial_file": str(partial_file),
            "output_size": None,
        }

    if not partial_file.exists():
        return {
            "finalized": False,
            "output_file": str(output_file),
            "partial_file": str(partial_file),
            "output_size": 0,
            "error": "partial_file_missing",
        }

    partial_size = partial_file.stat().st_size

    if partial_size <= 0:
        return {
            "finalized": False,
            "output_file": str(output_file),
            "partial_file": str(partial_file),
            "output_size": partial_size,
            "error": "partial_file_empty",
        }

    partial_file.replace(
        output_file
    )

    return {
        "finalized": True,
        "output_file": str(output_file),
        "partial_file": str(partial_file),
        "output_size": output_file.stat().st_size,
    }

def fake_recorder_command() -> list[str]:
    return [
        "sleep",
        str(FAKE_RECORDER_SECONDS),
    ]

def stream_supports_reconnect(
    stream_url: str,
) -> bool:
    normalized_url = stream_url.lower()

    return normalized_url.startswith(
        (
            "http://",
            "https://",
        )
    )

def ffmpeg_recorder_command(
    recording: dict[str, Any],
) -> list[str]:
    stream_url = str(
        recording.get(
            "stream_url",
            "",
        )
    ).strip()

    if not stream_url:
        raise ValueError(
            "Recording has no stream_url"
        )

    partial_file = recording_partial_file(
        recording
    )

    command = [
        FFMPEG_BINARY,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        FFMPEG_LOG_LEVEL,
        "-y",
    ]

    if stream_supports_reconnect(
        stream_url
    ):
        command.extend(
            [
                "-reconnect",
                "1",
                "-reconnect_streamed",
                "1",
                "-reconnect_on_network_error",
                "1",
                "-reconnect_on_http_error",
                "4xx,5xx",
                "-reconnect_delay_max",
                "5",
            ]
        )

    command.extend(
        [
            "-i",
            stream_url,
            "-map",
            "0",
            "-c",
            "copy",
            "-f",
            "matroska",
            str(partial_file),
        ]
    )

    return command


def recorder_command(
    recording: dict[str, Any],
) -> list[str]:
    if RECORDER_MODE == "fake":
        return fake_recorder_command()

    if RECORDER_MODE == "ffmpeg":
        return ffmpeg_recorder_command(
            recording
        )

    raise ValueError(
        f"Unsupported recorder mode: "
        f"{RECORDER_MODE}"
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
            "output_file": str(
                recording.get(
                    "output_file",
                    recording_output_file(recording),
                )
            ),
            "partial_file": str(
                recording.get(
                    "partial_file",
                    recording_partial_file(recording),
                )
            ),
            "exit_file": str(
                recording.get(
                    "exit_file",
                    recording_exit_file(recording),
                )
            ),
            "recorder_mode": str(
                recording.get(
                    "recorder_mode",
                    RECORDER_MODE,
                )
            ),
            "started": False,
        }

    RECORDING_LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SPORTS_MEDIA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_file = recording_log_file(
        recording
    )

    output_file = recording_output_file(
        recording
    )

    partial_file = recording_partial_file(
        recording
    )

    if (
        RECORDER_MODE == "ffmpeg"
        and partial_file.exists()
    ):
        partial_file.unlink()

    command = recorder_command(
        recording
    )

    exit_file = recording_exit_file(
        recording
    )

    try:
        exit_file.unlink()
    except FileNotFoundError:
        pass

    wrapped_command = [
        "/bin/sh",
        "-c",
        (
            '"$@"; '
            "exit_code=$?; "
            'printf "%s\\n" "$exit_code" '
            '> "$ATLAS_EXIT_FILE"; '
            'exit "$exit_code"'
        ),
        "atlas-recorder",
        *command,
    ]

    process_environment = os.environ.copy()
    process_environment[
        "ATLAS_EXIT_FILE"
    ] = str(exit_file)

    log_handle = log_file.open(
        "ab",
    )

    try:
        process = subprocess.Popen(
            wrapped_command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=process_environment,
        )
    finally:
        log_handle.close()

    return {
        "pid": process.pid,
        "log_file": str(log_file),
        "output_file": str(output_file),
        "partial_file": str(partial_file),
        "exit_file": str(exit_file),
        "recorder_mode": RECORDER_MODE,
        "command": command,
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
