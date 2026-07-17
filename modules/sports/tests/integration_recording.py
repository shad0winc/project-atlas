#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SPORTS_SRC_DIR = Path(
    "/opt/project-atlas/modules/sports/src"
)

if str(SPORTS_SRC_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(SPORTS_SRC_DIR),
    )

from recorder import (  # noqa: E402
    finalize_recording,
    launch_recording,
    process_is_running,
    recording_exit_code,
)


TEST_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 0.25


class IntegrationTestFailure(
    RuntimeError
):
    """Raised when a Sports integration assertion fails."""


def assert_test(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise IntegrationTestFailure(
            message
        )


def print_pass(
    message: str,
) -> None:
    print(
        f"PASS {message}"
    )


def print_fail(
    message: str,
) -> None:
    print(
        f"FAIL {message}"
    )


def remove_path(
    path_value: str | Path | None,
) -> None:
    if not path_value:
        return

    path = Path(
        str(path_value)
    )

    try:
        path.unlink()
    except FileNotFoundError:
        pass


def cleanup_recording(
    recording: dict[str, Any],
) -> None:
    for key in (
        "log_file",
        "exit_file",
        "partial_file",
        "output_file",
    ):
        remove_path(
            recording.get(key)
        )


def wait_for_recorder(
    recording: dict[str, Any],
) -> int:
    pid = int(
        recording["pid"]
    )

    exit_file = Path(
        str(
            recording["exit_file"]
        )
    )

    deadline = (
        time.monotonic()
        + TEST_TIMEOUT_SECONDS
    )

    while time.monotonic() < deadline:
        exit_code = recording_exit_code(
            recording
        )

        if exit_code is not None:
            return exit_code

        if (
            not process_is_running(pid)
            and not exit_file.exists()
        ):
            raise IntegrationTestFailure(
                "Recorder stopped without writing "
                "an exit-code sidecar."
            )

        time.sleep(
            POLL_INTERVAL_SECONDS
        )

    raise IntegrationTestFailure(
        "Recorder did not finish within "
        f"{TEST_TIMEOUT_SECONDS} seconds."
    )


def create_success_fixture(
    fixture_file: Path,
) -> None:
    fixture_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=size=320x240:rate=25:duration=2",
        "-c:v",
        "mpeg4",
        "-f",
        "matroska",
        str(fixture_file),
    ]

    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise IntegrationTestFailure(
            "Unable to generate the success fixture:\n"
            f"{result.stdout}"
        )

    assert_test(
        fixture_file.exists(),
        "Success fixture was not created.",
    )

    assert_test(
        fixture_file.stat().st_size > 0,
        "Success fixture is empty.",
    )


def test_successful_recording(
    test_id: str,
) -> None:
    print()
    print(
        "Successful Recording Test"
    )
    print(
        "-------------------------"
    )

    fixture_file = Path(
        f"/tmp/{test_id}-source.mkv"
    )

    recording: dict[str, Any] = {
        "id": f"{test_id}-success",
        "game": (
            "Atlas Integration Test Success"
        ),
        "stream_url": str(
            fixture_file
        ),
    }

    try:
        create_success_fixture(
            fixture_file
        )
        print_pass(
            "Deterministic media fixture created"
        )

        launch_result = launch_recording(
            recording
        )

        recording.update(
            launch_result
        )

        assert_test(
            bool(
                launch_result.get(
                    "started"
                )
            ),
            "Recorder did not report a new launch.",
        )
        print_pass(
            "Recorder launched"
        )

        exit_code = wait_for_recorder(
            recording
        )

        assert_test(
            exit_code == 0,
            (
                "Expected recorder exit code 0, "
                f"received {exit_code}."
            ),
        )
        print_pass(
            "Recorder exit code is 0"
        )

        exit_file = Path(
            str(
                recording["exit_file"]
            )
        )

        assert_test(
            exit_file.exists(),
            "Exit-code sidecar does not exist.",
        )
        print_pass(
            "Exit-code sidecar created"
        )

        partial_file = Path(
            str(
                recording["partial_file"]
            )
        )

        assert_test(
            partial_file.exists(),
            "Partial recording was not created.",
        )

        assert_test(
            partial_file.stat().st_size > 0,
            "Partial recording is empty.",
        )
        print_pass(
            "Partial recording created"
        )

        finalize_result = (
            finalize_recording(
                recording
            )
        )

        assert_test(
            bool(
                finalize_result.get(
                    "finalized"
                )
            ),
            (
                "Recording did not finalize: "
                f"{finalize_result}"
            ),
        )
        print_pass(
            "Recording finalized"
        )

        output_file = Path(
            str(
                recording["output_file"]
            )
        )

        assert_test(
            output_file.exists(),
            "Final recording does not exist.",
        )

        assert_test(
            output_file.stat().st_size > 0,
            "Final recording is empty.",
        )
        print_pass(
            "Final recording exists and is nonempty"
        )

        assert_test(
            not partial_file.exists(),
            (
                "Partial recording remains after "
                "successful finalization."
            ),
        )
        print_pass(
            "Partial file removed"
        )

    finally:
        cleanup_recording(
            recording
        )
        remove_path(
            fixture_file
        )


