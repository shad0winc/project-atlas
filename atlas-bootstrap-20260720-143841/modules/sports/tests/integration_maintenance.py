#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TEST_ROOT = Path(
    tempfile.mkdtemp(
        prefix="atlas-sports-maintenance-"
    )
)

TEST_MEDIA_DIR = TEST_ROOT / "media"
TEST_LOG_DIR = TEST_ROOT / "logs"
TEST_STATE_DIR = TEST_ROOT / "state"
TEST_RECORDINGS_DIR = TEST_ROOT / "recordings"

TEST_RECORDINGS_FILE = (
    TEST_RECORDINGS_DIR
    / "recordings.json"
)

TEST_MAINTENANCE_FILE = (
    TEST_STATE_DIR
    / "maintenance.json"
)


os.environ[
    "SPORTS_MEDIA_DIR"
] = str(TEST_MEDIA_DIR)

os.environ[
    "SPORTS_RECORDING_LOG_DIR"
] = str(TEST_LOG_DIR)

os.environ[
    "SPORTS_RECORDINGS_FILE"
] = str(TEST_RECORDINGS_FILE)

os.environ[
    "SPORTS_MAINTENANCE_STATE_FILE"
] = str(TEST_MAINTENANCE_FILE)

os.environ[
    "SPORTS_PARTIAL_RETENTION_HOURS"
] = "6"

os.environ[
    "SPORTS_RECORDING_LOG_RETENTION_DAYS"
] = "14"

os.environ[
    "SPORTS_RECORDING_EXIT_RETENTION_DAYS"
] = "7"

os.environ[
    "SPORTS_RECORDING_METADATA_RETENTION_DAYS"
] = "30"


import maintenance  # noqa: E402
import recordings  # noqa: E402


CLEANUP_PROCESSES: list[
    subprocess.Popen[Any]
] = []


def heading(
    title: str,
) -> None:
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


def timestamp(
    value: datetime,
) -> str:
    return value.astimezone(
        timezone.utc
    ).isoformat()


def create_file(
    path: Path,
    content: str,
    modified_at: datetime,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )

    unix_time = modified_at.timestamp()

    os.utime(
        path,
        (
            unix_time,
            unix_time,
        ),
    )


