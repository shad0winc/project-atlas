#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from recorder import (
    FFMPEG_BINARY,
    RECORDER_MODE,
    SPORTS_MEDIA_DIR,
)
from recordings import load_recordings


HEALTH_FILE = Path(
    os.getenv(
        "SPORTS_HEALTH_FILE",
        "/mnt/storage/configs/sportyfin/state/health.json",
    )
)

HEARTBEAT_FILE = Path(
    os.getenv(
        "SPORTS_CONTROLLER_HEARTBEAT_FILE",
        "/mnt/storage/configs/sportyfin/state/controller-heartbeat",
    )
)

PROVIDER_HEALTH_FILE = Path(
    os.getenv(
        "SPORTS_PROVIDER_HEALTH_FILE",
        "/mnt/storage/configs/sportyfin/state/provider-health.json",
    )
)

HEARTBEAT_MAX_AGE_SECONDS = int(
    os.getenv(
        "SPORTS_HEARTBEAT_MAX_AGE_SECONDS",
        "90",
    )
)

STORAGE_WARNING_PERCENT_FREE = float(
    os.getenv(
        "SPORTS_STORAGE_WARNING_PERCENT_FREE",
        "5",
    )
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(
    value: datetime,
) -> str:
    return value.isoformat()


def load_json_object(
    path: Path,
) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        data = json.loads(
            path.read_text(
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

    return data


def controller_health(
    now: datetime,
) -> dict[str, Any]:
    if not HEARTBEAT_FILE.exists():
        return {
            "status": "degraded",
            "heartbeat_file": str(
                HEARTBEAT_FILE
            ),
            "heartbeat_exists": False,
            "heartbeat_age_seconds": None,
        }

    try:
        heartbeat_modified = datetime.fromtimestamp(
            HEARTBEAT_FILE.stat().st_mtime,
            timezone.utc,
        )

        heartbeat_age = max(
            0,
            int(
                (
                    now
                    - heartbeat_modified
                ).total_seconds()
            ),
        )
    except OSError:
        return {
            "status": "degraded",
            "heartbeat_file": str(
                HEARTBEAT_FILE
            ),
            "heartbeat_exists": False,
            "heartbeat_age_seconds": None,
        }

    status = (
        "healthy"
        if heartbeat_age
        < HEARTBEAT_MAX_AGE_SECONDS
        else "degraded"
    )

    return {
        "status": status,
        "heartbeat_file": str(
            HEARTBEAT_FILE
        ),
        "heartbeat_exists": True,
        "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_max_age_seconds": (
            HEARTBEAT_MAX_AGE_SECONDS
        ),
    }


def provider_health() -> dict[str, Any]:
    providers = load_json_object(
        PROVIDER_HEALTH_FILE
    )

    provider_statuses = [
        str(
            provider.get(
                "status",
                "unknown",
            )
        ).lower()
        for provider in providers.values()
        if isinstance(provider, dict)
    ]

    if not provider_statuses:
        status = "unknown"
    elif all(
        item == "healthy"
        for item in provider_statuses
    ):
        status = "healthy"
    else:
        status = "degraded"

    return {
        "status": status,
        "count": len(providers),
        "providers": providers,
    }


def recorder_health() -> dict[str, Any]:
    ffmpeg_path = shutil.which(
        FFMPEG_BINARY
    )

    ffmpeg_available = (
        ffmpeg_path is not None
    )

    if RECORDER_MODE == "ffmpeg":
        status = (
            "healthy"
            if ffmpeg_available
            else "failed"
        )
    else:
        status = "degraded"

    return {
        "status": status,
        "mode": RECORDER_MODE,
        "ffmpeg_binary": FFMPEG_BINARY,
        "ffmpeg_available": ffmpeg_available,
        "ffmpeg_path": ffmpeg_path,
    }


def recording_health() -> dict[str, Any]:
    recordings = load_recordings()

    counts: dict[str, int] = {
        "pending": 0,
        "recording": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "unknown": 0,
    }

    for recording in recordings.values():
        status = str(
            recording.get(
                "status",
                "unknown",
            )
        ).lower()

        if status not in counts:
            status = "unknown"

        counts[status] += 1

    failed_count = counts["failed"]

    status = (
        "degraded"
        if failed_count > 0
        else "healthy"
    )

    return {
        "status": status,
        "total": len(recordings),
        **counts,
    }


def storage_health() -> dict[str, Any]:
    path_exists = SPORTS_MEDIA_DIR.exists()
    writable = (
        path_exists
        and os.access(
            SPORTS_MEDIA_DIR,
            os.W_OK,
        )
    )

    if not path_exists:
        return {
            "status": "failed",
            "path": str(
                SPORTS_MEDIA_DIR
            ),
            "exists": False,
            "writable": False,
            "total_bytes": None,
            "used_bytes": None,
            "free_bytes": None,
            "percent_free": None,
        }

    try:
        usage = shutil.disk_usage(
            SPORTS_MEDIA_DIR
        )
    except OSError:
        return {
            "status": "failed",
            "path": str(
                SPORTS_MEDIA_DIR
            ),
            "exists": True,
            "writable": writable,
            "total_bytes": None,
            "used_bytes": None,
            "free_bytes": None,
            "percent_free": None,
        }

    percent_free = (
        (
            usage.free
            / usage.total
        )
        * 100
        if usage.total
        else 0.0
    )

    if not writable:
        status = "failed"
    elif (
        percent_free
        < STORAGE_WARNING_PERCENT_FREE
    ):
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "path": str(
            SPORTS_MEDIA_DIR
        ),
        "exists": True,
        "writable": writable,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "percent_free": round(
            percent_free,
            2,
        ),
        "warning_percent_free": (
            STORAGE_WARNING_PERCENT_FREE
        ),
    }


def aggregate_status(
    sections: list[dict[str, Any]],
) -> str:
    statuses = {
        str(
            section.get(
                "status",
                "unknown",
            )
        ).lower()
        for section in sections
    }

    if "failed" in statuses:
        return "failed"

    if (
        "degraded" in statuses
        or "unknown" in statuses
    ):
        return "degraded"

    return "healthy"


def build_health_report() -> dict[str, Any]:
    now = utc_now()

    controller = controller_health(
        now
    )
    providers = provider_health()
    recorder = recorder_health()
    recordings = recording_health()
    storage = storage_health()

    status = aggregate_status(
        [
            controller,
            providers,
            recorder,
            recordings,
            storage,
        ]
    )

    return {
        "status": status,
        "generated_at": format_timestamp(
            now
        ),
        "controller": controller,
        "providers": providers,
        "recorder": recorder,
        "recordings": recordings,
        "storage": storage,
    }


def write_health_report() -> dict[str, Any]:
    report = build_health_report()

    HEALTH_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = HEALTH_FILE.with_suffix(
        ".json.tmp"
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
        HEALTH_FILE
    )

    return report


def main() -> int:
    report = write_health_report()

    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if report["status"]
        in {
            "healthy",
            "degraded",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