def test_failed_recording(
    test_id: str,
) -> None:
    print()
    print(
        "Failed Recording Test"
    )
    print(
        "---------------------"
    )

    missing_input = Path(
        f"/tmp/{test_id}-missing-source.mkv"
    )

    remove_path(
        missing_input
    )

    recording: dict[str, Any] = {
        "id": f"{test_id}-failure",
        "game": (
            "Atlas Integration Test Failure"
        ),
        "stream_url": str(
            missing_input
        ),
    }

    try:
        launch_result = launch_recording(
            recording
        )

        recording.update(
            launch_result
        )

        assert_test(
            bool(
                launch_result.get(
                    "started"
                )
            ),
            "Failure-case recorder did not launch.",
        )
        print_pass(
            "Recorder launched with invalid input"
        )

        exit_code = wait_for_recorder(
            recording
        )

        assert_test(
            exit_code != 0,
            (
                "Invalid input unexpectedly produced "
                "exit code 0."
            ),
        )
        print_pass(
            f"Nonzero exit code captured ({exit_code})"
        )

        exit_file = Path(
            str(
                recording["exit_file"]
            )
        )

        assert_test(
            exit_file.exists(),
            "Failure exit-code sidecar is missing.",
        )
        print_pass(
            "Failure exit-code sidecar created"
        )

        log_file = Path(
            str(
                recording["log_file"]
            )
        )

        assert_test(
            log_file.exists(),
            "Failure log was not retained.",
        )

        assert_test(
            log_file.stat().st_size > 0,
            "Failure log is empty.",
        )
        print_pass(
            "Failure log retained"
        )

        output_file = Path(
            str(
                recording["output_file"]
            )
        )

        assert_test(
            not output_file.exists(),
            (
                "Invalid recording unexpectedly "
                "created a final output file."
            ),
        )
        print_pass(
            "No final recording created"
        )

    finally:
        cleanup_recording(
            recording
        )


def main() -> int:
    test_id = (
        "atlas-sports-integration-"
        f"{uuid.uuid4().hex[:8]}"
    )

    print(
        "Project Atlas"
    )
    print(
        "Sports Recording Integration Tests"
    )
    print(
        "=================================="
    )
    print(
        f"Test ID: {test_id}"
    )

    try:
        test_successful_recording(
            test_id
        )

        test_failed_recording(
            test_id
        )

    except IntegrationTestFailure as exc:
        print()
        print_fail(
            str(exc)
        )
        print()
        print(
            "Sports Recording Integration "
            "Tests: FAIL"
        )
        return 1

    except Exception as exc:
        print()
        print_fail(
            f"Unexpected error: {exc}"
        )
        print()
        print(
            "Sports Recording Integration "
            "Tests: ERROR"
        )
        return 2

    print()
    print(
        "Sports Recording Integration "
        "Tests: PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
