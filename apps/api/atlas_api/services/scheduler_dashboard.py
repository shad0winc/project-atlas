"""Read-only scheduler dashboard aggregation service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from atlas.dashboard_runtime import read_scheduler_snapshot

from atlas_api.schemas.portal_dashboard import (
    PortalSchedulerFailureResponse,
    PortalSchedulerSummaryResponse,
)


PORTAL_RECENT_FAILURE_LIMIT: Final = 5


class RuntimeSchedulerProvider:
    """Read Scheduler observations from an API-safe runtime snapshot."""

    def __init__(self, snapshot_path: str | Path) -> None:
        self._snapshot_path = Path(snapshot_path).expanduser()

    def list_tasks(self) -> list[dict[str, Any]]:
        return [dict(task) for task in read_scheduler_snapshot(self._snapshot_path)]


class SchedulerDashboardService:
    """
    Read-only adapter over the Atlas scheduler runtime.

    This service intentionally does not execute, mutate, register,
    synchronize, or persist scheduler state.
    """

    def __init__(
        self,
        scheduler: Any,
    ) -> None:
        if not callable(
            getattr(
                scheduler,
                "list_tasks",
                None,
            )
        ):
            raise TypeError(
                "scheduler must provide list_tasks()"
            )

        self._scheduler = scheduler

    def read_summary(
        self,
    ) -> PortalSchedulerSummaryResponse:
        """
        Build the Portal scheduler widget.

        The scheduler remains the source of truth.
        """

        try:
            tasks = self._scheduler.list_tasks()
        except Exception as exc:
            return PortalSchedulerSummaryResponse(
                status="unavailable",
                detail=(
                    "Scheduler runtime state unavailable: "
                    f"{exc}"
                ),
            )

        try:
            normalized_tasks = tuple(
                task
                for task in tasks
                if isinstance(task, dict)
            )

            failures = self._recent_failures(
                normalized_tasks,
            )

            return PortalSchedulerSummaryResponse(
                status="available",
                registered_count=len(normalized_tasks),
                enabled_count=self._count_enabled(
                    normalized_tasks,
                ),
                disabled_count=self._count_disabled(
                    normalized_tasks,
                ),
                due_count=self._count_due(
                    normalized_tasks,
                ),
                running_count=self._count_running(
                    normalized_tasks,
                ),
                failed_count=self._count_failed(
                    normalized_tasks,
                ),
                last_run_at=self._latest_timestamp(
                    normalized_tasks,
                    (
                        "last_success",
                        "last_failure",
                        "last_started",
                    ),
                ),
                next_run_at=self._latest_timestamp(
                    normalized_tasks,
                    (
                        "next_run",
                    ),
                ),
                recent_failures=failures,
            )

        except Exception as exc:
            return PortalSchedulerSummaryResponse(
                status="unavailable",
                detail=(
                    "Scheduler state normalization failed: "
                    f"{exc}"
                ),
            )

    @staticmethod
    def _count_enabled(
        tasks: tuple[dict[str, Any], ...],
    ) -> int:
        return sum(
            1
            for task in tasks
            if task.get("enabled") is True
        )

    @staticmethod
    def _count_disabled(
        tasks: tuple[dict[str, Any], ...],
    ) -> int:
        return sum(
            1
            for task in tasks
            if task.get("enabled") is False
        )

    @staticmethod
    def _count_due(
        tasks: tuple[dict[str, Any], ...],
    ) -> int:
        return sum(
            1
            for task in tasks
            if task.get("due") is True
        )

    @staticmethod
    def _count_running(
        tasks: tuple[dict[str, Any], ...],
    ) -> int:
        return sum(
            1
            for task in tasks
            if task.get("status") == "running"
        )

    @staticmethod
    def _count_failed(
        tasks: tuple[dict[str, Any], ...],
    ) -> int:
        return sum(
            1
            for task in tasks
            if int(
                task.get(
                    "failure_count",
                    0,
                )
                or 0
            )
            > 0
        )

    @staticmethod
    def _latest_timestamp(
        tasks: tuple[dict[str, Any], ...],
        keys: tuple[str, ...],
    ) -> str | None:
        timestamps: list[str] = []

        for task in tasks:
            for key in keys:
                value = task.get(key)

                if isinstance(value, str) and value:
                    timestamps.append(value)

        if not timestamps:
            return None

        return max(
            timestamps,
        )

    @staticmethod
    def _recent_failures(
        tasks: tuple[dict[str, Any], ...],
    ) -> tuple[
        PortalSchedulerFailureResponse,
        ...,
    ]:
        failures: list[
            PortalSchedulerFailureResponse
        ] = []

        for task in tasks:
            failure_count = int(
                task.get(
                    "failure_count",
                    0,
                )
                or 0
            )

            if failure_count <= 0:
                continue

            failures.append(
                PortalSchedulerFailureResponse(
                    task_name=str(
                        task.get(
                            "name",
                            "unknown",
                        )
                    ),
                    failed_at=(
                        task.get(
                            "last_failure",
                        )
                    ),
                    error=str(
                        task.get(
                            "last_error",
                            "Scheduler task failed.",
                        )
                    ),
                )
            )

        return tuple(
            failures[
                :PORTAL_RECENT_FAILURE_LIMIT
            ]
        )


__all__ = [
    "PORTAL_RECENT_FAILURE_LIMIT",
    "SchedulerDashboardService",
]
