"""Tests for the Atlas cleanup workflow CLI."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import Mock, patch

from atlas.cleanup.execution_models import CleanupExecutionMode
from atlas.cleanup.executor import (
    CleanupExecutionError,
    CleanupExecutionSummary,
    CleanupRunStatus,
)
from atlas.cleanup_cli import main


def make_summary(
    *,
    status: CleanupRunStatus = CleanupRunStatus.SUCCESS,
    errors: tuple[str, ...] = (),
) -> CleanupExecutionSummary:
    """Create a normalized cleanup workflow summary."""

    return CleanupExecutionSummary(
        provider="jellyfin",
        mode=CleanupExecutionMode.DRY_RUN,
        status=status,
        started_at="2026-07-23T20:00:00Z",
        completed_at="2026-07-23T20:00:01Z",
        total=3,
        planned=1,
        skipped=2,
        modified=0,
        errors=errors,
    )


class CleanupWorkflowCliTests(unittest.TestCase):
    """Validate complete cleanup workflow CLI behavior."""

    def test_run_human_output(self) -> None:
        provider = Mock()
        workflow = Mock()
        workflow.execute.return_value = make_summary()

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "run",
                    "jellyfin",
                    "--dry-run",
                ],
                workflow_service=workflow,
                jellyfin_provider=provider,
            )

        output = stdout.getvalue()

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas Cleanup Workflow",
            output,
        )
        self.assertIn(
            "Provider: jellyfin",
            output,
        )
        self.assertIn(
            "Mode: dry_run",
            output,
        )
        self.assertIn(
            "Status: success",
            output,
        )
        self.assertIn(
            "Total: 3",
            output,
        )
        self.assertIn(
            "Planned: 1",
            output,
        )
        self.assertIn(
            "Skipped: 2",
            output,
        )
        self.assertIn(
            "Modified: 0",
            output,
        )

        workflow.execute.assert_called_once_with(
            provider,
            page_size=200,
            mode="dry_run",
        )

    def test_run_json_output(self) -> None:
        provider = Mock()
        workflow = Mock()
        workflow.execute.return_value = make_summary()

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "run",
                    "jellyfin",
                    "--json",
                ],
                workflow_service=workflow,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 0)

        payload = json.loads(stdout.getvalue())

        self.assertEqual(
            payload["provider"],
            "jellyfin",
        )
        self.assertEqual(
            payload["mode"],
            "dry_run",
        )
        self.assertEqual(
            payload["status"],
            "success",
        )
        self.assertEqual(
            payload["planned"],
            1,
        )
        self.assertEqual(
            payload["modified"],
            0,
        )

    def test_run_forwards_page_size(self) -> None:
        provider = Mock()
        workflow = Mock()
        workflow.execute.return_value = make_summary()

        result = main(
            [
                "run",
                " JELLYFIN ",
                "--page-size",
                "50",
            ],
            workflow_service=workflow,
            jellyfin_provider=provider,
        )

        self.assertEqual(result, 0)

        workflow.execute.assert_called_once_with(
            provider,
            page_size=50,
            mode="dry_run",
        )

    def test_run_rejects_unsupported_provider(self) -> None:
        provider = Mock()
        workflow = Mock()
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "run",
                    "plex",
                ],
                workflow_service=workflow,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "unsupported cleanup workflow provider: plex",
            stderr.getvalue(),
        )
        workflow.execute.assert_not_called()

    def test_run_reports_workflow_error(self) -> None:
        provider = Mock()
        workflow = Mock()
        workflow.execute.side_effect = CleanupExecutionError(
            "preview unavailable"
        )

        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "run",
                    "jellyfin",
                ],
                workflow_service=workflow,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup workflow failed: preview unavailable",
            stderr.getvalue(),
        )

    def test_run_renders_partial_errors(self) -> None:
        provider = Mock()
        workflow = Mock()
        workflow.execute.return_value = make_summary(
            status=CleanupRunStatus.PARTIAL,
            errors=(
                "movie-1: preview failed",
            ),
        )

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "run",
                    "jellyfin",
                ],
                workflow_service=workflow,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 0)
        self.assertIn(
            "Status: partial",
            stdout.getvalue(),
        )
        self.assertIn(
            "movie-1: preview failed",
            stdout.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
