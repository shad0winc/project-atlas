"""Atomic publication and strict reading for Downloads runtime snapshots."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .models import (
    SCHEMA_VERSION,
    DownloadItem,
    DownloadsError,
    DownloadsSnapshot,
    DownloadState,
    DownloadSummary,
    require_mapping,
)


RUNTIME_DIRECTORY_MODE = 0o750
RUNTIME_FILE_MODE = 0o640
RUNTIME_OWNER_UID = 0
RUNTIME_GROUP_GID = 20000
DEFAULT_MAX_AGE_SECONDS = 180


def publish_snapshot(payload: Mapping[str, Any], destination: str | Path) -> Path:
    """Atomically publish one API-readable bounded Downloads snapshot."""
    if not isinstance(payload, Mapping):
        raise TypeError("Downloads runtime snapshot payload must be a mapping")

    target = Path(destination).expanduser()
    directory = target.parent
    if not target.name:
        raise DownloadsError("Downloads runtime snapshot must name a file")

    try:
        directory.mkdir(parents=True, exist_ok=True)
        os.chown(directory, RUNTIME_OWNER_UID, RUNTIME_GROUP_GID)
        os.chmod(directory, RUNTIME_DIRECTORY_MODE)
    except OSError as exc:
        raise DownloadsError("unable to secure Downloads runtime directory") from exc

    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", dir=directory
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            os.fchown(stream.fileno(), RUNTIME_OWNER_UID, RUNTIME_GROUP_GID)
            os.fchmod(stream.fileno(), RUNTIME_FILE_MODE)
        os.replace(temporary, target)
        temporary = None

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(directory, flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except (OSError, TypeError, ValueError) as exc:
        raise DownloadsError("unable to publish Downloads runtime snapshot") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)

    return target


def read_snapshot(
    snapshot_path: str | Path,
    *,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> DownloadsSnapshot:
    """Read and validate one bounded Downloads runtime snapshot."""
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")

    path = Path(snapshot_path).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DownloadsError("Downloads runtime snapshot is unavailable") from exc

    root = require_mapping(payload, "snapshot")
    if root.get("schema_version") != SCHEMA_VERSION:
        raise DownloadsError("unsupported Downloads runtime snapshot schema")

    generated_at = root.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise DownloadsError("Downloads runtime snapshot generated_at is invalid")

    try:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DownloadsError("Downloads runtime snapshot generated_at is invalid") from exc
    if generated.tzinfo is None:
        raise DownloadsError("Downloads runtime snapshot generated_at must be timezone-aware")

    current = now or datetime.now(timezone.utc)
    age = (
        current.astimezone(timezone.utc) - generated.astimezone(timezone.utc)
    ).total_seconds()
    if age < -60 or age > max_age_seconds:
        raise DownloadsError("Downloads runtime snapshot is stale")

    summary_raw = require_mapping(root.get("summary"), "summary")
    downloads_raw = root.get("downloads")
    if not isinstance(downloads_raw, list):
        raise DownloadsError("Downloads runtime snapshot downloads must be a list")

    summary = DownloadSummary(
        active=_required_nonnegative_int(summary_raw.get("active"), "summary.active"),
        queued=_required_nonnegative_int(summary_raw.get("queued"), "summary.queued"),
        completed=_required_nonnegative_int(
            summary_raw.get("completed"), "summary.completed"
        ),
        error=_required_nonnegative_int(summary_raw.get("error"), "summary.error"),
        total_download_rate=_required_nonnegative_int(
            summary_raw.get("total_download_rate"), "summary.total_download_rate"
        ),
        total_upload_rate=_required_nonnegative_int(
            summary_raw.get("total_upload_rate"), "summary.total_upload_rate"
        ),
    )

    items: list[DownloadItem] = []
    for index, raw in enumerate(downloads_raw):
        entry = require_mapping(raw, f"downloads[{index}]")
        try:
            state = DownloadState(str(entry.get("state")))
        except ValueError as exc:
            raise DownloadsError(f"downloads[{index}].state is invalid") from exc

        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise DownloadsError(f"downloads[{index}].name is invalid")
        category = entry.get("category")
        if category is not None and not isinstance(category, str):
            raise DownloadsError(f"downloads[{index}].category is invalid")

        progress = entry.get("progress")
        if isinstance(progress, bool) or not isinstance(progress, (int, float)):
            raise DownloadsError(f"downloads[{index}].progress is invalid")
        progress_float = float(progress)
        if progress_float < 0 or progress_float > 1:
            raise DownloadsError(f"downloads[{index}].progress is invalid")

        eta = entry.get("eta_seconds")
        if eta is not None:
            eta = _required_nonnegative_int(eta, f"downloads[{index}].eta_seconds")

        items.append(
            DownloadItem(
                name=name,
                category=category,
                state=state,
                progress=progress_float,
                total_bytes=_required_nonnegative_int(
                    entry.get("total_bytes"), f"downloads[{index}].total_bytes"
                ),
                downloaded_bytes=_required_nonnegative_int(
                    entry.get("downloaded_bytes"),
                    f"downloads[{index}].downloaded_bytes",
                ),
                download_rate=_required_nonnegative_int(
                    entry.get("download_rate"), f"downloads[{index}].download_rate"
                ),
                upload_rate=_required_nonnegative_int(
                    entry.get("upload_rate"), f"downloads[{index}].upload_rate"
                ),
                eta_seconds=eta,
            )
        )

    return DownloadsSnapshot(
        generated_at=generated_at,
        summary=summary,
        downloads=tuple(items),
    )


def _required_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DownloadsError(f"{field} is invalid")
    return value
