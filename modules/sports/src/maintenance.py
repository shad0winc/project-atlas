#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import recordings
from recorder import process_is_running


SPORTS_MEDIA_DIR = Path(
    os.getenv(
        "SPORTS_MEDIA_DIR",
        "/mnt/storage/media/Sports",
    )
)

RECORDING_LOG_DIR = Path(
    os.getenv(
        "SPORTS_RECORDING_LOG_DIR",
        "/mnt/storage/configs/sportyfin/logs/recordings",
    )
)

MAINTENANCE_STATE_FILE = Path(
    os.getenv(
        "SPORTS_MAINTENANCE_STATE_FILE",
        "/mnt/storage/configs/sportyfin/state/maintenance.json",
    )
)

PARTIAL_RETENTION_HOURS = int(
    os.getenv(
        "SPORTS_PARTIAL_RETENTION_HOURS",
        "6",
    )
)

LOG_RETENTION_DAYS = int(
    os.getenv(
        "SPORTS_RECORDING_LOG_RETENTION_DAYS",
        "14",
    )
)

EXIT_RETENTION_DAYS = int(
    os.getenv(
        "SPORTS_RECORDING_EXIT_RETENTION_DAYS",
        "7",
    )
)

METADATA_RETENTION_DAYS = int(
    os.getenv(
        "SPORTS_RECORDING_METADATA_RETENTION_DAYS",
        "30",
    )
)

TERMINAL_STATUSES = {
    "completed",
    "failed",
    "cancelled",
}

ACTIVE_STATUSES = {
    "pending",
    "recording",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(
    value: datetime,
) -> str:
    return value.astimezone(
        timezone.utc
    ).isoformat()


def parse_timestamp(
    value: Any,
) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def file_modified_at(
    path: Path,
) -> datetime | None:
    try:
        return datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc,
        )
    except (
        FileNotFoundError,
        PermissionError,
        OSError,
    ):
        return None


def path_is_older_than(
    path: Path,
    cutoff: datetime,
) -> bool:
    modified_at = file_modified_at(path)

    if modified_at is None:
        return False

    return modified_at < cutoff


def normalized_path(
    value: Any,
) -> Path | None:
    if not value:
        return None

    try:
        return Path(
            str(value)
        ).resolve(strict=False)
    except (
        OSError,
        RuntimeError,
    ):
        return None


def active_recording_paths(
    recording_data: dict[
        str,
        dict[str, Any],
    ],
) -> set[Path]:
    protected: set[Path] = set()

    for recording in recording_data.values():
        status = str(
            recording.get(
                "status",
                "pending",
            )
        ).lower()

        if status not in ACTIVE_STATUSES:
            continue

        if status == "recording":
            pid = recording.get("pid")

            if not process_is_running(pid):
                continue

        for key in (
            "partial_file",
            "output_file",
            "log_file",
            "exit_file",
        ):
            path = normalized_path(
                recording.get(key)
            )

            if path is not None:
                protected.add(path)

    return protected


