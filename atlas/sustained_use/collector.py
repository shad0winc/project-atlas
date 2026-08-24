"""Read-only collectors for Atlas sustained-use certification."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from .models import (
    AriObservation,
    ContainerObservation,
    RuntimeBusObservation,
    SchedulerObservation,
    SustainedUseSample,
)


class SustainedUseCollectionError(RuntimeError):
    """Raised when live sustained-use evidence cannot be collected."""


@dataclass(frozen=True)
class AtlasHealthObservation:
    """Minimal Atlas health result consumed by Q.6."""

    status: str
    score: int

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or not self.status.strip():
            raise SustainedUseCollectionError(
                "Atlas health status must be a non-empty string",
            )

        if (
            isinstance(self.score, bool)
            or not isinstance(self.score, int)
            or self.score < 0
            or self.score > 100
        ):
            raise SustainedUseCollectionError(
                "Atlas health score must be an integer from 0 to 100",
            )

        object.__setattr__(
            self,
            "status",
            self.status.strip().lower(),
        )


@dataclass(frozen=True)
class FilesystemObservation:
    """Usage percentage for one mounted filesystem."""

    path: str
    usage_percent: int

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise SustainedUseCollectionError(
                "filesystem path must be a non-empty string",
            )

        if (
            isinstance(self.usage_percent, bool)
            or not isinstance(self.usage_percent, int)
            or self.usage_percent < 0
            or self.usage_percent > 100
        ):
            raise SustainedUseCollectionError(
                "filesystem usage_percent must be an integer from 0 to 100",
            )

        object.__setattr__(
            self,
            "path",
            self.path.strip(),
        )


def _run(
    command: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            tuple(command),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").strip()
        raise SustainedUseCollectionError(
            "command failed: "
            + " ".join(command)
            + (f": {stderr}" if stderr else "")
        ) from error
    except OSError as error:
        raise SustainedUseCollectionError(
            "unable to execute command: "
            + " ".join(command)
        ) from error


def collect_atlas_health() -> AtlasHealthObservation:
    """Collect Atlas compact health without mutating runtime state."""

    result = _run(
        (
            "atlas",
            "health",
            "--compact",
        )
    )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SustainedUseCollectionError(
            "Atlas health returned invalid JSON",
        ) from error

    if not isinstance(payload, Mapping):
        raise SustainedUseCollectionError(
            "Atlas health root must be an object",
        )

    return AtlasHealthObservation(
        status=payload.get("status"),
        score=payload.get("score"),
    )


def _parse_docker_inspect(
    payload: object,
) -> ContainerObservation:
    if (
        not isinstance(payload, list)
        or len(payload) != 1
        or not isinstance(payload[0], Mapping)
    ):
        raise SustainedUseCollectionError(
            "Docker inspect payload must contain one object",
        )

    container: Mapping[str, Any] = payload[0]

    state = container.get("State")

    if not isinstance(state, Mapping):
        raise SustainedUseCollectionError(
            "Docker inspect State is missing",
        )

    health_payload = state.get("Health")

    if isinstance(health_payload, Mapping):
        health = health_payload.get(
            "Status",
            "unknown",
        )
    else:
        health = "none"

    name = container.get("Name")

    if isinstance(name, str):
        name = name.lstrip("/")

    return ContainerObservation(
        name=name,
        container_id=container.get("Id"),
        status=state.get("Status"),
        health=health,
        restart_count=container.get("RestartCount"),
        oom_killed=state.get("OOMKilled"),
        started_at=state.get("StartedAt"),
    )


def collect_containers() -> tuple[ContainerObservation, ...]:
    """Collect every currently running Docker container."""

    names_result = _run(
        (
            "docker",
            "ps",
            "--format",
            "{{.Names}}",
        )
    )

    names = tuple(
        sorted(
            line.strip()
            for line in names_result.stdout.splitlines()
            if line.strip()
        )
    )

    observations: list[ContainerObservation] = []

    for name in names:
        inspect_result = _run(
            (
                "docker",
                "inspect",
                name,
            )
        )

        try:
            payload = json.loads(
                inspect_result.stdout,
            )
        except json.JSONDecodeError as error:
            raise SustainedUseCollectionError(
                f"Docker inspect returned invalid JSON: {name}",
            ) from error

        observations.append(
            _parse_docker_inspect(
                payload,
            )
        )

    return tuple(observations)


def collect_filesystem(
    path: str | Path,
) -> FilesystemObservation:
    """Collect one filesystem percentage using df portable output."""

    normalized_path = str(Path(path))

    result = _run(
        (
            "df",
            "-P",
            normalized_path,
        )
    )

    lines = tuple(
        line
        for line in result.stdout.splitlines()
        if line.strip()
    )

    if len(lines) != 2:
        raise SustainedUseCollectionError(
            f"unexpected df output for {normalized_path}",
        )

    fields = lines[1].split()

    if len(fields) < 5:
        raise SustainedUseCollectionError(
            f"unexpected df fields for {normalized_path}",
        )

    percent = fields[4]

    if not percent.endswith("%"):
        raise SustainedUseCollectionError(
            f"unexpected df percentage for {normalized_path}",
        )

    try:
        usage_percent = int(
            percent[:-1]
        )
    except ValueError as error:
        raise SustainedUseCollectionError(
            f"invalid df percentage for {normalized_path}",
        ) from error

    return FilesystemObservation(
        path=normalized_path,
        usage_percent=usage_percent,
    )


def _parse_scheduler_payload(
    payload: object,
) -> SchedulerObservation:
    """Normalize one `atlas scheduler inspect` JSON payload."""

    if not isinstance(payload, Mapping):
        raise SustainedUseCollectionError(
            "Scheduler inspect root must be an object",
        )

    return SchedulerObservation(
        name=payload.get("name"),
        enabled=payload.get("enabled"),
        status=payload.get("status"),
        due=payload.get("due"),
        run_count=payload.get("run_count"),
        failure_count=payload.get("failure_count"),
        last_success=payload.get("last_success"),
        next_run=payload.get("next_run"),
    )


def collect_scheduler(
    name: str,
) -> SchedulerObservation:
    """Read one scheduler task without executing it."""

    if not isinstance(name, str) or not name.strip():
        raise SustainedUseCollectionError(
            "scheduler name must be a non-empty string",
        )

    normalized = name.strip()

    result = _run(
        (
            "atlas",
            "scheduler",
            "inspect",
            normalized,
        )
    )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SustainedUseCollectionError(
            f"Scheduler inspect returned invalid JSON: {normalized}",
        ) from error

    return _parse_scheduler_payload(
        payload,
    )


def collect_schedulers(
    names: Sequence[str],
) -> tuple[SchedulerObservation, ...]:
    """Collect configured scheduler tasks deterministically."""

    if isinstance(names, str):
        raise SustainedUseCollectionError(
            "scheduler names must be a sequence",
        )

    normalized_names = tuple(
        sorted(
            {
                name.strip()
                for name in names
                if isinstance(name, str) and name.strip()
            }
        )
    )

    if not normalized_names:
        raise SustainedUseCollectionError(
            "at least one scheduler name is required",
        )

    return tuple(
        collect_scheduler(name)
        for name in normalized_names
    )


DEFAULT_EVENT_LOG = Path(
    "/mnt/storage/configs/atlas/runtime/events.jsonl"
)
DEFAULT_NOTIFICATIONS_CURSOR = Path(
    "/mnt/storage/configs/atlas/runtime/subscribers/"
    "module-notifications.cursor"
)
DEFAULT_NOTIFICATIONS_HEARTBEAT = Path(
    "/mnt/storage/configs/atlas/notifications/worker-heartbeat"
)
DEFAULT_NOTIFICATIONS_CONTAINER = "atlas-notifications-worker"


def _run_status(
    command: Sequence[str],
) -> int:
    """Run an observational predicate and return only its status."""

    try:
        result = subprocess.run(
            tuple(command),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise SustainedUseCollectionError(
            "unable to execute command: "
            + " ".join(command)
        ) from error

    return result.returncode


def _read_non_negative_integer(
    path: Path,
    *,
    field: str,
) -> int:
    try:
        value = path.read_text(
            encoding="utf-8",
        ).strip()
    except OSError as error:
        raise SustainedUseCollectionError(
            f"unable to read {field}: {path}",
        ) from error

    try:
        normalized = int(value)
    except ValueError as error:
        raise SustainedUseCollectionError(
            f"{field} must contain an integer",
        ) from error

    if normalized < 0:
        raise SustainedUseCollectionError(
            f"{field} cannot be negative",
        )

    return normalized


def collect_runtime_bus(
    *,
    event_log: str | Path = DEFAULT_EVENT_LOG,
    cursor: str | Path = DEFAULT_NOTIFICATIONS_CURSOR,
    heartbeat: str | Path = DEFAULT_NOTIFICATIONS_HEARTBEAT,
    notifications_container: str = DEFAULT_NOTIFICATIONS_CONTAINER,
    now_epoch: float | None = None,
) -> RuntimeBusObservation:
    """Collect Runtime Bus and Notifications reader state."""

    import stat as stat_module
    import time

    event_path = Path(event_log)
    cursor_path = Path(cursor)
    heartbeat_path = Path(heartbeat)

    for path, label in (
        (event_path, "event journal"),
        (cursor_path, "Notifications cursor"),
        (heartbeat_path, "Notifications heartbeat"),
    ):
        if not path.is_file():
            raise SustainedUseCollectionError(
                f"{label} is missing: {path}",
            )

    try:
        event_stat = event_path.stat()
        heartbeat_stat = heartbeat_path.stat()
    except OSError as error:
        raise SustainedUseCollectionError(
            "unable to stat Runtime Bus files",
        ) from error

    try:
        with event_path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            journal_lines = sum(
                1
                for _ in handle
            )
    except OSError as error:
        raise SustainedUseCollectionError(
            f"unable to read event journal: {event_path}",
        ) from error

    cursor_value = _read_non_negative_integer(
        cursor_path,
        field="Notifications cursor",
    )

    if cursor_value > journal_lines:
        raise SustainedUseCollectionError(
            "Notifications cursor exceeds event journal tail",
        )

    if (
        not isinstance(notifications_container, str)
        or not notifications_container.strip()
    ):
        raise SustainedUseCollectionError(
            "Notifications container name must be non-empty",
        )

    container_name = notifications_container.strip()

    container_journal = (
        "/mnt/storage/configs/atlas/runtime/events.jsonl"
    )

    readable = (
        _run_status(
            (
                "docker",
                "exec",
                container_name,
                "test",
                "-r",
                container_journal,
            )
        )
        == 0
    )

    writable = (
        _run_status(
            (
                "docker",
                "exec",
                container_name,
                "test",
                "-w",
                container_journal,
            )
        )
        == 0
    )

    current_epoch = (
        time.time()
        if now_epoch is None
        else now_epoch
    )

    if isinstance(current_epoch, bool) or not isinstance(
        current_epoch,
        (int, float),
    ):
        raise SustainedUseCollectionError(
            "now_epoch must be numeric",
        )

    heartbeat_age = max(
        0,
        int(current_epoch - heartbeat_stat.st_mtime),
    )

    journal_mode = stat_module.S_IMODE(
        event_stat.st_mode,
    )

    return RuntimeBusObservation(
        journal_lines=journal_lines,
        cursor_value=cursor_value,
        journal_uid=event_stat.st_uid,
        journal_gid=event_stat.st_gid,
        journal_mode=int(
            format(journal_mode, "o")
        ),
        journal_readable=readable,
        journal_writable=writable,
        heartbeat_age_seconds=heartbeat_age,
    )


def _parse_ari_report(
    report: str,
) -> AriObservation:
    """Parse stable fields from `atlas ari report`."""

    import re

    if not isinstance(report, str) or not report.strip():
        raise SustainedUseCollectionError(
            "ARI report must be non-empty text",
        )

    lines = report.splitlines()

    sections: dict[str, list[str]] = {}

    index = 0

    while index + 1 < len(lines):
        heading = lines[index].strip()
        underline = lines[index + 1].strip()

        is_heading = (
            bool(heading)
            and len(underline) >= 3
            and set(underline) == {"-"}
        )

        if not is_heading:
            index += 1
            continue

        body: list[str] = []
        index += 2

        while index < len(lines):
            next_heading = lines[index].strip()

            if index + 1 < len(lines):
                next_underline = lines[index + 1].strip()

                if (
                    bool(next_heading)
                    and len(next_underline) >= 3
                    and set(next_underline) == {"-"}
                ):
                    break

            body.append(lines[index])
            index += 1

        sections[heading] = body

    health_lines = sections.get("Atlas Health")

    if health_lines is None:
        raise SustainedUseCollectionError(
            "ARI report is missing Atlas Health section",
        )

    health_text = "\n".join(health_lines)

    score_match = re.search(
        r"(?m)^Score[ \t]*:[ \t]*(\d+)[ \t]*/[ \t]*100[ \t]*$",
        health_text,
    )

    status_match = re.search(
        r"(?m)^Status[ \t]*:[ \t]*(\S.*?)[ \t]*$",
        health_text,
    )

    if score_match is None:
        raise SustainedUseCollectionError(
            "ARI report is missing health score",
        )

    if status_match is None:
        raise SustainedUseCollectionError(
            "ARI report is missing health status",
        )

    score = int(score_match.group(1))
    status = status_match.group(1).strip()

    tv_jellyfin_count = None
    tv_filesystem_count = None

    jellyfin_lines = sections.get(
        "Jellyfin Counts",
        [],
    )

    for line in jellyfin_lines:
        match = re.match(
            r"^Series[ \t]*:[ \t]*(\d+)[ \t]*$",
            line,
        )

        if match is not None:
            tv_jellyfin_count = int(match.group(1))
            break

    library_lines = sections.get(
        "Libraries",
        [],
    )

    for line in library_lines:
        match = re.match(
            r"^TV[ \t]*:[ \t]*(\d+)[ \t]*$",
            line,
        )

        if match is not None:
            tv_filesystem_count = int(match.group(1))
            break

    warning_lines = sections.get(
        "Warnings",
        [],
    )

    warnings = tuple(
        line.strip()[2:].strip()
        for line in warning_lines
        if line.strip().startswith("- ")
        and line.strip()[2:].strip()
    )

    return AriObservation(
        status=status,
        score=score,
        warnings=warnings,
        tv_filesystem_count=tv_filesystem_count,
        tv_jellyfin_count=tv_jellyfin_count,
    )

def collect_ari() -> AriObservation:
    """Collect ARI state without creating a new ARI snapshot."""

    result = _run(
        (
            "atlas",
            "ari",
            "report",
        )
    )

    return _parse_ari_report(
        result.stdout,
    )


DEFAULT_Q6_SCHEDULERS = (
    "operations.collect",
    "sports.maintenance",
)


def collect_sample(
    *,
    scheduler_names: Sequence[str] = DEFAULT_Q6_SCHEDULERS,
) -> SustainedUseSample:
    """Collect one complete Q.6 observation without persisting it."""

    from datetime import datetime, timezone

    commit_result = _run(
        (
            "git",
            "rev-parse",
            "HEAD",
        )
    )

    git_commit = commit_result.stdout.strip()

    health = collect_atlas_health()
    containers = collect_containers()

    root = collect_filesystem("/")
    storage = collect_filesystem(
        "/mnt/storage",
    )

    schedulers = collect_schedulers(
        scheduler_names,
    )

    runtime_bus = collect_runtime_bus()
    ari = collect_ari()

    unhealthy_count = sum(
        1
        for item in containers
        if item.health == "unhealthy"
    )

    generated_at = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return SustainedUseSample(
        generated_at=generated_at,
        git_commit=git_commit,
        atlas_health_status=health.status,
        atlas_health_score=health.score,
        running_containers=len(containers),
        unhealthy_containers=unhealthy_count,
        root_usage_percent=root.usage_percent,
        storage_usage_percent=storage.usage_percent,
        containers=containers,
        schedulers=schedulers,
        runtime_bus=runtime_bus,
        ari=ari,
    )
