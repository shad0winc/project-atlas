"""Tests for Atlas Portal scheduler dashboard aggregation."""

from __future__ import annotations

from atlas_api.services.scheduler_dashboard import (
    PORTAL_RECENT_FAILURE_LIMIT,
    SchedulerDashboardService,
)


class EmptyScheduler:
    def list_tasks(self):
        return []


class FailedScheduler:
    def list_tasks(self):
        raise RuntimeError(
            "scheduler state unavailable"
        )


class PopulatedScheduler:
    def list_tasks(self):
        return [
            {
                "name": "operations.collect",
                "enabled": True,
                "running": False,
                "failed": False,
                "last_run_at": "2026-08-04T04:30:00Z",
                "next_run_at": "2026-08-04T05:00:00Z",
            },
            {
                "name": "media.refresh",
                "enabled": True,
                "status": "running",
                "failure_count": 0,
            },
            {
                "name": "backup.verify",
                "enabled": False,
                "status": "failed",
                "failure_count": 1,
                "last_error": "Backup verification failed.",
                "last_failure": "2026-08-04T04:00:00Z",
            },
        ]


def test_empty_scheduler_returns_available_empty_state() -> None:
    service = SchedulerDashboardService(
        EmptyScheduler()
    )

    response = service.read_summary()

    assert response.status == "available"
    assert response.registered_count == 0
    assert response.failed_count == 0


def test_failed_scheduler_returns_unavailable_state() -> None:
    service = SchedulerDashboardService(
        FailedScheduler()
    )

    response = service.read_summary()

    assert response.status == "unavailable"
    assert response.detail is not None


def test_populated_scheduler_normalizes_runtime_state() -> None:
    service = SchedulerDashboardService(
        PopulatedScheduler()
    )

    response = service.read_summary()

    assert response.status == "available"
    assert response.registered_count == 3
    assert response.enabled_count == 2
    assert response.disabled_count == 1
    assert response.running_count == 1
    assert response.failed_count == 1


def test_failure_results_are_bounded() -> None:
    assert PORTAL_RECENT_FAILURE_LIMIT == 5

    service = SchedulerDashboardService(
        PopulatedScheduler()
    )

    response = service.read_summary()

    assert len(response.recent_failures) <= (
        PORTAL_RECENT_FAILURE_LIMIT
    )

def test_runtime_scheduler_provider_missing_snapshot_is_unavailable(tmp_path):
    from atlas_api.services.scheduler_dashboard import RuntimeSchedulerProvider
    response = SchedulerDashboardService(
        RuntimeSchedulerProvider(tmp_path / "missing.json")
    ).read_summary()
    assert response.status == "unavailable"

def test_runtime_scheduler_provider_valid_empty_snapshot_is_available(tmp_path):
    import json
    from atlas_api.services.scheduler_dashboard import RuntimeSchedulerProvider
    path = tmp_path / "scheduler.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-08-29T12:00:00Z",
                "tasks": [],
            }
        ),
        encoding="utf-8",
    )
    response = SchedulerDashboardService(RuntimeSchedulerProvider(path)).read_summary()
    assert response.status == "available"
    assert response.registered_count == 0
