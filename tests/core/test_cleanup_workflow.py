"""Tests for the Atlas cleanup workflow service."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, call

from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
    CleanupExecutionReport,
)
from atlas.cleanup.executor import (
    CleanupExecutionError,
    CleanupExecutionSummary,
    CleanupRunStatus,
)
from atlas.cleanup.models import CleanupError
from atlas.cleanup.scan_models import CleanupScanReport
from atlas.cleanup.workflow import CleanupWorkflowService


NOW = datetime(
    2026,
    7,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_scan_report() -> CleanupScanReport:
    """Create an empty normalized cleanup scan."""

    return CleanupScanReport(
        provider="jellyfin",
        decisions=(),
        scanned_at=NOW,
    )


def make_execution_report() -> CleanupExecutionReport:
    """Create an empty normalized cleanup execution report."""

    return CleanupExecutionReport(
        provider="jellyfin",
        items=(),
        mode=CleanupExecutionMode.DRY_RUN,
        created_at=NOW,
    )


def make_summary() -> CleanupExecutionSummary:
    """Create a successful empty cleanup execution summary."""

    return CleanupExecutionSummary(
        provider="jellyfin",
        mode=CleanupExecutionMode.DRY_RUN,
        status=CleanupRunStatus.SUCCESS,
        started_at="2026-07-20T12:00:00Z",
        completed_at="2026-07-20T12:00:01Z",
        total=0,
        planned=0,
        skipped=0,
        modified=0,
    )


def make_provider(
    *,
    name: object = "jellyfin",
    item_ids: tuple[str, ...] = (),
) -> Mock:
    """Create a provider-shaped mock."""

    provider = Mock()
    provider.name = name
    provider.list_media_item_ids.return_value = item_ids
    return provider


class CleanupWorkflowServiceTests(unittest.TestCase):
    """Validate cleanup workflow orchestration."""

    def test_execute_coordinates_complete_workflow(
        self,
    ) -> None:
        provider = make_provider(
            name=" JELLYFIN ",
            item_ids=(
                "movie-1",
                "series-1",
            ),
        )
        scan_report = make_scan_report()
        execution_report = make_execution_report()
        summary = make_summary()

        scanner = Mock()
        scanner.scan.return_value = scan_report

        planner = Mock()
        planner.plan.return_value = execution_report

        executor = Mock()
        executor.execute.return_value = summary

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=planner,
            executor=executor,
        )

        result = workflow.execute(
            provider,
            page_size=50,
            mode="dry_run",
        )

        self.assertIs(result, summary)
        self.assertEqual(
            provider.list_media_item_ids.call_args_list,
            [
                call(page_size=50),
            ],
        )
        scanner.scan.assert_called_once_with(
            "jellyfin",
            (
                "movie-1",
                "series-1",
            ),
        )
        planner.plan.assert_called_once_with(
            scan_report,
            mode="dry_run",
        )
        executor.execute.assert_called_once_with(
            execution_report,
        )

    def test_execute_uses_default_page_size_and_mode(
        self,
    ) -> None:
        provider = make_provider()
        scan_report = make_scan_report()
        execution_report = make_execution_report()
        summary = make_summary()

        scanner = Mock()
        scanner.scan.return_value = scan_report

        planner = Mock()
        planner.plan.return_value = execution_report

        executor = Mock()
        executor.execute.return_value = summary

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=planner,
            executor=executor,
        )

        result = workflow.execute(provider)

        self.assertIs(result, summary)
        provider.list_media_item_ids.assert_called_once_with(
            page_size=200,
        )
        planner.plan.assert_called_once_with(
            scan_report,
            mode=CleanupExecutionMode.DRY_RUN,
        )

    def test_execute_rejects_missing_provider_name(
        self,
    ) -> None:
        provider = Mock()
        del provider.name

        workflow = CleanupWorkflowService(
            scanner=Mock(),
            planner=Mock(),
            executor=Mock(),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "provider must define a name",
        ):
            workflow.execute(provider)

    def test_execute_rejects_empty_provider_name(
        self,
    ) -> None:
        provider = make_provider(name="   ")

        workflow = CleanupWorkflowService(
            scanner=Mock(),
            planner=Mock(),
            executor=Mock(),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "provider name is required",
        ):
            workflow.execute(provider)

    def test_execute_rejects_missing_enumeration_method(
        self,
    ) -> None:
        provider = Mock()
        provider.name = "jellyfin"
        provider.list_media_item_ids = None

        workflow = CleanupWorkflowService(
            scanner=Mock(),
            planner=Mock(),
            executor=Mock(),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "provider must implement list_media_item_ids",
        ):
            workflow.execute(provider)

    def test_execute_rejects_invalid_page_size(
        self,
    ) -> None:
        workflow = CleanupWorkflowService(
            scanner=Mock(),
            planner=Mock(),
            executor=Mock(),
        )

        for page_size in (
            True,
            0,
            -1,
            1.5,
            "200",
        ):
            with self.subTest(page_size=page_size):
                provider = make_provider()

                with self.assertRaisesRegex(
                    CleanupExecutionError,
                    "page_size must be a positive integer",
                ):
                    workflow.execute(
                        provider,
                        page_size=page_size,
                    )

                provider.list_media_item_ids.assert_not_called()

    def test_execute_rejects_invalid_scanner_result(
        self,
    ) -> None:
        provider = make_provider()
        scanner = Mock()
        scanner.scan.return_value = object()

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=Mock(),
            executor=Mock(),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "scanner must return a CleanupScanReport",
        ):
            workflow.execute(provider)

    def test_execute_rejects_invalid_planner_result(
        self,
    ) -> None:
        provider = make_provider()
        scanner = Mock()
        scanner.scan.return_value = make_scan_report()

        planner = Mock()
        planner.plan.return_value = object()

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=planner,
            executor=Mock(),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "planner must return a CleanupExecutionReport",
        ):
            workflow.execute(provider)

    def test_execute_rejects_invalid_executor_result(
        self,
    ) -> None:
        provider = make_provider()
        scanner = Mock()
        scanner.scan.return_value = make_scan_report()

        planner = Mock()
        planner.plan.return_value = make_execution_report()

        executor = Mock()
        executor.execute.return_value = object()

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=planner,
            executor=executor,
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "executor must return a CleanupExecutionSummary",
        ):
            workflow.execute(provider)

    def test_execute_propagates_provider_error(
        self,
    ) -> None:
        provider = make_provider()
        provider.list_media_item_ids.side_effect = RuntimeError(
            "provider failed"
        )

        workflow = CleanupWorkflowService(
            scanner=Mock(),
            planner=Mock(),
            executor=Mock(),
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "provider failed",
        ):
            workflow.execute(provider)

    def test_execute_propagates_scanner_error(
        self,
    ) -> None:
        provider = make_provider()
        scanner = Mock()
        scanner.scan.side_effect = CleanupError(
            "scan failed"
        )

        planner = Mock()

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=planner,
            executor=Mock(),
        )

        with self.assertRaisesRegex(
            CleanupError,
            "scan failed",
        ):
            workflow.execute(provider)

        planner.plan.assert_not_called()

    def test_execute_propagates_planner_error(
        self,
    ) -> None:
        provider = make_provider()
        scanner = Mock()
        scanner.scan.return_value = make_scan_report()

        planner = Mock()
        planner.plan.side_effect = CleanupError(
            "planning failed"
        )

        executor = Mock()

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=planner,
            executor=executor,
        )

        with self.assertRaisesRegex(
            CleanupError,
            "planning failed",
        ):
            workflow.execute(provider)

        executor.execute.assert_not_called()

    def test_execute_propagates_executor_error(
        self,
    ) -> None:
        provider = make_provider()
        scanner = Mock()
        scanner.scan.return_value = make_scan_report()

        planner = Mock()
        planner.plan.return_value = make_execution_report()

        executor = Mock()
        executor.execute.side_effect = CleanupExecutionError(
            "execution failed"
        )

        workflow = CleanupWorkflowService(
            scanner=scanner,
            planner=planner,
            executor=executor,
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "execution failed",
        ):
            workflow.execute(provider)


if __name__ == "__main__":
    unittest.main()