def build_recording(
    *,
    recording_id: str,
    status: str,
    now: datetime,
    partial_file: Path | None = None,
    log_file: Path | None = None,
    exit_file: Path | None = None,
    pid: int | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    recording: dict[str, Any] = {
        "id": recording_id,
        "game_id": f"game-{recording_id}",
        "game": recording_id,
        "scheduled_start": timestamp(
            now - timedelta(hours=2)
        ),
        "scheduled_end": timestamp(
            now - timedelta(hours=1)
        ),
        "status": status,
        "created_at": timestamp(
            now - timedelta(days=40)
        ),
        "updated_at": timestamp(
            updated_at or now
        ),
    }

    if partial_file is not None:
        recording[
            "partial_file"
        ] = str(partial_file)

    if log_file is not None:
        recording[
            "log_file"
        ] = str(log_file)

    if exit_file is not None:
        recording[
            "exit_file"
        ] = str(exit_file)

    if pid is not None:
        recording["pid"] = pid

    return recording


def prepare_directories() -> None:
    for directory in (
        TEST_MEDIA_DIR,
        TEST_LOG_DIR,
        TEST_STATE_DIR,
        TEST_RECORDINGS_DIR,
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


def run_dry_run_test(
    now: datetime,
) -> None:
    heading("Maintenance Dry-Run Test")

    stale_partial = (
        TEST_MEDIA_DIR
        / "stale-recording.mkv.part"
    )

    old_log = (
        TEST_LOG_DIR
        / "old-recording.log"
    )

    old_exit = (
        TEST_LOG_DIR
        / "old-recording.exit"
    )

    create_file(
        stale_partial,
        "partial",
        now - timedelta(hours=12),
    )

    create_file(
        old_log,
        "old log",
        now - timedelta(days=20),
    )

    create_file(
        old_exit,
        "0\n",
        now - timedelta(days=10),
    )

    recordings.write_recordings(
        {
            "old-completed": build_recording(
                recording_id="old-completed",
                status="completed",
                now=now,
                updated_at=(
                    now
                    - timedelta(days=40)
                ),
            ),
        }
    )

    report = maintenance.run_maintenance(
        dry_run=True,
        now=now,
    )

    check(
        report["status"] == "healthy",
        "Dry-run completed successfully",
    )

    check(
        report["summary"]["candidates"]
        == 3,
        "Dry-run identified three stale artifacts",
    )

    check(
        report["summary"][
            "metadata_candidates"
        ]
        == 1,
        "Dry-run identified expired metadata",
    )

    check(
        stale_partial.exists(),
        "Dry-run preserved stale partial file",
    )

    check(
        old_log.exists(),
        "Dry-run preserved old log file",
    )

    check(
        old_exit.exists(),
        "Dry-run preserved old exit file",
    )

    persisted = recordings.load_recordings()

    check(
        "old-completed" in persisted,
        "Dry-run preserved recording metadata",
    )


def run_apply_test(
    now: datetime,
) -> None:
    heading("Maintenance Apply Test")

    report = maintenance.run_maintenance(
        dry_run=False,
        now=now,
    )

    check(
        report["status"] == "healthy",
        "Applied maintenance completed successfully",
    )

    check(
        report["summary"]["removed"]
        == 3,
        "Applied maintenance removed three artifacts",
    )

    check(
        report["summary"][
            "metadata_pruned"
        ]
        == 1,
        "Applied maintenance pruned expired metadata",
    )

    check(
        not (
            TEST_MEDIA_DIR
            / "stale-recording.mkv.part"
        ).exists(),
        "Stale partial file removed",
    )

    check(
        not (
            TEST_LOG_DIR
            / "old-recording.log"
        ).exists(),
        "Old recording log removed",
    )

    check(
        not (
            TEST_LOG_DIR
            / "old-recording.exit"
        ).exists(),
        "Old exit-code file removed",
    )

    persisted = recordings.load_recordings()

    check(
        "old-completed" not in persisted,
        "Expired metadata removed",
    )


def run_active_protection_test(
    now: datetime,
) -> None:
    heading("Active Recording Protection Test")

    active_partial = (
        TEST_MEDIA_DIR
        / "active-recording.mkv.part"
    )

    active_log = (
        TEST_LOG_DIR
        / "active-recording.log"
    )

    active_exit = (
        TEST_LOG_DIR
        / "active-recording.exit"
    )

    create_file(
        active_partial,
        "active partial",
        now - timedelta(days=30),
    )

    create_file(
        active_log,
        "active log",
        now - timedelta(days=30),
    )

    create_file(
        active_exit,
        "0\n",
        now - timedelta(days=30),
    )

    process = subprocess.Popen(
        ["sleep", "30"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    CLEANUP_PROCESSES.append(process)

    try:
        active_recording = build_recording(
            recording_id="active-recording",
            status="recording",
            now=now,
            partial_file=active_partial,
            log_file=active_log,
            exit_file=active_exit,
            pid=process.pid,
        )

        recordings.write_recordings(
            {
                "active-recording": (
                    active_recording
                ),
            }
        )

        report = maintenance.run_maintenance(
            dry_run=False,
            now=now,
        )

        protected_paths = {
            entry["path"]
            for entry in report["protected"]
        }

        check(
            str(active_partial)
            in protected_paths,
            "Active partial file marked protected",
        )

        check(
            str(active_log)
            in protected_paths,
            "Active log file marked protected",
        )

        check(
            str(active_exit)
            in protected_paths,
            "Active exit file marked protected",
        )

        check(
            active_partial.exists(),
            "Active partial file preserved",
        )

        check(
            active_log.exists(),
            "Active log file preserved",
        )

        check(
            active_exit.exists(),
            "Active exit file preserved",
        )

        persisted = recordings.load_recordings()

        check(
            "active-recording" in persisted,
            "Active recording metadata preserved",
        )

    finally:
        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

        for cleanup_path in (
            active_partial,
            active_log,
            active_exit,
        ):
            if cleanup_path.exists():
                cleanup_path.unlink()

        recordings.write_recordings({})


def run_recent_artifact_test(
    now: datetime,
) -> None:
    heading("Recent Artifact Retention Test")

    recordings.write_recordings({})

    recent_partial = (
        TEST_MEDIA_DIR
        / "recent-recording.mkv.part"
    )

    recent_log = (
        TEST_LOG_DIR
        / "recent-recording.log"
    )

    recent_exit = (
        TEST_LOG_DIR
        / "recent-recording.exit"
    )

    create_file(
        recent_partial,
        "recent partial",
        now - timedelta(hours=1),
    )

    create_file(
        recent_log,
        "recent log",
        now - timedelta(days=1),
    )

    create_file(
        recent_exit,
        "0\n",
        now - timedelta(days=1),
    )

    report = maintenance.run_maintenance(
        dry_run=False,
        now=now,
    )

    check(
        report["summary"]["removed"]
        == 0,
        "Recent artifacts were not removed",
    )

    check(
        recent_partial.exists(),
        "Recent partial file preserved",
    )

    check(
        recent_log.exists(),
        "Recent log file preserved",
    )

    check(
        recent_exit.exists(),
        "Recent exit file preserved",
    )


def cleanup() -> None:
    for process in CLEANUP_PROCESSES:
        if process.poll() is not None:
            continue

        process.terminate()

        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def main() -> int:
    prepare_directories()

    now = datetime.now(
        timezone.utc
    ).replace(
        microsecond=0
    )

    try:
        run_dry_run_test(now)
        run_apply_test(now)
        run_active_protection_test(now)
        run_recent_artifact_test(now)

        heading("Maintenance Integration Result")
        print("PASS Sports maintenance integration")

        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
