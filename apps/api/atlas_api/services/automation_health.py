"""Bounded, read-only observations. Never construct a writer or provider client."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
from typing import Mapping


MAX_BYTES = 8 * 1024**2
FRESH_SECONDS = 300


def _read(path: Path) -> dict:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError("Unavailable observation")
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
        if len(raw) > MAX_BYTES or (
            before.st_ino, before.st_size, before.st_mtime_ns
        ) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("Observation changed")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Invalid observation")
    return value


def _age(value: object, now: datetime) -> tuple[str, int]:
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Missing timezone")
    elapsed = (now - stamp).total_seconds()
    age = int(elapsed)
    if elapsed < 0:
        raise ValueError("Future timestamp")
    return stamp.astimezone(timezone.utc).isoformat(), age


def read_automation_health(
    environment: Mapping[str, str] | None = None, *, now: datetime | None = None,
) -> dict:
    env = os.environ if environment is None else environment
    instant = now or datetime.now(timezone.utc)
    flags = {}
    for label, variable in (
        ("receipt_recovery", "ATLAS_SUBMISSION_RECOVERY_ENABLED"),
        ("acquisition_routing", "ATLAS_ACQUISITION_ROUTING_ENABLED"),
    ):
        value = env.get(variable, "0").strip()
        flags[label] = "enabled" if value == "1" else "disabled" if value == "0" else "invalid"

    registry = {"status": "unavailable"}
    try:
        root = env.get("ATLAS_REQUESTS_DIR", "/mnt/storage/configs/atlas/runtime/requests").strip()
        if not root:
            raise ValueError("Empty path")
        document = _read(Path(root) / "requests.json")
        schema = document.get("schema_version")
        requests = document.get("requests")
        if type(schema) is not int or schema not in (1, 2) or not isinstance(requests, dict):
            raise ValueError("Invalid registry")
        if not all(isinstance(row, dict) for row in requests.values()):
            raise ValueError("Invalid records")
        registry = {"status": "observed", "schema_version": schema, "request_count": len(requests)}
        if schema == 2:
            attempts = document.get("submissions")
            outbox = document.get("submission_outbox")
            if not isinstance(attempts, dict) or not isinstance(outbox, dict):
                raise ValueError("Invalid journals")
            phases = [row.get("phase") for row in attempts.values() if isinstance(row, dict)]
            if len(phases) != len(attempts) or any(
                phase not in ("POST_STARTED", "RECEIPT_OBSERVED", "BOUND") for phase in phases
            ):
                raise ValueError("Invalid phases")
            if not all(isinstance(row, dict) and type(row.get("delivered")) is bool for row in outbox.values()):
                raise ValueError("Invalid outbox")
            registry.update(
                unresolved_submission_count=sum(phase != "BOUND" for phase in phases),
                observed_receipt_count=phases.count("RECEIPT_OBSERVED"),
                pending_event_count=sum(not row["delivered"] for row in outbox.values()),
            )
    except (OSError, ValueError, TypeError, OverflowError):
        registry = {"status": "unavailable"}

    reconcile = {"status": "unavailable"}
    try:
        value = env.get("ATLAS_DASHBOARD_SCHEDULER_SNAPSHOT_PATH", "/mnt/storage/configs/atlas/runtime/dashboard/scheduler.json").strip()
        if not value:
            raise ValueError("Empty path")
        snapshot = _read(Path(value))
        if type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1 or not isinstance(snapshot.get("tasks"), list):
            raise ValueError("Invalid scheduler snapshot")
        _, snapshot_age = _age(snapshot.get("generated_at"), instant)
        rows = [row for row in snapshot["tasks"] if isinstance(row, dict) and row.get("name") == "requests.reconcile"]
        if len(rows) != 1:
            raise ValueError("Missing or ambiguous task")
        task = rows[0]
        failures = task.get("consecutive_failures", 0)
        if type(failures) is not int or failures < 0:
            raise ValueError("Invalid failure count")
        last_success, success_age = _age(task.get("last_success"), instant)
        state = task.get("status")
        if state not in ("healthy", "running", "failed", "degraded", "disabled"):
            raise ValueError("Invalid task status")
        health = "stale" if max(snapshot_age, success_age) > FRESH_SECONDS else (
            "attention" if failures or state in ("failed", "degraded", "disabled") or task.get("enabled") is False else "healthy"
        )
        reconcile = dict(status=health, task_status=state, last_success=last_success,
                         snapshot_age_seconds=snapshot_age, success_age_seconds=success_age,
                         consecutive_failures=failures)
    except (OSError, ValueError, TypeError, OverflowError):
        pass
    return dict(observed_at=instant.isoformat(), api_configuration=flags,
                request_registry=registry, request_reconciliation=reconcile)