def remove_candidate(
    *,
    path: Path,
    category: str,
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    entry = {
        "category": category,
        "path": str(path),
    }

    if dry_run:
        report["candidates"].append(entry)
        return

    try:
        path.unlink()
    except FileNotFoundError:
        return
    except (
        PermissionError,
        OSError,
    ) as error:
        entry["error"] = str(error)
        report["errors"].append(entry)
        return

    report["removed"].append(entry)


def cleanup_files(
    *,
    directory: Path,
    patterns: tuple[str, ...],
    cutoff: datetime,
    category: str,
    protected: set[Path],
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    if not directory.exists():
        return

    seen: set[Path] = set()

    for pattern in patterns:
        for path in directory.rglob(pattern):
            if not path.is_file():
                continue

            resolved = path.resolve(
                strict=False
            )

            if resolved in seen:
                continue

            seen.add(resolved)

            if resolved in protected:
                report["protected"].append(
                    {
                        "category": category,
                        "path": str(path),
                    }
                )
                continue

            if not path_is_older_than(
                path,
                cutoff,
            ):
                continue

            remove_candidate(
                path=path,
                category=category,
                dry_run=dry_run,
                report=report,
            )


def recording_reference_time(
    recording: dict[str, Any],
) -> datetime | None:
    for field in (
        "updated_at",
        "completed_at",
        "failed_at",
        "scheduled_end",
        "created_at",
    ):
        parsed = parse_timestamp(
            recording.get(field)
        )

        if parsed is not None:
            return parsed

    return None


def prune_recording_metadata(
    *,
    recording_data: dict[
        str,
        dict[str, Any],
    ],
    cutoff: datetime,
    dry_run: bool,
    report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    retained = dict(recording_data)

    for recording_id, recording in (
        recording_data.items()
    ):
        status = str(
            recording.get(
                "status",
                "",
            )
        ).lower()

        if status not in TERMINAL_STATUSES:
            continue

        reference_time = (
            recording_reference_time(
                recording
            )
        )

        if (
            reference_time is None
            or reference_time >= cutoff
        ):
            continue

        entry = {
            "recording_id": recording_id,
            "status": status,
            "reference_time": (
                format_timestamp(
                    reference_time
                )
            ),
        }

        if dry_run:
            report[
                "metadata_candidates"
            ].append(entry)
            continue

        retained.pop(
            recording_id,
            None,
        )

        report[
            "metadata_pruned"
        ].append(entry)

    return retained


def write_report(
    report: dict[str, Any],
) -> None:
    MAINTENANCE_STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = (
        MAINTENANCE_STATE_FILE.with_suffix(
            ".tmp"
        )
    )

    temporary_file.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_file.replace(
        MAINTENANCE_STATE_FILE
    )


def run_maintenance(
    *,
    dry_run: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = (
        now.astimezone(timezone.utc)
        if now is not None
        else utc_now()
    )

    recording_data = (
        recordings.load_recordings()
    )

    protected = active_recording_paths(
        recording_data
    )

    report: dict[str, Any] = {
        "status": "healthy",
        "dry_run": dry_run,
        "generated_at": format_timestamp(
            current_time
        ),
        "policy": {
            "partial_retention_hours": (
                PARTIAL_RETENTION_HOURS
            ),
            "log_retention_days": (
                LOG_RETENTION_DAYS
            ),
            "exit_retention_days": (
                EXIT_RETENTION_DAYS
            ),
            "metadata_retention_days": (
                METADATA_RETENTION_DAYS
            ),
        },
        "recordings_examined": len(
            recording_data
        ),
        "protected": [],
        "candidates": [],
        "removed": [],
        "metadata_candidates": [],
        "metadata_pruned": [],
        "errors": [],
    }

    cleanup_files(
        directory=SPORTS_MEDIA_DIR,
        patterns=(
            "*.part",
            "*.partial",
        ),
        cutoff=(
            current_time
            - timedelta(
                hours=PARTIAL_RETENTION_HOURS
            )
        ),
        category="partial_recording",
        protected=protected,
        dry_run=dry_run,
        report=report,
    )

    cleanup_files(
        directory=RECORDING_LOG_DIR,
        patterns=("*.log",),
        cutoff=(
            current_time
            - timedelta(
                days=LOG_RETENTION_DAYS
            )
        ),
        category="recording_log",
        protected=protected,
        dry_run=dry_run,
        report=report,
    )

    cleanup_files(
        directory=RECORDING_LOG_DIR,
        patterns=("*.exit",),
        cutoff=(
            current_time
            - timedelta(
                days=EXIT_RETENTION_DAYS
            )
        ),
        category="recording_exit",
        protected=protected,
        dry_run=dry_run,
        report=report,
    )

    retained_recordings = (
        prune_recording_metadata(
            recording_data=recording_data,
            cutoff=(
                current_time
                - timedelta(
                    days=(
                        METADATA_RETENTION_DAYS
                    )
                )
            ),
            dry_run=dry_run,
            report=report,
        )
    )

    if (
        not dry_run
        and retained_recordings
        != recording_data
    ):
        recordings.write_recordings(
            retained_recordings
        )

    if report["errors"]:
        report["status"] = "degraded"

    report["summary"] = {
        "protected": len(
            report["protected"]
        ),
        "candidates": len(
            report["candidates"]
        ),
        "removed": len(
            report["removed"]
        ),
        "metadata_candidates": len(
            report[
                "metadata_candidates"
            ]
        ),
        "metadata_pruned": len(
            report["metadata_pruned"]
        ),
        "errors": len(
            report["errors"]
        ),
    }

    write_report(report)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Project Atlas Sports artifact "
            "maintenance"
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply cleanup actions. Without "
            "this option, maintenance runs "
            "in dry-run mode."
        ),
    )

    args = parser.parse_args()

    report = run_maintenance(
        dry_run=not args.apply
    )

    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        1
        if report["errors"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
